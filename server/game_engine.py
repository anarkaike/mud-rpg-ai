"""
MUD-AI — Game Engine v2.1.

Central orchestrator: slash commands, seeds economy, contextual AI,
badges, and referral system.
"""

import hashlib
import re
from . import database as db
from . import message_formatter as fmt
from .image_pipeline import enqueue_room_image_generation
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
- "matches" — jogador quer ver conexões sugeridas
- "social_mutual" — jogador quer ver conexões mútuas/recíprocas
- "social_confirmed" — jogador quer ver conexões confirmadas
- "confirm_social_match" — jogador quer confirmar uma conexão específica
- "social_useful" — jogador quer ver conexões úteis
- "mark_social_useful" — jogador quer marcar uma conexão como útil
- "social_favorites" — jogador quer ver conexões favoritas
- "favorite_social_match" — jogador quer favoritar uma conexão
- "social_history" — jogador quer ver memória/histórico de conexões
- "social_note" — jogador quer anotar uma nota privada em uma conexão
- "social_tags" — jogador quer salvar tags em uma conexão
- "help" — jogador pede ajuda
- "seeds" — jogador pergunta sobre sementes, moedas, pontos, como ganhar
- "referral" — jogador quer indicar/convidar alguém
- "reset" — jogador quer apagar o progresso e recomeçar
- "chat" — qualquer outra interação conversacional

REGRAS CRÍTICAS:
- Só classifique como "decorate" quando o jogador estiver DE FATO deixando uma marca, descrevendo algo para ser adicionado, ou dando uma instrução decorativa direta.
- Se a mensagem for pergunta, dúvida, pedido de opinião, pedido de permissão ou conversa sobre decorar, classifique como "chat".
- Exemplos que DEVEM ser "chat": "posso colocar uma árvore no meio da recepção?", "fica bom botar flores aqui?", "o que acha de decorar com velas?"

Responda APENAS com JSON:
{"action": "<tipo>", "target": "<alvo se houver>"}

Exemplos:
- "ir para norte" → {"action": "move", "target": "norte"}
- "quero ir pra praça das trocas" → {"action": "move", "target": "praça das trocas"}
- "olhar" → {"action": "look", "target": ""}
- "perfil" → {"action": "profile", "target": ""}
- "salas" → {"action": "explore", "target": ""}
- "quero decorar essa sala" → {"action": "decorate", "target": ""}
- "adicione uma árvore no meio da recepção" → {"action": "decorate", "target": "adicione uma árvore no meio da recepção"}
- "mostre minhas conexões" → {"action": "matches", "target": ""}
- "quero ver minhas conexões mútuas" → {"action": "social_mutual", "target": ""}
- "me mostra minhas conexões confirmadas" → {"action": "social_confirmed", "target": ""}
- "confirma minha conexão com Ana" → {"action": "confirm_social_match", "target": "Ana"}
- "marque Bruno como conexão útil" → {"action": "mark_social_useful", "target": "Bruno"}
- "me mostra minhas favoritas" → {"action": "social_favorites", "target": ""}
- "favorite Carlos" → {"action": "favorite_social_match", "target": "Carlos"}
- "quero ver meu histórico de conexões" → {"action": "social_history", "target": ""}
- "anote na conexão Ana :: founder de healthtech" → {"action": "social_note", "target": "Ana :: founder de healthtech"}
- "etiquete Bruno :: investidor, produto" → {"action": "social_tags", "target": "Bruno :: investidor, produto"}
- "ajuda" → {"action": "help", "target": ""}
- "como ganho sementes?" → {"action": "seeds", "target": ""}
- "o que são sementes?" → {"action": "seeds", "target": ""}
- "quantas sementes tenho?" → {"action": "seeds", "target": ""}
- "quero indicar +5511999999999" → {"action": "referral", "target": "+5511999999999"}
- "quero recomeçar do zero" → {"action": "reset", "target": ""}
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


CHALLENGE_GENERATOR_PROMPT = """Você cria desafios dinâmicos para uma sala viva de um RPG textual.

Objetivo:
- Gerar desafios curtos, diversos e acionáveis.
- NÃO repetir semanticamente desafios existentes.
- Considerar o clima da sala, respostas recentes, perfil do jogador e sinais sociais do momento.

Responda APENAS com JSON no formato:
{
  "challenges": [
    {
      "title": "...",
      "instruction": "...",
      "challenge_type": "reflexão|perspectiva|história|troca|decoração|apoio|insight",
      "novelty_key": "slug-curto-unico",
      "relevance_score": 0.0
    }
  ]
}

Regras:
- Cada instruction deve caber em 1 ou 2 frases curtas.
- Evite desafios genéricos demais.
- Evite repetir novelty_key ou ideia central fornecida no contexto.
- Gere entre 2 e 4 desafios quando possível.
"""


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
- Sinais principais do jogador: {player_top_signals}
- Resumo semântico do jogador: {player_profile_summary}
- Momento atual do jogador: {player_current_moment}
- Tons sugeridos para falar com esse jogador: {player_tone_hints}
- Instruções de estilo para este jogador: {player_style_notes}

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
    "relationship_milestone": 1,
    "relationship_confirmed": 2,
    "relationship_mutual": 3,
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
    "curador_social": {"emoji": "🏷", "name": "Curador Social", "desc": "Enriqueceu sua memória social com notas, tags e curadoria"},
    "aliado": {"emoji": "🪢", "name": "Aliado", "desc": "Confirmou vínculos sociais reais"},
    "elo_mutuo": {"emoji": "🫂", "name": "Elo Mútuo", "desc": "Alcançou uma conexão recíproca"},
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

    pending_response = await _handle_pending_action(phone, meta, message)
    if pending_response:
        return pending_response

    active_challenge = meta.get("active_challenge")
    if active_challenge:
        challenge_response = _resolve_active_challenge(phone, meta, message, active_challenge)
        if challenge_response:
            return challenge_response
    elif _is_challenge_rotation_request(msg.lower()):
        challenge_response = await _activate_room_challenge_from_idle(phone, meta, message)
        if challenge_response:
            return challenge_response

    # 3. Parse player intent
    action = await _parse_action(message, meta)
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
            case "reset":
                return _handle_reset(phone)
            case "social_mutual":
                return _handle_mutual_social_matches(phone, meta)
            case "social_confirmed":
                return _handle_confirmed_social_matches(phone, meta)
            case "confirm_social_match":
                return _handle_confirm_social_match(phone, meta, target)
            case "social_useful":
                return _handle_useful_social_matches(phone, meta)
            case "mark_social_useful":
                return _handle_mark_social_match_useful(phone, meta, target)
            case "social_favorites":
                return _handle_favorite_social_matches(phone, meta)
            case "favorite_social_match":
                return _handle_favorite_social_match(phone, meta, target)
            case "social_history":
                return _handle_social_match_history(phone, meta)
            case "social_note":
                return _handle_social_match_note(phone, meta, target)
            case "social_tags":
                return _handle_social_match_tags(phone, meta, target)
            case "matches":
                return _handle_social_matches(phone, meta)
            case "explore":
                return _handle_explore(phone, meta)
            case "decorate_question":
                return _handle_decor_question(phone, meta, target or message)
            case "confirm_contextual_publish":
                return _handle_contextual_publish_confirmation(phone, meta, action)
            case "decorate":
                return await _handle_decorate(phone, meta, target or message)
            case "help":
                return _handle_help()
            case "seeds":
                return _handle_seeds(phone, meta)
            case "referral":
                return _handle_referral(phone, target)
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
        case "/conexoes-mutuas" | "/conexões-mútuas" | "/mutuas-sociais" | "/mútuas-sociais":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_mutual_social_matches(phone, player.get("metadata_parsed", {}))
        case "/conexoes-confirmadas" | "/conexões-confirmadas" | "/confirmadas-sociais":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_confirmed_social_matches(phone, player.get("metadata_parsed", {}))
        case "/confirmar-conexao" | "/confirmar-conexão":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_confirm_social_match(phone, player.get("metadata_parsed", {}), args)
        case "/anotar-conexao" | "/anotar-conexão":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_social_match_note(phone, player.get("metadata_parsed", {}), args)
        case "/taguear-conexao" | "/taguear-conexão" | "/etiquetar-conexao" | "/etiquetar-conexão":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_social_match_tags(phone, player.get("metadata_parsed", {}), args)
        case "/conexoes-uteis" | "/conexões-úteis" | "/uteis-sociais" | "/úteis-sociais":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_useful_social_matches(phone, player.get("metadata_parsed", {}))
        case "/marcar-conexao-util" | "/marcar-conexão-útil":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_mark_social_match_useful(phone, player.get("metadata_parsed", {}), args)
        case "/conexoes-favoritas" | "/conexões-favoritas" | "/favoritas-sociais":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_favorite_social_matches(phone, player.get("metadata_parsed", {}))
        case "/favoritar-conexao" | "/favoritar-conexão":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_favorite_social_match(phone, player.get("metadata_parsed", {}), args)
        case "/historico-conexoes" | "/histórico-conexões" | "/memoria-social" | "/memória-social":
            clean = _clean_phone(phone)
            player = db.get_artifact(f"mudai.users.{clean}")
            if not player:
                return fmt.format_error("Você ainda não tem perfil. Envie 'oi' para começar!")
            return _handle_social_match_history(phone, player.get("metadata_parsed", {}))
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
                "  /conexoes-mutuas — ver vínculos recíprocos\n"
                "  /confirmar-conexao NOME — confirmar vínculo\n"
                "  /anotar-conexao NOME :: NOTA — salvar nota privada\n"
                "  /taguear-conexao NOME :: tag1,tag2 — salvar tags\n"
                "  /conexoes-confirmadas — ver confirmadas\n"
                "  /marcar-conexao-util NOME — salvar conexão útil\n"
                "  /conexoes-uteis — ver úteis\n"
                "  /favoritar-conexao NOME — salvar favorita\n"
                "  /conexoes-favoritas — ver favoritas\n"
                "  /historico-conexoes — ver memória social\n"
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


def _handle_contextual_publish_confirmation(phone: str, meta: dict, contextual: dict) -> str:
    room_info = _get_current_room_context(meta)
    intent_type = str(contextual.get("intent_type", "decorate") or "decorate")
    payload = str(contextual.get("payload", "") or "").strip()
    if not payload:
        return fmt.format_error("Não consegui extrair a essência dessa ação ainda. Tente reformular em uma frase curta.")
    _update_meta(phone, {"pending_action": {"type": "contextual_publish", "intent_type": intent_type, "payload": payload}})
    action_label, narrative, suggestions = _build_contextual_confirmation_prompt(intent_type, payload, room_info)
    return fmt.format_interaction(
        room_name=room_info.get("name", "Sala"),
        action_label=action_label,
        seeds=meta.get("seeds", 0),
        seeds_change=0,
        level=_calculate_level(meta),
        narrative=narrative,
        badge=None,
        suggestions=suggestions,
        breadcrumb=room_info.get("name", "Sala").replace("🌱 ", ""),
        profile_url=_generate_profile_url(phone),
    )


def _derive_player_tone_hints(meta: dict, profile_signals: dict) -> list[str]:
    normalized = profile_signals.get("normalized", {}) if profile_signals else {}
    hints = ["claro", "humano"]

    if float(normalized.get("technicality", 0.0) or 0.0) >= 0.6:
        hints.append("objetivo")
    if float(normalized.get("reflection", 0.0) or 0.0) >= 0.6:
        hints.append("reflexivo")
    if float(normalized.get("creativity", 0.0) or 0.0) >= 0.6:
        hints.append("criativo")
    if float(normalized.get("humanity", 0.0) or 0.0) >= 0.6 or float(normalized.get("support", 0.0) or 0.0) >= 0.6:
        hints.append("acolhedor")
    if float(normalized.get("intensity", 0.0) or 0.0) >= 0.6:
        hints.append("intenso-sem-exagero")
    if float(normalized.get("practicality", 0.0) or 0.0) >= 0.6:
        hints.append("prático")

    return list(dict.fromkeys(hints))[:5]


def _build_player_style_notes(meta: dict, profile_signals: dict) -> str:
    normalized = profile_signals.get("normalized", {}) if profile_signals else {}
    top = profile_signals.get("top", []) if profile_signals else []
    notes = ["Se adapte levemente ao jeito do jogador sem parecer forçado."]

    if top:
        notes.append(f"Priorize linguagem compatível com estes sinais: {', '.join(top[:4])}.")
    if float(normalized.get("technicality", 0.0) or 0.0) >= 0.6:
        notes.append("Prefira respostas mais estruturadas e concretas.")
    if float(normalized.get("reflection", 0.0) or 0.0) >= 0.6:
        notes.append("Pode trazer profundidade leve, mas sem ficar poética demais.")
    if float(normalized.get("creativity", 0.0) or 0.0) >= 0.6:
        notes.append("Use sensibilidade e imaginação com moderação.")
    if float(normalized.get("humanity", 0.0) or 0.0) >= 0.6 or float(normalized.get("support", 0.0) or 0.0) >= 0.6:
        notes.append("Valorize acolhimento, escuta e vínculo quando fizer sentido.")
    if float(normalized.get("practicality", 0.0) or 0.0) >= 0.6:
        notes.append("Quando a pessoa pedir direção, responda com clareza acionável.")
    if float(normalized.get("intensity", 0.0) or 0.0) >= 0.6:
        notes.append("Aceite intensidade, mas mantenha contenção e segurança no tom.")

    return " ".join(notes[:5])


def _build_structured_profile_context(meta: dict) -> dict:
    structured = meta.get("structured_profile", {}) if isinstance(meta.get("structured_profile", {}), dict) else {}
    summary = str(structured.get("summary", "")).strip() or "sem resumo semântico ainda"
    current_moment = structured.get("current_moment", [])
    communication_style = structured.get("communication_style", [])

    if not isinstance(current_moment, list):
        current_moment = []
    if not isinstance(communication_style, list):
        communication_style = []

    current_moment_text = ", ".join(str(item).strip() for item in current_moment[:3] if str(item).strip()) or "não identificado claramente"
    communication_style_text = ", ".join(str(item).strip() for item in communication_style[:3] if str(item).strip())

    return {
        "summary": summary[:220],
        "current_moment": current_moment_text[:220],
        "communication_style": communication_style_text[:180],
    }


async def _handle_look(phone: str, meta: dict) -> str:
    """Describe current room in detail."""
    current_room = meta.get("current_room", "mudai.places.start")
    room_info = rooms.get_room_info(current_room)

    if not room_info:
        return fmt.format_error("Você parece estar... em lugar nenhum. Diga \"salas\" para explorar.")

    nickname = meta.get("nickname", "Aventureiro")
    active_challenge = await _ensure_active_challenge(phone, meta, room_info, trigger="look")
    narrative = await _generate_narrative(
        room_name=room_info["name"],
        player_name=nickname,
        action="olha ao redor com atenção",
    )
    room_dynamic = _build_room_dynamic_suffix(room_info, active_challenge=active_challenge)
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
        suggestions=_get_room_suggestions(room_info, active_challenge=active_challenge),
        breadcrumb=room_info["name"].replace("🌱 ", "").replace("📝 ", ""),
        profile_url=_generate_profile_url(phone),
    )
    return await _attach_room_challenge(phone, meta, room_info, response, trigger="look", challenge=active_challenge)


def _handle_profile(phone: str, meta: dict) -> str:
    """Show player profile."""
    current_room = meta.get("current_room", "mudai.places.start")
    room_info = rooms.get_room_info(current_room)
    room_name = room_info["name"] if room_info else "Desconhecido"
    badges = meta.get("badges", [])
    badge_str = " ".join(BADGES[b]["emoji"] for b in badges if b in BADGES) if badges else "nenhum ainda"
    structured_profile = meta.get("structured_profile", {}) if isinstance(meta.get("structured_profile", {}), dict) else {}

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
        structured_summary=str(structured_profile.get("summary", "")).strip(),
        structured_worlds=structured_profile.get("worlds", []) if isinstance(structured_profile.get("worlds", []), list) else [],
        structured_strengths=structured_profile.get("strengths", []) if isinstance(structured_profile.get("strengths", []), list) else [],
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


def _handle_social_match_history(phone: str, meta: dict) -> str:
    history = rooms.list_social_match_history(phone, limit=8)
    return fmt.format_social_match_history(history, profile_url=_generate_profile_url(phone))


def _handle_mutual_social_matches(phone: str, meta: dict) -> str:
    mutual = rooms.list_mutual_social_matches(phone, limit=8)
    return fmt.format_mutual_social_matches(mutual, profile_url=_generate_profile_url(phone))


def _split_social_memory_payload(raw_args: str) -> tuple[str, str]:
    if "::" not in (raw_args or ""):
        return "", ""
    query, payload = raw_args.split("::", 1)
    return query.strip(), payload.strip()


def _handle_confirm_social_match(phone: str, meta: dict, target: str) -> str:
    if not (target or "").strip():
        return fmt.format_error("Use /confirmar-conexao NOME para marcar alguém da sua memória social como vínculo real.")
    saved = rooms.confirm_social_match(phone, target)
    if not saved:
        return fmt.format_error("Não encontrei essa conexão na sua memória social. Veja /historico-conexoes primeiro.")
    _apply_relationship_progress(phone, "confirm", saved)
    if saved.get("is_mutual") and str(saved.get("other_phone", "") or "").strip():
        _apply_relationship_progress(str(saved.get("other_phone", "")), "mutual", {
            "nickname": meta.get("nickname", "Viajante"),
            "other_phone": _clean_phone(phone),
            "is_mutual": True,
        })
    return fmt.format_social_confirmed_saved(saved, profile_url=_generate_profile_url(phone))


def _handle_social_match_note(phone: str, meta: dict, raw_args: str) -> str:
    target, note = _split_social_memory_payload(raw_args)
    if not target or not note:
        return fmt.format_error("Use /anotar-conexao NOME :: SUA NOTA para registrar uma nota privada.")
    saved = rooms.save_social_match_private_note(phone, target, note)
    if not saved:
        return fmt.format_error("Não encontrei essa conexão na sua memória social. Veja /historico-conexoes primeiro.")
    _apply_relationship_progress(phone, "note", saved)
    return fmt.format_social_note_saved(saved, profile_url=_generate_profile_url(phone))


def _handle_social_match_tags(phone: str, meta: dict, raw_args: str) -> str:
    target, tags = _split_social_memory_payload(raw_args)
    if not target or not tags:
        return fmt.format_error("Use /taguear-conexao NOME :: tag1, tag2 para atualizar tags manuais.")
    saved = rooms.save_social_match_tags(phone, target, tags)
    if not saved:
        return fmt.format_error("Não encontrei essa conexão na sua memória social. Veja /historico-conexoes primeiro.")
    _apply_relationship_progress(phone, "tags", saved)
    return fmt.format_social_tags_saved(saved, profile_url=_generate_profile_url(phone))


def _handle_confirmed_social_matches(phone: str, meta: dict) -> str:
    confirmed = rooms.list_confirmed_social_matches(phone, limit=8)
    return fmt.format_confirmed_social_matches(confirmed, profile_url=_generate_profile_url(phone))


def _handle_mark_social_match_useful(phone: str, meta: dict, target: str) -> str:
    if not (target or "").strip():
        return fmt.format_error("Use /marcar-conexao-util NOME para marcar alguém da sua memória social.")
    saved = rooms.mark_social_match_useful(phone, target)
    if not saved:
        return fmt.format_error("Não encontrei essa conexão na sua memória social. Veja /historico-conexoes primeiro.")
    _apply_relationship_progress(phone, "useful", saved)
    return fmt.format_social_useful_saved(saved, profile_url=_generate_profile_url(phone))


def _handle_useful_social_matches(phone: str, meta: dict) -> str:
    useful = rooms.list_useful_social_matches(phone, limit=8)
    return fmt.format_useful_social_matches(useful, profile_url=_generate_profile_url(phone))


def _handle_favorite_social_match(phone: str, meta: dict, target: str) -> str:
    if not (target or "").strip():
        return fmt.format_error("Use /favoritar-conexao NOME para marcar alguém da sua memória social.")
    saved = rooms.favorite_social_match(phone, target)
    if not saved:
        return fmt.format_error("Não encontrei essa conexão na sua memória social. Veja /historico-conexoes primeiro.")
    _apply_relationship_progress(phone, "favorite", saved)
    return fmt.format_social_favorite_saved(saved, profile_url=_generate_profile_url(phone))


def _handle_favorite_social_matches(phone: str, meta: dict) -> str:
    favorites = rooms.list_favorite_social_matches(phone, limit=8)
    return fmt.format_favorite_social_matches(favorites, profile_url=_generate_profile_url(phone))


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
    if _looks_like_decor_question(message):
        return await _handle_chat(phone, meta, message)

    seeds = meta.get("seeds", 0)
    if seeds < SEEDS_COSTS["decorate"]:
        return fmt.format_error(
            f"Você precisa de pelo menos 🪙 {SEEDS_COSTS['decorate']} semente para decorar.\n\n"
            "Diga _\"/sementes\"_ para ver como ganhar mais!"
        )

    current_room, needs_room_clarification = _resolve_decoration_room(meta, message)
    nickname = meta.get("nickname", "Alguém")

    fragment = _extract_decoration_fragment(message)

    if needs_room_clarification:
        _update_meta(phone, {"pending_action": {"type": "decorate", "fragment": fragment}})
        room_info = rooms.get_room_info(meta.get("current_room", "mudai.places.start"))
        return fmt.format_interaction(
            room_name=room_info["name"] if room_info else "Sala",
            action_label="Decorar",
            seeds=seeds,
            seeds_change=0,
            level=_calculate_level(meta),
            narrative=f"Entendi o que você quer adicionar: _{fragment or 'esse elemento'}_. Em qual sala você quer colocar isso? Pode dizer, por exemplo, _na recepção_ ou _na sala atual_.",
            badge=None,
            suggestions=[
                {"cmd": "na recepção", "desc": "colocar lá"},
                {"cmd": "na sala atual", "desc": "usar a sala onde você está"},
            ],
            profile_url=_generate_profile_url(phone),
        )

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
    _update_meta(phone, {"pending_action": None})
    room_state = world_state.get_room_state(current_room)
    state_meta = room_state.get("metadata_parsed", {}) if room_state else {}
    if state_meta.get("image_refresh_needed"):
        await enqueue_room_image_generation(current_room, reason="new decoration")

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


def _looks_like_decor_question(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    question_signals = [
        "?",
        "posso ",
        "poderia ",
        "da para ",
        "dá para ",
        "sera que",
        "será que",
        "fica bom",
        "o que acha",
        "acha que",
        "tem como",
    ]
    decor_signals = [
        "arvore", "árvore", "flor", "flores", "planta", "jardim", "vela", "velas",
        "quadro", "mural", "sofá", "sofa", "mesa", "recepção", "recepcao", "decor",
        "colocar", "botar", "por ", "adicionar", "adiciona", "adicione", "adicao", "adição",
        "sala", "lugar", "aqui", "nesse lugar", "nesta sala", "arco iris", "arco-iris", "arco íris",
    ]
    room_change_signals = ["adicionar", "adiciona", "adicione", "colocar", "botar", "por ", "decor", "mudar", "deixar"]
    if any(signal in text for signal in question_signals) and any(signal in text for signal in decor_signals):
        return True
    return any(signal in text for signal in question_signals) and any(signal in text for signal in room_change_signals) and any(signal in text for signal in ["sala", "lugar", "aqui", "nesse lugar", "nesta sala"])


def _contains_any(text: str, options: list[str]) -> bool:
    return any(option in text for option in options)


def _normalize_phrase(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-ZÀ-ÿ0-9\s]", " ", text or "")
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _extract_phone_candidate(text: str) -> str:
    match = re.search(r"\+?\d[\d\s().-]{8,}\d", text or "")
    if not match:
        return ""
    candidate = re.sub(r"[^\d+]", "", match.group(0))
    return candidate if len(re.sub(r"\D", "", candidate)) >= 10 else ""


def _extract_target_after_phrase(message: str, phrases: list[str]) -> str:
    lowered = (message or "").lower()
    for phrase in phrases:
        index = lowered.find(phrase)
        if index >= 0:
            extracted = message[index + len(phrase):].strip(" :-\n\t")
            if extracted:
                return extracted
    return ""


def _looks_like_direct_decoration_intent(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text or _looks_like_decor_question(message):
        return False
    imperative_starts = (
        "decorar", "decorar:", "adicione", "adiciona", "adicionar", "coloque", "coloca",
        "botar", "bota", "ponha", "põe", "por ", "crie ", "criar ", "quero adicionar",
        "quero colocar", "quero botar", "quero pôr", "quero por"
    )
    decor_terms = (
        "árvore", "arvore", "flor", "flores", "planta", "jardim", "vela", "velas", "quadro",
        "mural", "mesa", "sofá", "sofa", "objeto", "decoração", "decoracao", "estatuta", "estátua"
    )
    return text.startswith(imperative_starts) or (_contains_any(text, list(decor_terms)) and _contains_any(text, ["adicion", "coloc", "bot", "decor", "ponh", "por "]))


def _get_current_room_context(meta: dict) -> dict:
    current_room = meta.get("current_room", "mudai.places.start") if isinstance(meta, dict) else "mudai.places.start"
    room_info = rooms.get_room_info(current_room)
    return room_info or {"path": current_room, "tags": [], "purpose": "", "name": "Sala"}


def _looks_like_question(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    if "?" in text:
        return True
    question_starts = (
        "posso", "pode", "dá pra", "da pra", "será que", "sera que", "fica bom", "ficaria bom",
        "o que acha", "acha que", "tem como", "consigo", "devo"
    )
    return text.startswith(question_starts)


def _clean_implicit_contribution_text(message: str) -> str:
    fragment = (message or "").strip()
    cleanup_prefixes = [
        "quero postar ", "vou postar ", "posta ", "publique ", "publica ",
        "quero deixar ", "vou deixar ", "deixa ", "quero escrever ", "vou escrever ",
        "escreve ", "escrever ", "quero compartilhar ", "vou compartilhar ", "compartilhar ",
    ]
    lowered = fragment.lower()
    for prefix in cleanup_prefixes:
        if lowered.startswith(prefix):
            fragment = fragment[len(prefix):].strip()
            lowered = fragment.lower()
            break
    return fragment.strip(" \n\t")


def _infer_room_primary_action(room_info: dict | None) -> str:
    tags = [str(tag or "").lower() for tag in (room_info or {}).get("tags", [])]
    purpose = str((room_info or {}).get("purpose", "") or "").lower()
    if any(tag in tags for tag in ["poesia", "escrita", "poema", "literatura"]) or any(term in purpose for term in ["poesia", "escrita", "verso", "poema"]):
        return "publish"
    if any(tag in tags for tag in ["arte", "galeria", "exposição", "exposicao", "criatividade", "visual"]) or any(term in purpose for term in ["arte", "galeria", "expos", "criação", "criacao", "visual"]):
        return "showcase_creation"
    if any(tag in tags for tag in ["psicodelia", "psicodélica", "psicodelico", "psicodélico", "experiência", "experiencia"]) or any(term in purpose for term in ["psicodel", "experiência", "experiencia", "visão", "visao"]):
        return "share_experience"
    if any(tag in tags for tag in ["meditação", "meditacao", "reflexão", "reflexao", "silêncio", "silencio", "contemplação", "contemplacao"]) or any(term in purpose for term in ["medita", "reflex", "silêncio", "silencio", "contempla"]):
        return "share_reflection"
    if any(tag in tags for tag in ["apoio", "acolhimento", "cuidado", "escuta", "terapia"]) or any(term in purpose for term in ["apoio", "acolh", "cuidado", "escuta", "amparo"]):
        return "share_support"
    if any(tag in tags for tag in ["troca", "conexão", "conexao", "networking"] ) or any(term in purpose for term in ["troca", "networking", "conex"]):
        return "register_exchange"
    if any(tag in tags for tag in ["laboratório", "laboratorio", "oficina", "aprendizado", "estudo", "pesquisa", "experimento"]) or any(term in purpose for term in ["laborat", "oficina", "aprend", "estudo", "pesquisa", "experimento"]):
        return "share_insight"
    return "decorate"


def _analyze_contextual_message_intent(message: str, room_info: dict | None) -> dict | None:
    text = (message or "").strip()
    normalized = _normalize_phrase(text)
    if not normalized or _looks_like_question(message):
        return None
    if normalized in {"olhar", "perfil", "salas", "explorar", "ajuda", "help", "sementes"}:
        return None
    if _infer_conversational_action(message, room_info=room_info):
        return None

    tags = [str(tag or "").lower() for tag in (room_info or {}).get("tags", [])]
    purpose = str((room_info or {}).get("purpose", "") or "").lower()
    line_count = len([line for line in text.splitlines() if line.strip()])
    word_count = len(normalized.split())
    primary_action = _infer_room_primary_action(room_info)

    poetic_room = any(tag in tags for tag in ["poesia", "escrita", "poema", "literatura"]) or any(term in purpose for term in ["poesia", "escrita", "verso", "poema"])
    exchange_room = any(tag in tags for tag in ["troca", "conexão", "conexao", "networking"]) or any(term in purpose for term in ["troca", "conex", "networking"])
    psychedelic_room = any(tag in tags for tag in ["psicodelia", "psicodélica", "psicodelico", "psicodélico", "experiência", "experiencia"]) or any(term in purpose for term in ["psicodel", "experiência", "experiencia", "visão", "visao"])
    art_room = any(tag in tags for tag in ["arte", "galeria", "exposição", "exposicao", "criatividade", "visual"]) or any(term in purpose for term in ["arte", "galeria", "expos", "criação", "criacao", "visual"])
    reflection_room = any(tag in tags for tag in ["meditação", "meditacao", "reflexão", "reflexao", "silêncio", "silencio", "contemplação", "contemplacao"]) or any(term in purpose for term in ["medita", "reflex", "silêncio", "silencio", "contempla"])
    support_room = any(tag in tags for tag in ["apoio", "acolhimento", "cuidado", "escuta", "terapia"]) or any(term in purpose for term in ["apoio", "acolh", "cuidado", "escuta", "amparo"])
    learning_room = any(tag in tags for tag in ["laboratório", "laboratorio", "oficina", "aprendizado", "estudo", "pesquisa", "experimento"]) or any(term in purpose for term in ["laborat", "oficina", "aprend", "estudo", "pesquisa", "experimento"])

    if poetic_room and (line_count >= 2 or word_count >= 6):
        return {
            "action": "confirm_contextual_publish",
            "intent_type": "publish",
            "payload": _clean_implicit_contribution_text(message),
            "label": "publicar este poema",
        }
    if exchange_room and _contains_any(normalized, ["ofereço", "ofereco", "busco", "procuro", "troco", "posso ajudar", "preciso de", "quero encontrar"]):
        return {
            "action": "confirm_contextual_publish",
            "intent_type": "register_exchange",
            "payload": _clean_implicit_contribution_text(message),
            "label": "registrar essa troca",
        }
    if psychedelic_room and (line_count >= 2 or word_count >= 8 or _contains_any(normalized, ["vi", "senti", "percebi", "experiencia", "experiência", "visão", "visao", "sensação", "sensacao"])):
        return {
            "action": "confirm_contextual_publish",
            "intent_type": "share_experience",
            "payload": _clean_implicit_contribution_text(message),
            "label": "compartilhar essa experiência",
        }
    if art_room and (line_count >= 2 or word_count >= 6 or _contains_any(normalized, ["criei", "pintei", "desenhei", "colagem", "instalação", "instalacao", "obra", "composição", "composicao"])):
        return {
            "action": "confirm_contextual_publish",
            "intent_type": "showcase_creation",
            "payload": _clean_implicit_contribution_text(message),
            "label": "expor essa criação",
        }
    if reflection_room and (line_count >= 2 or word_count >= 6 or _contains_any(normalized, ["refleti", "percebi", "aprendi", "silêncio", "silencio", "presença", "presenca", "contemplei"])):
        return {
            "action": "confirm_contextual_publish",
            "intent_type": "share_reflection",
            "payload": _clean_implicit_contribution_text(message),
            "label": "registrar essa reflexão",
        }
    if support_room and (line_count >= 2 or word_count >= 6 or _contains_any(normalized, ["estou", "preciso", "quero apoio", "me sinto", "desabafo", "cuidar", "acolher", "escuta"])):
        return {
            "action": "confirm_contextual_publish",
            "intent_type": "share_support",
            "payload": _clean_implicit_contribution_text(message),
            "label": "compartilhar isso como cuidado ou desabafo",
        }
    if learning_room and (line_count >= 2 or word_count >= 6 or _contains_any(normalized, ["aprendi", "testei", "experimentei", "descobri", "insight", "hipótese", "hipotese", "método", "metodo"])):
        return {
            "action": "confirm_contextual_publish",
            "intent_type": "share_insight",
            "payload": _clean_implicit_contribution_text(message),
            "label": "compartilhar esse insight",
        }
    if primary_action == "decorate" and (_contains_any(normalized, ["arvore", "árvore", "flor", "vela", "quadro", "mural", "cor", "cores", "luz", "brilho"]) or _looks_like_direct_decoration_intent(message)):
        return {
            "action": "confirm_contextual_publish",
            "intent_type": "decorate",
            "payload": _extract_decoration_fragment(message) or _clean_implicit_contribution_text(message),
            "label": "adicionar esse elemento",
        }
    return None


def _build_contextual_confirmation_prompt(intent_type: str, payload: str, room_info: dict | None) -> tuple[str, str, list[dict]]:
    room_name = (room_info or {}).get("name", "Sala")
    clean_payload = (payload or "").strip() or "essa contribuição"
    if intent_type == "publish":
        narrative = f"Identifiquei um poema ou texto autoral com cara de publicação em *{room_name}*. Deseja publicar este poema?\n\n_{clean_payload}_"
        return "Publicar", narrative, [{"cmd": "sim", "desc": "publicar agora"}, {"cmd": "ajusta o final", "desc": "refinar antes"}]
    if intent_type == "share_experience":
        narrative = f"Essa mensagem parece um relato ou experiência que combina com *{room_name}*. Deseja compartilhar essa experiência nesta sala?\n\n_{clean_payload}_"
        return "Compartilhar experiência", narrative, [{"cmd": "sim", "desc": "compartilhar agora"}, {"cmd": "resuma mais", "desc": "refinar antes"}]
    if intent_type == "showcase_creation":
        narrative = f"Isso parece uma criação ou proposta artística alinhada com *{room_name}*. Deseja expor essa criação aqui?\n\n_{clean_payload}_"
        return "Expor criação", narrative, [{"cmd": "sim", "desc": "expor agora"}, {"cmd": "deixa mais visual", "desc": "refinar antes"}]
    if intent_type == "share_reflection":
        narrative = f"Essa mensagem soa como uma reflexão que combina com *{room_name}*. Deseja registrar essa reflexão nesta sala?\n\n_{clean_payload}_"
        return "Registrar reflexão", narrative, [{"cmd": "sim", "desc": "registrar agora"}, {"cmd": "resuma melhor", "desc": "refinar antes"}]
    if intent_type == "share_support":
        narrative = f"Isso parece um desabafo, cuidado ou gesto de apoio coerente com *{room_name}*. Deseja compartilhar isso aqui?\n\n_{clean_payload}_"
        return "Compartilhar apoio", narrative, [{"cmd": "sim", "desc": "compartilhar agora"}, {"cmd": "deixa mais delicado", "desc": "refinar antes"}]
    if intent_type == "register_exchange":
        narrative = f"Isso parece uma oferta, pedido ou ponte útil para *{room_name}*. Deseja registrar essa troca aqui?\n\n_{clean_payload}_"
        return "Registrar troca", narrative, [{"cmd": "sim", "desc": "registrar agora"}, {"cmd": "deixa mais claro", "desc": "refinar antes"}]
    if intent_type == "share_insight":
        narrative = f"Essa mensagem parece um insight, experimento ou descoberta útil para *{room_name}*. Deseja compartilhar esse insight aqui?\n\n_{clean_payload}_"
        return "Compartilhar insight", narrative, [{"cmd": "sim", "desc": "compartilhar agora"}, {"cmd": "organiza melhor", "desc": "refinar antes"}]
    narrative = f"Entendi isso como uma ação de modificação em *{room_name}*. Deseja adicionar esse elemento à sala?\n\n_{clean_payload}_"
    return "Adicionar elemento", narrative, [{"cmd": "sim", "desc": "adicionar agora"}, {"cmd": "com mais detalhe", "desc": "refinar antes"}]


def _infer_contextual_conversational_action(message: str, meta: dict) -> dict | None:
    room_info = _get_current_room_context(meta)
    if _looks_like_decor_question(message):
        fragment = _extract_decoration_fragment(message)
        return {"action": "decorate_question", "target": fragment or message.strip()}
    contextual = _analyze_contextual_message_intent(message, room_info)
    if contextual:
        return contextual
    return None


def _infer_conversational_action(message: str, room_info: dict | None = None) -> dict | None:
    text = _normalize_phrase(message)
    if not text:
        return None

    if _contains_any(text, ["recomecar do zero", "recomecar do zero", "resetar meu perfil", "apagar meu progresso", "zerar meu progresso"]):
        return {"action": "reset", "target": ""}
    if _looks_like_direct_decoration_intent(message):
        return {"action": "decorate", "target": message.strip()}
    if _contains_any(text, ["me ajuda", "preciso de ajuda", "como funciona", "quais comandos", "o que posso fazer", "o que da pra fazer", "o que dá pra fazer"]):
        return {"action": "help", "target": ""}
    if _contains_any(text, ["meu perfil", "mostrar perfil", "mostra meu perfil", "quem sou eu", "meu personagem"]):
        return {"action": "profile", "target": ""}
    if _contains_any(text, ["quais salas", "mostrar salas", "mostra as salas", "para onde posso ir", "onde posso ir", "explorar salas", "lista de salas"]):
        return {"action": "explore", "target": ""}
    if _contains_any(text, ["quantas sementes", "meu saldo", "saldo de sementes", "como ganho sementes", "como ganhar sementes", "o que sao sementes", "o que são sementes"]):
        return {"action": "seeds", "target": ""}
    if _contains_any(text, ["conexoes mutuas", "conexões mútuas", "conexoes reciprocas", "conexões recíprocas", "conexoes reciprocas"]):
        return {"action": "social_mutual", "target": ""}
    if _contains_any(text, ["conexoes confirmadas", "conexões confirmadas", "vinculos confirmados", "vínculos confirmados"]):
        return {"action": "social_confirmed", "target": ""}
    if _contains_any(text, ["conexoes uteis", "conexões úteis", "conexoes úteis", "pessoas uteis", "pessoas úteis"]):
        return {"action": "social_useful", "target": ""}
    if _contains_any(text, ["conexoes favoritas", "conexões favoritas", "favoritas", "favoritos de conexao", "favoritos de conexão"]):
        return {"action": "social_favorites", "target": ""}
    if _contains_any(text, ["historico de conex", "histórico de conex", "memoria social", "memória social"]):
        return {"action": "social_history", "target": ""}
    if _contains_any(text, ["minhas conexoes", "minhas conexões", "quem combina comigo", "pessoas compativeis", "pessoas compatíveis", "com quem posso falar"]):
        return {"action": "matches", "target": ""}

    confirm_target = _extract_target_after_phrase(message, ["confirmar conexão com ", "confirma minha conexão com ", "confirma conexão com "])
    if confirm_target:
        return {"action": "confirm_social_match", "target": confirm_target}

    useful_target = _extract_target_after_phrase(message, ["marque ", "marca "])
    if useful_target and _contains_any(text, ["como util", "como útil", "conexao util", "conexão útil"]):
        cleaned = re.sub(r"\s+como\s+conex[aã]o\s+[uú]til.*$", "", useful_target, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+como\s+[uú]til.*$", "", cleaned, flags=re.IGNORECASE).strip()
        return {"action": "mark_social_useful", "target": cleaned}

    favorite_target = _extract_target_after_phrase(message, ["favorite ", "favoritar ", "favorita "])
    if favorite_target:
        return {"action": "favorite_social_match", "target": favorite_target}

    note_target = _extract_target_after_phrase(message, ["anote na conexão ", "anota na conexão ", "anotar conexão ", "salve uma nota para "])
    if note_target and "::" in note_target:
        return {"action": "social_note", "target": note_target}

    tag_target = _extract_target_after_phrase(message, ["etiquete ", "tagueie ", "taguear "])
    if tag_target and "::" in tag_target:
        return {"action": "social_tags", "target": tag_target}

    phone_candidate = _extract_phone_candidate(message)
    if phone_candidate and _contains_any(text, ["indicar", "indique", "convidar", "convide", "chamar para", "trazer para"]):
        return {"action": "referral", "target": phone_candidate}

    return None


def _resolve_decoration_room(meta: dict, message: str) -> tuple[str | None, bool]:
    current_room = meta.get("current_room", "mudai.places.start")
    text = _normalize_phrase(message)
    if _contains_any(text, ["nessa sala", "nesta sala", "na sala", "sala atual", "aqui", "neste lugar", "nesse lugar"]):
        return current_room, False

    all_rooms = db.list_by_prefix("mudai.places.", direct_children_only=True)
    for room in all_rooms:
        room_name = rooms._extract_room_name(room.get("content", ""))
        normalized_room_name = _normalize_phrase(room_name)
        if normalized_room_name and normalized_room_name in text:
            return room["path"], False

    if _looks_like_direct_decoration_intent(message) and not (message or "").strip().lower().startswith("decorar"):
        return None, True
    return current_room, False


def _extract_decoration_fragment(message: str) -> str:
    fragment = (message or "").strip()
    lowered = fragment.lower()
    prefixes = [
        "decorar ",
        "decorar:",
        "decoração ",
        "quero decorar ",
        "vou decorar ",
        "adicionar ",
        "adicione ",
        "adiciona ",
        "colocar ",
        "coloque ",
        "coloca ",
        "botar ",
        "bota ",
        "ponha ",
        "põe ",
        "por ",
        "quero adicionar ",
        "quero colocar ",
        "quero botar ",
        "posso adicionar ",
        "posso colocar ",
        "posso botar ",
        "pode adicionar ",
        "pode colocar ",
        "pode botar ",
        "dá para adicionar ",
        "da para adicionar ",
        "dá pra adicionar ",
        "da pra adicionar ",
        "dá para colocar ",
        "da para colocar ",
        "dá pra colocar ",
        "da pra colocar ",
    ]
    for prefix in prefixes:
        if lowered.startswith(prefix):
            fragment = fragment[len(prefix):].strip()
            lowered = fragment.lower()
            break

    question_prefixes = [
        "será que dá para ", "sera que da para ", "será que dá pra ", "sera que da pra ",
        "tem como adicionar ", "tem como colocar ", "fica bom colocar ", "ficaria bom colocar ",
        "o que acha de colocar ", "acha que dá para colocar ",
    ]
    for prefix in question_prefixes:
        if lowered.startswith(prefix):
            fragment = fragment[len(prefix):].strip()
            lowered = fragment.lower()
            break

    cleanup_prefixes = [
        "uma ", "um ", "umas ", "uns ", "a ", "o ",
    ]
    if any(lowered.startswith(prefix) for prefix in ["colocar ", "botar ", "por "]):
        for prefix in cleanup_prefixes:
            if lowered.startswith(prefix):
                fragment = fragment[len(prefix):].strip()
                lowered = fragment.lower()
                break

    location_markers = [
        " no meio da ", " no meio do ", " no centro da ", " no centro do ",
        " na ", " no ", " em ", " aqui",
    ]
    normalized_fragment = _normalize_phrase(fragment)
    all_rooms = db.list_by_prefix("mudai.places.", direct_children_only=True)
    known_room_names = [_normalize_phrase(rooms._extract_room_name(room.get("content", ""))) for room in all_rooms]
    for marker in location_markers:
        index = lowered.rfind(marker)
        if index <= 0:
            continue
        tail = _normalize_phrase(fragment[index + len(marker):])
        if tail in {"sala", "sala atual", "recepcao", "recepção", "aqui", "lugar"} or tail in known_room_names:
            fragment = fragment[:index].strip()
            lowered = fragment.lower()
            normalized_fragment = _normalize_phrase(fragment)
            break

    if normalized_fragment.startswith(("uma ", "um ", "umas ", "uns ")):
        fragment = fragment.split(" ", 1)[1].strip() if " " in fragment else fragment

    fragment = fragment.strip(" .!?\n\t")
    return fragment


async def _handle_pending_action(phone: str, meta: dict, message: str) -> str | None:
    pending = meta.get("pending_action")
    if not isinstance(pending, dict):
        return None

    pending_type = pending.get("type")
    text = (message or "").strip()
    if not text:
        return None

    if text.lower() in {"cancelar", "cancela", "deixa", "deixa pra la", "deixa pra lá"}:
        _update_meta(phone, {"pending_action": None})
        room_info = rooms.get_room_info(meta.get("current_room", "mudai.places.start"))
        return fmt.format_interaction(
            room_name=room_info["name"] if room_info else "Sala",
            action_label="Ação cancelada",
            seeds=meta.get("seeds", 0),
            seeds_change=0,
            level=_calculate_level(meta),
            narrative="Tudo bem. Cancelei essa ação pendente.",
            badge=None,
            suggestions=_get_room_suggestions(room_info) if room_info else [{"cmd": "olhar", "desc": "ver detalhes"}],
            profile_url=_generate_profile_url(phone),
        )

    if pending_type == "decorate_idea":
        normalized = _normalize_phrase(text)
        if normalized in {"sim", "s", "pode", "pode sim", "manda", "pode adicionar", "pode postar", "ok", "isso", "faz isso"}:
            fragment = str(pending.get("fragment", "") or "").strip()
            if not fragment:
                _update_meta(phone, {"pending_action": None})
                return None
            return await _handle_decorate(phone, {**meta, "pending_action": None}, f"decorar {fragment}")
        fragment = str(pending.get("fragment", "") or "").strip()
        if fragment:
            return await _handle_decorate(phone, {**meta, "pending_action": None}, f"decorar {fragment} {text}".strip())
        _update_meta(phone, {"pending_action": None})
        return None

    if pending_type == "contextual_publish":
        normalized = _normalize_phrase(text)
        payload = str(pending.get("payload", "") or "").strip()
        intent_type = str(pending.get("intent_type", "decorate") or "decorate").strip()
        if normalized in {"sim", "s", "pode", "pode sim", "manda", "ok", "isso", "faz isso", "publica", "publique"}:
            if not payload:
                _update_meta(phone, {"pending_action": None})
                return None
            return await _handle_decorate(phone, {**meta, "pending_action": None}, f"decorar {payload}")
        if payload:
            refined_payload = f"{payload} {text}".strip()
            _update_meta(phone, {"pending_action": {"type": "contextual_publish", "intent_type": intent_type, "payload": refined_payload}})
            room_info = _get_current_room_context(meta)
            action_label, narrative, suggestions = _build_contextual_confirmation_prompt(intent_type, refined_payload, room_info)
            return fmt.format_interaction(
                room_name=room_info.get("name", "Sala"),
                action_label=action_label,
                seeds=meta.get("seeds", 0),
                seeds_change=0,
                level=_calculate_level(meta),
                narrative=narrative,
                badge=None,
                suggestions=suggestions,
                breadcrumb=room_info.get("name", "Sala").replace("🌱 ", ""),
                profile_url=_generate_profile_url(phone),
            )
        _update_meta(phone, {"pending_action": None})
        return None

    if pending_type == "decorate":
        fragment = str(pending.get("fragment", "") or "").strip()
        if not fragment:
            _update_meta(phone, {"pending_action": None})
            return None
        combined_message = f"decorar {fragment} {text}".strip()
        return await _handle_decorate(phone, {**meta, "pending_action": None}, combined_message)

    return None


def _handle_decor_question(phone: str, meta: dict, raw_fragment: str) -> str:
    room_info = _get_current_room_context(meta)
    fragment = _extract_decoration_fragment(raw_fragment)
    fragment = fragment or _clean_implicit_contribution_text(raw_fragment)
    _update_meta(phone, {"pending_action": {"type": "decorate_idea", "fragment": fragment}})
    room_name = room_info.get("name", "Sala")
    seeds = meta.get("seeds", 0)
    narrative = (
        f"Pode sim. Em *{room_name}*, isso pode virar uma contribuição persistida. "
        f"Entendi a essência como: _{fragment or 'uma nova marca visual'}_. Se quiser, responda _sim_ para eu postar, ou detalhe melhor como você quer que isso apareça."
    )
    return fmt.format_interaction(
        room_name=room_name,
        action_label="Ideia de contribuição",
        seeds=seeds,
        seeds_change=0,
        level=_calculate_level(meta),
        narrative=narrative,
        badge=None,
        suggestions=[
            {"cmd": "sim", "desc": "postar essa ideia"},
            {"cmd": "com mais brilho e cor", "desc": "refinar a ideia"},
        ],
        breadcrumb=room_name.replace("🌱 ", ""),
        profile_url=_generate_profile_url(phone),
    )


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
    recent_responses = world_state.recent_responses(f"player.{_clean_phone(phone)}", limit=4)
    player_profile_signals = meta.get("profile_signals", {})
    player_structured_profile = _build_structured_profile_context(meta)
    player_top_signals = ", ".join(player_profile_signals.get("top", [])[:4]) or "nenhum forte ainda"
    player_tone_hints = ", ".join(_derive_player_tone_hints(meta, player_profile_signals))
    player_style_notes = _build_player_style_notes(meta, player_profile_signals)
    if player_structured_profile.get("communication_style"):
        player_style_notes = f"{player_style_notes} Considere também: {player_structured_profile['communication_style']}."

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
        player_top_signals=player_top_signals,
        player_profile_summary=player_structured_profile.get("summary", "sem resumo semântico ainda"),
        player_current_moment=player_structured_profile.get("current_moment", "não identificado claramente"),
        player_tone_hints=player_tone_hints,
        player_style_notes=player_style_notes,
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

async def _parse_action(message: str, meta: dict | None = None) -> dict:
    """Use AI to determine the player's intent."""
    msg = message.strip().lower()

    contextual = _infer_contextual_conversational_action(message, meta or {})
    if contextual:
        return contextual

    inferred = _infer_conversational_action(message, room_info=_get_current_room_context(meta or {}))
    if inferred:
        return inferred

    # Fast-path common commands (no AI needed)
    fast_map = {
        "olhar": {"action": "look", "target": ""},
        "look": {"action": "look", "target": ""},
        "perfil": {"action": "profile", "target": ""},
        "eu": {"action": "profile", "target": ""},
        "conexoes mutuas": {"action": "social_mutual", "target": ""},
        "conexões mútuas": {"action": "social_mutual", "target": ""},
        "mutuas sociais": {"action": "social_mutual", "target": ""},
        "mútuas sociais": {"action": "social_mutual", "target": ""},
        "conexoes confirmadas": {"action": "social_confirmed", "target": ""},
        "conexões confirmadas": {"action": "social_confirmed", "target": ""},
        "confirmadas sociais": {"action": "social_confirmed", "target": ""},
        "conexoes uteis": {"action": "social_useful", "target": ""},
        "conexões úteis": {"action": "social_useful", "target": ""},
        "uteis sociais": {"action": "social_useful", "target": ""},
        "úteis sociais": {"action": "social_useful", "target": ""},
        "conexoes favoritas": {"action": "social_favorites", "target": ""},
        "conexões favoritas": {"action": "social_favorites", "target": ""},
        "favoritas sociais": {"action": "social_favorites", "target": ""},
        "historico conexoes": {"action": "social_history", "target": ""},
        "histórico conexões": {"action": "social_history", "target": ""},
        "memoria social": {"action": "social_history", "target": ""},
        "memória social": {"action": "social_history", "target": ""},
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
    if msg.startswith("decorar") and not _looks_like_decor_question(message):
        return {"action": "decorate", "target": msg}

    # Check seeds-related keywords
    seeds_keywords = ["semente", "moeda", "ponto", "como ganho", "como consigo", "como ganhar"]
    if any(kw in msg for kw in seeds_keywords):
        return {"action": "seeds", "target": ""}

    match_keywords = ["conex", "compat", "match", "quem pode me ajudar", "com quem posso falar"]
    if any(kw in msg for kw in match_keywords):
        return {"action": "matches", "target": ""}

    mutual_keywords = ["conexoes mutuas", "conexões mútuas", "mutuas sociais", "mútuas sociais"]
    if any(kw in msg for kw in mutual_keywords):
        return {"action": "social_mutual", "target": ""}

    confirmed_keywords = ["conexoes confirmadas", "conexões confirmadas", "confirmadas sociais"]
    if any(kw in msg for kw in confirmed_keywords):
        return {"action": "social_confirmed", "target": ""}

    useful_keywords = ["conexoes uteis", "conexões úteis", "uteis sociais", "úteis sociais"]
    if any(kw in msg for kw in useful_keywords):
        return {"action": "social_useful", "target": ""}

    favorite_keywords = ["conexoes favoritas", "conexões favoritas", "favoritas sociais"]
    if any(kw in msg for kw in favorite_keywords):
        return {"action": "social_favorites", "target": ""}

    history_keywords = ["historico de conex", "histórico de conex", "memoria social", "memória social"]
    if any(kw in msg for kw in history_keywords):
        return {"action": "social_history", "target": ""}

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


def _apply_relationship_progress(phone: str, event_type: str, saved_meta: dict | None = None):
    clean = _clean_phone(phone)
    player = db.get_artifact(f"mudai.users.{clean}")
    if not player:
        return

    meta = player.get("metadata_parsed", {})
    progress = meta.get("relationship_progress", {}) if isinstance(meta.get("relationship_progress", {}), dict) else {}
    unlocked = set(progress.get("unlocked_milestones", [])) if isinstance(progress.get("unlocked_milestones", []), list) else set()
    stats = rooms.get_social_relationship_progress(phone)

    milestone_specs = [
        ("first_favorite", stats.get("favorites", 0) >= 1, SEEDS_REWARDS["relationship_milestone"], None),
        ("first_useful", stats.get("useful", 0) >= 1, SEEDS_REWARDS["relationship_milestone"], None),
        ("first_note", stats.get("noted", 0) >= 1, SEEDS_REWARDS["relationship_milestone"], None),
        ("first_tags", stats.get("tagged", 0) >= 1, SEEDS_REWARDS["relationship_milestone"], "curador_social"),
        ("first_confirmed", stats.get("confirmed", 0) >= 1, SEEDS_REWARDS["relationship_confirmed"], "aliado"),
        ("first_mutual", stats.get("mutual", 0) >= 1, SEEDS_REWARDS["relationship_mutual"], "elo_mutuo"),
        ("curation_set", (stats.get("favorites", 0) + stats.get("useful", 0) + stats.get("noted", 0) + stats.get("tagged", 0)) >= 4, SEEDS_REWARDS["relationship_milestone"], "curador_social"),
    ]

    earned_any = False
    for milestone_id, achieved, seeds_reward, badge_id in milestone_specs:
        if not achieved or milestone_id in unlocked:
            continue
        unlocked.add(milestone_id)
        if seeds_reward > 0:
            _award_seeds(phone, seeds_reward)
        if badge_id:
            _check_and_award_badge(phone, badge_id)
        earned_any = True

    latest_meta = db.get_artifact(f"mudai.users.{clean}")
    latest_progress = latest_meta.get("metadata_parsed", {}).get("relationship_progress", {}) if latest_meta else {}
    merged_progress = latest_progress if isinstance(latest_progress, dict) else {}
    merged_progress.update({
        "stats": stats,
        "last_event_type": event_type,
        "last_event_target": str((saved_meta or {}).get("nickname", "") or ""),
        "unlocked_milestones": sorted(unlocked),
        "updated_at": db._now(),
    })
    if earned_any:
        merged_progress["last_rewarded_at"] = db._now()
    _update_meta(phone, {"relationship_progress": merged_progress})
    current_room = str(meta.get("current_room", "") or "").strip()
    if current_room and event_type in {"confirm", "mutual", "note", "tags", "favorite", "useful"}:
        nickname = meta.get("nickname", "Viajante")
        target_name = str((saved_meta or {}).get("nickname", "") or "alguém")
        world_state.apply_room_consequence(
            room_path=current_room,
            consequence_type=f"social_{event_type}",
            summary=f"{nickname} aprofundou um vínculo com {target_name} nesta sala.",
            intensity=2 if event_type in {"confirm", "mutual"} else 1,
            social_delta=2 if event_type in {"confirm", "mutual"} else 1,
        )


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


async def _attach_room_challenge(phone: str, meta: dict, room_info: dict | None, response: str, trigger: str, challenge: dict | None = None) -> str:
    if not room_info:
        return response
    challenge = challenge or await _ensure_active_challenge(phone, meta, room_info, trigger=trigger)
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


async def _ensure_active_challenge(phone: str, meta: dict, room_info: dict, trigger: str) -> dict | None:
    current_room = room_info.get("path")
    active = meta.get("active_challenge")
    if active and active.get("status") == "active" and active.get("room_path") == current_room:
        if active.get("mission_id"):
            return active
        persisted = world_state.get_room_challenge(current_room, active.get("id", ""))
        persisted_meta = persisted.get("metadata_parsed", {}) if persisted else {}
        if persisted_meta.get("status", "active") == "active":
            return _serialize_room_challenge(persisted_meta, room_info)
        _update_meta(phone, {"active_challenge": None})
    if trigger == "move" and active and active.get("status") == "active":
        return None

    mission = world_state.get_player_room_mission(current_room, meta)
    if mission:
        challenge = _build_room_mission_challenge(mission, meta)
    else:
        await _ensure_room_challenge_pool(room_info, meta)
        challenge = _select_room_challenge_for_player(room_info, meta)
    if not challenge:
        return None
    seen_ids = list(_seen_challenge_ids(meta))
    challenge_id = str(challenge.get("id", "") or "")
    if challenge_id and challenge_id not in seen_ids:
        seen_ids.append(challenge_id)
    _update_meta(phone, {
        "active_challenge": challenge,
        "last_challenge_room": current_room,
        "seen_challenge_ids": seen_ids[-40:],
    })
    return challenge


async def _activate_room_challenge_from_idle(phone: str, meta: dict, message: str) -> str | None:
    current_room = meta.get("current_room", "mudai.places.start")
    room_info = rooms.get_room_info(current_room)
    if not room_info:
        return None
    challenge = await _ensure_active_challenge(phone, meta, room_info, trigger="look")
    if not challenge:
        return fmt.format_interaction(
            room_name=room_info.get("name", "Sala"),
            action_label="Desafio indisponível",
            seeds=meta.get("seeds", 0),
            seeds_change=0,
            level=_calculate_level(meta),
            narrative="Tentei puxar um desafio para esta sala, mas por enquanto não apareceu nenhum bom. Você pode explorar, olhar a sala ou tentar de novo daqui a pouco.",
            badge=None,
            suggestions=_get_room_suggestions(room_info),
            breadcrumb=(room_info.get("name", "Sala")).replace("🌱 ", ""),
            profile_url=_generate_profile_url(phone),
        )
    action_label = "Desafio ativado"
    normalized = message.strip().lower()
    if normalized != "pular":
        action_label = "Desafio renovado"
    suggestions = _get_room_suggestions(room_info, active_challenge=challenge)
    return fmt.format_interaction(
        room_name=challenge.get("room_name", room_info.get("name", "Sala")),
        action_label=action_label,
        seeds=meta.get("seeds", 0),
        seeds_change=0,
        level=_calculate_level(meta),
        narrative=(
            f"Separei um desafio para você nesta sala. "
            f"Se quiser, o atual é *{challenge.get('title', 'Desafio')}*: {challenge.get('instruction', '')}"
        ),
        badge=None,
        suggestions=suggestions,
        breadcrumb=(challenge.get("room_name", room_info.get("name", "Sala"))).replace("🌱 ", ""),
        profile_url=_generate_profile_url(phone),
    )


def _build_room_challenge(room_info: dict, player_meta: dict | None = None) -> dict | None:
    room_path = room_info.get("path", "")
    room_name = room_info.get("name", "Sala")
    motifs = room_info.get("motifs", [])[:3]
    highlights = room_info.get("recent_contributions", [])[:2]
    purpose = room_info.get("purpose", "")
    tags = room_info.get("tags", [])
    profile_signals = (player_meta or {}).get("profile_signals", {})
    normalized_signals = profile_signals.get("normalized", {}) if profile_signals else {}
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

    if float(normalized_signals.get("technicality", 0.0) or 0.0) >= 0.7 and challenge_type in {"reflexão", "perspectiva"}:
        instruction = f"Em 1 ou 2 frases, dê uma leitura clara e concreta sobre {room_name}."
    elif float(normalized_signals.get("creativity", 0.0) or 0.0) >= 0.7 and challenge_type in {"reflexão", "perspectiva"}:
        challenge_type = "história"
        instruction = f"Escreva uma frase viva que combine com o clima de {room_name} sem exagerar no tamanho."
    elif float(normalized_signals.get("support", 0.0) or 0.0) >= 0.7 or float(normalized_signals.get("humanity", 0.0) or 0.0) >= 0.7:
        if challenge_type in {"reflexão", "troca", "perspectiva"}:
            instruction = f"Em 1 frase, diga algo que possa acolher, ajudar ou fortalecer quem passar por {room_name}."
    elif float(normalized_signals.get("practicality", 0.0) or 0.0) >= 0.7:
        instruction = f"Responda com 1 frase útil e prática que faça sentido dentro de {room_name}."
    elif float(normalized_signals.get("intensity", 0.0) or 0.0) >= 0.7 and challenge_type == "reflexão":
        instruction = f"Em 1 frase forte e honesta, diga o que este lugar ativa em você."

    challenge_id = hashlib.sha256(f"{room_path}:{instruction}".encode()).hexdigest()[:12]
    return {
        "id": challenge_id,
        "room_path": room_path,
        "room_name": room_name,
        "title": f"Pulso de {room_name.replace('🌱 ', '').replace('📝 ', '').strip() or 'Sala'}",
        "type": challenge_type,
        "instruction": instruction,
        "reward_seeds": SEEDS_REWARDS["challenge"],
        "status": "active",
        "source": "dynamic_challenge",
        "novelty_key": f"fallback-{challenge_type}-{challenge_id[:6]}",
    }


def _build_room_mission_challenge(mission: dict | None, player_meta: dict | None = None) -> dict | None:
    if not mission:
        return None
    meta = mission.get("metadata_parsed", {})
    mission_id = meta.get("id")
    if not mission_id:
        return None
    mission_type = meta.get("mission_type", "missão")
    profile_signals = (player_meta or {}).get("profile_signals", {})
    normalized_signals = profile_signals.get("normalized", {}) if profile_signals else {}
    challenge_type_map = {
        "echo": "reflexão",
        "bridge": "perspectiva",
        "exchange": "troca",
    }
    instruction = meta.get("instruction", mission.get("content", ""))
    if float(normalized_signals.get("technicality", 0.0) or 0.0) >= 0.7:
        instruction = f"Responda com clareza e objetividade: {instruction}"
    elif float(normalized_signals.get("creativity", 0.0) or 0.0) >= 0.7:
        instruction = f"Responda de forma viva e autoral, em poucas linhas: {instruction}"
    elif float(normalized_signals.get("support", 0.0) or 0.0) >= 0.7 or float(normalized_signals.get("humanity", 0.0) or 0.0) >= 0.7:
        instruction = f"Responda de um jeito humano e útil para quem ler depois: {instruction}"
    elif float(normalized_signals.get("practicality", 0.0) or 0.0) >= 0.7:
        instruction = f"Se puder, responda com algo claro, aplicável e direto: {instruction}"

    return {
        "id": mission_id,
        "mission_id": mission_id,
        "room_path": meta.get("room_path", ""),
        "room_name": meta.get("room_name", "Sala"),
        "title": meta.get("title", "Missão"),
        "type": challenge_type_map.get(mission_type, "reflexão"),
        "instruction": instruction,
        "reward_seeds": meta.get("reward_seeds", SEEDS_REWARDS["challenge"]),
        "status": "active",
        "source": "room_mission",
        "novelty_key": f"mission-{mission_id}",
    }


def _completed_challenge_ids(meta: dict) -> set[str]:
    items = meta.get("completed_challenge_ids", [])
    if not isinstance(items, list):
        return set()
    return {str(item) for item in items if item}


def _completed_challenge_novelty_keys(meta: dict) -> set[str]:
    items = meta.get("completed_challenge_novelty_keys", [])
    if not isinstance(items, list):
        return set()
    return {str(item) for item in items if item}


def _seen_challenge_ids(meta: dict) -> set[str]:
    items = meta.get("seen_challenge_ids", [])
    if not isinstance(items, list):
        return set()
    return {str(item) for item in items if item}


def _skipped_challenge_ids(meta: dict) -> set[str]:
    items = meta.get("skipped_challenge_ids", [])
    if not isinstance(items, list):
        return set()
    return {str(item) for item in items if item}


def _skipped_challenge_ids_by_room(meta: dict, room_path: str) -> set[str]:
    scoped = meta.get("skipped_challenge_ids_by_room", {})
    if not isinstance(scoped, dict):
        return set()
    items = scoped.get(room_path, [])
    if not isinstance(items, list):
        return set()
    return {str(item) for item in items if item}


def _with_skipped_challenge_for_room(meta: dict, room_path: str, challenge_id: str) -> dict:
    scoped = meta.get("skipped_challenge_ids_by_room", {})
    scoped = dict(scoped) if isinstance(scoped, dict) else {}
    room_items = scoped.get(room_path, [])
    room_items = [str(item) for item in room_items if item]
    if challenge_id and challenge_id not in room_items:
        room_items.append(challenge_id)
    scoped[room_path] = room_items[-20:]

    global_items = list(_skipped_challenge_ids(meta))
    if challenge_id and challenge_id not in global_items:
        global_items.append(challenge_id)

    return {
        "skipped_challenge_ids": global_items[-40:],
        "skipped_challenge_ids_by_room": scoped,
    }


def _recent_skipped_challenge_ids_by_room(meta: dict, room_path: str, cooldown_window: int = 2) -> set[str]:
    scoped = meta.get("skipped_challenge_ids_by_room", {})
    if not isinstance(scoped, dict):
        return set()
    items = scoped.get(room_path, [])
    if not isinstance(items, list):
        return set()
    recent = [str(item) for item in items if item][-max(0, int(cooldown_window)):]
    return set(recent)


def _is_challenge_rotation_request(normalized: str) -> bool:
    aliases = {
        "pular",
        "skip",
        "trocar desafio",
        "novo desafio",
        "renovar desafio",
        "outro desafio",
    }
    return normalized in aliases


def _challenge_type_label(challenge_type: str) -> str:
    mapping = {
        "reflexão": "reflexão",
        "perspectiva": "perspectiva",
        "história": "história",
        "troca": "troca",
        "decoração": "decoração",
        "apoio": "apoio",
        "insight": "insight",
    }
    return mapping.get(challenge_type, challenge_type or "desafio")


def _serialize_room_challenge(challenge_meta: dict, room_info: dict | None = None) -> dict:
    room_name = challenge_meta.get("room_name") or (room_info or {}).get("name", "Sala")
    return {
        "id": challenge_meta.get("id", ""),
        "room_path": challenge_meta.get("room_path", (room_info or {}).get("path", "")),
        "room_name": room_name,
        "title": challenge_meta.get("title", "Desafio"),
        "type": _challenge_type_label(str(challenge_meta.get("challenge_type", "reflexão") or "reflexão")),
        "instruction": challenge_meta.get("instruction", ""),
        "reward_seeds": int(challenge_meta.get("reward_seeds", SEEDS_REWARDS["challenge"]) or SEEDS_REWARDS["challenge"]),
        "status": challenge_meta.get("status", "active"),
        "source": challenge_meta.get("source", "dynamic_challenge"),
        "novelty_key": challenge_meta.get("novelty_key", challenge_meta.get("id", "")),
        "response_count": int(challenge_meta.get("response_count", 0) or 0),
        "completion_count": int(challenge_meta.get("completion_count", 0) or 0),
    }


def _build_challenge_generation_input(room_info: dict, player_meta: dict | None = None) -> str:
    context = world_state.build_room_challenge_context(room_info.get("path", ""))
    structured_profile = _build_structured_profile_context(player_meta or {})
    normalized_signals = ((player_meta or {}).get("profile_signals", {}) or {}).get("normalized", {})
    signal_pairs = [f"{key}:{round(float(value or 0.0), 2)}" for key, value in normalized_signals.items()]
    return "\n".join([
        f"Sala: {context.get('room_name', room_info.get('name', 'Sala'))}",
        f"Propósito: {context.get('purpose', room_info.get('purpose', ''))}",
        f"Tags: {', '.join(context.get('tags', [])) or 'nenhuma'}",
        f"Motifs: {', '.join(context.get('motifs', [])) or 'nenhum'}",
        f"Resumo vivo: {context.get('evolving_summary', room_info.get('evolving_summary', '')) or 'sem resumo'}",
        f"Consequência recente: {context.get('last_consequence_summary', room_info.get('last_consequence_summary', '')) or 'nenhuma'}",
        f"Temperatura social: {context.get('social_heat', 0)}",
        f"Momentum: {context.get('momentum_score', 0)}",
        f"Últimos ecos: {' | '.join(context.get('recent_blocks', [])) or 'nenhum'}",
        f"Últimas respostas de desafios: {' | '.join(context.get('recent_challenge_responses', [])) or 'nenhuma'}",
        f"Desafios existentes: {' | '.join([item.get('title', '') + ': ' + item.get('instruction', '') for item in context.get('existing_challenges', [])[:6]]) or 'nenhum'}",
        f"Novelty keys existentes: {', '.join(context.get('existing_novelty_keys', [])) or 'nenhuma'}",
        f"Resumo do jogador: {structured_profile.get('summary', 'sem resumo')}",
        f"Momento do jogador: {structured_profile.get('current_moment', 'não identificado')}",
        f"Sinais do jogador: {', '.join(signal_pairs) or 'nenhum'}",
    ])


def _fallback_room_challenge_specs(room_info: dict, player_meta: dict | None = None) -> list[dict]:
    base = _build_room_challenge(room_info, player_meta)
    if not base:
        return []
    room_name = room_info.get("name", "Sala")
    motifs = room_info.get("motifs", [])[:3]
    motif_text = ", ".join(motifs) if motifs else room_name
    purpose = room_info.get("purpose", room_name)
    slug = world_state.room_slug(room_info.get("path", "mudai.places.room"))
    return [
        {
            "title": base.get("title", "Pulso da sala"),
            "instruction": base.get("instruction", "Deixe uma frase curta dizendo o que este lugar desperta em você."),
            "challenge_type": base.get("type", "reflexão"),
            "novelty_key": base.get("novelty_key", f"fallback-{slug}-base"),
            "relevance_score": 0.72,
        },
        {
            "title": f"Ecos de {room_name}",
            "instruction": f"Responda em 1 frase a algo que a sala está puxando agora: {motif_text}.",
            "challenge_type": "perspectiva",
            "novelty_key": f"echo-{slug}-{hashlib.sha256(motif_text.encode()).hexdigest()[:6]}",
            "relevance_score": 0.68,
        },
        {
            "title": f"Próximo gesto em {room_name}",
            "instruction": f"Em 1 frase útil, diga algo que fortaleceria o propósito desta sala: {purpose}.",
            "challenge_type": "insight",
            "novelty_key": f"purpose-{slug}-{hashlib.sha256(purpose.encode()).hexdigest()[:6]}",
            "relevance_score": 0.64,
        },
    ]


async def _generate_dynamic_room_challenge_specs(room_info: dict, player_meta: dict | None = None) -> list[dict]:
    fallback = _fallback_room_challenge_specs(room_info, player_meta)
    try:
        result = await chat_completion_json(
            system_prompt=CHALLENGE_GENERATOR_PROMPT,
            user_message=_build_challenge_generation_input(room_info, player_meta),
            temperature=0.45,
            max_tokens=700,
        )
    except Exception:
        return fallback
    items = result.get("challenges", []) if isinstance(result, dict) else []
    if not isinstance(items, list) or not items:
        return fallback
    return _normalize_generated_challenge_specs(items, room_info, player_meta) or fallback


def _normalize_generated_challenge_specs(items: list[dict], room_info: dict, player_meta: dict | None = None) -> list[dict]:
    normalized = []
    existing_novelty_keys = set(world_state.build_room_challenge_context(room_info.get("path", "")).get("existing_novelty_keys", []))
    for item in items:
        title = str(item.get("title", "") or "").strip()
        instruction = str(item.get("instruction", "") or "").strip()
        challenge_type = _challenge_type_label(str(item.get("challenge_type", "reflexão") or "reflexão"))
        novelty_key = str(item.get("novelty_key", "") or "").strip().lower()
        relevance_score = float(item.get("relevance_score", 0.0) or 0.0)
        if not instruction:
            continue
        if not title:
            title = f"Pulso de {(room_info.get('name', 'Sala')).replace('🌱 ', '').replace('📝 ', '').strip() or 'Sala'}"
        if not novelty_key:
            novelty_key = hashlib.sha256(f"{room_info.get('path', '')}:{title}:{instruction}".encode()).hexdigest()[:12]
        if novelty_key in existing_novelty_keys:
            continue
        normalized.append({
            "title": title,
            "instruction": instruction,
            "challenge_type": challenge_type,
            "novelty_key": novelty_key,
            "relevance_score": relevance_score,
        })
        existing_novelty_keys.add(novelty_key)
    return normalized


async def _ensure_room_challenge_pool(room_info: dict, player_meta: dict | None = None, min_active: int = 6) -> list[dict]:
    room_path = room_info.get("path", "")
    active = world_state.list_room_challenges(room_path, limit=50)
    if len(active) >= min_active:
        return active
    specs = await _generate_dynamic_room_challenge_specs(room_info, player_meta)
    specs = _normalize_generated_challenge_specs(specs, room_info, player_meta)
    context = world_state.build_room_challenge_context(room_path)
    for spec in specs:
        world_state.create_room_challenge(
            room_path=room_path,
            title=spec["title"],
            instruction=spec["instruction"],
            challenge_type=spec["challenge_type"],
            reward_seeds=SEEDS_REWARDS["challenge"],
            source="dynamic_challenge",
            novelty_key=spec["novelty_key"],
            prompt_fingerprint=hashlib.sha256(_build_challenge_generation_input(room_info, player_meta).encode()).hexdigest()[:16],
            generator_version=1,
            relevance_score=spec.get("relevance_score", 0.5),
            created_from_block_ids=[item.get("id", "") for item in room_info.get("recent_contributions", [])[:6] if item.get("id")],
            created_from_recent_players=context.get("recent_players", []),
        )
    world_state.refresh_room_state(room_path)
    return world_state.list_room_challenges(room_path, limit=50)


def _select_room_challenge_for_player(room_info: dict, meta: dict, excluded_ids: set[str] | None = None) -> dict | None:
    room_path = room_info.get("path", "")
    challenges = world_state.list_room_challenges(room_path, limit=50)
    completed_ids = _completed_challenge_ids(meta)
    completed_novelty = _completed_challenge_novelty_keys(meta)
    seen_ids = _seen_challenge_ids(meta)
    skipped_ids = _skipped_challenge_ids_by_room(meta, room_path) or _skipped_challenge_ids(meta)
    cooled_down_ids = _recent_skipped_challenge_ids_by_room(meta, room_path)
    excluded = set(excluded_ids or set())
    scored_primary = []
    scored_fallback = []
    for challenge in challenges:
        challenge_meta = challenge.get("metadata_parsed", {})
        challenge_id = str(challenge_meta.get("id", "") or "")
        novelty_key = str(challenge_meta.get("novelty_key", challenge_id) or challenge_id)
        if not challenge_id or challenge_meta.get("status") != "active":
            continue
        if challenge_id in excluded:
            continue
        if challenge_id in completed_ids or novelty_key in completed_novelty:
            continue
        score = float(challenge_meta.get("relevance_score", 0) or 0)
        if challenge_id in seen_ids:
            score -= 0.15
        if challenge_id in skipped_ids:
            score -= 0.45
        score += min(int(challenge_meta.get("response_count", 0) or 0), 4) * 0.02
        bucket = scored_fallback if challenge_id in cooled_down_ids else scored_primary
        bucket.append((score, challenge_meta))
    scored = scored_primary or scored_fallback
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = scored[0][1]
    return _serialize_room_challenge(selected, room_info)


def _resolve_active_challenge(phone: str, meta: dict, message: str, challenge: dict) -> str | None:
    text = message.strip()
    normalized = text.lower()
    if not text:
        return None
    if _is_challenge_rotation_request(normalized):
        room_info = rooms.get_room_info(challenge.get("room_path", meta.get("current_room", "mudai.places.start")))
        room_path = challenge.get("room_path", meta.get("current_room", "mudai.places.start"))
        challenge_id = str(challenge.get("id", "") or "")
        updates = {
            "active_challenge": None,
        }
        updates.update(_with_skipped_challenge_for_room(meta, room_path, challenge_id))
        next_challenge = None
        if room_info and not challenge.get("mission_id"):
            next_challenge = _select_room_challenge_for_player(room_info, {**meta, **updates}, excluded_ids={challenge_id} if challenge_id else None)
            if next_challenge:
                next_seen_ids = list(_seen_challenge_ids({**meta, **updates}))
                next_id = str(next_challenge.get("id", "") or "")
                if next_id and next_id not in next_seen_ids:
                    next_seen_ids.append(next_id)
                updates["active_challenge"] = next_challenge
                updates["seen_challenge_ids"] = next_seen_ids[-40:]
        _update_meta(phone, updates)
        suggestions = _get_room_suggestions(room_info, active_challenge=next_challenge) if room_info else [{"cmd": "olhar", "desc": "ver detalhes"}]
        narrative = "Tudo bem. Você pode continuar explorando e pegar outro desafio mais tarde."
        action_label = "Desafio ignorado"
        if next_challenge:
            narrative = (
                f"Tudo bem. Deixei o desafio anterior de lado. "
                f"Se quiser, o próximo é *{next_challenge.get('title', 'Desafio')}*: {next_challenge.get('instruction', '')}"
            )
            if normalized != "pular":
                action_label = "Desafio renovado"
        elif normalized != "pular":
            narrative = "Certo. Tentei renovar o desafio, mas por enquanto não apareceu outro melhor. Você pode explorar a sala ou responder depois."
            action_label = "Desafio renovado"
        return fmt.format_interaction(
            room_name=challenge.get("room_name", room_info["name"] if room_info else "Sala"),
            action_label=action_label,
            seeds=meta.get("seeds", 0),
            seeds_change=0,
            level=_calculate_level(meta),
            narrative=narrative,
            badge=None,
            suggestions=suggestions,
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
    completed_ids = list(_completed_challenge_ids(meta))
    completed_novelty = list(_completed_challenge_novelty_keys(meta))
    challenge_id = str(challenge.get("id", "") or "")
    novelty_key = str(challenge.get("novelty_key", challenge_id) or challenge_id)
    if challenge_id and challenge_id not in completed_ids:
        completed_ids.append(challenge_id)
    if novelty_key and novelty_key not in completed_novelty:
        completed_novelty.append(novelty_key)
    updates = {
        "seeds": new_seeds,
        "total_seeds_earned": new_total,
        "completed_challenges": completed,
        "active_challenge": None,
        "last_completed_challenge_id": challenge.get("id", ""),
        "completed_challenge_ids": completed_ids[-80:],
        "completed_challenge_novelty_keys": completed_novelty[-80:],
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
    elif challenge_id:
        world_state.register_challenge_response(room_path, challenge_id, block)
        world_state.archive_room_challenge(room_path, challenge_id, reason="completed_by_player")

    world_state.apply_room_consequence(
        room_path=room_path,
        consequence_type="mission_completion" if challenge.get("mission_id") else "challenge_completion",
        summary=f"{meta.get('nickname', 'Aventureiro')} concluiu {challenge.get('title', 'um desafio')}.",
        intensity=max(1, int(seeds_change or 1)),
        social_delta=1,
    )
    world_state.refresh_room_state(room_path)

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


def _get_room_suggestions(room_info: dict, active_challenge: dict | None = None) -> list[dict]:
    """Get contextual suggestions based on room state."""
    suggestions = [
        {"cmd": "olhar", "desc": "ver detalhes"},
    ]

    if active_challenge:
        suggestions.append({"cmd": "responder desafio", "desc": active_challenge.get("title", "encarar desafio ativo")})
        suggestions.append({"cmd": "trocar desafio", "desc": "pedir outro desafio"})
        suggestions.append({"cmd": "pular", "desc": "ignorar o desafio atual"})
    else:
        challenges = room_info.get("challenges", []) if room_info else []
        if challenges:
            first_challenge = challenges[0]
            suggestions.append({"cmd": "responder desafio", "desc": first_challenge.get("title", "encarar desafio ativo")})
            suggestions.append({"cmd": "novo desafio", "desc": "pedir outro desafio"})

    missions = room_info.get("missions", []) if room_info else []
    if missions and not active_challenge:
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
    deduped = []
    seen = set()
    for suggestion in suggestions:
        key = (suggestion.get("cmd", ""), suggestion.get("desc", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(suggestion)
    return deduped[:4]


def _build_room_dynamic_suffix(room_info: dict | None, active_challenge: dict | None = None) -> str:
    if not room_info:
        return ""
    motifs = room_info.get("motifs", [])[:3]
    highlight = room_info.get("recent_contributions", [])[:1]
    parts = []
    consequence = str(room_info.get("last_consequence_summary", "") or "").strip()
    if consequence:
        parts.append(f"Consequência recente: {consequence}")
    if motifs:
        parts.append(f"O clima recente gira em torno de {', '.join(motifs)}.")
    if highlight:
        excerpt = highlight[0].get("excerpt", "")
        if excerpt:
            parts.append(f"Um eco recente ficou no ar: _{excerpt}_")
    momentum = int(room_info.get("momentum_score", 0) or 0)
    social_heat = int(room_info.get("social_heat", 0) or 0)
    if momentum >= 3:
        parts.append(f"O lugar está ganhando tração coletiva ({momentum}).")
    if social_heat >= 2:
        parts.append(f"Existe uma temperatura social viva aqui ({social_heat}).")
    image = room_info.get("image")
    if image and image.get("status") == "pending_generation":
        parts.append("A sala está juntando detalhes para ganhar uma nova imagem.")
    challenge = active_challenge or ((room_info.get("challenges", []) or [None])[0])
    if challenge:
        title = str(challenge.get("title", "Desafio") or "Desafio").strip()
        instruction = str(challenge.get("instruction", "") or "").strip()
        reward = int(challenge.get("reward_seeds", SEEDS_REWARDS["challenge"]) or SEEDS_REWARDS["challenge"])
        if instruction:
            parts.append(f"Desafio ativo: *{title}* — {instruction} (vale {reward} sementes; responda ou diga _pular_).")
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
