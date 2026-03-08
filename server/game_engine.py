"""
MUD-AI — Game Engine v2.1.

Central orchestrator: slash commands, seeds economy, contextual AI,
badges, and referral system.
"""

import hashlib
from . import database as db
from . import message_formatter as fmt
from . import room_manager as rooms
from .onboarding import start_onboarding, process_onboarding, _update_meta, _clean_phone
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
- "seeds" — jogador pergunta sobre sementes, moedas, pontos, como ganhar
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
- "como ganho sementes?" → {"action": "seeds", "target": ""}
- "o que são sementes?" → {"action": "seeds", "target": ""}
- "quantas sementes tenho?" → {"action": "seeds", "target": ""}
- "Que lugar bonito!" → {"action": "chat", "target": ""}
- "norte" → {"action": "move", "target": "norte"}
- "n" → {"action": "move", "target": "norte"}
- "s" → {"action": "move", "target": "sul"}
- "eu" → {"action": "profile", "target": ""}"""


NARRATIVE_PROMPT = """Você é o narrador do MUD-AI, um RPG textual via WhatsApp em português.

REGRAS:
- NO MÁXIMO 2 frases curtas e diretas
- Tom casual e leve — como um narrador de jogo, não um poeta
- Use vocabulário simples, evite metáforas rebuscadas
- Máximo 1 emoji no final
- Não liste saídas ou comandos (o template faz isso)
- Foque no que está acontecendo, não em divagações
- NUNCA quebre a quarta parede

Contexto:
- Sala: {room_name}
- Jogador: {player_name}
- Ação: {action}

Gere APENAS a frase narrativa."""


CHAT_PROMPT = """Você é o guia do MUD-AI, um RPG textual via WhatsApp.
Seu nome é CultivIA. Responda de forma direta, útil e amigável.

REGRAS IMPORTANTES:
- Responda em NO MÁXIMO 3 frases
- Seja direto e útil — nada de enrolação poética
- Se a pessoa perguntar algo sobre o jogo, responda claramente
- Se for uma conversa casual, seja amigável e breve
- Use no máximo 1-2 emojis
- NUNCA invente mecânicas que não existem

MECÂNICA DO JOGO (use para responder perguntas):
- 🪙 Sementes = moeda do jogo
- Jogador começa com 50 sementes
- Ganhar sementes: visitar salas novas (+2), decorar (+1), conversar (+1), indicar amigos (+5)
- Gastar sementes: decorar salas (-1)
- Níveis sobem conforme acumula ações
- Badges: 🌱 Primeiro Passo, 📝 Escritor, 🗺 Explorador, 🤝 Conector
- Comandos: /reset, /ajuda, /sementes, /indicar, /perfil, /salas
- Digitar "salas" mostra salas disponíveis
- Digitar "perfil" mostra seu personagem

CONTEXTO ATUAL:
- Sala: {room_name}
- Propósito da sala: {room_purpose}
- Jogador: {player_name} (Nv.{player_level}, {player_seeds} sementes)

{room_system_prompt}

Mensagem do jogador: {message}

Responda de forma direta e útil."""


# ─── Seeds Economy Config ─────────────────────────────

SEEDS_REWARDS = {
    "visit_new_room": 2,
    "decorate": 1,
    "chat": 1,
    "onboarding_complete": 3,
    "referral": 5,
    "first_look": 1,
}

SEEDS_COSTS = {
    "decorate": 1,
}

# ─── Levels & Badges ─────────────────────────────────

LEVEL_THRESHOLDS = [0, 10, 30, 60, 100, 150, 220, 300]

BADGES = {
    "primeiro_passo": {"emoji": "🌱", "name": "Primeiro Passo", "desc": "Completou o onboarding"},
    "escritor": {"emoji": "📝", "name": "Escritor", "desc": "Decorou 3+ salas"},
    "explorador": {"emoji": "🗺", "name": "Explorador", "desc": "Visitou 5+ salas"},
    "conector": {"emoji": "🤝", "name": "Conector", "desc": "Fez 1+ indicação"},
    "veterano": {"emoji": "💎", "name": "Veterano", "desc": "Chegou ao nível 5"},
    "social": {"emoji": "💬", "name": "Social", "desc": "Conversou 20+ vezes"},
}


# ─── Main Entry Point ─────────────────────────────────

async def process_action(phone: str, message: str) -> str:
    """
    Process any player action and return a formatted WhatsApp message.
    This is the single entry point for all game logic.
    """
    clean = _clean_phone(phone)
    player_path = f"mudai.users.{clean}"
    msg = message.strip()

    # 0. Check slash commands FIRST (even before player exists for /reset)
    if msg.startswith("/"):
        return await _handle_slash_command(phone, msg)

    # 1. Check if player exists
    player = db.get_artifact(player_path)

    if not player:
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
            case "seeds":
                return _handle_seeds(phone, meta)
            case _:
                return await _handle_chat(phone, meta, message)
    except Exception as e:
        print(f"❌ Error processing action: {e}")
        return fmt.format_error(f"Algo deu errado. Tente novamente ou diga \"ajuda\".")


# ─── Slash Command Handler ───────────────────────────

async def _handle_slash_command(phone: str, msg: str) -> str:
    """Handle /commands before any other processing."""
    parts = msg.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    match cmd:
        case "/reset":
            return _handle_reset(phone)
        case "/ajuda" | "/help":
            return _handle_help()
        case "/sementes" | "/seeds":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_seeds(phone, player.get("metadata_parsed", {}))
        case "/perfil" | "/profile":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_profile(phone, player.get("metadata_parsed", {}))
        case "/salas" | "/rooms":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_explore(phone, player.get("metadata_parsed", {}))
        case "/indicar" | "/invite":
            return _handle_referral(phone, args)
        case _:
            return fmt.format_error(
                f"Comando desconhecido: {cmd}\n\n"
                "Comandos disponíveis:\n"
                "  /ajuda — ver ajuda\n"
                "  /sementes — seu saldo\n"
                "  /perfil — seu personagem\n"
                "  /salas — explorar\n"
                "  /indicar +55... — convidar amigo\n"
                "  /reset — recomeçar do zero"
            )


def _handle_reset(phone: str) -> str:
    """Delete player profile and start fresh."""
    clean = _clean_phone(phone)
    player_path = f"mudai.users.{clean}"
    player = db.get_artifact(player_path)

    if player:
        db.delete_artifact(player_path)

    return "\n".join([
        fmt.SEP,
        "🔄 *RESET COMPLETO*",
        fmt.SEP,
        "",
        "Seu perfil foi apagado.",
        "Envie qualquer mensagem para começar de novo!",
        "",
        "💬 _Digite 'oi' para recomeçar_",
        fmt.SEP,
    ])


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
            f"Diga _\"olhar\"_ para ver as saídas ou _\"salas\"_ para a lista completa."
        )

    # Move player
    rooms.move_player(phone, target_path)

    # Check if new room → reward
    visited = meta.get("rooms_visited", [])
    seeds_change = 0
    new_badge = None

    if target_path not in visited:
        seeds_change = SEEDS_REWARDS["visit_new_room"]
        _award_seeds(phone, seeds_change)
        visited.append(target_path)

        # Check explorer badge
        if len(visited) >= 5:
            new_badge = _check_and_award_badge(phone, "explorador")

    # Get room info
    room_info = rooms.get_room_info(target_path)
    if not room_info:
        return fmt.format_error("Essa sala parece não existir... estranho.")

    # Generate short narrative
    nickname = meta.get("nickname", "Aventureiro")
    narrative = await _generate_narrative(
        room_name=room_info["name"],
        player_name=nickname,
        action=f"chegou na sala",
    )

    seeds = meta.get("seeds", 0) + seeds_change

    return fmt.format_room_view(
        room_name=room_info["name"],
        room_subtitle=room_info.get("subtitle", room_info.get("purpose", "")),
        seeds=seeds,
        level=_calculate_level(meta),
        players_here=room_info["players_here"],
        narrative=narrative,
        exits=room_info["exits"],
        suggestions=_get_room_suggestions(room_info),
        breadcrumb=room_info["name"].replace("🌱 ", "").replace("📝 ", ""),
        seeds_change=seeds_change,
        badge=new_badge,
        profile_url=_generate_profile_url(phone),
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
        action="olha ao redor com atenção",
    )

    return fmt.format_room_view(
        room_name=room_info["name"],
        room_subtitle=room_info.get("subtitle", room_info.get("purpose", "")),
        seeds=meta.get("seeds", 0),
        level=_calculate_level(meta),
        players_here=room_info["players_here"],
        narrative=narrative,
        exits=room_info["exits"],
        suggestions=_get_room_suggestions(room_info),
        breadcrumb=room_info["name"].replace("🌱 ", "").replace("📝 ", ""),
        profile_url=_generate_profile_url(phone),
    )


def _handle_profile(phone: str, meta: dict) -> str:
    """Show player profile."""
    current_room = meta.get("current_room", "mudai.places.start")
    room_info = rooms.get_room_info(current_room)
    room_name = room_info["name"] if room_info else "Desconhecido"
    badges = meta.get("badges", [])
    badge_str = " ".join(BADGES[b]["emoji"] for b in badges if b in BADGES) if badges else "nenhum ainda"

    return fmt.format_profile(
        nickname=meta.get("nickname", "Anônimo"),
        level=_calculate_level(meta),
        seeds=meta.get("seeds", 50),
        current_room=room_name.replace("🌱 ", ""),
        since="hoje",
        essence=meta.get("essence", ""),
        badges=badge_str,
        seeks=meta.get("seeks", ""),
        offers=meta.get("offers", ""),
        rooms_visited=len(meta.get("rooms_visited", [])),
        decorations=meta.get("decorations_count", 0),
        suggestions=[
            {"cmd": "olhar", "desc": "ver sala atual"},
            {"cmd": "salas", "desc": "explorar"},
            {"cmd": "/sementes", "desc": "ver como ganhar"},
        ],
        profile_url=_generate_profile_url(phone),
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

    return fmt.format_room_list(room_list, current_room, _generate_profile_url(phone))


async def _handle_decorate(phone: str, meta: dict, message: str) -> str:
    """Add a fragment to the current room."""
    seeds = meta.get("seeds", 0)
    if seeds < SEEDS_COSTS["decorate"]:
        return fmt.format_error(
            f"Você precisa de pelo menos 🪙 {SEEDS_COSTS['decorate']} semente para decorar.\n\n"
            "Diga _\"/sementes\"_ para ver como ganhar mais!"
        )

    current_room = meta.get("current_room", "mudai.places.start")
    nickname = meta.get("nickname", "Alguém")

    # Use the message itself as the fragment
    fragment = message.strip()
    for prefix in ["decorar ", "decorar:", "decoração ", "quero decorar "]:
        if fragment.lower().startswith(prefix):
            fragment = fragment[len(prefix):].strip()
            break

    if len(fragment) < 3:
        room_info = rooms.get_room_info(current_room)
        return fmt.format_interaction(
            room_name=room_info["name"] if room_info else "Sala",
            action_label="Decorar",
            seeds=seeds,
            seeds_change=0,
            level=_calculate_level(meta),
            narrative="O que quer deixar escrito? Diga algo depois de \"decorar\".",
            badge=None,
            suggestions=[
                {"cmd": "decorar Aqui esteve alguém que sonhava alto", "desc": "exemplo"},
            ],
            profile_url=_generate_profile_url(phone),
        )

    # Add fragment
    from .onboarding import _add_fragment_to_room
    _add_fragment_to_room(current_room, fragment, nickname)

    # Deduct seed cost + award participation seed (net 0 first time, but tracks)
    new_seeds = seeds - SEEDS_COSTS["decorate"] + SEEDS_REWARDS["decorate"]
    dec_count = meta.get("decorations_count", 0) + 1
    _update_meta(phone, {"seeds": new_seeds, "decorations_count": dec_count})

    # Check writer badge
    new_badge = None
    if dec_count >= 3:
        new_badge = _check_and_award_badge(phone, "escritor")

    room_info = rooms.get_room_info(current_room)

    net_change = -SEEDS_COSTS["decorate"] + SEEDS_REWARDS["decorate"]

    return fmt.format_interaction(
        room_name=room_info["name"] if room_info else "Sala",
        action_label="Decorando",
        seeds=new_seeds,
        seeds_change=net_change,
        level=_calculate_level(meta),
        narrative=f"Você deixou sua marca: _{fragment}_ ✨",
        badge=BADGES[new_badge]["emoji"] + " " + BADGES[new_badge]["name"] if new_badge else "Fragmento adicionado!",
        suggestions=[
            {"cmd": "olhar", "desc": "ver como ficou"},
            {"cmd": "salas", "desc": "explorar mais"},
        ],
        breadcrumb=room_info["name"].replace("🌱 ", "") if room_info else "",
        profile_url=_generate_profile_url(phone),
    )


def _handle_help() -> str:
    """Show help message with seeds info."""
    return "\n".join([
        fmt.SEP,
        "📖 *COMANDOS DO MUD-AI*",
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
        "",
        "⚡ *Comandos:*",
        "  ▸ /sementes — saldo e como ganhar",
        "  ▸ /indicar +55... — convidar amigo",
        "  ▸ /reset — recomeçar do zero",
        "",
        "💬 *Ou simplesmente converse!*",
        "Pode perguntar qualquer coisa.",
        fmt.SEP,
    ])


def _handle_seeds(phone: str, meta: dict) -> str:
    """Show seeds balance and ways to earn."""
    seeds = meta.get("seeds", 0)
    total_earned = meta.get("total_seeds_earned", 0)

    return "\n".join([
        fmt.SEP,
        "🪙 *SUAS SEMENTES*",
        fmt.SEP,
        f"Saldo atual: *{seeds}* sementes",
        "",
        "💡 *Como ganhar:*",
        f"  ▸ Visitar sala nova → +{SEEDS_REWARDS['visit_new_room']} 🪙",
        f"  ▸ Decorar uma sala → +{SEEDS_REWARDS['decorate']} 🪙",
        f"  ▸ Conversar → +{SEEDS_REWARDS['chat']} 🪙",
        f"  ▸ Indicar amigo → +{SEEDS_REWARDS['referral']} 🪙",
        "",
        "💸 *Como gastar:*",
        f"  ▸ Decorar sala → -{SEEDS_COSTS['decorate']} 🪙",
        "",
        f"📊 Total já ganho: {total_earned} sementes",
        "",
        "💬 _Cada interação vale! Explore e ganhe._",
        fmt.SEP,
    ])


def _handle_referral(phone: str, target_phone: str) -> str:
    """Handle referral invitation."""
    if not target_phone or len(target_phone) < 10:
        return fmt.format_error(
            "Use: /indicar +5511999999999\n\n"
            "Quando a pessoa entrar, vocês dois ganham 🪙 5 sementes!"
        )

    clean = _clean_phone(phone)
    target_clean = _clean_phone(target_phone)

    if clean == target_clean:
        return fmt.format_error("Você não pode indicar a si mesmo! 😄")

    # Save referral
    referral_path = f"mudai.referrals.{target_clean}"
    existing = db.get_artifact(referral_path)
    if existing:
        return fmt.format_error("Essa pessoa já foi indicada por alguém!")

    db.put_artifact(
        path=referral_path,
        content=f"Indicação de {phone} para {target_phone}",
        metadata={"referrer": phone, "target": target_phone, "claimed": False},
    )

    return "\n".join([
        fmt.SEP,
        "🤝 *INDICAÇÃO REGISTRADA*",
        fmt.SEP,
        "",
        f"Quando *{target_phone}* entrar no MUD-AI,",
        f"vocês dois ganham 🪙 {SEEDS_REWARDS['referral']} sementes!",
        "",
        "💬 _Mande esse link para a pessoa:_",
        "wa.me/5511976871674?text=oi",
        fmt.SEP,
    ])


async def _handle_chat(phone: str, meta: dict, message: str) -> str:
    """Handle general chat/conversation with AI context."""
    current_room = meta.get("current_room", "mudai.places.start")
    room_info = rooms.get_room_info(current_room)
    nickname = meta.get("nickname", "Aventureiro")

    # Get room-specific system prompt
    room_system_prompt = ""
    room_purpose = ""
    room_name = "Sala"
    if room_info:
        room_name = room_info["name"]
        room_purpose = room_info.get("purpose", "")
        room_meta = room_info.get("metadata", {})
        room_system_prompt = room_meta.get("system_prompt", "")

    # Build contextual prompt
    prompt = CHAT_PROMPT.format(
        room_name=room_name,
        room_purpose=room_purpose,
        player_name=nickname,
        player_level=_calculate_level(meta),
        player_seeds=meta.get("seeds", 0),
        room_system_prompt=f"INSTRUÇÕES EXTRAS DA SALA:\n{room_system_prompt}" if room_system_prompt else "",
        message=message,
    )

    try:
        narrative = await chat_completion(
            system_prompt=prompt,
            user_message=message,
            temperature=0.7,
            max_tokens=200,
        )
    except Exception as e:
        print(f"⚠️ Chat AI failed: {e}")
        narrative = "Hmm, não consegui processar isso agora. Tente de novo ou diga \"ajuda\"."

    # Award chat seed (max 1 per interaction)
    chat_count = meta.get("chat_count", 0) + 1
    seeds_change = SEEDS_REWARDS["chat"]
    new_seeds = meta.get("seeds", 0) + seeds_change
    _update_meta(phone, {"seeds": new_seeds, "chat_count": chat_count,
                         "total_seeds_earned": meta.get("total_seeds_earned", 0) + seeds_change})

    # Check social badge
    new_badge = None
    if chat_count >= 20:
        new_badge = _check_and_award_badge(phone, "social")

    return fmt.format_interaction(
        room_name=room_name,
        action_label="Conversando",
        seeds=new_seeds,
        seeds_change=seeds_change,
        level=_calculate_level(meta),
        narrative=narrative,
        badge=BADGES[new_badge]["emoji"] + " " + BADGES[new_badge]["name"] if new_badge else None,
        suggestions=_get_room_suggestions(room_info) if room_info else [
            {"cmd": "olhar", "desc": "ver onde está"},
        ],
        breadcrumb=room_name.replace("🌱 ", "") if room_info else "",
        profile_url=_generate_profile_url(phone),
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
        "sementes": {"action": "seeds", "target": ""},
    }

    if msg in fast_map:
        return fast_map[msg]

    # Check decorar prefix
    if msg.startswith("decorar"):
        return {"action": "decorate", "target": msg}

    # Check seeds-related keywords
    seeds_keywords = ["semente", "moeda", "ponto", "como ganho", "como consigo", "como ganhar"]
    if any(kw in msg for kw in seeds_keywords):
        return {"action": "seeds", "target": ""}

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
            temperature=0.7,
            max_tokens=80,
        )
    except Exception as e:
        print(f"⚠️ Narrative generation failed: {e}")
        return "Você olha ao redor, absorvendo o ambiente."


# ─── Seeds & Level Helpers ────────────────────────────

def _award_seeds(phone: str, amount: int):
    """Add seeds to player."""
    clean = _clean_phone(phone)
    player = db.get_artifact(f"mudai.users.{clean}")
    if not player:
        return
    meta = player.get("metadata_parsed", {})
    meta["seeds"] = meta.get("seeds", 0) + amount
    meta["total_seeds_earned"] = meta.get("total_seeds_earned", 0) + amount
    _update_meta(phone, meta)


def _calculate_level(meta: dict) -> int:
    """Calculate level from total actions."""
    total = meta.get("total_seeds_earned", 0)
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if total >= threshold:
            level = i + 1
    return min(level, len(LEVEL_THRESHOLDS))


def _check_and_award_badge(phone: str, badge_id: str) -> str | None:
    """Check if player earned a badge, award if new. Returns badge_id or None."""
    clean = _clean_phone(phone)
    player = db.get_artifact(f"mudai.users.{clean}")
    if not player:
        return None
    meta = player.get("metadata_parsed", {})
    badges = meta.get("badges", [])
    if badge_id in badges:
        return None  # Already has it
    badges.append(badge_id)
    _update_meta(phone, {"badges": badges})
    return badge_id


def _generate_profile_url(phone: str) -> str:
    """Generate a profile URL with hash token."""
    clean = _clean_phone(phone)
    token = hashlib.sha256(f"mudai-{clean}-2026".encode()).hexdigest()[:16]
    return f"https://mudai.servinder.com.br/p/{token}"


# ─── Helpers ──────────────────────────────────────────

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
