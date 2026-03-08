"""
MUD-AI — Onboarding System v2.1.

5-step conversational flow to capture player essence.
Starts with 50 seeds, awards bonus on completion.
"""

from . import database as db
from . import message_formatter as fmt
from .ai_client import chat_completion


INITIAL_SEEDS = 50

ONBOARDING_STEPS = [
    {
        "step": 1,
        "title": "CRIANDO SEU PERFIL",
        "question": "Antes de tudo, *como quer ser chamado* aqui dentro?\n\nPode ser um apelido, um nome inventado, ou seu nome real.",
        "hint": "✨ _Exemplos: Luna, Eco, seu nome..._",
        "field": "nickname",
    },
    {
        "step": 2,
        "title": "SUA ESSÊNCIA",
        "question": "Legal, *{nickname}*! Agora me conta:\n\n> _\"Se você fosse um som, qual seria?\"_ 🎵\n\nPode ser qualquer coisa: chuva, risada, um acorde...",
        "hint": "",
        "field": "essence",
    },
    {
        "step": 3,
        "title": "O QUE VOCÊ BUSCA",
        "question": "Show, *{nickname}*! ✨\n\n*O que te traz aqui?*\n\nConversas? Inspiração? Histórias? Conexões? Diversão?",
        "hint": "💬 _Fale livremente_",
        "field": "seeks",
    },
    {
        "step": 4,
        "title": "O QUE VOCÊ OFERECE",
        "question": "E o contrário: *o que você tem pra compartilhar?*\n\nEscuta, humor, habilidade, histórias, conselhos...",
        "hint": "🤝 _O que vem à mente?_",
        "field": "offers",
    },
    {
        "step": 5,
        "title": "PRIMEIRA MARCA",
        "question": "Última! 🎉\n\n> _Deixe uma frase na parede da Recepção — algo que represente você._\n\nPode ser uma frase sua, citação, ou qualquer coisa.",
        "hint": "📝 _Essa frase fica visível para outros visitantes_",
        "field": "first_fragment",
    },
]


async def process_onboarding(phone: str, message: str) -> str:
    """
    Process an onboarding step for a player.
    Returns the formatted response message.
    """
    player = db.get_artifact(f"mudai.users.{_clean_phone(phone)}")
    if not player:
        return fmt.format_error("Perfil não encontrado. Envie 'oi' para começar.")

    meta = player.get("metadata_parsed", {})
    current_step = meta.get("onboarding_step", 0)

    # Step 0: Show welcome, advance to step 1
    if current_step == 0:
        _update_meta(phone, {"onboarding_step": 1, "state": "onboarding"})
        step_data = ONBOARDING_STEPS[0]
        return fmt.format_onboarding_step(
            step=1,
            total=5,
            title=step_data["title"],
            question=step_data["question"],
            hint=step_data["hint"],
        )

    # Steps 1-5: Save answer and advance
    if 1 <= current_step <= 5:
        step_idx = current_step - 1
        step_data = ONBOARDING_STEPS[step_idx]
        field = step_data["field"]

        # Save the answer
        updates = {field: message.strip()}

        # If step 1, also update the nickname
        if current_step == 1:
            updates["nickname"] = message.strip()

        # If step 5 (last), finalize onboarding
        if current_step == 5:
            # Award completion bonus
            bonus = 3
            current_seeds = meta.get("seeds", INITIAL_SEEDS)
            updates["state"] = "playing"
            updates["onboarding_step"] = 6  # done
            updates["current_room"] = "mudai.places.start"
            updates["seeds"] = current_seeds + bonus
            updates["total_seeds_earned"] = meta.get("total_seeds_earned", 0) + bonus
            updates["badges"] = meta.get("badges", []) + ["primeiro_passo"]
            _update_meta(phone, updates)

            # Check referral bonus
            _check_referral_bonus(phone)

            # Add fragment to reception
            _add_fragment_to_room(
                "mudai.places.start",
                message.strip(),
                meta.get("nickname", "Alguém"),
            )

            # Return the first room view
            return await _build_welcome_room_response(phone)

        # Advance to next step
        next_step = current_step + 1
        updates["onboarding_step"] = next_step
        _update_meta(phone, updates)

        # Get next step data
        next_step_data = ONBOARDING_STEPS[next_step - 1]
        nickname = meta.get("nickname", updates.get("nickname", ""))

        question = next_step_data["question"].replace("{nickname}", nickname)

        return fmt.format_onboarding_step(
            step=next_step,
            total=5,
            title=next_step_data["title"],
            question=question,
            hint=next_step_data["hint"],
        )

    # Already done
    return fmt.format_error("Onboarding já concluído! Diga 'olhar' para ver onde está.")


async def start_onboarding(phone: str) -> str:
    """
    Initialize a new player and return welcome message.
    Creates the player artifact from template and shows welcome.
    """
    clean = _clean_phone(phone)
    player_path = f"mudai.users.{clean}"

    # Check if player exists
    existing = db.get_artifact(player_path)
    if existing:
        meta = existing.get("metadata_parsed", {})
        state = meta.get("state", "")

        if state == "onboarding":
            return await process_onboarding(phone, "")

        return None

    # Create player from template
    db.copy_artifact("mudai.templates.player", player_path)

    # Set initial metadata with 50 seeds
    _update_meta(phone, {
        "state": "onboarding",
        "onboarding_step": 0,
        "current_room": "mudai.places.start",
        "rooms_visited": ["mudai.places.start"],
        "seeds": INITIAL_SEEDS,
        "total_seeds_earned": INITIAL_SEEDS,
        "level": 1,
        "badges": [],
        "chat_count": 0,
        "decorations_count": 0,
        "challenges_completed": 0,
        "has_house": False,
        "opted_in_adult": False,
        "interests": [],
    })

    return fmt.format_welcome()


# ─── Helpers ──────────────────────────────────────────

def _clean_phone(phone: str) -> str:
    """Remove non-alphanumeric characters from phone."""
    return "".join(c for c in phone if c.isalnum())


def _update_meta(phone: str, updates: dict):
    """Merge updates into player metadata."""
    clean = _clean_phone(phone)
    player_path = f"mudai.users.{clean}"
    player = db.get_artifact(player_path)
    if not player:
        return

    import json
    meta = player.get("metadata_parsed", {})
    meta.update(updates)

    db.put_artifact(
        path=player_path,
        content=player["content"],
        content_type=player["content_type"],
        metadata=meta,
        is_template=False,
        template_source=player.get("template_source"),
    )


def _add_fragment_to_room(room_path: str, fragment: str, author: str):
    """Add a player fragment to a room's content."""
    room = db.get_artifact(room_path)
    if not room:
        return

    content = room["content"]

    fragment_line = f'- _"{fragment}"_ — {author} 🌱'

    if "## Fragmentos" in content:
        content = content.replace(
            "_Seja o primeiro a deixar sua marca aqui._",
            fragment_line,
        )
        if fragment_line not in content:
            content = content.replace(
                "## Fragmentos\n",
                f"## Fragmentos\n{fragment_line}\n",
            )
    else:
        content += f"\n## Fragmentos\n{fragment_line}\n"

    db.put_artifact(
        path=room_path,
        content=content,
        content_type=room["content_type"],
        metadata=room.get("metadata_parsed", {}),
        is_template=False,
    )


def _check_referral_bonus(phone: str):
    """Check if this player was referred, award bonus to both."""
    clean = _clean_phone(phone)
    referral_path = f"mudai.referrals.{clean}"
    referral = db.get_artifact(referral_path)

    if not referral:
        return

    ref_meta = referral.get("metadata_parsed", {})
    if ref_meta.get("claimed"):
        return

    referrer_phone = ref_meta.get("referrer", "")
    if not referrer_phone:
        return

    # Award bonus to new player
    player = db.get_artifact(f"mudai.users.{clean}")
    if player:
        p_meta = player.get("metadata_parsed", {})
        p_meta["seeds"] = p_meta.get("seeds", 0) + 5
        p_meta["total_seeds_earned"] = p_meta.get("total_seeds_earned", 0) + 5
        _update_meta(phone, p_meta)

    # Award bonus to referrer
    referrer_clean = _clean_phone(referrer_phone)
    referrer = db.get_artifact(f"mudai.users.{referrer_clean}")
    if referrer:
        r_meta = referrer.get("metadata_parsed", {})
        r_meta["seeds"] = r_meta.get("seeds", 0) + 5
        r_meta["total_seeds_earned"] = r_meta.get("total_seeds_earned", 0) + 5
        badges = r_meta.get("badges", [])
        if "conector" not in badges:
            badges.append("conector")
            r_meta["badges"] = badges
        _update_meta(referrer_phone, r_meta)

    # Mark referral as claimed
    ref_meta["claimed"] = True
    db.put_artifact(
        path=referral_path,
        content=referral["content"],
        content_type=referral.get("content_type", "text/plain"),
        metadata=ref_meta,
        is_template=False,
    )


async def _build_welcome_room_response(phone: str) -> str:
    """Build the first room response after onboarding is complete."""
    import hashlib
    clean = _clean_phone(phone)
    player = db.get_artifact(f"mudai.users.{clean}")
    meta = player.get("metadata_parsed", {})
    nickname = meta.get("nickname", "Aventureiro")

    room = db.get_artifact("mudai.places.start")

    # Count players in room
    players_here = _count_players_in_room("mudai.places.start")

    room_name = "Recepção"
    if room:
        lines = room["content"].split("\n")
        for line in lines:
            if line.startswith("# "):
                room_name = line.replace("#", "").strip()
                break

    token = hashlib.sha256(f"mudai-{clean}-2026".encode()).hexdigest()[:16]
    profile_url = f"https://mudai.servinder.com.br/p/{token}"

    return fmt.format_room_view(
        room_name=room_name,
        room_subtitle="Perfil criado! Explore o mundo. 🌱",
        seeds=meta.get("seeds", INITIAL_SEEDS),
        level=1,
        players_here=players_here,
        narrative=f"Bem-vindo, *{nickname}*! Seu perfil está pronto. Você ganhou 🌱 *Primeiro Passo* e {INITIAL_SEEDS + 3} sementes. Bora explorar!",
        exits=[
            {"direction": "norte", "name": "Praça das Trocas"},
            {"direction": "leste", "name": "Fogueira dos Contos"},
            {"direction": "oeste", "name": "Mesa da Verdade"},
            {"direction": "sul", "name": "Jardim dos Ecos"},
        ],
        suggestions=[
            {"cmd": "salas", "desc": "explorar salas"},
            {"cmd": "/sementes", "desc": "ver como ganhar"},
            {"cmd": "perfil", "desc": "ver seu personagem"},
        ],
        breadcrumb="Recepção",
        seeds_change=3,
        badge="🌱 Primeiro Passo — completou onboarding!",
        profile_url=profile_url,
    )


def _count_players_in_room(room_path: str) -> int:
    """Count how many players are currently in a room."""
    players = db.list_by_prefix("mudai.users.", direct_children_only=True)
    count = 0
    for p in players:
        meta = p.get("metadata_parsed", {})
        if meta.get("current_room") == room_path and meta.get("state") == "playing":
            count += 1
    return count
