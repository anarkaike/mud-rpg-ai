"""
MUD-AI — Game Engine.

Central orchestrator that processes all player actions.
Determines intent, manages state, calls AI when needed,
and returns formatted responses.
"""

from . import database as db
from . import message_formatter as fmt
from . import room_manager as rooms
from .onboarding import start_onboarding, process_onboarding
from .ai_client import chat_completion, chat_completion_json


# ─── Action Parsing Prompt ────────────────────────────

ACTION_PARSE_PROMPT = """Você é o interpretador de comandos do MUD-AI, um RPG textual via WhatsApp.
Dada a mensagem do jogador, determine a INTENÇÃO numa dessas categorias:

- "move" — jogador quer se mover (direção ou nome de sala)
- "look" — jogador quer ver a sala atual em detalhe
- "profile" — jogador quer ver seu perfil
- "explore" — jogador quer ver lista de salas disponíveis
- "decorate" — jogador quer deixar uma marca/fragmento na sala
- "help" — jogador pede ajuda
- "chat" — qualquer outra interação conversacional

Responda APENAS com JSON:
{"action": "<tipo>", "target": "<alvo se houver>"}

Exemplos:
- "ir para norte" → {"action": "move", "target": "norte"}
- "quero ir pra praça das trocas" → {"action": "move", "target": "praça das trocas"}
- "olhar" → {"action": "look", "target": ""}
- "perfil" → {"action": "profile", "target": ""}
- "salas" → {"action": "explore", "target": ""}
- "quero decorar essa sala" → {"action": "decorate", "target": ""}
- "ajuda" → {"action": "help", "target": ""}
- "Que lugar bonito!" → {"action": "chat", "target": ""}
- "norte" → {"action": "move", "target": "norte"}
- "n" → {"action": "move", "target": "norte"}
- "s" → {"action": "move", "target": "sul"}
- "eu" → {"action": "profile", "target": ""}"""


NARRATIVE_PROMPT = """Você é o Game Master do MUD-AI, um RPG textual via WhatsApp em português.

REGRAS ESTRITAS:
- Responda em NO MÁXIMO 2 frases curtas
- Seja poético mas CONCISO
- Use emojis com moderação (máximo 1)
- Não liste saídas ou comandos (isso é feito pelo template)
- Foque na ATMOSFERA e SENSAÇÃO do momento
- NUNCA quebre a quarta parede

Contexto:
- Sala: {room_name}
- Jogador: {player_name}
- Ação: {action}

Gere APENAS a frase narrativa de resposta."""


# ─── Main Entry Point ─────────────────────────────────

async def process_action(phone: str, message: str) -> str:
    """
    Process any player action and return a formatted WhatsApp message.
    This is the single entry point for all game logic.
    """
    clean = _clean_phone(phone)
    player_path = f"mudai.users.{clean}"

    # 1. Check if player exists
    player = db.get_artifact(player_path)

    if not player:
        # New player — start onboarding
        result = await start_onboarding(phone)
        return result

    meta = player.get("metadata_parsed", {})
    state = meta.get("state", "")

    # 2. If in onboarding, process onboarding step
    if state == "onboarding":
        return await process_onboarding(phone, message)

    # 3. Parse player intent
    action = await _parse_action(message)
    action_type = action.get("action", "chat")
    target = action.get("target", "")

    # 4. Route to handler
    try:
        match action_type:
            case "move":
                return await _handle_move(phone, meta, target)
            case "look":
                return await _handle_look(phone, meta)
            case "profile":
                return _handle_profile(phone, meta)
            case "explore":
                return _handle_explore(phone, meta)
            case "decorate":
                return await _handle_decorate(phone, meta, message)
            case "help":
                return _handle_help()
            case _:
                return await _handle_chat(phone, meta, message)
    except Exception as e:
        print(f"❌ Error processing action: {e}")
        return fmt.format_error(f"Algo deu errado. Tente novamente ou diga \"ajuda\".")


# ─── Action Handlers ──────────────────────────────────

async def _handle_move(phone: str, meta: dict, target: str) -> str:
    """Handle player movement."""
    current_room = meta.get("current_room", "mudai.places.start")

    # Try direction first
    target_path = rooms.find_room_by_direction(current_room, target)

    # Try room name if direction didn't work
    if not target_path:
        target_path = rooms.find_room_by_name(target)

    if not target_path:
        return fmt.format_error(
            f"Não encontrei \"{target}\" por aqui.\n"
            f"Diga _\"olhar\"_ para ver as saídas disponíveis."
        )

    # Move player
    rooms.move_player(phone, target_path)

    # Get room info
    room_info = rooms.get_room_info(target_path)
    if not room_info:
        return fmt.format_error("Essa sala parece não existir... estranho.")

    # Generate short narrative
    nickname = meta.get("nickname", "Aventureiro")
    narrative = await _generate_narrative(
        room_name=room_info["name"],
        player_name=nickname,
        action=f"chegou vindo de {_extract_room_name_from_path(current_room)}",
    )

    # Build room view
    return fmt.format_room_view(
        room_name=room_info["name"],
        room_subtitle=room_info.get("subtitle", room_info.get("purpose", "")),
        seeds=meta.get("seeds", 0),
        level=meta.get("level", 1),
        players_here=room_info["players_here"],
        narrative=narrative,
        exits=room_info["exits"],
        suggestions=_get_room_suggestions(room_info),
        breadcrumb=room_info["name"].replace("🌱 ", "").replace("📝 ", ""),
    )


async def _handle_look(phone: str, meta: dict) -> str:
    """Describe current room in detail."""
    current_room = meta.get("current_room", "mudai.places.start")
    room_info = rooms.get_room_info(current_room)

    if not room_info:
        return fmt.format_error("Você parece estar... em lugar nenhum. Diga \"salas\" para explorar.")

    nickname = meta.get("nickname", "Aventureiro")
    narrative = await _generate_narrative(
        room_name=room_info["name"],
        player_name=nickname,
        action="olha ao redor, observando cada detalhe",
    )

    return fmt.format_room_view(
        room_name=room_info["name"],
        room_subtitle=room_info.get("subtitle", room_info.get("purpose", "")),
        seeds=meta.get("seeds", 0),
        level=meta.get("level", 1),
        players_here=room_info["players_here"],
        narrative=narrative,
        exits=room_info["exits"],
        suggestions=_get_room_suggestions(room_info),
        breadcrumb=room_info["name"].replace("🌱 ", "").replace("📝 ", ""),
    )


def _handle_profile(phone: str, meta: dict) -> str:
    """Show player profile."""
    current_room = meta.get("current_room", "mudai.places.start")
    room_info = rooms.get_room_info(current_room)
    room_name = room_info["name"] if room_info else "Desconhecido"

    return fmt.format_profile(
        nickname=meta.get("nickname", "Anônimo"),
        level=meta.get("level", 1),
        seeds=meta.get("seeds", 10),
        current_room=room_name.replace("🌱 ", ""),
        since="hoje",
        essence=meta.get("essence", ""),
        traits="",
        seeks=meta.get("seeks", ""),
        offers=meta.get("offers", ""),
        has_house=meta.get("has_house", False),
        challenges_done=meta.get("challenges_completed", 0),
        suggestions=[
            {"cmd": "olhar", "desc": "ver sala atual"},
            {"cmd": "salas", "desc": "explorar"},
            {"cmd": "voltar", "desc": "ir para sala anterior"},
        ],
    )


def _handle_explore(phone: str, meta: dict) -> str:
    """List available rooms filtered by profile."""
    current_room = meta.get("current_room", "mudai.places.start")
    available = rooms.get_rooms_for_player(phone)

    room_list = []
    for r in available:
        r_meta = r.get("metadata_parsed", {})
        name = rooms._extract_room_name(r.get("content", ""))
        room_list.append({
            "emoji": r_meta.get("emoji", "🚪"),
            "name": name,
            "subtitle": r_meta.get("purpose", _extract_short_subtitle(r.get("content", ""))),
            "path": r["path"],
        })

    return fmt.format_room_list(room_list, current_room)


async def _handle_decorate(phone: str, meta: dict, message: str) -> str:
    """Add a fragment to the current room."""
    seeds = meta.get("seeds", 0)
    if seeds < 1:
        return fmt.format_error("Você precisa de pelo menos 🪙 1 semente para decorar.")

    current_room = meta.get("current_room", "mudai.places.start")
    nickname = meta.get("nickname", "Alguém")

    # Use the message itself as the fragment (strip "decorar" prefix if present)
    fragment = message.strip()
    for prefix in ["decorar ", "decorar:", "decoração ", "quero decorar "]:
        if fragment.lower().startswith(prefix):
            fragment = fragment[len(prefix):].strip()
            break

    if len(fragment) < 3:
        return fmt.format_interaction(
            room_name=rooms._extract_room_name(db.get_artifact(current_room)["content"]),
            action_label="Decorar",
            seeds=seeds,
            seeds_change=0,
            level=meta.get("level", 1),
            narrative="O que gostaria de deixar escrito aqui? Diga algo após \"decorar\".",
            badge=None,
            suggestions=[
                {"cmd": "decorar A esperança é a última que morre", "desc": "exemplo"},
            ],
        )

    # Add fragment
    from .onboarding import _add_fragment_to_room, _update_meta
    _add_fragment_to_room(current_room, fragment, nickname)

    # Deduct seed
    _update_meta(phone, {"seeds": seeds - 1})

    room_info = rooms.get_room_info(current_room)

    return fmt.format_interaction(
        room_name=room_info["name"] if room_info else "Sala",
        action_label="Decorando",
        seeds=seeds - 1,
        seeds_change=-1,
        level=meta.get("level", 1),
        narrative=f"Você deixou sua marca: _{fragment}_ ✨",
        badge="Fragmento adicionado à sala!",
        suggestions=[
            {"cmd": "olhar", "desc": "ver como ficou"},
            {"cmd": "salas", "desc": "explorar mais"},
        ],
        breadcrumb=room_info["name"].replace("🌱 ", "") if room_info else "",
    )


def _handle_help() -> str:
    """Show help message."""
    return "\n".join([
        fmt.SEP,
        "📖 *COMANDOS*",
        fmt.SEP,
        "",
        "🗺 *Navegação:*",
        "  ▸ _\"olhar\"_ — ver sala atual",
        "  ▸ _\"norte/sul/leste/oeste\"_ — mover",
        "  ▸ _\"salas\"_ — explorar salas",
        "  ▸ _Nome da sala_ — ir direto",
        "",
        "👤 *Perfil:*",
        "  ▸ _\"perfil\"_ ou _\"eu\"_ — seu personagem",
        "",
        "🎨 *Interação:*",
        "  ▸ _\"decorar [texto]\"_ — deixar marca",
        "  ▸ _\"quem está aqui\"_ — ver jogadores",
        "",
        "💬 *Ou simplesmente converse!*",
        "A IA entende linguagem natural.",
        fmt.SEP,
    ])


async def _handle_chat(phone: str, meta: dict, message: str) -> str:
    """Handle general chat/conversation."""
    current_room = meta.get("current_room", "mudai.places.start")
    room_info = rooms.get_room_info(current_room)
    nickname = meta.get("nickname", "Aventureiro")

    narrative = await _generate_narrative(
        room_name=room_info["name"] if room_info else "???",
        player_name=nickname,
        action=f"diz: \"{message}\"",
    )

    return fmt.format_interaction(
        room_name=room_info["name"] if room_info else "Sala",
        action_label="Conversando",
        seeds=meta.get("seeds", 0),
        seeds_change=0,
        level=meta.get("level", 1),
        narrative=narrative,
        badge=None,
        suggestions=_get_room_suggestions(room_info) if room_info else [
            {"cmd": "olhar", "desc": "ver onde está"},
        ],
        breadcrumb=room_info["name"].replace("🌱 ", "") if room_info else "",
    )


# ─── AI Helpers ───────────────────────────────────────

async def _parse_action(message: str) -> dict:
    """Use AI to determine the player's intent."""
    msg = message.strip().lower()

    # Fast-path common commands (no AI needed)
    fast_map = {
        "olhar": {"action": "look", "target": ""},
        "look": {"action": "look", "target": ""},
        "perfil": {"action": "profile", "target": ""},
        "eu": {"action": "profile", "target": ""},
        "salas": {"action": "explore", "target": ""},
        "explorar": {"action": "explore", "target": ""},
        "ajuda": {"action": "help", "target": ""},
        "help": {"action": "help", "target": ""},
        "norte": {"action": "move", "target": "norte"},
        "sul": {"action": "move", "target": "sul"},
        "leste": {"action": "move", "target": "leste"},
        "oeste": {"action": "move", "target": "oeste"},
        "n": {"action": "move", "target": "norte"},
        "s": {"action": "move", "target": "sul"},
        "l": {"action": "move", "target": "leste"},
        "o": {"action": "move", "target": "oeste"},
    }

    if msg in fast_map:
        return fast_map[msg]

    # Check decorar prefix
    if msg.startswith("decorar"):
        return {"action": "decorate", "target": msg}

    # Use AI for complex messages
    try:
        result = await chat_completion_json(
            system_prompt=ACTION_PARSE_PROMPT,
            user_message=message,
            temperature=0.1,
            max_tokens=60,
        )
        return result
    except Exception:
        return {"action": "chat", "target": ""}


async def _generate_narrative(room_name: str, player_name: str, action: str) -> str:
    """Generate a short narrative response."""
    try:
        prompt = NARRATIVE_PROMPT.format(
            room_name=room_name,
            player_name=player_name,
            action=action,
        )
        return await chat_completion(
            system_prompt=prompt,
            user_message=action,
            temperature=0.8,
            max_tokens=80,
        )
    except Exception as e:
        print(f"⚠️ Narrative generation failed: {e}")
        return "A atmosfera do lugar te envolve silenciosamente."


# ─── Helpers ──────────────────────────────────────────

def _clean_phone(phone: str) -> str:
    return "".join(c for c in phone if c.isalnum())


def _extract_room_name_from_path(path: str) -> str:
    """Get a human-readable name from a room path."""
    room = db.get_artifact(path)
    if room:
        return rooms._extract_room_name(room["content"])
    parts = path.split(".")
    return parts[-1].replace("_", " ").title() if parts else "Sala"


def _extract_short_subtitle(content: str) -> str:
    """Get a short subtitle from content."""
    sub = rooms._extract_subtitle(content)
    return sub[:50] + "..." if len(sub) > 50 else sub


def _get_room_suggestions(room_info: dict) -> list[dict]:
    """Get contextual suggestions based on room state."""
    suggestions = [
        {"cmd": "olhar", "desc": "ver detalhes"},
    ]

    if room_info and room_info.get("tags"):
        tags = room_info["tags"]
        if "poesia" in tags:
            suggestions.append({"cmd": "escrever", "desc": "compor um verso"})
        elif "jogo" in tags:
            suggestions.append({"cmd": "jogar", "desc": "iniciar um jogo"})
        elif "escrita" in tags:
            suggestions.append({"cmd": "contribuir", "desc": "adicionar à história"})
        else:
            suggestions.append({"cmd": "decorar", "desc": "deixar sua marca"})
    else:
        suggestions.append({"cmd": "decorar", "desc": "deixar sua marca"})

    suggestions.append({"cmd": "salas", "desc": "explorar mais"})
    return suggestions[:3]
