"""
MUD-AI — Public HTML Pages Router.

Renders artifacts as beautiful HTML pages, accessible without authentication.
The AI can generate links like:
    https://mudai.servinder.com.br/p/mudai.users.junio
"""

from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime, timezone
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


def _build_landing_html() -> str:
    total = db.count_artifacts()
    players = db.count_artifacts("mudai.users.")
    places = db.count_artifacts("mudai.places.")
    world = db.count_artifacts("mudai.world.")

    md = f"""# 🎮 MUD-AI — RPG textual mediado por IA

> Jogue um MUD moderno via WhatsApp e Dashboard Web, onde cada mensagem planta uma semente no mundo.

## 📊 Agora mesmo
- 👤 Jogadores criados: **{players}**
- 🏠 Salas vivas: **{places}**
- 🌍 Artefatos de mundo: **{world}**
- 📦 Registros totais: **{total}**

---

## ✨ O que você pode fazer
- Explorar salas dinâmicas que mudam com as interações
- Deixar fragmentos de texto que viram parte da história
- Ganhar 🪙 sementes por explorar, conversar e criar
- Ver seu perfil e progresso em um dashboard em tempo real

## 💬 Jogar pelo WhatsApp
- Adicione o número oficial do MUD-AI
- Envie "oi" para começar o onboarding
- Você receberá um link seguro para o seu Dashboard Web

## 🖥 Jogar pela Web

Você pode navegar pelo mundo sem login, só para espiar:

- [Explorar Salas e Jogadores](/p)

Se já recebeu um link com token pelo WhatsApp, é só abrir:

- Cole o link direto no navegador, ou
- Cole apenas o token abaixo para ir direto ao seu painel.

<form method="get" action="/p" style="margin-top: 1.5rem;">
  <label for="token">Token de sessão (16 caracteres)</label><br/>
  <input id="token" name="token" maxlength="16" style="margin-top: 0.25rem; padding: 0.4rem 0.6rem; width: 220px;" />
  <button type="submit" style="padding: 0.4rem 0.8rem; margin-left: 0.5rem;">Abrir Dashboard</button>
</form>

---

## 🔐 Entrar com telefone + código

Se você já conversa com o MUD-AI pelo WhatsApp, pode entrar na versão Web assim:

1. Peça um código rápido para seu número.
2. Confira o código recebido no WhatsApp.
3. Digite telefone + código para entrar.

<form method="post" action="/auth/request-code" style="margin-top: 1.5rem;">
  <label for="phone-request">Seu telefone (com DDI)</label><br/>
  <input id="phone-request" name="phone" placeholder="+5511999999999" style="margin-top: 0.25rem; padding: 0.4rem 0.6rem; width: 220px;" />
  <button type="submit" style="padding: 0.4rem 0.8rem; margin-left: 0.5rem;">Pedir código</button>
</form>

<form method="post" action="/auth/verify-code" style="margin-top: 1rem;">
  <label for="phone-verify">Telefone</label><br/>
  <input id="phone-verify" name="phone" placeholder="+5511999999999" style="margin-top: 0.25rem; padding: 0.4rem 0.6rem; width: 220px;" />
  <br/>
  <label for="code" style="margin-top: 0.75rem; display:inline-block;">Código recebido</label><br/>
  <input id="code" name="code" maxlength="6" style="margin-top: 0.25rem; padding: 0.4rem 0.6rem; width: 120px;" />
  <button type="submit" style="padding: 0.4rem 0.8rem; margin-left: 0.5rem;">Entrar</button>
</form>

---

> MUD-AI é um experimento vivo. Cada resposta da IA é uma hipótese, cada jogador é um autor.
"""
    return render_markdown_to_html(content=md, title="MUD-AI — RPG textual", path="landing", full_page=True)


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page():
    return HTMLResponse(content=_build_landing_html())


@router.get("/p", response_class=HTMLResponse, include_in_schema=False)
async def index_page_no_slash(token: str | None = None):
    if token:
        t = token.strip()
        if len(t) == 16:
            return RedirectResponse(url=f"/p/{t}")
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


def _build_player_state(artifact: dict) -> dict:
    meta = artifact.get("metadata_parsed", {})
    return {
        "nickname": meta.get("nickname", "Viajante"),
        "seeds": meta.get("seeds", 0),
        "level": meta.get("level", 1),
        "current_room": meta.get("current_room", ""),
        "active_challenge": meta.get("active_challenge"),
        "mission_progress": meta.get("mission_progress", {}),
        "profile_signals": meta.get("profile_signals", {}),
        "structured_profile": meta.get("structured_profile", {}),
    }


@router.post("/auth/request-code", include_in_schema=False)
async def request_login_code(phone: str = Form(...)):
    clean = _clean_phone(phone)
    code = f"{datetime.now(timezone.utc).microsecond % 1000000:06d}"
    path = f"mudai.login_codes.{clean}"
    db.put_artifact(
        path=path,
        content="login code",
        metadata={
            "phone": clean,
            "code": code,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    md = """# Login via WhatsApp

Se o número estiver correto e já estiver jogando pelo WhatsApp,
você receberá um código por lá.

Depois, volte para a página inicial e informe telefone e código para entrar.

[_Voltar para o início_](/)
"""
    html = render_markdown_to_html(content=md, title="Login MUD-AI", path="login-request", full_page=True)
    return HTMLResponse(content=html)


@router.post("/auth/verify-code", include_in_schema=False)
async def verify_login_code(phone: str = Form(...), code: str = Form(...)):
    clean = _clean_phone(phone)
    path = f"mudai.login_codes.{clean}"
    artifact = db.get_artifact(path)
    if not artifact:
        md = """# Código inválido

Não encontrei um código ativo para este número.

Tente pedir um novo código e tentar novamente.

[_Voltar para o início_](/)
"""
        html = render_markdown_to_html(content=md, title="Login MUD-AI", path="login-error", full_page=True)
        return HTMLResponse(content=html, status_code=400)
    meta = artifact.get("metadata_parsed", {})
    if meta.get("code") != code.strip():
        md = """# Código incorreto

O código informado não confere.

Confira a mensagem recebida no WhatsApp e tente novamente.

[_Voltar para o início_](/)
"""
        html = render_markdown_to_html(content=md, title="Login MUD-AI", path="login-error", full_page=True)
        return HTMLResponse(content=html, status_code=400)
    import hashlib as _hash
    clean_phone = clean
    token = _hash.sha256(f"mudai-{clean_phone}-2026".encode()).hexdigest()[:16]
    return RedirectResponse(url=f"/p/{token}", status_code=303)


def _render_artifact_to_html_inner(artifact: dict, path: str, session_token: str | None = None, player_artifact: dict | None = None) -> str:
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
    player_state = None
    if player_artifact:
        player_state = _build_player_state(player_artifact)
        player_stats = {
            "nickname": player_state.get("nickname", "Viajante"),
            "seeds": player_state.get("seeds", 0),
            "level": player_state.get("level", 1),
        }
    elif session_token:
        artifact = _find_user_by_token(session_token)
        if artifact:
            player_state = _build_player_state(artifact)
            player_stats = {
                "nickname": player_state.get("nickname", "Viajante"),
                "seeds": player_state.get("seeds", 0),
                "level": player_state.get("level", 1),
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
        player_state=player_state,
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
    player_state = None
    if len(original_path) == 16:
        user_artifact = _find_user_by_token(original_path)
        if user_artifact:
            player_state = _build_player_state(user_artifact)
            player_stats = {
                "nickname": player_state.get("nickname", "Viajante"),
                "seeds": player_state.get("seeds", 0),
                "level": player_state.get("level", 1),
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
        player_state=player_state,
        players_here=players_here,
    )
    return HTMLResponse(content=full_html)
