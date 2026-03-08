"""
MUD-AI — WhatsApp Message Formatter.

Generates consistent, compact, visually rich text messages
using only WhatsApp-supported formatting (bold, italic, monospace).

Maximum ~800 characters per message to fit one phone screen.
"""

from typing import Optional


# ─── Constants ────────────────────────────────────────

SEP = "━━━━━━━━━━━━━━━━━━━━"
DIV = "─ ─ ─ ─ ─ ─ ─ ─ ─ ─"


# ─── Main Templates ──────────────────────────────────

def format_room_view(
    room_name: str,
    room_subtitle: str,
    seeds: int,
    level: int,
    players_here: int,
    narrative: str,
    exits: list[dict],
    suggestions: list[dict],
    breadcrumb: str = "",
) -> str:
    """
    Standard room view template.

    exits: [{"direction": "norte", "name": "Praça das Trocas"}, ...]
    suggestions: [{"cmd": "olhar", "desc": "ver detalhes"}, ...]
    """
    stats = f"🪙 {seeds}  ·  ⭐ Nv.{level}"
    if players_here > 0:
        stats += f"  ·  👥 {players_here} aqui"

    exit_lines = "\n".join(f"  ▸ {e['direction']} → {e['name']}" for e in exits)
    suggestion_lines = "\n".join(f"  ▸ _\"{s['cmd']}\"_ — {s['desc']}" for s in suggestions[:3])

    parts = [
        SEP,
        f"🌱 *{room_name.upper()}*",
        f"_{room_subtitle}_",
        SEP,
        stats,
        "",
        f"> {narrative}",
        "",
        DIV,
        f"📍 *Ir para:*",
        exit_lines,
    ]

    if suggestion_lines:
        parts += [
            "",
            f"💡 *Sugestões:*",
            suggestion_lines,
        ]

    if breadcrumb:
        parts.append(f"\n🗺 {breadcrumb}")

    parts.append(SEP)
    return "\n".join(parts)


def format_interaction(
    room_name: str,
    action_label: str,
    seeds: int,
    seeds_change: int,
    level: int,
    narrative: str,
    badge: Optional[str],
    suggestions: list[dict],
    breadcrumb: str = "",
) -> str:
    """
    Interaction response template (after player does something).
    """
    seeds_str = f"🪙 {seeds}"
    if seeds_change != 0:
        sign = "+" if seeds_change > 0 else ""
        seeds_str += f" ({sign}{seeds_change})"
    stats = f"{seeds_str}  ·  ⭐ Nv.{level}"

    suggestion_lines = "\n".join(f"  ▸ _\"{s['cmd']}\"_ — {s['desc']}" for s in suggestions[:3])

    parts = [
        SEP,
        f"🌱 *{room_name.upper()}* · {action_label}",
        SEP,
        stats,
        "",
        f"> {narrative}",
    ]

    if badge:
        parts.append(f"\n🏷 _{badge}_")

    if suggestion_lines:
        parts += [
            "",
            f"💡 *E agora?*",
            suggestion_lines,
        ]

    if breadcrumb:
        parts.append(f"\n🗺 {breadcrumb}")

    parts.append(SEP)
    return "\n".join(parts)


def format_onboarding_step(
    step: int,
    total: int,
    title: str,
    question: str,
    hint: str = "",
) -> str:
    """
    Onboarding step template.
    """
    parts = [
        SEP,
        f"📋 *{title.upper()}* ({step}/{total})",
        SEP,
        "",
        question,
    ]

    if hint:
        parts.append(f"\n{hint}")

    parts += [
        "",
        f"💬 _Responda livremente_",
        SEP,
    ]
    return "\n".join(parts)


def format_profile(
    nickname: str,
    level: int,
    seeds: int,
    current_room: str,
    since: str,
    essence: str,
    traits: str,
    seeks: str,
    offers: str,
    has_house: bool,
    challenges_done: int,
    suggestions: list[dict],
) -> str:
    """
    Player profile view template.
    """
    house_str = "🏠 _construída_" if has_house else "🏠 _ainda não construída_"
    suggestion_lines = "\n".join(f"  ▸ _\"{s['cmd']}\"_ — {s['desc']}" for s in suggestions[:3])

    parts = [
        SEP,
        f"👤 *{nickname.upper()}* · Nível {level}",
        SEP,
        f"🪙 {seeds}  ·  📍 {current_room}  ·  📅 {since}",
        "",
        f"_{essence}_" if essence else "",
        "",
        f"🏷 Traços: {traits}" if traits else "",
        f"🎯 Busca: {seeks}" if seeks else "",
        f"🤝 Oferece: {offers}" if offers else "",
        "",
        house_str,
        f"⚔️ Desafios: {challenges_done} concluídos",
    ]

    if suggestion_lines:
        parts += [
            "",
            f"💡 *Ações:*",
            suggestion_lines,
        ]

    parts.append(SEP)
    # Filter out empty strings for cleaner output
    return "\n".join(p for p in parts if p is not None)


def format_challenge(
    challenge_type: str,
    instruction: str,
    reward_seeds: int,
) -> str:
    """
    Challenge template.
    """
    type_emoji = {
        "reflexão": "🧠",
        "perspectiva": "👁",
        "sentimento": "💜",
        "história": "📖",
        "troca": "🤝",
        "decoração": "🎨",
    }.get(challenge_type, "⚔️")

    parts = [
        SEP,
        f"{type_emoji} *DESAFIO* · {challenge_type.capitalize()}",
        SEP,
        f"🏆 Recompensa: 🪙 {reward_seeds} sementes",
        "",
        f"> _{instruction}_",
        "",
        f"💬 _Responda para completar_",
        f"🚫 _\"pular\"_ — ignorar desafio",
        SEP,
    ]
    return "\n".join(parts)


def format_room_list(
    rooms: list[dict],
    player_room: str,
) -> str:
    """
    List of available rooms for exploration.
    rooms: [{"emoji": "📝", "name": "Cantinho dos Versos", "subtitle": "Poesias e poemas"}, ...]
    """
    room_lines = []
    for r in rooms:
        marker = " ◀ _você está aqui_" if r.get("path") == player_room else ""
        room_lines.append(f"  {r.get('emoji', '🚪')} *{r['name']}*{marker}")
        room_lines.append(f"     _{r['subtitle']}_")

    parts = [
        SEP,
        "🗺 *EXPLORAR SALAS*",
        SEP,
        "",
        "\n".join(room_lines),
        "",
        "💬 _Digite o nome da sala para ir_",
        SEP,
    ]
    return "\n".join(parts)


def format_welcome() -> str:
    """
    First-time welcome message before onboarding.
    """
    return "\n".join([
        SEP,
        "🌱 *BEM-VINDO AO MUD-AI*",
        "_Um mundo feito de palavras e conexões_",
        SEP,
        "",
        "Olá! Você acaba de entrar num mundo",
        "onde histórias se cruzam e pessoas",
        "se conectam pela essência.",
        "",
        "Antes de explorar, me conta um",
        "pouquinho sobre você? São 5 perguntas",
        "rápidas para criar seu personagem. 🎭",
        "",
        "Vamos lá?",
        "",
        "💬 _Digite qualquer coisa para começar_",
        SEP,
    ])


def format_error(message: str) -> str:
    """Generic error message."""
    return "\n".join([
        SEP,
        "⚠️ *OPS*",
        SEP,
        "",
        message,
        "",
        "💬 _\"ajuda\"_ — ver comandos",
        SEP,
    ])
