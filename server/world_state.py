import hashlib
import re
import uuid
from collections import Counter
from typing import Optional

from . import database as db


def room_slug(room_path: str) -> str:
    return room_path.replace("mudai.places.", "").replace(".", "_")


def room_state_path(room_path: str) -> str:
    return f"mudai.world.rooms.{room_slug(room_path)}.state"


def room_blocks_prefix(room_path: str) -> str:
    return f"mudai.world.rooms.{room_slug(room_path)}.blocks."


def room_images_prefix(room_path: str) -> str:
    return f"mudai.world.rooms.{room_slug(room_path)}.images."


def room_missions_prefix(room_path: str) -> str:
    return f"mudai.world.rooms.{room_slug(room_path)}.missions."


def response_memory_path(scope: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]", "_", scope.strip().lower())
    return f"mudai.world.memory.responses.{normalized}"


def ensure_room_state(room_path: str, room_name: str = "", purpose: str = "", tags: Optional[list[str]] = None) -> dict:
    path = room_state_path(room_path)
    existing = db.get_artifact(path)
    if existing:
        return existing

    metadata = {
        "room_path": room_path,
        "room_name": room_name,
        "purpose": purpose,
        "tags": tags or [],
        "state_version": 1,
        "block_count": 0,
        "highlight_count": 0,
        "motifs": [],
        "recent_block_ids": [],
        "recent_authors": [],
        "recent_contributions": [],
        "evolving_summary": "",
        "visual_summary": "",
        "image_pool_size": 0,
        "image_refresh_needed": True,
        "last_refresh_reason": "bootstrap",
        "momentum_score": 0,
        "social_heat": 0,
        "challenge_completion_count": 0,
        "last_consequence_type": "bootstrap",
        "last_consequence_summary": "",
    }
    return db.put_artifact(path=path, content=room_name or room_path, metadata=metadata)


def get_room_state(room_path: str) -> Optional[dict]:
    return db.get_artifact(room_state_path(room_path))


def list_room_blocks(room_path: str, limit: int = 20) -> list[dict]:
    blocks = db.list_by_prefix(room_blocks_prefix(room_path), direct_children_only=True)
    blocks.sort(key=lambda b: b.get("updated_at", ""), reverse=True)
    return blocks[:limit]


def list_room_images(room_path: str, limit: int = 12) -> list[dict]:
    images = db.list_by_prefix(room_images_prefix(room_path), direct_children_only=True)
    images.sort(key=lambda img: img.get("updated_at", ""), reverse=True)
    return images[:limit]


def list_room_missions(room_path: str, limit: int = 6) -> list[dict]:
    ensure_room_missions(room_path)
    missions = db.list_by_prefix(room_missions_prefix(room_path), direct_children_only=True)
    missions.sort(key=lambda mission: mission.get("updated_at", ""), reverse=True)
    return missions[:limit]


def ensure_room_missions(room_path: str, room_name: str = "", purpose: str = "", tags: Optional[list[str]] = None) -> list[dict]:
    existing = db.list_by_prefix(room_missions_prefix(room_path), direct_children_only=True)
    if existing:
        return existing

    state = ensure_room_state(room_path, room_name=room_name, purpose=purpose, tags=tags)
    state_meta = state.get("metadata_parsed", {})
    motifs = state_meta.get("motifs", [])[:3]
    mission_specs = _build_room_mission_specs(
        room_path=room_path,
        room_name=room_name or state_meta.get("room_name", room_path),
        purpose=purpose or state_meta.get("purpose", ""),
        tags=tags or state_meta.get("tags", []),
        motifs=motifs,
    )
    created = []
    for spec in mission_specs:
        mission_id = spec["id"]
        path = f"{room_missions_prefix(room_path)}{mission_id}"
        mission = db.put_artifact(
            path=path,
            content=spec["instruction"],
            metadata={
                "id": mission_id,
                "room_path": room_path,
                "room_name": room_name or state_meta.get("room_name", room_path),
                "title": spec["title"],
                "instruction": spec["instruction"],
                "mission_type": spec["mission_type"],
                "reward_seeds": spec["reward_seeds"],
                "status": "active",
                "times_completed": 0,
                "tags": spec.get("tags", []),
            },
        )
        created.append(mission)
    return created


def get_room_mission(room_path: str, mission_id: str) -> Optional[dict]:
    if not mission_id:
        return None
    return db.get_artifact(f"{room_missions_prefix(room_path)}{mission_id}")


def get_player_room_mission(room_path: str, player_meta: dict) -> Optional[dict]:
    missions = list_room_missions(room_path, limit=6)
    progress = player_meta.get("mission_progress", {})
    room_progress = progress.get(room_path, {}) if isinstance(progress, dict) else {}
    for mission in missions:
        meta = mission.get("metadata_parsed", {})
        mission_id = meta.get("id")
        if not mission_id:
            continue
        if room_progress.get(mission_id, {}).get("status") == "completed":
            continue
        return mission
    return missions[0] if missions else None


def complete_room_mission(room_path: str, mission_id: str, player_phone: str, player_name: str) -> Optional[dict]:
    mission = get_room_mission(room_path, mission_id)
    if not mission:
        return None
    meta = mission.get("metadata_parsed", {})
    meta["times_completed"] = int(meta.get("times_completed", 0)) + 1
    meta["last_completed_by"] = player_name
    meta["last_completed_by_hash"] = hashlib.sha256(player_phone.encode()).hexdigest()[:16] if player_phone else ""
    updated = db.put_artifact(path=mission["path"], content=mission["content"], metadata=meta)
    apply_room_consequence(
        room_path=room_path,
        consequence_type="mission_completion",
        summary=f"{player_name} concluiu uma missão desta sala.",
        intensity=2,
        social_delta=1,
    )
    return updated


def record_room_block(
    room_path: str,
    author_name: str,
    author_phone: str,
    content: str,
    block_type: str = "fragment",
) -> dict:
    clean_content = normalize_text(content)
    block_id = uuid.uuid4().hex[:12]
    path = f"{room_blocks_prefix(room_path)}{block_id}"
    tags = extract_tags(clean_content)
    metadata = {
        "id": block_id,
        "room_path": room_path,
        "author_name": author_name,
        "author_phone_hash": hashlib.sha256(author_phone.encode()).hexdigest()[:16] if author_phone else "",
        "block_type": block_type,
        "length": len(clean_content),
        "impact_score": calculate_impact_score(clean_content, block_type),
        "tags": tags,
        "used_in_summary": False,
    }
    block = db.put_artifact(path=path, content=clean_content, metadata=metadata)
    
    # Add to room game log
    from datetime import datetime
    time_str = datetime.now().strftime("%H:%M")
    log_entry = {
        "time": time_str,
        "text": f'<span class="log-accent">{author_name}</span> deixou um eco: "{clean_content[:40]}..."',
        "type": "block"
    }
    _add_to_game_log(room_path, log_entry)
    apply_room_consequence(
        room_path=room_path,
        consequence_type=block_type,
        summary=f"{author_name} alterou o clima da sala com um novo eco.",
        intensity=max(1, int(metadata.get("impact_score", 1) or 1)),
        social_delta=1 if block_type in {"mission_response", "challenge_response"} else 0,
    )

    _refresh_room_state(room_path)
    return block


def _add_to_game_log(room_path: str, entry: dict, limit: int = 15):
    """Add an entry to the room's persistent game log."""
    state = ensure_room_state(room_path)
    if not state:
        return

    meta = state.get("metadata_parsed", {})
    log = meta.get("game_log", [])
    log.insert(0, entry)
    meta["game_log"] = log[:limit]

    db.put_artifact(path=state["path"], content=state["content"], metadata=meta)


def ensure_room_image_stub(room_path: str, reason: str = "room evolution") -> dict:
    existing = list_room_images(room_path, limit=1)
    state = get_room_state(room_path)
    state_meta = state.get("metadata_parsed", {}) if state else {}
    if existing and not state_meta.get("image_refresh_needed", False):
        return existing[0]

    image_id = uuid.uuid4().hex[:12]
    path = f"{room_images_prefix(room_path)}{image_id}"
    visual_summary = state_meta.get("visual_summary", "")
    evolving_summary = state_meta.get("evolving_summary", "")
    prompt = build_image_prompt(room_path, visual_summary, evolving_summary)
    image = db.put_artifact(
        path=path,
        content=prompt,
        metadata={
            "room_path": room_path,
            "status": "pending_generation",
            "prompt": prompt,
            "reason": reason,
            "weight": 1,
            "is_active": True,
        },
    )

    if state:
        meta = state.get("metadata_parsed", {})
        meta["image_pool_size"] = len(list_room_images(room_path))
        meta["image_refresh_needed"] = False
        meta["last_refresh_reason"] = reason
        db.put_artifact(path=state["path"], content=state["content"], metadata=meta)
    return image


def get_random_room_image(room_path: str) -> Optional[dict]:
    images = [img for img in list_room_images(room_path) if img.get("metadata_parsed", {}).get("is_active", True)]
    if not images:
        return None
    images.sort(key=lambda img: (img.get("metadata_parsed", {}).get("status") == "ready", img.get("updated_at", "")), reverse=True)
    return images[0]


def remember_response(scope: str, text: str, limit: int = 6) -> dict:
    path = response_memory_path(scope)
    artifact = db.get_artifact(path)
    metadata = artifact.get("metadata_parsed", {}) if artifact else {"items": []}
    normalized = normalize_text(text)
    items = metadata.get("items", [])
    if normalized:
        items = [item for item in items if item != normalized]
        items.insert(0, normalized)
    metadata["items"] = items[:limit]
    return db.put_artifact(path=path, content="\n".join(metadata["items"]), metadata=metadata)


def recent_responses(scope: str, limit: int = 6) -> list[str]:
    artifact = db.get_artifact(response_memory_path(scope))
    if not artifact:
        return []
    return artifact.get("metadata_parsed", {}).get("items", [])[:limit]


def room_dynamic_snapshot(room_path: str) -> dict:
    state = ensure_room_state(room_path)
    meta = state.get("metadata_parsed", {})
    image = get_random_room_image(room_path)

    all_images_artifacts = list_room_images(room_path, limit=12)
    all_images = [img.get("metadata_parsed", {}) for img in all_images_artifacts]
    missions = [mission.get("metadata_parsed", {}) for mission in list_room_missions(room_path, limit=4)]

    enriched_meta = {**meta, "all_images": all_images, "missions": missions}

    return {
        "state": enriched_meta,
        "highlight": meta.get("recent_contributions", [])[:3],
        "image": image.get("metadata_parsed", {}) if image else None,
        "missions": missions,
    }


def refresh_room_state(room_path: str) -> dict:
    return _refresh_room_state(room_path)


def apply_room_consequence(
    room_path: str,
    consequence_type: str,
    summary: str,
    intensity: int = 1,
    social_delta: int = 0,
) -> dict:
    state = ensure_room_state(room_path)
    meta = state.get("metadata_parsed", {}) if state else {}
    momentum = int(meta.get("momentum_score", 0) or 0) + max(1, int(intensity or 1))
    social_heat = int(meta.get("social_heat", 0) or 0) + max(0, int(social_delta or 0))
    if consequence_type == "mission_completion":
        meta["challenge_completion_count"] = int(meta.get("challenge_completion_count", 0) or 0) + 1
    meta["momentum_score"] = momentum
    meta["social_heat"] = social_heat
    meta["last_consequence_type"] = str(consequence_type or "world_event")[:40]
    meta["last_consequence_summary"] = normalize_text(summary)[:220]
    return db.put_artifact(path=state["path"], content=state["content"], metadata=meta)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def extract_tags(text: str, limit: int = 6) -> list[str]:
    words = re.findall(r"[a-zA-ZÀ-ÿ]{4,}", (text or "").lower())
    stopwords = {
        "para", "como", "muito", "mais", "essa", "esse", "isso", "aqui", "agora", "sobre", "entre",
        "onde", "quando", "quero", "deixar", "sala", "texto", "pois", "com", "sem", "uma", "umas",
        "umas", "meus", "suas", "seus", "esta", "estou", "você", "voces", "tambem", "ainda",
    }
    ranked = [word for word, _ in Counter(w for w in words if w not in stopwords).most_common(limit)]
    return ranked


def calculate_impact_score(text: str, block_type: str) -> int:
    base = min(max(len(text) // 24, 1), 8)
    bonus = 2 if block_type in {"decoration", "story", "ritual"} else 0
    return base + bonus


def build_image_prompt(room_path: str, visual_summary: str, evolving_summary: str) -> str:
    room_name = room_path.replace("mudai.places.", "").replace("_", " ")
    return (
        f"Cena de RPG textual brasileiro inspirada na sala '{room_name}'. "
        f"Resumo visual: {visual_summary or evolving_summary or room_name}. "
        "Estética cinematográfica, acolhedora, rica em atmosfera, sem texto sobreposto, sem pessoas em destaque frontal."
    )


def _build_room_mission_specs(room_path: str, room_name: str, purpose: str, tags: list[str], motifs: list[str]) -> list[dict]:
    label = room_name.replace('🌱 ', '').replace('📝 ', '').strip() or room_path.replace('mudai.places.', '')
    primary = motifs[0] if motifs else purpose or label
    reward = 4
    specs = [
        {
            "id": hashlib.sha256(f"{room_path}:echoes".encode()).hexdigest()[:12],
            "title": f"Ecos de {label}",
            "instruction": f"Deixe uma contribuição curta que fortaleça o clima de {label} em torno de {primary}.",
            "mission_type": "echo",
            "reward_seeds": reward,
            "tags": motifs[:2] or tags[:2],
        },
        {
            "id": hashlib.sha256(f"{room_path}:bridge".encode()).hexdigest()[:12],
            "title": f"Ponte de {label}",
            "instruction": f"Escreva uma frase que conecte quem chega agora ao propósito desta sala: {purpose or label}.",
            "mission_type": "bridge",
            "reward_seeds": reward,
            "tags": tags[:2],
        },
    ]
    if any(tag in tags for tag in ["troca", "conexão", "networking"]):
        specs.append({
            "id": hashlib.sha256(f"{room_path}:exchange".encode()).hexdigest()[:12],
            "title": f"Troca Viva em {label}",
            "instruction": f"Registre uma oferta, pedido ou conexão que faria sentido nascer em {label}.",
            "mission_type": "exchange",
            "reward_seeds": reward + 1,
            "tags": [tag for tag in tags if tag in {"troca", "conexão", "networking"}],
        })
    return specs[:3]


def _refresh_room_state(room_path: str) -> dict:
    state = ensure_room_state(room_path)
    state_meta = state.get("metadata_parsed", {})
    blocks = list_room_blocks(room_path, limit=40)
    recent = blocks[:6]
    recent_contributions = []
    recent_authors = []
    all_tags = []
    for block in recent:
        meta = block.get("metadata_parsed", {})
        author = meta.get("author_name", "Alguém")
        recent_authors.append(author)
        all_tags.extend(meta.get("tags", []))
        recent_contributions.append({
            "id": meta.get("id"),
            "author": author,
            "type": meta.get("block_type", "fragment"),
            "excerpt": truncate(block.get("content", ""), 120),
        })

    if not all_tags:
        for block in blocks:
            all_tags.extend(block.get("metadata_parsed", {}).get("tags", []))

    motifs = [tag for tag, _ in Counter(all_tags).most_common(5)]
    summary = synthesize_room_summary(room_path, blocks, motifs)
    visual_summary = synthesize_visual_summary(room_path, blocks, motifs)

    missions = list_room_missions(room_path, limit=6)
    mission_meta = [mission.get("metadata_parsed", {}) for mission in missions]

    state_meta.update({
        "state_version": int(state_meta.get("state_version", 0)) + 1,
        "block_count": len(blocks),
        "highlight_count": len(recent_contributions),
        "motifs": motifs,
        "recent_block_ids": [b.get("metadata_parsed", {}).get("id") for b in recent if b.get("metadata_parsed", {}).get("id")],
        "recent_authors": list(dict.fromkeys(recent_authors))[:6],
        "recent_contributions": recent_contributions,
        "evolving_summary": summary,
        "visual_summary": visual_summary,
        "image_pool_size": len(list_room_images(room_path)),
        "active_missions": mission_meta,
        "mission_count": len(mission_meta),
        "image_refresh_needed": should_refresh_images(state_meta, blocks, visual_summary),
        "momentum_score": max(int(state_meta.get("momentum_score", 0) or 0), len(blocks)),
    })

    return db.put_artifact(path=state["path"], content=summary or state["content"], metadata=state_meta)


def synthesize_room_summary(room_path: str, blocks: list[dict], motifs: list[str]) -> str:
    room_name = room_path.replace("mudai.places.", "").replace("_", " ")
    if not blocks:
        return f"{room_name.title()} aguarda novas contribuições para ganhar forma coletiva."
    excerpts = [truncate(block.get("content", ""), 80) for block in blocks[:3] if block.get("content")]
    motif_text = ", ".join(motifs[:3]) if motifs else "presença, memória e descoberta"
    return f"{room_name.title()} pulsa com {motif_text}. Ecos recentes: {' | '.join(excerpts)}"


def synthesize_visual_summary(room_path: str, blocks: list[dict], motifs: list[str]) -> str:
    room_name = room_path.replace("mudai.places.", "").replace("_", " ")
    tone = ", ".join(motifs[:4]) if motifs else "luz suave, texturas orgânicas, detalhes narrativos"
    details = []
    for block in blocks[:4]:
        text = block.get("content", "")
        lower = text.lower()
        if any(keyword in lower for keyword in ["vela", "fogueira", "luz", "brilho"]):
            details.append("iluminação simbólica")
        if any(keyword in lower for keyword in ["parede", "mural", "quadro", "desenho"]):
            details.append("paredes marcadas por contribuições")
        if any(keyword in lower for keyword in ["flor", "planta", "árvore", "jardim"]):
            details.append("elementos naturais vivos")
    details = list(dict.fromkeys(details))[:3]
    suffix = ", ".join(details) if details else "cenário moldado por visitantes"
    return f"{room_name.title()} com {tone}; {suffix}."


def should_refresh_images(state_meta: dict, blocks: list[dict], visual_summary: str) -> bool:
    previous = state_meta.get("visual_summary", "")
    previous_count = int(state_meta.get("block_count", 0))
    count = len(blocks)
    if count == 0:
        return True
    if count <= 2 and int(state_meta.get("image_pool_size", 0)) == 0:
        return True
    if count - previous_count >= 3:
        return True
    if previous and previous != visual_summary:
        return True
    return False


def truncate(text: str, limit: int) -> str:
    text = normalize_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
