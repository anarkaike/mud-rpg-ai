"""
MUD-AI — WhatsApp Message Formatter v2.1.

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
    seeds_change: int = 0,
    badge: str = None,
    profile_url: str = "",
) -> str:
    """
    Standard room view template.

    exits: [{"direction": "norte", "name": "Praça das Trocas"}, ...]
    suggestions: [{"cmd": "olhar", "desc": "ver detalhes"}, ...]
    """
    seeds_str = f"🪙 {seeds}"
    if seeds_change > 0:
        seeds_str += f" (+{seeds_change})"
    stats = f"{seeds_str}  ·  ⭐ Nv.{level}"
    if players_here > 0:
        stats += f"  ·  👥 {players_here}"

    exit_lines = "\n".join(f"  ▸ {e['direction']} → {e['name']}" for e in exits)
    suggestion_lines = "\n".join(f"  ▸ _\"{s['cmd']}\"_ — {s['desc']}" for s in suggestions[:3])

    parts = [
        SEP,
        f"🌱 *{room_name.upper()}*",
        f"_{room_subtitle}_" if room_subtitle else "",
        SEP,
        stats,
        "",
        f"> {narrative}",
    ]

    if badge:
        parts.append(f"\n🏅 _{badge}_")

    parts += [
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

    if profile_url:
        parts.append(f"🔗 {profile_url}")

    parts.append(SEP)
    return "\n".join(p for p in parts if p is not None)


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
    profile_url: str = "",
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
        parts.append(f"\n🏅 _{badge}_")

    if suggestion_lines:
        parts += [
            "",
            f"💡 *E agora?*",
            suggestion_lines,
        ]

    if breadcrumb:
        parts.append(f"\n🗺 {breadcrumb}")

    if profile_url:
        parts.append(f"🔗 {profile_url}")

    parts.append(SEP)
    return "\n".join(p for p in parts if p is not None)


def format_onboarding_step(
    step: int,
    total: int,
    title: str,
    question: str,
    hint: str = "",
    seeds_change: int = 0,
) -> str:
    """
    Onboarding step template.
    """
    parts = [
        SEP,
        f"📋 *{title.upper()}* ({step}/{total})",
        SEP,
    ]

    if seeds_change > 0:
        parts.append(f"🪙 +{seeds_change} sementes ganhas!")

    parts += [
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
    badges: str,
    seeks: str,
    offers: str,
    rooms_visited: int,
    decorations: int,
    suggestions: list[dict],
    profile_url: str = "",
) -> str:
    """
    Player profile view template.
    """
    suggestion_lines = "\n".join(f"  ▸ _\"{s['cmd']}\"_ — {s['desc']}" for s in suggestions[:3])

    parts = [
        SEP,
        f"👤 *{nickname.upper()}* · Nível {level}",
        SEP,
        f"🪙 {seeds}  ·  📍 {current_room}  ·  📅 {since}",
        "",
    ]

    if essence:
        parts.append(f"_{essence}_")
        parts.append("")

    parts += [
        f"🏅 Badges: {badges}",
        f"🗺 Salas visitadas: {rooms_visited}",
        f"📝 Decorações: {decorations}",
    ]

    if seeks:
        parts.append(f"🎯 Busca: {seeks}")
    if offers:
        parts.append(f"🤝 Oferece: {offers}")

    if suggestion_lines:
        parts += [
            "",
            f"💡 *Ações:*",
            suggestion_lines,
        ]

    if profile_url:
        parts.append(f"\n🔗 {profile_url}")

    parts.append(SEP)
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
    profile_url: str = "",
) -> str:
    """
    List of available rooms for exploration.
    """
    room_lines = []
    for r in rooms:
        marker = " ◀ _aqui_" if r.get("path") == player_room else ""
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
    ]

    if profile_url:
        parts.append(f"🔗 {profile_url}")

    parts.append(SEP)
    return "\n".join(parts)


def format_welcome() -> str:
    """
    First-time welcome message before onboarding.
    """
    return "\n".join([
        SEP,
        "🌱 *BEM-VINDO AO MUD-AI*",
        "_Um mundo de texto, conexões e descobertas_",
        SEP,
        "",
        "Opa! Você acaba de entrar num mundo",
        "onde pessoas se conectam de verdade",
        "através de texto e criatividade.",
        "",
        "Você começa com *50 🪙 sementes**",
        "e pode ganhar mais explorando,",
        "conversando e interagindo!",
        "",
        "Mas antes, me conta um pouco sobre",
        "você? São 5 perguntas rápidas. 🎭",
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
        "💬 _\"ajuda\"_ ou _/ajuda_ — ver comandos",
        SEP,
    ])
