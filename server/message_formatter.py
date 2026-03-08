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
        parts.append(f"\n🌐 *Live Dashboard (Jogue via Web):*\n{profile_url}")

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
        parts.append(f"\n🌐 *Live Dashboard (Jogue via Web):*\n{profile_url}")

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
    structured_summary: str,
    structured_worlds: list[str],
    structured_strengths: list[str],
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

    if structured_summary:
        parts.append(f"🧠 {structured_summary}")

    worlds_preview = ", ".join(structured_worlds[:2]) if structured_worlds else ""
    strengths_preview = ", ".join(structured_strengths[:2]) if structured_strengths else ""
    if worlds_preview:
        parts.append(f"🌍 Afinidades: {worlds_preview}")
    if strengths_preview:
        parts.append(f"✨ Forças: {strengths_preview}")
    if structured_summary or worlds_preview or strengths_preview:
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


def format_social_matches(matches: list[dict], profile_url: str = "") -> str:
    lines = []
    for match in matches[:5]:
        room = match.get("current_room", "")
        room_label = room.split(".")[-1].replace("_", " ").title() if room else "Em trânsito"
        room_hint = " · mesma sala" if match.get("same_room") else f" · {room_label}"
        favorite_hint = " ⭐" if match.get("is_favorite") else ""
        useful_hint = " 🛠" if match.get("is_useful") else ""
        confirmed_hint = " 🤝" if match.get("is_confirmed") else ""
        mutual_hint = " 🫂" if match.get("is_mutual") else ""
        if match.get("is_new"):
            state_hint = " · nova"
        elif match.get("seen_count", 0):
            state_hint = f" · vista {match.get('seen_count')}x"
        else:
            state_hint = ""
        lines.append(f"  ▸ *{match.get('nickname', 'Viajante')}*{favorite_hint}{useful_hint}{confirmed_hint}{mutual_hint}{room_hint}{state_hint}")
        seek_matches = match.get("seek_matches", [])[:2]
        offer_matches = match.get("offer_matches", [])[:2]
        shared_signals = match.get("shared_signals", [])[:2]
        complementary_signals = match.get("complementary_signals", [])[:2]
        if seek_matches:
            lines.append(f"     _pode te oferecer:_ {', '.join(seek_matches)}")
        if offer_matches:
            lines.append(f"     _pode buscar de você:_ {', '.join(offer_matches)}")
        if shared_signals:
            lines.append(f"     _afinidades:_ {', '.join(shared_signals)}")
        if complementary_signals:
            lines.append(f"     _te complementa em:_ {', '.join(complementary_signals)}")
        tags = match.get("manual_tags", [])[:4]
        note = str(match.get("private_note", "") or "").strip()
        if tags:
            lines.append(f"     _tags:_ {', '.join(tags)}")
        if note:
            lines.append(f"     _nota:_ {note[:120]}")

    if not lines:
        lines.append("  ▸ Ainda não achei conexões fortes com base no seu perfil.")
        lines.append("     _Tente enriquecer o que você busca e oferece no onboarding futuro._")

    parts = [
        SEP,
        "🤝 *CONEXÕES SUGERIDAS*",
        SEP,
        "",
        "Com base no que você busca e no que pode oferecer:",
        "",
        "\n".join(lines),
        "",
        "💬 _Use isso para puxar conversa, encontrar ajuda ou oferecer algo útil._",
    ]

    if profile_url:
        parts.append(f"\n🔗 {profile_url}")

    parts.append(SEP)
    return "\n".join(parts)


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


def format_social_match_history(history: list[dict], profile_url: str = "") -> str:
    lines = []
    for item in history[:8]:
        room = item.get("current_room", "")
        room_label = room.split(".")[-1].replace("_", " ").title() if room else "Em trânsito"
        room_hint = "mesma sala" if item.get("same_room") else room_label
        favorite_hint = " ⭐" if item.get("is_favorite") else ""
        useful_hint = " 🛠" if item.get("is_useful") else ""
        confirmed_hint = " 🤝" if item.get("is_confirmed") else ""
        mutual_hint = " 🫂" if item.get("is_mutual") else ""
        lines.append(
            f"  ▸ *{item.get('nickname', 'Viajante')}*{favorite_hint}{useful_hint}{confirmed_hint}{mutual_hint} · score {item.get('score', 0)} · vista {item.get('seen_count', 0)}x"
        )
        lines.append(f"     _{room_hint}_")
        seek_matches = item.get("seek_matches", [])[:2]
        offer_matches = item.get("offer_matches", [])[:2]
        shared_signals = item.get("shared_signals", [])[:2]
        complementary_signals = item.get("complementary_signals", [])[:2]
        if seek_matches:
            lines.append(f"     _te oferece:_ {', '.join(seek_matches)}")
        if offer_matches:
            lines.append(f"     _busca de você:_ {', '.join(offer_matches)}")
        if shared_signals:
            lines.append(f"     _afinidades:_ {', '.join(shared_signals)}")
        if complementary_signals:
            lines.append(f"     _te complementa em:_ {', '.join(complementary_signals)}")
        tags = item.get("manual_tags", [])[:4]
        note = str(item.get("private_note", "") or "").strip()
        if tags:
            lines.append(f"     _tags:_ {', '.join(tags)}")
        if note:
            lines.append(f"     _nota:_ {note[:120]}")

    if not lines:
        lines.append("  ▸ Você ainda não tem histórico de conexões persistido.")
        lines.append("     _Use /conexoes para começar a construir sua memória social._")

    parts = [
        SEP,
        "🧠 *MEMÓRIA SOCIAL*",
        SEP,
        "",
        "Seu histórico recente de conexões sugeridas:",
        "",
        "\n".join(lines),
        "",
        "💬 _Use /conexoes para renovar ou descobrir novas afinidades._",
    ]

    if profile_url:
        parts.append(f"\n🔗 {profile_url}")

    parts.append(SEP)
    return "\n".join(parts)


def format_social_favorite_saved(match_meta: dict, profile_url: str = "") -> str:
    nickname = match_meta.get("nickname", "Viajante")
    parts = [
        SEP,
        "⭐ *CONEXÃO FAVORITADA*",
        SEP,
        "",
        f"Você marcou *{nickname}* como favorita.",
        "",
        "💬 _Use /conexoes-favoritas para revisar seus vínculos prioritários._",
    ]
    if profile_url:
        parts.append(f"\n🔗 {profile_url}")
    parts.append(SEP)
    return "\n".join(parts)


def format_social_useful_saved(match_meta: dict, profile_url: str = "") -> str:
    nickname = match_meta.get("nickname", "Viajante")
    parts = [
        SEP,
        "🛠 *CONEXÃO ÚTIL SALVA*",
        SEP,
        "",
        f"Você marcou *{nickname}* como uma conexão útil.",
        "",
        "💬 _Use /conexoes-uteis para revisar quem mais te ajuda a agir._",
    ]
    if profile_url:
        parts.append(f"\n🔗 {profile_url}")
    parts.append(SEP)
    return "\n".join(parts)


def format_social_confirmed_saved(match_meta: dict, profile_url: str = "") -> str:
    nickname = match_meta.get("nickname", "Viajante")
    parts = [
        SEP,
        "🤝 *CONEXÃO CONFIRMADA*",
        SEP,
        "",
        f"Você confirmou *{nickname}* como um vínculo social real.",
        "",
        "💬 _Use /conexoes-confirmadas para revisar suas conexões já reconhecidas._",
    ]
    if profile_url:
        parts.append(f"\n🔗 {profile_url}")
    parts.append(SEP)
    return "\n".join(parts)


def format_social_note_saved(match_meta: dict, profile_url: str = "") -> str:
    nickname = match_meta.get("nickname", "Viajante")
    note = str(match_meta.get("private_note", "") or "").strip()
    parts = [
        SEP,
        "📝 *NOTA SOCIAL SALVA*",
        SEP,
        "",
        f"Você registrou uma nota privada sobre *{nickname}*.",
        "",
        f"_{note[:180]}_" if note else "_Sem conteúdo de nota._",
        "",
        "💬 _Use /historico-conexoes para revisar sua memória social enriquecida._",
    ]
    if profile_url:
        parts.append(f"\n🔗 {profile_url}")
    parts.append(SEP)
    return "\n".join(parts)


def format_social_tags_saved(match_meta: dict, profile_url: str = "") -> str:
    nickname = match_meta.get("nickname", "Viajante")
    tags = match_meta.get("manual_tags", [])[:8]
    tags_text = ", ".join(tags) if tags else "sem tags"
    parts = [
        SEP,
        "🏷 *TAGS SOCIAIS SALVAS*",
        SEP,
        "",
        f"Você atualizou as tags manuais de *{nickname}*.",
        "",
        f"_{tags_text}_",
        "",
        "💬 _Essas tags passam a viver na sua memória social persistida._",
    ]
    if profile_url:
        parts.append(f"\n🔗 {profile_url}")
    parts.append(SEP)
    return "\n".join(parts)


def format_favorite_social_matches(history: list[dict], profile_url: str = "") -> str:
    lines = []
    for item in history[:8]:
        room = item.get("current_room", "")
        room_label = room.split(".")[-1].replace("_", " ").title() if room else "Em trânsito"
        room_hint = "mesma sala" if item.get("same_room") else room_label
        lines.append(
            f"  ▸ *{item.get('nickname', 'Viajante')}* · score {item.get('score', 0)} · vista {item.get('seen_count', 0)}x"
        )
        lines.append(f"     _{room_hint}_")
        tags = item.get("manual_tags", [])[:4]
        if tags:
            lines.append(f"     _tags:_ {', '.join(tags)}")

    if not lines:
        lines.append("  ▸ Você ainda não marcou conexões favoritas.")
        lines.append("     _Use /favoritar-conexao NOME depois de ver /conexoes ou /historico-conexoes._")

    parts = [
        SEP,
        "⭐ *CONEXÕES FAVORITAS*",
        SEP,
        "",
        "Seus vínculos sociais priorizados:",
        "",
        "\n".join(lines),
    ]
    if profile_url:
        parts.append(f"\n🔗 {profile_url}")
    parts.append(SEP)
    return "\n".join(parts)


def format_useful_social_matches(history: list[dict], profile_url: str = "") -> str:
    lines = []
    for item in history[:8]:
        room = item.get("current_room", "")
        room_label = room.split(".")[-1].replace("_", " ").title() if room else "Em trânsito"
        room_hint = "mesma sala" if item.get("same_room") else room_label
        lines.append(
            f"  ▸ *{item.get('nickname', 'Viajante')}* · score {item.get('score', 0)} · vista {item.get('seen_count', 0)}x"
        )
        lines.append(f"     _{room_hint}_")
        tags = item.get("manual_tags", [])[:4]
        if tags:
            lines.append(f"     _tags:_ {', '.join(tags)}")

    if not lines:
        lines.append("  ▸ Você ainda não marcou conexões úteis.")
        lines.append("     _Use /marcar-conexao-util NOME depois de ver /conexoes ou /historico-conexoes._")

    parts = [
        SEP,
        "🛠 *CONEXÕES ÚTEIS*",
        SEP,
        "",
        "Seus vínculos sociais mais acionáveis:",
        "",
        "\n".join(lines),
    ]
    if profile_url:
        parts.append(f"\n🔗 {profile_url}")
    parts.append(SEP)
    return "\n".join(parts)


def format_confirmed_social_matches(history: list[dict], profile_url: str = "") -> str:
    lines = []
    for item in history[:8]:
        room = item.get("current_room", "")
        room_label = room.split(".")[-1].replace("_", " ").title() if room else "Em trânsito"
        room_hint = "mesma sala" if item.get("same_room") else room_label
        mutual_hint = " · recíproca" if item.get("is_mutual") else ""
        lines.append(
            f"  ▸ *{item.get('nickname', 'Viajante')}*{mutual_hint} · score {item.get('score', 0)} · vista {item.get('seen_count', 0)}x"
        )
        lines.append(f"     _{room_hint}_")
        tags = item.get("manual_tags", [])[:4]
        note = str(item.get("private_note", "") or "").strip()
        if tags:
            lines.append(f"     _tags:_ {', '.join(tags)}")
        if note:
            lines.append(f"     _nota:_ {note[:120]}")

    if not lines:
        lines.append("  ▸ Você ainda não confirmou conexões sociais.")
        lines.append("     _Use /confirmar-conexao NOME depois de ver /conexoes ou /historico-conexoes._")

    parts = [
        SEP,
        "🤝 *CONEXÕES CONFIRMADAS*",
        SEP,
        "",
        "Seus vínculos sociais já reconhecidos:",
        "",
        "\n".join(lines),
    ]
    if profile_url:
        parts.append(f"\n🔗 {profile_url}")
    parts.append(SEP)
    return "\n".join(parts)


def format_mutual_social_matches(history: list[dict], profile_url: str = "") -> str:
    lines = []
    for item in history[:8]:
        room = item.get("current_room", "")
        room_label = room.split(".")[-1].replace("_", " ").title() if room else "Em trânsito"
        room_hint = "mesma sala" if item.get("same_room") else room_label
        lines.append(
            f"  ▸ *{item.get('nickname', 'Viajante')}* · score {item.get('score', 0)} · vista {item.get('seen_count', 0)}x"
        )
        lines.append(f"     _{room_hint}_")
        tags = item.get("manual_tags", [])[:4]
        if tags:
            lines.append(f"     _tags:_ {', '.join(tags)}")

    if not lines:
        lines.append("  ▸ Você ainda não tem conexões mútuas.")
        lines.append("     _Uma conexão mútua nasce quando os dois lados usam /confirmar-conexao._")

    parts = [
        SEP,
        "🫂 *CONEXÕES MÚTUAS*",
        SEP,
        "",
        "Vínculos confirmados pelos dois lados:",
        "",
        "\n".join(lines),
    ]
    if profile_url:
        parts.append(f"\n🔗 {profile_url}")
    parts.append(SEP)
    return "\n".join(parts)


def format_welcome(first_question: str = "", first_hint: str = "") -> str:
    """
    First-time welcome message before onboarding.
    Includes the first question directly to avoid an extra step.
    """
    parts = [
        SEP,
        "🌱 *BEM-VINDO AO MUD-AI*",
        "_Um mundo de texto, conexões e descobertas_",
        SEP,
        "",
        "Opa! Você acaba de entrar num mundo",
        "onde pessoas se conectam de verdade",
        "através de texto e criatividade.",
        "",
        "Você começa com *50 🪙 sementes*",
        "e pode ganhar mais explorando,",
        "conversando e interagindo!",
        "",
        DIV,
        "📋 *CRIANDO SEU PERFIL* (1/5)",
        DIV,
        "",
    ]

    if first_question:
        parts.append(first_question)
    else:
        parts.append("Antes de tudo, *como quer ser chamado* aqui dentro?")
        parts.append("\nPode ser um apelido, um nome inventado, ou seu nome real.")

    if first_hint:
        parts.append(f"\n{first_hint}")
    else:
        parts.append("\n✨ _Exemplos: Luna, Eco, seu nome..._")

    parts += [
        "",
        SEP,
    ]
    return "\n".join(parts)


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
