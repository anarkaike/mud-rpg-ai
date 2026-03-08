"""
MUD-AI — Public HTML Pages Router.

Renders artifacts as beautiful HTML pages, accessible without authentication.
The AI can generate links like:
    https://mudai.servinder.com.br/p/mudai.users.junio
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from .. import database as db
from ..renderer import render_markdown_to_html
from .. import world_state
from .. import room_manager


router = APIRouter(tags=["pages"])


def _build_index_html() -> str:
    """Build the index page HTML showing rooms and players."""
    places = db.list_by_prefix("mudai.places.", direct_children_only=True)
    users = db.list_by_prefix("mudai.users.", direct_children_only=True)

    links_places = "\n".join(
        f'- [{p["path"].split(".")[-1]}](/p/{p["path"]})' for p in places
    )
    links_users = "\n".join(
        f'- [{u["path"].split(".")[-1]}](/p/{u["path"]})' for u in users
    )

    md = f"""# 🌱 MUD-AI — Mundo

## 🏠 Salas
{links_places or "_Nenhuma sala ainda_"}

## 👤 Jogadores
{links_users or "_Nenhum jogador ainda_"}

---

> Esse mundo está crescendo. Cada interação é uma semente.
"""
    return render_markdown_to_html(content=md, title="MUD-AI — Mundo", path="mudai")


@router.get("/p", response_class=HTMLResponse, include_in_schema=False)
async def index_page_no_slash():
    """Index page without trailing slash."""
    return HTMLResponse(content=_build_index_html())


import hashlib

def _clean_phone(phone: str) -> str:
    return "".join(c for c in phone if c.isalnum())


def _find_user_by_token(token: str):
    """Find a user artifact by its hashed token."""
    users = db.list_by_prefix("mudai.users.", direct_children_only=True)
    for user in users:
        clean = user["path"].split(".")[-1]
        user_token = hashlib.sha256(f"mudai-{clean}-2026".encode()).hexdigest()[:16]
        if user_token == token:
            return user
    return None


def _render_artifact_to_html_inner(artifact: dict, path: str) -> str:
    """Helper to render an artifact to HTML (inner container only)."""
    # Extract a nice title
    title = path.split(".")[-1].replace("-", " ").title()
    meta = artifact.get("metadata_parsed", {})
    if meta.get("nickname"):
        title = meta["nickname"]

    # Substitute template placeholders if this is a user profile
    content = artifact["content"]
    if path.startswith("mudai.users."):
        import re
        def replace_var(match):
            key = match.group(1)
            # Map template keys to metadata keys where they differ slightly
            key_map = {
                "habilidades_ofereco": "offers",
                "habilidades_busco": "seeks",
                "tracos": "essence",
                "avatar_textual": "avatar"
            }
            actual_key = key_map.get(key, key)
            val = meta.get(actual_key)
            if not val:
                return "_ainda não descoberto_"
            return str(val)
        
        content = re.sub(r'\{([a-zA-Z0-9_]+)\}', replace_var, content)

    # Fetch room state if this is a room
    room_state = None
    if path.startswith("mudai.places."):
        # Use snapshot to get state + current image
        room_state = world_state.room_dynamic_snapshot(path)

    # Fetch player stats if session token is provided
    player_stats = None
    if len(path) == 16:
        artifact = _find_user_by_token(path)
        if artifact:
            meta = artifact.get("metadata_parsed", {})
            player_stats = {
                "nickname": meta.get("nickname", "Viajante"),
                "seeds": meta.get("seeds", 0),
                "level": meta.get("level", 1),
            }

    # Fetch players here if this is a room
    players_here = None
    if path.startswith("mudai.places."):
        players_here = room_manager.get_players_in_room(path)

    return render_markdown_to_html(
        content=content,
        title=title,
        path=path,
        full_page=False,
        room_state=room_state,
        player_stats=player_stats,
        players_here=players_here,
    )


@router.get("/p/{path:path}", response_class=HTMLResponse)
async def render_page(path: str):
    """
    Render an artifact as a public HTML page.
    Supports both direct dot-paths and 16-char hashed profile tokens.
    """
    if not path or path.strip() == "":
        return HTMLResponse(content=_build_index_html())

    # 1. Try direct path first
    artifact = db.get_artifact(path)
    original_path = path

    # 2. If not found and path looks like a 16-char token, search for user
    if artifact is None and len(path) == 16:
        artifact = _find_user_by_token(path)
        if artifact:
            path = artifact["path"]

    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Page not found: {path}")

    # Fetch room state if this is a room
    room_state = None
    if path.startswith("mudai.places."):
        room_state = world_state.room_dynamic_snapshot(path)

    # Fetch player stats if session token is provided
    player_stats = None
    if len(original_path) == 16:
        user_artifact = _find_user_by_token(original_path)
        if user_artifact:
            u_meta = user_artifact.get("metadata_parsed", {})
            player_stats = {
                "nickname": u_meta.get("nickname", "Viajante"),
                "seeds": u_meta.get("seeds", 0),
                "level": u_meta.get("level", 1),
            }

    # For full pages, we want the outer wrapper too
    # Extract title from meta for the wrapper
    title = path.split(".")[-1].replace("-", " ").title()
    if artifact.get("metadata_parsed", {}).get("nickname"):
        title = artifact["metadata_parsed"]["nickname"]
        
    # Re-render to get the full page with the correct path (original token if provided)
    meta = artifact.get("metadata_parsed", {})
    content = artifact["content"]
    if path.startswith("mudai.users."):
        import re
        def replace_var(match):
            key = match.group(1)
            key_map = {"habilidades_ofereco": "offers", "habilidades_busco": "seeks", "tracos": "essence", "avatar_textual": "avatar"}
            val = meta.get(key_map.get(key, key))
            return str(val) if val else "_ainda não descoberto_"
        content = re.sub(r'\{([a-zA-Z0-9_]+)\}', replace_var, content)

    # Fetch players here if this is a room
    players_here = None
    if path.startswith("mudai.places."):
        players_here = room_manager.get_players_in_room(path)

    full_html = render_markdown_to_html(
        content=content,
        title=title,
        path=original_path, # Use original token path to show terminal
        full_page=True,
        room_state=room_state,
        player_stats=player_stats,
        players_here=players_here,
    )
    return HTMLResponse(content=full_html)
