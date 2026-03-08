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


@router.get("/p/{path:path}", response_class=HTMLResponse)
async def render_page(path: str):
    """
    Render an artifact as a public HTML page.

    The path uses dot-notation: /p/mudai.users.junio
    Use /p/ for the index page.
    """
    # Handle empty path (index page)
    if not path or path.strip() == "":
        return HTMLResponse(content=_build_index_html())

    artifact = db.get_artifact(path)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Page not found: {path}")

    # Extract a nice title from the path
    title = path.split(".")[-1].replace("-", " ").title()

    html = render_markdown_to_html(
        content=artifact["content"],
        title=title,
        path=path,
    )
    return HTMLResponse(content=html)
