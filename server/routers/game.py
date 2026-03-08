"""
MUD-AI — Game Router.

Single endpoint that processes all player actions.
N8N just proxies: Chatwoot → POST /api/v1/game/action → Chatwoot reply.
"""

import hashlib
from fastapi import APIRouter, HTTPException, Form
from pydantic import BaseModel, Field
from typing import Optional
from fastapi.responses import HTMLResponse

from ..game_engine import process_action
from .. import database as db
from .. import world_state
from .. import room_manager as rooms
from ..renderer import render_markdown_to_html


router = APIRouter(prefix="/api/v1", tags=["game"])


def _find_phone_by_token(token: str) -> Optional[str]:
    """Find a player phone by its hashed token."""
    users = db.list_by_prefix("mudai.users.", direct_children_only=True)
    for user in users:
        clean = user["path"].split(".")[-1]
        user_token = hashlib.sha256(f"mudai-{clean}-2026".encode()).hexdigest()[:16]
        if user_token == token:
            # Recover phone (assuming the path suffix is the clean phone)
            # This is a bit hacky but consistent with how users are stored
            return clean
    return None


@router.post("/game/web-action")
async def web_action(
    token: str = Form(...),
    message: str = Form(...),
):
    """
    Process an action from the web UI.
    Identifies player by token, runs action, and returns updated room HTML.
    """
    phone = _find_phone_by_token(token)
    if not phone:
        raise HTTPException(status_code=401, detail="Sessão inválida")

    # 1. Process the action
    # We ignore the text response for now as we'll show the updated state
    await process_action(phone=phone, message=message)

    # 2. Get the new state
    player_path = f"mudai.users.{phone}"
    player = db.get_artifact(player_path)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    meta = player.get("metadata_parsed", {})
    current_room_path = meta.get("current_room", "mudai.places.start")
    
    # If the action was 'profile', show the profile
    if message.lower() in ["perfil", "profile", "me", "eu"]:
        target_path = player_path
    elif message.lower() in ["salas", "rooms", "explore", "explorar"]:
        # Show the index page content for rooms? 
        # For now, let's just show the current room or profile
        target_path = current_room_path
    else:
        target_path = current_room_path

    artifact = db.get_artifact(target_path)
    if not artifact:
        # Fallback to start
        artifact = db.get_artifact("mudai.places.start")

    # 3. Render the updated content
    # For HTMX, we just need the inner HTML of the container
    # But let's use the full renderer logic if possible
    from .pages import _render_artifact_to_html_inner
    
    html_inner = _render_artifact_to_html_inner(artifact, target_path)
    return HTMLResponse(content=html_inner)


@router.get("/game/web-sync/{token}")
async def web_sync(token: str):
    """
    Sync the web UI with the current player state.
    Used for polling and realtime updates.
    Returns 204 No Content if nothing changed (HTMX won't swap).
    """
    phone = _find_phone_by_token(token)
    if not phone:
        raise HTTPException(status_code=401, detail="Sessão inválida")

    player_path = f"mudai.users.{phone}"
    player = db.get_artifact(player_path)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    meta = player.get("metadata_parsed", {})
    current_room_path = meta.get("current_room", "mudai.places.start")
    
    # Simple check: has the room changed or was there a recent interaction?
    # For now, we'll just render and let HTMX handle it, 
    # but we could add a version/timestamp check in metadata later.
    
    artifact = db.get_artifact(current_room_path)
    if not artifact:
        artifact = db.get_artifact("mudai.places.start")

    from .pages import _render_artifact_to_html_inner
    html_inner = _render_artifact_to_html_inner(artifact, current_room_path)
    
    # Calculate hash to check for changes
    content_hash = hashlib.md5(html_inner.encode()).hexdigest()
    
    # Check if the client sent an ETag-like header
    from fastapi import Request
    # Note: we need to add Request to the function params if we want to use it
    # But for now, let's just return the content and let HTMX handle it.
    # Actually, HTMX 1.9+ supports hx-swap="none" or similar if we return 204.
    
    # We can add a custom header to indicate sync status
    return HTMLResponse(
        content=html_inner,
        headers={"X-Sync-Hash": content_hash}
    )


class GameActionRequest(BaseModel):
    """Input from N8N webhook relay."""
    phone: str = Field(..., description="Player phone number (e.g. +5511976871674)")
    message: str = Field(..., description="Player's message text")
    conversation_id: Optional[str] = Field(None, description="Chatwoot conversation ID")
    account_id: Optional[str] = Field(None, description="Chatwoot account ID")


class GameActionResponse(BaseModel):
    """Output to N8N for Chatwoot reply."""
    response: str = Field(..., description="Formatted WhatsApp message")
    conversation_id: Optional[str] = None
    account_id: Optional[str] = None


@router.post("/game/action", response_model=GameActionResponse)
async def game_action(body: GameActionRequest):
    """
    Process a player action and return a formatted response.
    """
    if not body.phone or not body.message:
        raise HTTPException(status_code=400, detail="phone and message are required")

    try:
        response_text = await process_action(
            phone=body.phone,
            message=body.message,
        )

        return GameActionResponse(
            response=response_text,
            conversation_id=body.conversation_id,
            account_id=body.account_id,
        )

    except Exception as e:
        print(f"❌ Game action error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/game/state/{phone}")
async def get_player_state(phone: str):
    """
    Get the full state of a player (for debugging/web UI).
    """
    from .. import database as db
    from .. import room_manager as rooms

    clean = "".join(c for c in phone if c.isalnum())
    player = db.get_artifact(f"mudai.users.{clean}")

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    meta = player.get("metadata_parsed", {})
    current_room_path = meta.get("current_room", "")
    room_info = rooms.get_room_info(current_room_path) if current_room_path else None

    return {
        "phone": phone,
        "player": player,
        "active_challenge": meta.get("active_challenge"),
        "current_room": room_info,
        "current_room_state": world_state.get_room_state(current_room_path) if current_room_path else None,
        "current_room_blocks": world_state.list_room_blocks(current_room_path, limit=8) if current_room_path else [],
        "current_room_images": world_state.list_room_images(current_room_path, limit=8) if current_room_path else [],
        "available_rooms": [
            {
                "path": r["path"],
                "name": rooms._extract_room_name(r.get("content", "")),
                "tags": r.get("metadata_parsed", {}).get("tags", []),
            }
            for r in rooms.get_rooms_for_player(phone)
        ],
    }


@router.get("/game/room-state/{room_path:path}")
async def get_room_world_state(room_path: str):
    """
    Inspect the enriched world state for a room.
    """
    room = db.get_artifact(room_path)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    return {
        "room": room,
        "room_info": rooms.get_room_info(room_path),
        "state": world_state.get_room_state(room_path) or world_state.ensure_room_state(room_path),
        "blocks": world_state.list_room_blocks(room_path, limit=20),
        "images": world_state.list_room_images(room_path, limit=20),
        "snapshot": world_state.room_dynamic_snapshot(room_path),
    }
