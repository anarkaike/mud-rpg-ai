"""
MUD-AI — Game Engine v2.1.

Central orchestrator: slash commands, seeds economy, contextual AI,
badges, and referral system.
"""

import hashlib
from . import database as db
from . import message_formatter as fmt
from . import room_manager as rooms
from . import world_state
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
- Resumo vivo da sala: {room_evolving_summary}
- Motivos recentes da sala: {room_motifs}
- Jogador: {player_name} (Nv.{player_level}, {player_seeds} sementes)
- Últimas respostas parecidas usadas com esse jogador: {recent_responses}

{room_system_prompt}

Mensagem do jogador: {message}

Responda de forma direta e útil."""


# ─── Seeds Economy Config ─────────────────────────────

SEEDS_REWARDS = {
    "visit_new_room": 2,
    "decorate": 1,
    "chat": 1,
    "challenge": 3,
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
            case "matches":
                return _handle_social_matches(phone, meta)
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
        case "/conexoes" | "/conexões" | "/matches":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_social_matches(phone, player.get("metadata_parsed", {}))
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
                "  /conexoes — ver conexões sugeridas\n"
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
    if not target_path:
        target_path = rooms.materialize_room_from_exit(current_room, target)

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

    room_dynamic = _build_room_dynamic_suffix(room_info)

    # Generate short narrative
    nickname = meta.get("nickname", "Aventureiro")
    narrative = await _generate_narrative(
        room_name=room_info["name"],
        player_name=nickname,
        action=f"chegou na sala",
    )
    if room_dynamic:
        narrative = f"{narrative} {room_dynamic}".strip()

    seeds = meta.get("seeds", 0) + seeds_change
    
    # Add to room log if seeds were earned
    if seeds_change > 0:
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M")
        log_entry = {
            "time": time_str,
            "text": f'<span class="log-accent">{nickname}</span> cultivou <span class="player-seeds">+{seeds_change} sementes</span>.',
            "type": "reward"
        }
        world_state._add_to_game_log(target_path, log_entry)

    response = fmt.format_room_view(
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
    return _attach_room_challenge(phone, meta, room_info, response, trigger="move")


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
    room_dynamic = _build_room_dynamic_suffix(room_info)
    if room_dynamic:
        narrative = f"{narrative} {room_dynamic}".strip()

    response = fmt.format_room_view(
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
    return _attach_room_challenge(phone, meta, room_info, response, trigger="look")


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
            {"cmd": "/conexoes", "desc": "ver pessoas compatíveis"},
            {"cmd": "/sementes", "desc": "ver como ganhar"},
        ],
        profile_url=_generate_profile_url(phone),
    )


def _handle_social_matches(phone: str, meta: dict) -> str:
    matches = rooms.find_social_matches(phone, limit=5)
    matches = rooms.persist_social_matches(phone, matches)
    return fmt.format_social_matches(matches, profile_url=_generate_profile_url(phone))


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
    block = world_state.record_room_block(
        room_path=current_room,
        author_name=nickname,
        author_phone=phone,
        content=fragment,
        block_type="decoration",
    )
    room_state = world_state.get_room_state(current_room)
    state_meta = room_state.get("metadata_parsed", {}) if room_state else {}
    if state_meta.get("image_refresh_needed"):
        world_state.ensure_room_image_stub(current_room, reason="new decoration")

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
        narrative=_build_decoration_feedback(fragment, room_info, block),
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
    active_challenge = meta.get("active_challenge")
    if active_challenge:
        resolution = _resolve_active_challenge(phone, meta, message, active_challenge)
        if resolution:
            return resolution

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
    recent_responses = world_state.recent_responses(f"player.{_clean_phone(phone)}", limit=4)

    # Build contextual prompt
    prompt = CHAT_PROMPT.format(
        room_name=room_name,
        room_purpose=room_purpose,
        room_evolving_summary=room_info.get("evolving_summary", "") if room_info else "",
        room_motifs=", ".join(room_info.get("motifs", [])[:4]) if room_info else "",
        player_name=nickname,
        player_level=_calculate_level(meta),
        player_seeds=meta.get("seeds", 0),
        recent_responses=" | ".join(recent_responses) if recent_responses else "nenhuma",
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

    narrative = _dedupe_narrative(narrative, phone, room_info)
    world_state.remember_response(f"player.{_clean_phone(phone)}", narrative)
    if room_info:
        world_state.remember_response(f"room.{room_info['path']}", narrative)

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
        "conexoes": {"action": "matches", "target": ""},
        "conexões": {"action": "matches", "target": ""},
        "matches": {"action": "matches", "target": ""},
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

    match_keywords = ["conex", "compat", "match", "quem pode me ajudar", "com quem posso falar"]
    if any(kw in msg for kw in match_keywords):
        return {"action": "matches", "target": ""}

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
    import os
    base_url = os.environ.get("MUDAI_BASE_URL", "https://mudai.servinder.com.br")
    clean = _clean_phone(phone)
    token = hashlib.sha256(f"mudai-{clean}-2026".encode()).hexdigest()[:16]
    return f"{base_url}/p/{token}"


def _attach_room_challenge(phone: str, meta: dict, room_info: dict | None, response: str, trigger: str) -> str:
    if not room_info:
        return response
    challenge = _ensure_active_challenge(phone, meta, room_info, trigger=trigger)
    if not challenge:
        return response
    challenge_text = fmt.format_challenge(
        challenge_type=challenge["type"],
        instruction=challenge["instruction"],
        reward_seeds=challenge["reward_seeds"],
    )
    title = challenge.get("title")
    if title:
        challenge_text = challenge_text.replace("💬 _Responda para completar_", f"🎯 *{title}*\n\n💬 _Responda para completar_", 1)
    return f"{response}\n\n{challenge_text}"


def _ensure_active_challenge(phone: str, meta: dict, room_info: dict, trigger: str) -> dict | None:
    current_room = room_info.get("path")
    active = meta.get("active_challenge")
    if active and active.get("status") == "active" and active.get("room_path") == current_room:
        return active
    if trigger == "move" and active and active.get("status") == "active":
        return None

    mission = world_state.get_player_room_mission(current_room, meta)
    challenge = _build_room_mission_challenge(mission) if mission else _build_room_challenge(room_info)
    if not challenge:
        return None
    _update_meta(phone, {
        "active_challenge": challenge,
        "last_challenge_room": current_room,
    })
    return challenge


def _build_room_challenge(room_info: dict) -> dict | None:
    room_path = room_info.get("path", "")
    room_name = room_info.get("name", "Sala")
    motifs = room_info.get("motifs", [])[:3]
    highlights = room_info.get("recent_contributions", [])[:2]
    purpose = room_info.get("purpose", "")
    tags = room_info.get("tags", [])
    challenge_type = "reflexão"
    instruction = "Deixe uma frase curta dizendo o que este lugar desperta em você."

    if any(tag in tags for tag in ["poesia", "escrita"]):
        challenge_type = "história"
        instruction = f"Escreva 1 frase que poderia ficar gravada em {room_name} sem quebrar o clima da sala."
    elif any(tag in tags for tag in ["troca", "conexão", "networking"]):
        challenge_type = "troca"
        instruction = f"Diga em 1 frase algo que você pode oferecer ou buscar aqui em {room_name}."
    elif motifs:
        challenge_type = "perspectiva"
        instruction = f"Escolha um dos temas desta sala ({', '.join(motifs)}) e responda com uma visão sua em 1 ou 2 frases."
    elif purpose:
        challenge_type = "reflexão"
        instruction = f"Em 1 frase, contribua com o propósito desta sala: {purpose}."
    elif highlights:
        excerpt = highlights[0].get("excerpt", "")
        if excerpt:
            challenge_type = "perspectiva"
            instruction = f"Responda ao eco recente da sala com 1 frase nova: \"{excerpt}\""

    challenge_id = hashlib.sha256(f"{room_path}:{instruction}".encode()).hexdigest()[:12]
    return {
        "id": challenge_id,
        "room_path": room_path,
        "room_name": room_name,
        "type": challenge_type,
        "instruction": instruction,
        "reward_seeds": SEEDS_REWARDS["challenge"],
        "status": "active",
        "source": "dynamic_challenge",
    }


def _build_room_mission_challenge(mission: dict | None) -> dict | None:
    if not mission:
        return None
    meta = mission.get("metadata_parsed", {})
    mission_id = meta.get("id")
    if not mission_id:
        return None
    mission_type = meta.get("mission_type", "missão")
    challenge_type_map = {
        "echo": "reflexão",
        "bridge": "perspectiva",
        "exchange": "troca",
    }
    return {
        "id": mission_id,
        "mission_id": mission_id,
        "room_path": meta.get("room_path", ""),
        "room_name": meta.get("room_name", "Sala"),
        "title": meta.get("title", "Missão"),
        "type": challenge_type_map.get(mission_type, "reflexão"),
        "instruction": meta.get("instruction", mission.get("content", "")),
        "reward_seeds": meta.get("reward_seeds", SEEDS_REWARDS["challenge"]),
        "status": "active",
        "source": "room_mission",
    }


def _resolve_active_challenge(phone: str, meta: dict, message: str, challenge: dict) -> str | None:
    text = message.strip()
    normalized = text.lower()
    if not text:
        return None
    if normalized in {"pular", "skip"}:
        _update_meta(phone, {"active_challenge": None})
        room_info = rooms.get_room_info(challenge.get("room_path", meta.get("current_room", "mudai.places.start")))
        return fmt.format_interaction(
            room_name=challenge.get("room_name", room_info["name"] if room_info else "Sala"),
            action_label="Desafio ignorado",
            seeds=meta.get("seeds", 0),
            seeds_change=0,
            level=_calculate_level(meta),
            narrative="Tudo bem. Você pode continuar explorando e pegar outro desafio mais tarde.",
            badge=None,
            suggestions=_get_room_suggestions(room_info) if room_info else [{"cmd": "olhar", "desc": "ver detalhes"}],
            breadcrumb=(challenge.get("room_name", "Sala")).replace("🌱 ", ""),
            profile_url=_generate_profile_url(phone),
        )
    if len(text) < 6:
        return fmt.format_challenge(
            challenge_type=challenge.get("type", "desafio"),
            instruction=f"Sua resposta ainda ficou curta. {challenge.get('instruction', '')}",
            reward_seeds=challenge.get("reward_seeds", SEEDS_REWARDS["challenge"]),
        )

    room_path = challenge.get("room_path", meta.get("current_room", "mudai.places.start"))
    room_info = rooms.get_room_info(room_path)
    block = world_state.record_room_block(
        room_path=room_path,
        author_name=meta.get("nickname", "Aventureiro"),
        author_phone=phone,
        content=text,
        block_type="mission_response" if challenge.get("mission_id") else "challenge_response",
    )
    seeds_change = challenge.get("reward_seeds", SEEDS_REWARDS["challenge"])
    new_total = meta.get("total_seeds_earned", 0) + seeds_change
    new_seeds = meta.get("seeds", 0) + seeds_change
    completed = int(meta.get("completed_challenges", 0)) + 1
    updates = {
        "seeds": new_seeds,
        "total_seeds_earned": new_total,
        "completed_challenges": completed,
        "active_challenge": None,
        "last_completed_challenge_id": challenge.get("id", ""),
    }
    if challenge.get("mission_id"):
        mission_progress = meta.get("mission_progress", {}) if isinstance(meta.get("mission_progress", {}), dict) else {}
        room_progress = mission_progress.get(room_path, {}) if isinstance(mission_progress.get(room_path, {}), dict) else {}
        room_progress[challenge["mission_id"]] = {
            "status": "completed",
            "completed_at_block": block.get("metadata_parsed", {}).get("id", ""),
            "reward_seeds": seeds_change,
        }
        mission_progress[room_path] = room_progress
        updates["mission_progress"] = mission_progress
        updates["completed_missions"] = int(meta.get("completed_missions", 0)) + 1
        world_state.complete_room_mission(room_path, challenge["mission_id"], phone, meta.get("nickname", "Aventureiro"))

    _update_meta(phone, updates)
    label = "missão" if challenge.get("mission_id") else f"desafio de {challenge.get('type', 'exploração')}"
    narrative = (
        f"Você concluiu a {label} e deixou um novo eco na sala. "
        f"Impacto narrativo: {block.get('metadata_parsed', {}).get('impact_score', 1)}."
    )
    return fmt.format_interaction(
        room_name=challenge.get("room_name", room_info["name"] if room_info else "Sala"),
        action_label="Missão concluída" if challenge.get("mission_id") else "Desafio concluído",
        seeds=new_seeds,
        seeds_change=seeds_change,
        level=_calculate_level({**meta, "total_seeds_earned": new_total}),
        narrative=narrative,
        badge=None,
        suggestions=_get_room_suggestions(room_info) if room_info else [{"cmd": "olhar", "desc": "ver detalhes"}],
        breadcrumb=(challenge.get("room_name", "Sala")).replace("🌱 ", ""),
        profile_url=_generate_profile_url(phone),
    )


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

    missions = room_info.get("missions", []) if room_info else []
    if missions:
        first_mission = missions[0]
        suggestions.append({"cmd": "responder missão", "desc": first_mission.get("title", "avançar missão")})

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

    recent = room_info.get("recent_contributions", []) if room_info else []
    if recent:
        first_type = recent[0].get("type", "fragmento")
        suggestions.append({"cmd": "decorar", "desc": f"responder ao {first_type} recente"})

    image = room_info.get("image") if room_info else None
    if image and image.get("status") == "pending_generation":
        suggestions.append({"cmd": "olhar", "desc": "ver a sala evoluindo"})

    suggestions.append({"cmd": "salas", "desc": "explorar mais"})
    return suggestions[:3]


def _build_room_dynamic_suffix(room_info: dict | None) -> str:
    if not room_info:
        return ""
    motifs = room_info.get("motifs", [])[:3]
    highlight = room_info.get("recent_contributions", [])[:1]
    parts = []
    if motifs:
        parts.append(f"O clima recente gira em torno de {', '.join(motifs)}.")
    if highlight:
        excerpt = highlight[0].get("excerpt", "")
        if excerpt:
            parts.append(f"Um eco recente ficou no ar: _{excerpt}_")
    image = room_info.get("image")
    if image and image.get("status") == "pending_generation":
        parts.append("A sala está juntando detalhes para ganhar uma nova imagem.")
    return " ".join(parts[:2])


def _build_decoration_feedback(fragment: str, room_info: dict | None, block: dict) -> str:
    motifs = room_info.get("motifs", [])[:3] if room_info else []
    impact = block.get("metadata_parsed", {}).get("impact_score", 1)
    base = f"Você deixou sua marca: _{fragment}_ ✨"
    if motifs:
        return f"{base} A sala agora puxa ainda mais para {', '.join(motifs)}. Impacto narrativo: {impact}."
    return f"{base} Isso já começou a alterar o clima do lugar. Impacto narrativo: {impact}."


def _dedupe_narrative(narrative: str, phone: str, room_info: dict | None) -> str:
    cleaned = " ".join(narrative.split())
    if not cleaned:
        return narrative
    recent = set(world_state.recent_responses(f"player.{_clean_phone(phone)}", limit=4))
    if room_info:
        recent.update(world_state.recent_responses(f"room.{room_info['path']}", limit=4))
    if cleaned in recent:
        if room_info and room_info.get("evolving_summary"):
            return f"Vou variar: {room_info['evolving_summary']}"
        return "Vou mudar o tom desta vez: tem algo novo se formando por aqui."
    return cleaned
