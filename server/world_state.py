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
    
    # Get all images for gallery
    all_images_artifacts = list_room_images(room_path, limit=12)
    all_images = [img.get("metadata_parsed", {}) for img in all_images_artifacts]
    
    # Enrich meta with gallery
    enriched_meta = {**meta, "all_images": all_images}
    
    return {
        "state": enriched_meta,
        "highlight": meta.get("recent_contributions", [])[:3],
        "image": image.get("metadata_parsed", {}) if image else None,
    }


def refresh_room_state(room_path: str) -> dict:
    return _refresh_room_state(room_path)


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
        "image_refresh_needed": should_refresh_images(state_meta, blocks, visual_summary),
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
