"""
MUD-AI — Onboarding System v3.0.

5-step conversational flow to capture player essence.
Starts with 50 seeds, awards bonus on completion.
"""

import hashlib

from . import database as db
from . import message_formatter as fmt
from . import world_state
from .ai_client import chat_completion_json


INITIAL_SEEDS = 50

TOTAL_ONBOARDING_STEPS = 5
FIXED_ONBOARDING_CATEGORY_KEYS = [
    "nickname",
    "current_need",
    "profession_vocation",
]
ADAPTIVE_ONBOARDING_CATEGORY_KEYS = [
    "connection_style",
    "world_affinity",
    "natural_role",
    "offer_signature",
]

ONBOARDING_CATEGORIES = [
    {
        "step": 1,
        "key": "nickname",
        "title": "CRIANDO SEU PERFIL",
        "field": "nickname",
        "mode": "fixed",
        "variants": [
            {
                "id": "nick_direct",
                "tones": ["clear", "warm"],
                "signals": ["identity", "entry"],
                "question": "Antes de tudo, *como você quer ser chamado* aqui dentro?",
                "hint": "✨ _Pode ser apelido, nome inventado ou seu nome real._",
            },
            {
                "id": "nick_light",
                "tones": ["light", "warm"],
                "signals": ["identity", "entry"],
                "question": "Pra eu te receber direito: *qual nome faz sentido pra você aqui*?",
                "hint": "🌱 _Vale um nome seu, um apelido ou algo que combine com você._",
            },
            {
                "id": "nick_identity",
                "tones": ["reflective", "clear"],
                "signals": ["identity", "entry"],
                "question": "Se este mundo fosse te chamar de um jeito que combine com você, *que nome seria*?",
                "hint": "💬 _Escolha algo simples e natural para você responder e ser lembrado._",
            },
        ],
    },
    {
        "step": 2,
        "key": "current_need",
        "title": "O QUE VOCÊ BUSCA",
        "field": "seeks",
        "mode": "fixed",
        "variants": [
            {
                "id": "need_missing",
                "tones": ["clear", "reflective"],
                "signals": ["desire", "moment", "connection"],
                "question": "Legal, *{nickname}*. O que mais tem faltado pra você ultimamente: conexão, leveza, direção, profundidade, acolhimento, aventura ou outra coisa?",
                "hint": "🎯 _Se quiser, responda em uma frase curta._",
            },
            {
                "id": "need_phase",
                "tones": ["practical", "clear"],
                "signals": ["desire", "moment", "practicality"],
                "question": "Me ajuda a te entender melhor: *o que você mais está buscando nesta fase da vida*?",
                "hint": "🧭 _Pode ser companhia, clareza, descanso, troca, inspiração, diversão ou algo bem seu._",
            },
            {
                "id": "need_arrival",
                "tones": ["warm", "light"],
                "signals": ["desire", "moment", "warmth"],
                "question": "Se você chegou aqui procurando alguma coisa, *o que seria mais gostoso encontrar*?",
                "hint": "💛 _Pode falar de conversa, presença, ideias, ajuda, novidade ou paz._",
            },
        ],
    },
    {
        "step": 3,
        "key": "connection_style",
        "title": "SEU JEITO DE SE CONECTAR",
        "field": "essence",
        "mode": "adaptive",
        "variants": [
            {
                "id": "style_presence",
                "tones": ["clear", "warm"],
                "signals": ["connection_style", "affective", "intensity"],
                "question": "E no contato com alguém, *que tipo de presença mais te atrai*: leve e divertida, profunda e emocional, inteligente e instigante, prática e objetiva, provocante e intensa, sensível e bonita ou outra?",
                "hint": "🤝 _Responda do seu jeito; não precisa escolher só uma._",
            },
            {
                "id": "style_true_self",
                "tones": ["reflective", "creative"],
                "signals": ["connection_style", "identity", "energy"],
                "question": "Quando você se sente mais você, normalmente está *criando, cuidando, explorando ideias, resolvendo problemas, vivendo algo intenso, se conectando com alguém* ou de outro jeito?",
                "hint": "✨ _Isso ajuda a entender seu tom e sua energia._",
            },
            {
                "id": "style_conversation",
                "tones": ["practical", "clear"],
                "signals": ["connection_style", "conversation", "tone"],
                "question": "Pra você se engajar de verdade, *a conversa ou a experiência precisa ter mais o quê*?",
                "hint": "💬 _Humor, profundidade, inteligência, acolhimento, tensão, beleza, objetividade... o que pesa mais?_",
            },
        ],
    },
    {
        "step": 4,
        "key": "profession_vocation",
        "title": "SEU MUNDO E SUA VOCAÇÃO",
        "field": "profession_vocation",
        "mode": "fixed",
        "variants": [
            {
                "id": "work_calling",
                "tones": ["clear", "reflective"],
                "signals": ["profession", "vocation", "context"],
                "question": "Hoje você atua em que área, e *em qual área sente que mora sua vocação ou inclinação mais verdadeira* — mesmo que ainda não viva disso?",
                "hint": "🛠 _Pode responder algo como: trabalho com X, mas minha inclinação é Y._",
            },
            {
                "id": "work_world",
                "tones": ["practical", "technical"],
                "signals": ["profession", "vocation", "technical_context"],
                "question": "Quero mapear seu mundo real também: *com o que você trabalha hoje, e com o que gostaria de trabalhar se seguisse mais sua natureza*?",
                "hint": "📌 _Isso ajuda a entender seu repertório, ritmo e linguagem._",
            },
            {
                "id": "work_identity",
                "tones": ["warm", "reflective"],
                "signals": ["profession", "vocation", "social_context"],
                "question": "No mundo de fora, *qual é sua área hoje*? E por dentro, *que tipo de trabalho ou expressão parece combinar mais com quem você é*?",
                "hint": "🌍 _Vale profissão, nicho, ofício, estudo ou transição._",
            },
        ],
    },
    {
        "step": 4,
        "key": "world_affinity",
        "title": "OS MUNDOS ONDE VOCÊ SE SENTE EM CASA",
        "field": "world_affinity",
        "mode": "adaptive",
        "variants": [
            {
                "id": "world_domains",
                "tones": ["clear", "practical"],
                "signals": ["world", "technicality", "creativity", "humanity"],
                "question": "Você se sente mais em casa em quais mundos: tecnologia, arte, negócios, cuidado, educação, espiritualidade, comunicação, pesquisa, relações humanas ou uma mistura?",
                "hint": "🌐 _Pode citar os que mais combinam com seu jeito e repertório._",
            },
            {
                "id": "world_language",
                "tones": ["reflective", "clear"],
                "signals": ["world", "language", "social_context"],
                "question": "Que tipo de ambiente ou linguagem costuma combinar mais com você: algo mais técnico, humano, criativo, intelectual, sensível, estratégico ou misturado?",
                "hint": "🧩 _Isso ajuda a calibrar o tom e o tipo de experiência que mais faz sentido pra você._",
            },
        ],
    },
    {
        "step": 4,
        "key": "natural_role",
        "title": "SEU PAPEL NATURAL",
        "field": "natural_role",
        "mode": "adaptive",
        "variants": [
            {
                "id": "role_groups",
                "tones": ["clear", "warm"],
                "signals": ["role", "support", "leadership", "creation"],
                "question": "Em grupos, conversas ou projetos, qual papel você tende a ocupar mais naturalmente: quem acolhe, quem cria, quem organiza, quem provoca, quem lidera, quem resolve ou outro?",
                "hint": "🎭 _Se mais de um combinar com você, pode dizer._",
            },
            {
                "id": "role_presence",
                "tones": ["reflective", "practical"],
                "signals": ["role", "presence", "energy"],
                "question": "Quando sua presença faz diferença, normalmente ela aparece mais como cuidado, clareza, visão, humor, direção, profundidade, técnica ou movimento?",
                "hint": "🫶 _Pense no que costuma emergir de você sem muito esforço._",
            },
        ],
    },
    {
        "step": 5,
        "key": "offer_signature",
        "title": "SUA PRIMEIRA MARCA",
        "field": "offers",
        "mode": "adaptive",
        "variants": [
            {
                "id": "offer_mark",
                "tones": ["clear", "warm"],
                "signals": ["offer", "presence", "contribution"],
                "question": "Pra fechar: *o que você sente que pode trazer pra uma boa conversa ou pra este mundo*? Pode ser escuta, humor, visão, sensibilidade, repertório, técnica, presença...",
                "hint": "📝 _Se quiser, responda como uma frase curta — ela vai virar sua primeira marca na Recepção._",
            },
            {
                "id": "offer_signature",
                "tones": ["reflective", "creative"],
                "signals": ["offer", "signature", "contribution"],
                "question": "Última, *{nickname}*: quando alguém cruza seu caminho, o que você costuma deixar de melhor?",
                "hint": "🌱 _Pode responder como se fosse sua assinatura em uma parede: algo curto e verdadeiro._",
            },
            {
                "id": "offer_value",
                "tones": ["practical", "clear"],
                "signals": ["offer", "value", "presence"],
                "question": "Pra quem encontrar você aqui, *o que existe de valioso na sua presença*?",
                "hint": "🤲 _Pode ser ajuda, escuta, conhecimento, humor, direção, arte, companhia ou outra qualidade sua._",
            },
        ],
    },
]


AI_ONBOARDING_PROMPT = """Você é CultivIA, a guia do MUD-AI.
Você está conduzindo o onboarding de um novo jogador. Seu objetivo é fazer perguntas claras, humanas e variadas, mantendo o tom casual e direto do jogo.

DADOS DO PASSO:
- Passo Atual: {step}/{total}
- Categoria: {category}
- Objetivo: {title}
- Pergunta Base: {question_base}
- Dica/Sugestão Base: {hint_base}
- Apelido do Jogador: {nickname}
- Tons Preferidos: {tones}
- Respostas Anteriores: {context}

REGRAS ESTRITAS:
- Preserve EXATAMENTE a essência da pergunta base. Você só pode mudar a forma, não o objetivo semântico.
- Faça a pergunta soar natural, clara e curta. Evite poesia excessiva, metáforas rebuscadas ou tom místico.
- Adapte levemente o vocabulário aos tons preferidos e às respostas anteriores.
- Não seja invasiva. Não mencione trauma, sexualidade, religião ou política, a menos que o jogador já tenha trazido isso.
- A pergunta deve caber em 1-3 frases curtas.
- A dica deve ser objetiva, útil e concisa.
- Responda OBRIGATORIAMENTE em JSON válido com duas chaves:
  "question": O texto da sua pergunta usando formatação Markdown de WhatsApp (*negrito*, _itálico_). 1-3 frases curtas.
  "hint": Uma dica curta. Comece com 1 emoji e _itálico_.

Não gere markdown ````json em volta, apenas o JSON puro, começando com {{. 
"""


STRUCTURED_PROFILE_PROMPT = """Você é um analisador de perfil de jogador para o MUD-AI.
Seu trabalho é ler as respostas finais do onboarding e sintetizar um perfil estruturado, útil para personalização do jogo.

REGRAS ESTRITAS:
- Seja inferencial, mas conservador. Não invente fatos específicos.
- Não mencione trauma, sexualidade, religião ou política a menos que isso esteja explicitamente no texto.
- Normalize em linguagem curta e útil.
- Se algo não estiver claro, use lista vazia ou string vazia.
- Responda OBRIGATORIAMENTE em JSON válido com estas chaves:
  "summary": frase curta em 1 linha resumindo a essência atual da pessoa.
  "current_moment": lista curta com 1-3 temas do que ela parece buscar/viver agora.
  "relationship_style": lista curta com 1-3 traços de como tende a se conectar.
  "worlds": lista curta com 1-4 mundos/áreas com os quais parece ter afinidade.
  "strengths": lista curta com 1-4 forças que ela parece trazer.
  "vocation_vector": frase curta sobre vocação/inclinação, se aparecer.
  "communication_style": lista curta com 1-3 instruções de tom úteis para a IA falar com essa pessoa.

Não gere markdown ````json em volta, apenas o JSON puro, começando com {{.
"""


async def _generate_ai_question(step_data: dict, nickname: str, meta: dict) -> dict:
    """Generate a varied onboarding question and hint using AI."""
    context = _build_onboarding_context(meta)
    tones = ", ".join(_infer_preferred_tones(meta))

    prompt = AI_ONBOARDING_PROMPT.format(
        step=step_data["step"],
        total=TOTAL_ONBOARDING_STEPS,
        category=step_data["key"],
        title=step_data["title"],
        question_base=step_data["question"],
        hint_base=step_data["hint"],
        nickname=nickname or "viajante",
        tones=tones,
        context=context or "Iniciando agora."
    )

    try:
        varied = await chat_completion_json(
            system_prompt=prompt,
            user_message=f"Gere a pergunta para o passo {step_data['step']} em JSON",
            temperature=0.65,
            max_tokens=200
        )
        return varied
    except Exception as e:
        print(f"⚠️ AI Onboarding variation failed: {e}")
        return {
            "question": step_data["question"].replace("{nickname}", nickname or "viajante"),
            "hint": step_data["hint"]
        }


def _build_onboarding_context(meta: dict) -> str:
    fields = [
        "nickname",
        "seeks",
        "essence",
        "profession_vocation",
        "offers",
    ]
    lines = []
    for field in fields:
        value = meta.get(field)
        if value:
            lines.append(f"{field}: {value}")
    return "\n".join(lines)


def _infer_preferred_tones(meta: dict) -> list[str]:
    text = " ".join(
        str(meta.get(field, ""))
        for field in ["seeks", "essence", "profession_vocation", "offers"]
    ).lower()

    scores = {
        "clear": 2,
        "warm": 1,
        "practical": 0,
        "reflective": 0,
        "creative": 0,
        "technical": 0,
        "light": 0,
    }

    practical_terms = ["trabalho", "carreira", "objetivo", "direção", "resultado", "negócio", "mercado", "processo"]
    reflective_terms = ["sentido", "conexão", "profundidade", "verdade", "essência", "alma", "presença"]
    creative_terms = ["arte", "música", "escrita", "criar", "criatividade", "poesia", "estética", "sensível"]
    technical_terms = ["tecnologia", "produto", "dados", "código", "software", "engenharia", "ia", "digital"]
    light_terms = ["leveza", "diversão", "humor", "rir", "curtir", "solto"]
    warm_terms = ["acolhimento", "cuidar", "escuta", "ajudar", "afeto", "companhia", "presença"]

    for term in practical_terms:
        if term in text:
            scores["practical"] += 1
    for term in reflective_terms:
        if term in text:
            scores["reflective"] += 1
    for term in creative_terms:
        if term in text:
            scores["creative"] += 1
    for term in technical_terms:
        if term in text:
            scores["technical"] += 1
    for term in light_terms:
        if term in text:
            scores["light"] += 1
    for term in warm_terms:
        if term in text:
            scores["warm"] += 1

    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [tone for tone, score in ordered[:3] if score > 0] or ["clear", "warm"]


def _get_step_category(step: int) -> dict:
    return ONBOARDING_CATEGORIES[step - 1]


def _get_category_by_key(category_key: str) -> dict:
    for category in ONBOARDING_CATEGORIES:
        if category["key"] == category_key:
            return category
    raise KeyError(f"Unknown onboarding category: {category_key}")


def _get_onboarding_plan(meta: dict) -> list[str]:
    plan = list(meta.get("onboarding_plan", []))
    if not plan:
        return FIXED_ONBOARDING_CATEGORY_KEYS[:]
    return plan


def _build_signal_scores(meta: dict) -> dict:
    text = " ".join(
        str(meta.get(field, ""))
        for field in [
            "seeks",
            "essence",
            "profession_vocation",
            "offers",
            "world_affinity",
            "natural_role",
        ]
    ).lower()

    keyword_map = {
        "connection": ["conex", "companh", "presença", "troca", "gente", "relacion", "escuta"],
        "technicality": ["tecnologia", "código", "software", "dados", "produto", "digital", "engenharia", "ia"],
        "creativity": ["arte", "música", "escrita", "criar", "design", "estética", "sensível"],
        "humanity": ["cuidado", "acolh", "ajuda", "escuta", "afeto", "humano", "família"],
        "leadership": ["lider", "guiar", "direção", "organiza", "decidir", "comandar"],
        "support": ["cuid", "ajud", "acolh", "ouvir", "escuta", "amparo"],
        "intensity": ["intenso", "provoca", "tesão", "ousad", "profund", "forte"],
        "reflection": ["sentido", "verdade", "essência", "alma", "filos", "profund", "reflex"],
        "practicality": ["objetivo", "resultado", "prático", "resolver", "processo", "trabalho", "carreira"],
    }

    scores = {key: 0 for key in keyword_map}
    for signal, keywords in keyword_map.items():
        for keyword in keywords:
            if keyword in text:
                scores[signal] += 1
    return scores


def _build_profile_signals(meta: dict) -> dict:
    raw_scores = _build_signal_scores(meta)
    max_score = max(raw_scores.values(), default=0)

    normalized = {
        key: round((value / max_score), 3) if max_score else 0.0
        for key, value in raw_scores.items()
    }

    top_signals = [
        signal
        for signal, value in sorted(raw_scores.items(), key=lambda item: (-item[1], item[0]))
        if value > 0
    ][:4]

    return {
        "raw": raw_scores,
        "normalized": normalized,
        "top": top_signals,
    }


def _build_structured_profile_fallback(meta: dict) -> dict:
    answers = meta.get("onboarding_answers", {}) if isinstance(meta.get("onboarding_answers", {}), dict) else {}
    signals = meta.get("profile_signals", {}) if isinstance(meta.get("profile_signals", {}), dict) else {}
    top_signals = signals.get("top", [])[:4] if isinstance(signals.get("top", []), list) else []

    seeks = meta.get("seeks", "")
    essence = meta.get("essence", "")
    offers = meta.get("offers", "")
    profession_vocation = meta.get("profession_vocation", "")
    world_affinity = meta.get("world_affinity", answers.get("world_affinity", ""))

    summary_parts = [part for part in [seeks, essence, offers] if part]
    summary = " | ".join(summary_parts[:2]) or "Jogador em fase inicial de descoberta."

    communication_style = ["claro", "humano"]
    if "technicality" in top_signals:
        communication_style.append("objetivo")
    if "reflection" in top_signals:
        communication_style.append("reflexivo")
    if "creativity" in top_signals:
        communication_style.append("criativo")
    if "humanity" in top_signals or "support" in top_signals:
        communication_style.append("acolhedor")

    return {
        "summary": summary[:220],
        "current_moment": _compact_profile_items([seeks, answers.get("current_need", "")], limit=3),
        "relationship_style": _compact_profile_items([essence, answers.get("connection_style", "")], limit=3),
        "worlds": _compact_profile_items([world_affinity, profession_vocation], limit=4),
        "strengths": _compact_profile_items([offers, answers.get("natural_role", "")], limit=4),
        "vocation_vector": profession_vocation[:220],
        "communication_style": communication_style[:3],
    }


def _compact_profile_items(values: list[str], limit: int) -> list[str]:
    items = []
    for value in values:
        if not value:
            continue
        normalized = str(value).replace("|", ",")
        for part in normalized.split(","):
            clean = part.strip(" .;:-_")
            if len(clean) < 3:
                continue
            if clean not in items:
                items.append(clean)
            if len(items) >= limit:
                return items
    return items[:limit]


def _normalize_profile_text(value, fallback: str = "", limit: int = 220) -> str:
    if isinstance(value, list):
        value = ", ".join(str(item).strip() for item in value if str(item).strip())
    text = str(value or fallback).strip()
    return text[:limit]


def _normalize_profile_list(value, fallback: list[str], limit: int) -> list[str]:
    if isinstance(value, list):
        return _compact_profile_items([str(item) for item in value], limit=limit)
    if isinstance(value, str):
        return _compact_profile_items([value], limit=limit)
    return list(fallback)[:limit]


def _sanitize_structured_profile(result: dict, fallback: dict) -> dict:
    safe_result = result if isinstance(result, dict) else {}
    return {
        "summary": _normalize_profile_text(safe_result.get("summary"), fallback=fallback["summary"], limit=220),
        "current_moment": _normalize_profile_list(safe_result.get("current_moment"), fallback=fallback["current_moment"], limit=3),
        "relationship_style": _normalize_profile_list(safe_result.get("relationship_style"), fallback=fallback["relationship_style"], limit=3),
        "worlds": _normalize_profile_list(safe_result.get("worlds"), fallback=fallback["worlds"], limit=4),
        "strengths": _normalize_profile_list(safe_result.get("strengths"), fallback=fallback["strengths"], limit=4),
        "vocation_vector": _normalize_profile_text(safe_result.get("vocation_vector"), fallback=fallback["vocation_vector"], limit=220),
        "communication_style": _normalize_profile_list(safe_result.get("communication_style"), fallback=fallback["communication_style"], limit=3),
    }


async def _extract_structured_profile(meta: dict) -> dict:
    fallback = _build_structured_profile_fallback(meta)
    answers = meta.get("onboarding_answers", {}) if isinstance(meta.get("onboarding_answers", {}), dict) else {}
    context_lines = []
    for key, value in answers.items():
        if value:
            context_lines.append(f"{key}: {value}")

    if not context_lines:
        return fallback

    try:
        result = await chat_completion_json(
            system_prompt=STRUCTURED_PROFILE_PROMPT,
            user_message="\n".join(context_lines),
            temperature=0.2,
            max_tokens=300,
        )
        return _sanitize_structured_profile(result, fallback)
    except Exception as e:
        print(f"⚠️ Structured profile extraction failed: {e}")
        return fallback


def _score_adaptive_categories(meta: dict, excluded: set[str]) -> list[tuple[int, str]]:
    scores = _build_signal_scores(meta)
    category_scores = {
        "offer_signature": 4,
        "connection_style": 1,
        "world_affinity": 1,
        "natural_role": 1,
    }

    if not meta.get("offers"):
        category_scores["offer_signature"] += 2
    if not meta.get("essence"):
        category_scores["connection_style"] += 2
    if not meta.get("world_affinity"):
        category_scores["world_affinity"] += 2
    if not meta.get("natural_role"):
        category_scores["natural_role"] += 2

    if scores["connection"] + scores["intensity"] + scores["reflection"] <= 2:
        category_scores["connection_style"] += 2
    if scores["technicality"] + scores["creativity"] + scores["humanity"] <= 2:
        category_scores["world_affinity"] += 2
    if scores["leadership"] + scores["support"] + scores["practicality"] <= 2:
        category_scores["natural_role"] += 2
    if scores["support"] + scores["connection"] <= 2:
        category_scores["offer_signature"] += 1

    ranked = []
    for category_key in ADAPTIVE_ONBOARDING_CATEGORY_KEYS:
        if category_key in excluded:
            continue
        ranked.append((category_scores.get(category_key, 0), category_key))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked


def _refresh_onboarding_plan(meta: dict, asked_count: int = 0) -> list[str]:
    base_plan = _get_onboarding_plan(meta)
    fixed_plan = FIXED_ONBOARDING_CATEGORY_KEYS[:]

    preserved = base_plan[:asked_count]
    if asked_count <= len(fixed_plan):
        preserved = fixed_plan[:asked_count]

    excluded = set(preserved)
    adaptive_ranked = _score_adaptive_categories(meta, excluded)
    adaptive_selected = [category_key for _, category_key in adaptive_ranked[:2]]

    full_plan = fixed_plan + adaptive_selected
    if asked_count > len(fixed_plan):
        remainder = [key for key in full_plan if key not in preserved]
        return preserved + remainder
    return full_plan[:TOTAL_ONBOARDING_STEPS]


def _select_variant(category: dict, phone: str, meta: dict) -> dict:
    preferred_tones = set(_infer_preferred_tones(meta))
    history = set(meta.get("onboarding_question_history", []))
    variants = category["variants"]

    matching = [variant for variant in variants if preferred_tones.intersection(variant.get("tones", []))]
    pool = matching or variants
    unused_pool = [variant for variant in pool if variant["id"] not in history] or pool

    seed = hashlib.sha256(
        f"{_clean_phone(phone)}:{category['key']}:{meta.get('nickname', '')}:{len(history)}".encode()
    ).hexdigest()
    index = int(seed[:8], 16) % len(unused_pool)
    return unused_pool[index]


def _build_step_data(step: int, phone: str, meta: dict) -> dict:
    plan = _refresh_onboarding_plan(meta, asked_count=max(0, step - 1))
    category_key = plan[step - 1] if len(plan) >= step else FIXED_ONBOARDING_CATEGORY_KEYS[min(step - 1, len(FIXED_ONBOARDING_CATEGORY_KEYS) - 1)]
    category = _get_category_by_key(category_key)
    variant = _select_variant(category, phone, meta)
    nickname = meta.get("nickname", "viajante")
    return {
        "step": step,
        "key": category["key"],
        "title": category["title"],
        "field": category["field"],
        "variant_id": variant["id"],
        "question": variant["question"].replace("{nickname}", nickname or "viajante"),
        "hint": variant["hint"].replace("{nickname}", nickname or "viajante"),
    }


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

    # Legacy edge case: step 0 players — upgrade to step 1
    if current_step == 0:
        _update_meta(phone, {"onboarding_step": 1})
        current_step = 1

    # Steps 1-5: Save answer and advance
    if 1 <= current_step <= TOTAL_ONBOARDING_STEPS:
        current_plan = _refresh_onboarding_plan(meta, asked_count=max(0, current_step - 1))
        step_key = current_plan[current_step - 1] if len(current_plan) >= current_step else FIXED_ONBOARDING_CATEGORY_KEYS[min(current_step - 1, len(FIXED_ONBOARDING_CATEGORY_KEYS) - 1)]
        step_data = _get_category_by_key(step_key)
        field = step_data["field"]
        answer = message.strip()

        # Save the answer
        updates = {field: answer}
        answers = dict(meta.get("onboarding_answers", {}))
        answers[step_data["key"]] = answer
        updates["onboarding_answers"] = answers

        # If step 1, also update the nickname
        if current_step == 1:
            updates["nickname"] = answer

        if step_data["key"] == "offer_signature":
            updates["first_fragment"] = answer

        if step_data["key"] == "connection_style" and not updates.get("essence"):
            updates["essence"] = answer
        if step_data["key"] == "natural_role" and not meta.get("offers"):
            updates["offers"] = answer

        updates["profile_signals"] = _build_profile_signals({**meta, **updates})

        question_history = list(meta.get("onboarding_question_history", []))
        rendered_step = _build_step_data(current_step, phone, {**meta, **updates})
        if rendered_step["variant_id"] not in question_history:
            question_history.append(rendered_step["variant_id"])
        updates["onboarding_question_history"] = question_history

        category_history = list(meta.get("onboarding_category_history", []))
        if step_data["key"] not in category_history:
            category_history.append(step_data["key"])
        updates["onboarding_category_history"] = category_history
        updates["onboarding_plan"] = _refresh_onboarding_plan({**meta, **updates}, asked_count=current_step)

        # If step 5 (last), finalize onboarding
        if current_step == TOTAL_ONBOARDING_STEPS:
            # Award completion bonus
            bonus = 3
            current_seeds = meta.get("seeds", INITIAL_SEEDS)
            final_answers = updates.get("onboarding_answers", {})
            final_offers = updates.get("offers") or final_answers.get("offer_signature") or final_answers.get("natural_role") or final_answers.get("connection_style") or final_answers.get("current_need", "")
            final_essence = updates.get("essence") or final_answers.get("connection_style") or final_answers.get("natural_role") or final_answers.get("world_affinity", "")
            final_fragment = updates.get("first_fragment") or final_answers.get("offer_signature") or final_offers or answer
            updates["state"] = "playing"
            updates["onboarding_step"] = 6  # done
            updates["current_room"] = "mudai.places.start"
            updates["seeds"] = current_seeds + bonus
            updates["total_seeds_earned"] = meta.get("total_seeds_earned", 0) + bonus
            updates["badges"] = meta.get("badges", []) + ["primeiro_passo"]
            updates["offers"] = final_offers
            updates["essence"] = final_essence
            updates["first_fragment"] = final_fragment
            updates["profile_signals"] = _build_profile_signals({**meta, **updates})
            updates["structured_profile"] = await _extract_structured_profile({**meta, **updates})
            _update_meta(phone, updates)

            # Check referral bonus
            _check_referral_bonus(phone)

            # Add fragment to reception
            _add_fragment_to_room(
                "mudai.places.start",
                final_fragment,
                updates.get("nickname", meta.get("nickname", "Alguém")),
            )
            world_state.record_room_block(
                room_path="mudai.places.start",
                author_name=updates.get("nickname", meta.get("nickname", "Alguém")),
                author_phone=phone,
                content=final_fragment,
                block_type="first_fragment",
            )
            room_state = world_state.get_room_state("mudai.places.start")
            room_state_meta = room_state.get("metadata_parsed", {}) if room_state else {}
            if room_state_meta.get("image_refresh_needed"):
                world_state.ensure_room_image_stub("mudai.places.start", reason="onboarding fragment")

            # Return the first room view
            return await _build_welcome_room_response(phone)

        # Advance to next step
        next_step = current_step + 1
        updates["onboarding_step"] = next_step
        _update_meta(phone, updates)

        # Get next step data
        next_step_data = _build_step_data(next_step, phone, {**meta, **updates})
        nickname = updates.get("nickname", meta.get("nickname", "viajante"))

        # Generate dynamic AI question and hint
        variation = await _generate_ai_question(next_step_data, nickname=nickname, meta={**meta, **updates})

        return fmt.format_onboarding_step(
            step=next_step,
            total=TOTAL_ONBOARDING_STEPS,
            title=next_step_data["title"],
            question=variation.get("question", next_step_data["question"]),
            hint=variation.get("hint", next_step_data["hint"]),
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
            # Already in onboarding, show welcome with first question
            step_data = _build_step_data(1, phone, meta)
            variation = await _generate_ai_question(step_data, nickname="", meta=meta)
            return fmt.format_welcome(
                first_question=variation.get("question", ""),
                first_hint=variation.get("hint", "")
            )

        return None

    # Create player from template
    db.copy_artifact("mudai.templates.player", player_path)

    # Set initial metadata with 50 seeds
    initial_meta = {
        "state": "onboarding",
        "onboarding_step": 1,
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
        "onboarding_answers": {},
        "onboarding_question_history": [],
        "onboarding_category_history": [],
        "profile_signals": {
            "raw": {},
            "normalized": {},
            "top": [],
        },
        "structured_profile": {
            "summary": "",
            "current_moment": [],
            "relationship_style": [],
            "worlds": [],
            "strengths": [],
            "vocation_vector": "",
            "communication_style": [],
        },
    }
    initial_meta["onboarding_plan"] = _refresh_onboarding_plan(initial_meta, asked_count=0)
    _update_meta(phone, initial_meta)

    step_data = _build_step_data(1, phone, initial_meta)
    variation = await _generate_ai_question(step_data, nickname="", meta={})
    return fmt.format_welcome(
        first_question=variation.get("question", ""),
        first_hint=variation.get("hint", "")
    )


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
    world_state.refresh_room_state(room_path)


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
