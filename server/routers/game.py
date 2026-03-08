"""
MUD-AI — Game Router.

Single endpoint that processes all player actions.
N8N just proxies: Chatwoot → POST /api/v1/game/action → Chatwoot reply.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ..game_engine import process_action


router = APIRouter(prefix="/api/v1", tags=["game"])


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
    print(f"📥 Received game action: phone={body.phone}, conv_id={body.conversation_id}, acc_id={body.account_id}")
    
    if not body.phone or not body.message:
        raise HTTPException(status_code=400, detail="phone and message are required")

    try:
        response_text = await process_action(
            phone=body.phone,
            message=body.message,
        )

        return GameActionResponse(
            response=response_text,
            conversation_id=body.conversation_id or "",
            account_id=body.account_id or "1",
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
        "current_room": room_info,
        "available_rooms": [
            {
                "path": r["path"],
                "name": rooms._extract_room_name(r.get("content", "")),
                "tags": r.get("metadata_parsed", {}).get("tags", []),
            }
            for r in rooms.get_rooms_for_player(phone)
        ],
    }
