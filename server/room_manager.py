"""
MUD-AI — Room Manager.

Handles room discovery, filtering by player profile,
navigation, and room data enrichment.
"""

from typing import Optional
import re
from . import database as db
from . import message_formatter as fmt
from . import world_state


MAX_GENERATED_ROOM_DEPTH = 2
MAX_GENERATED_CHILDREN_PER_ROOM = 3


# ─── Room Discovery ──────────────────────────────────

def get_rooms_for_player(phone: str) -> list[dict]:
    """
    Get rooms visible to this player, filtered by profile.
    Returns enriched room dicts sorted by relevance.
    """
    clean = _clean_phone(phone)
    player = db.get_artifact(f"mudai.users.{clean}")
    if not player:
        return []

    meta = player.get("metadata_parsed", {})
    player_level = meta.get("level", 1)
    player_interests = meta.get("interests", [])
    player_signals = meta.get("profile_signals", {})
    player_structured_profile = meta.get("structured_profile", {})
    opted_in_adult = meta.get("opted_in_adult", False)

    # Get all place artifacts
    all_rooms = db.list_by_prefix("mudai.places.", direct_children_only=True)

    visible = []
    for room in all_rooms:
        room_meta = room.get("metadata_parsed", {})
        tags = room_meta.get("tags", [])
        unlock_level = room_meta.get("unlock_level", 1)
        state = world_state.ensure_room_state(
            room["path"],
            room_name=_extract_room_name(room.get("content", "")),
            purpose=room_meta.get("purpose", ""),
            tags=tags,
        )
        state_meta = state.get("metadata_parsed", {})

        # Filter: level requirement
        if unlock_level > player_level:
            continue

        # Filter: adult content
        if "18+" in tags and not opted_in_adult:
            continue

        # Filter: niche rooms (only show if player has related interest)
        niche_tags = {"maternidade", "empreendedorismo"}
        if niche_tags.intersection(set(tags)):
            if not any(t in player_interests for t in tags):
                # Check with looser matching via seeks/offers
                seeks = meta.get("seeks", "").lower()
                offers = meta.get("offers", "").lower()
                tag_str = " ".join(tags).lower()
                if not any(word in seeks + " " + offers for word in tags):
                    continue

        # Calculate relevance score
        relevance = _calculate_relevance(
            player_interests,
            tags,
            player_signals=player_signals,
            player_structured_profile=player_structured_profile,
            room_purpose=room_meta.get("purpose", ""),
        )

        # Bump rooms the player hasn't visited
        rooms_visited = meta.get("rooms_visited", [])
        if room["path"] not in rooms_visited:
            relevance += 2

        visible.append({
            **room,
            "relevance": relevance,
            "state": state_meta,
        })

    # Sort by relevance (highest first)
    visible.sort(key=lambda r: r.get("relevance", 0), reverse=True)

    # Return top 8
    return visible[:8]


def get_room_info(room_path: str) -> Optional[dict]:
    """
    Get enriched room data including parsed exits, name, subtitle, etc.
    """
    room = db.get_artifact(room_path)
    if not room:
        return None

    content = room["content"]
    meta = room.get("metadata_parsed", {})
    state = world_state.ensure_room_state(
        room_path,
        room_name=_extract_room_name(content),
        purpose=meta.get("purpose", ""),
        tags=meta.get("tags", []),
    )
    state_meta = state.get("metadata_parsed", {})
    snapshot = world_state.room_dynamic_snapshot(room_path)

    info = {
        "path": room_path,
        "content": content,
        "metadata": meta,
        "name": _extract_room_name(content),
        "subtitle": _extract_subtitle(content),
        "emoji": meta.get("emoji", "🚪"),
        "exits": _extract_exits(content),
        "fragments": _extract_fragments(content),
        "narrative": _extract_narrative(content),
        "players_here": _count_players_in_room(room_path),
        "tags": meta.get("tags", []),
        "purpose": meta.get("purpose", ""),
        "evolving_summary": state_meta.get("evolving_summary", ""),
        "visual_summary": state_meta.get("visual_summary", ""),
        "motifs": state_meta.get("motifs", []),
        "recent_contributions": snapshot.get("highlight", []),
        "image": snapshot.get("image"),
        "missions": snapshot.get("missions", []),
    }
    return info


def find_social_matches(phone: str, limit: int = 5) -> list[dict]:
    clean = _clean_phone(phone)
    player = db.get_artifact(f"mudai.users.{clean}")
    if not player:
        return []

    meta = player.get("metadata_parsed", {})
    seeks_terms = _tokenize_match_text(meta.get("seeks", ""))
    offers_terms = _tokenize_match_text(meta.get("offers", ""))
    player_signals = meta.get("profile_signals", {})
    current_room = meta.get("current_room", "")
    persisted_by_phone = {
        artifact["metadata_parsed"].get("other_phone"): artifact.get("metadata_parsed", {})
        for artifact in db.list_by_prefix(_social_matches_prefix(clean), direct_children_only=True)
        if artifact.get("metadata_parsed", {}).get("other_phone")
    }

    candidates = []
    for other in db.list_by_prefix("mudai.users.", direct_children_only=True):
        if other["path"] == player["path"]:
            continue
        other_meta = other.get("metadata_parsed", {})
        if other_meta.get("state") != "playing":
            continue

        other_seeks = _tokenize_match_text(other_meta.get("seeks", ""))
        other_offers = _tokenize_match_text(other_meta.get("offers", ""))
        if not (other_seeks or other_offers):
            continue

        seek_matches = sorted(seeks_terms.intersection(other_offers))
        offer_matches = sorted(offers_terms.intersection(other_seeks))
        signal_overlap = _score_profile_signal_affinity(player_signals, other_meta.get("profile_signals", {}))
        signal_complement = _score_profile_signal_complementarity(player_signals, other_meta.get("profile_signals", {}))
        score = len(seek_matches) * 3 + len(offer_matches) * 2
        score += signal_overlap.get("score_bonus", 0)
        score += signal_complement.get("score_bonus", 0)
        if other_meta.get("current_room") == current_room and current_room:
            score += 2
        if score <= 0:
            continue

        persisted = persisted_by_phone.get(other["path"].split(".")[-1], {})

        candidates.append({
            "phone": other["path"].split(".")[-1],
            "nickname": other_meta.get("nickname", "Viajante"),
            "current_room": other_meta.get("current_room", ""),
            "seek_matches": seek_matches,
            "offer_matches": offer_matches,
            "shared_signals": signal_overlap.get("shared_signals", []),
            "signal_score_bonus": signal_overlap.get("score_bonus", 0),
            "complementary_signals": signal_complement.get("complementary_signals", []),
            "complementarity_score_bonus": signal_complement.get("score_bonus", 0),
            "score": score,
            "same_room": other_meta.get("current_room") == current_room and bool(current_room),
            "seen_count": int(persisted.get("seen_count", 0) or 0),
            "last_seen_at": persisted.get("last_seen_at", ""),
            "is_new": not bool(persisted),
        })

    candidates.sort(key=lambda item: (-item["score"], item["nickname"].lower()))
    return candidates[:limit]


def persist_social_matches(phone: str, matches: list[dict]) -> list[dict]:
    clean = _clean_phone(phone)
    player = db.get_artifact(f"mudai.users.{clean}")
    if not player:
        return []

    persisted_matches = []
    for match in matches:
        other_phone = match.get("phone")
        if not other_phone:
            continue
        path = _social_match_path(clean, other_phone)
        existing = db.get_artifact(path)
        existing_meta = existing.get("metadata_parsed", {}) if existing else {}
        reverse_meta = _get_reverse_social_match_meta(clean, other_phone)
        seen_count = int(existing_meta.get("seen_count", 0) or 0) + 1
        is_mutual = bool(existing_meta.get("is_mutual", False))
        mutual_confirmed_at = existing_meta.get("mutual_confirmed_at", "")
        if bool(existing_meta.get("is_confirmed", False)) and bool(reverse_meta.get("is_confirmed", False)):
            is_mutual = True
            mutual_confirmed_at = mutual_confirmed_at or reverse_meta.get("confirmed_at", "") or existing_meta.get("confirmed_at", "") or db._now()
        metadata = {
            "owner_phone": clean,
            "other_phone": other_phone,
            "nickname": match.get("nickname", "Viajante"),
            "score": match.get("score", 0),
            "same_room": match.get("same_room", False),
            "current_room": match.get("current_room", ""),
            "seek_matches": match.get("seek_matches", []),
            "offer_matches": match.get("offer_matches", []),
            "shared_signals": match.get("shared_signals", []),
            "signal_score_bonus": match.get("signal_score_bonus", 0),
            "complementary_signals": match.get("complementary_signals", []),
            "complementarity_score_bonus": match.get("complementarity_score_bonus", 0),
            "seen_count": seen_count,
            "is_favorite": bool(existing_meta.get("is_favorite", False)),
            "favorited_at": existing_meta.get("favorited_at", ""),
            "is_useful": bool(existing_meta.get("is_useful", False)),
            "marked_useful_at": existing_meta.get("marked_useful_at", ""),
            "is_confirmed": bool(existing_meta.get("is_confirmed", False)),
            "confirmed_at": existing_meta.get("confirmed_at", ""),
            "is_mutual": is_mutual,
            "mutual_confirmed_at": mutual_confirmed_at,
            "first_seen_at": existing_meta.get("first_seen_at") or db._now(),
            "last_seen_at": db._now(),
        }
        artifact = db.put_artifact(
            path=path,
            content=f"Match entre {clean} e {other_phone}",
            content_type="text/plain",
            metadata=metadata,
            is_template=False,
        )
        persisted_matches.append({
            **match,
            "seen_count": artifact.get("metadata_parsed", {}).get("seen_count", seen_count),
            "last_seen_at": artifact.get("metadata_parsed", {}).get("last_seen_at", ""),
            "is_new": seen_count == 1,
            "is_favorite": artifact.get("metadata_parsed", {}).get("is_favorite", False),
            "is_useful": artifact.get("metadata_parsed", {}).get("is_useful", False),
            "is_confirmed": artifact.get("metadata_parsed", {}).get("is_confirmed", False),
            "is_mutual": artifact.get("metadata_parsed", {}).get("is_mutual", False),
        })

    return persisted_matches


def list_social_match_history(phone: str, limit: int = 10) -> list[dict]:
    clean = _clean_phone(phone)
    player = db.get_artifact(f"mudai.users.{clean}")
    if not player:
        return []

    artifacts = db.list_by_prefix(_social_matches_prefix(clean), direct_children_only=True)
    history = []
    for artifact in artifacts:
        meta = artifact.get("metadata_parsed", {})
        other_phone = meta.get("other_phone")
        if not other_phone:
            continue
        history.append({
            "phone": other_phone,
            "nickname": meta.get("nickname", "Viajante"),
            "score": int(meta.get("score", 0) or 0),
            "seen_count": int(meta.get("seen_count", 0) or 0),
            "same_room": bool(meta.get("same_room", False)),
            "current_room": meta.get("current_room", ""),
            "seek_matches": meta.get("seek_matches", []),
            "offer_matches": meta.get("offer_matches", []),
            "shared_signals": meta.get("shared_signals", []),
            "signal_score_bonus": int(meta.get("signal_score_bonus", 0) or 0),
            "complementary_signals": meta.get("complementary_signals", []),
            "complementarity_score_bonus": int(meta.get("complementarity_score_bonus", 0) or 0),
            "is_favorite": bool(meta.get("is_favorite", False)),
            "favorited_at": meta.get("favorited_at", ""),
            "is_useful": bool(meta.get("is_useful", False)),
            "marked_useful_at": meta.get("marked_useful_at", ""),
            "is_confirmed": bool(meta.get("is_confirmed", False)),
            "confirmed_at": meta.get("confirmed_at", ""),
            "is_mutual": bool(meta.get("is_mutual", False)),
            "mutual_confirmed_at": meta.get("mutual_confirmed_at", ""),
            "first_seen_at": meta.get("first_seen_at", ""),
            "last_seen_at": meta.get("last_seen_at", ""),
        })

    history.sort(key=lambda item: (item.get("last_seen_at", ""), item.get("seen_count", 0), item.get("score", 0)), reverse=True)
    return history[:limit]


def _get_reverse_social_match_meta(clean_phone: str, other_phone: str) -> dict:
    reverse = db.get_artifact(_social_match_path(other_phone, clean_phone))
    return reverse.get("metadata_parsed", {}) if reverse else {}


def _find_social_match_artifact(clean_phone: str, query: str) -> Optional[dict]:
    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return None

    artifacts = db.list_by_prefix(_social_matches_prefix(clean_phone), direct_children_only=True)
    for artifact in artifacts:
        meta = artifact.get("metadata_parsed", {})
        other_phone = str(meta.get("other_phone", "")).lower()
        nickname = str(meta.get("nickname", "")).lower()
        if normalized_query == other_phone or normalized_query in nickname:
            return artifact
    return None


def favorite_social_match(phone: str, query: str) -> Optional[dict]:
    clean = _clean_phone(phone)
    player = db.get_artifact(f"mudai.users.{clean}")
    if not player:
        return None

    target_artifact = _find_social_match_artifact(clean, query)
    if not target_artifact:
        return None

    meta = target_artifact.get("metadata_parsed", {}).copy()
    meta["is_favorite"] = True
    meta["favorited_at"] = meta.get("favorited_at") or db._now()
    updated = db.put_artifact(
        path=target_artifact["path"],
        content=target_artifact["content"],
        content_type=target_artifact.get("content_type", "text/plain"),
        metadata=meta,
        is_template=False,
        template_source=target_artifact.get("template_source"),
    )
    return updated.get("metadata_parsed", {})


def mark_social_match_useful(phone: str, query: str) -> Optional[dict]:
    clean = _clean_phone(phone)
    player = db.get_artifact(f"mudai.users.{clean}")
    if not player:
        return None

    target_artifact = _find_social_match_artifact(clean, query)
    if not target_artifact:
        return None

    meta = target_artifact.get("metadata_parsed", {}).copy()
    meta["is_useful"] = True
    meta["marked_useful_at"] = meta.get("marked_useful_at") or db._now()
    updated = db.put_artifact(
        path=target_artifact["path"],
        content=target_artifact["content"],
        content_type=target_artifact.get("content_type", "text/plain"),
        metadata=meta,
        is_template=False,
        template_source=target_artifact.get("template_source"),
    )
    return updated.get("metadata_parsed", {})


def _sync_mutual_social_match(clean_phone: str, other_phone: str) -> None:
    own_artifact = db.get_artifact(_social_match_path(clean_phone, other_phone))
    reverse_artifact = db.get_artifact(_social_match_path(other_phone, clean_phone))
    if not own_artifact or not reverse_artifact:
        return

    own_meta = own_artifact.get("metadata_parsed", {}).copy()
    reverse_meta = reverse_artifact.get("metadata_parsed", {}).copy()
    is_mutual = bool(own_meta.get("is_confirmed", False)) and bool(reverse_meta.get("is_confirmed", False))
    mutual_confirmed_at = ""
    if is_mutual:
        mutual_confirmed_at = own_meta.get("mutual_confirmed_at") or reverse_meta.get("mutual_confirmed_at") or reverse_meta.get("confirmed_at", "") or own_meta.get("confirmed_at", "") or db._now()

    own_meta["is_mutual"] = is_mutual
    reverse_meta["is_mutual"] = is_mutual
    own_meta["mutual_confirmed_at"] = mutual_confirmed_at
    reverse_meta["mutual_confirmed_at"] = mutual_confirmed_at

    db.put_artifact(
        path=own_artifact["path"],
        content=own_artifact["content"],
        content_type=own_artifact.get("content_type", "text/plain"),
        metadata=own_meta,
        is_template=False,
        template_source=own_artifact.get("template_source"),
    )
    db.put_artifact(
        path=reverse_artifact["path"],
        content=reverse_artifact["content"],
        content_type=reverse_artifact.get("content_type", "text/plain"),
        metadata=reverse_meta,
        is_template=False,
        template_source=reverse_artifact.get("template_source"),
    )


def confirm_social_match(phone: str, query: str) -> Optional[dict]:
    clean = _clean_phone(phone)
    player = db.get_artifact(f"mudai.users.{clean}")
    if not player:
        return None

    target_artifact = _find_social_match_artifact(clean, query)
    if not target_artifact:
        return None

    meta = target_artifact.get("metadata_parsed", {}).copy()
    meta["is_confirmed"] = True
    meta["confirmed_at"] = meta.get("confirmed_at") or db._now()
    updated = db.put_artifact(
        path=target_artifact["path"],
        content=target_artifact["content"],
        content_type=target_artifact.get("content_type", "text/plain"),
        metadata=meta,
        is_template=False,
        template_source=target_artifact.get("template_source"),
    )
    _sync_mutual_social_match(clean, str(meta.get("other_phone", "")))
    refreshed = db.get_artifact(target_artifact["path"])
    if refreshed:
        return refreshed.get("metadata_parsed", {})
    return updated.get("metadata_parsed", {})


def list_favorite_social_matches(phone: str, limit: int = 10) -> list[dict]:
    history = list_social_match_history(phone, limit=100)
    favorites = [item for item in history if item.get("is_favorite")]
    favorites.sort(key=lambda item: (item.get("favorited_at", ""), item.get("last_seen_at", ""), item.get("seen_count", 0)), reverse=True)
    return favorites[:limit]


def list_useful_social_matches(phone: str, limit: int = 10) -> list[dict]:
    history = list_social_match_history(phone, limit=100)
    useful = [item for item in history if item.get("is_useful")]
    useful.sort(key=lambda item: (item.get("marked_useful_at", ""), item.get("last_seen_at", ""), item.get("seen_count", 0)), reverse=True)
    return useful[:limit]


def list_confirmed_social_matches(phone: str, limit: int = 10) -> list[dict]:
    history = list_social_match_history(phone, limit=100)
    confirmed = [item for item in history if item.get("is_confirmed")]
    confirmed.sort(key=lambda item: (item.get("confirmed_at", ""), item.get("last_seen_at", ""), item.get("seen_count", 0)), reverse=True)
    return confirmed[:limit]


def list_mutual_social_matches(phone: str, limit: int = 10) -> list[dict]:
    history = list_social_match_history(phone, limit=100)
    mutual = [item for item in history if item.get("is_mutual")]
    mutual.sort(key=lambda item: (item.get("mutual_confirmed_at", ""), item.get("confirmed_at", ""), item.get("last_seen_at", "")), reverse=True)
    return mutual[:limit]


def find_room_by_name(name: str) -> Optional[str]:
    """
    Find a room path by partial name match.
    Returns the path or None.
    """
    name_lower = name.lower().strip()

    # Direct path match
    direct = db.get_artifact(f"mudai.places.{name_lower.replace(' ', '_')}")
    if direct:
        return direct["path"]

    # Search all rooms
    all_rooms = db.list_by_prefix("mudai.places.", direct_children_only=True)
    for room in all_rooms:
        room_name = _extract_room_name(room["content"]).lower()
        # Remove emojis for comparison
        clean_name = "".join(c for c in room_name if c.isalnum() or c.isspace()).strip()

        if name_lower in clean_name or clean_name in name_lower:
            return room["path"]

    return None


def find_room_by_direction(current_room_path: str, direction: str) -> Optional[str]:
    """
    Given a direction from the current room, find the target room.
    Returns the target room path or None.
    """
    room = db.get_artifact(current_room_path)
    if not room:
        return None

    exits = _extract_exits(room["content"])
    direction_lower = direction.lower().strip()

    # Map short commands to full directions
    direction_map = {
        "n": "norte", "s": "sul", "l": "leste", "o": "oeste",
        "north": "norte", "south": "sul", "east": "leste", "west": "oeste",
    }
    direction_lower = direction_map.get(direction_lower, direction_lower)

    for exit_info in exits:
        if exit_info["direction"].lower() == direction_lower:
            # Try to find the target room
            target_name = exit_info["name"]
            target_path = find_room_by_name(target_name)
            return target_path

    return None


def materialize_room_from_exit(current_room_path: str, direction: str) -> Optional[str]:
    room = db.get_artifact(current_room_path)
    if not room:
        return None
    if not _can_expand_from_room(room):
        return None

    exits = _extract_exits(room["content"])
    direction_lower = _normalize_direction(direction)
    for exit_info in exits:
        if _normalize_direction(exit_info["direction"]) != direction_lower:
            continue
        target_name = exit_info["name"].strip()
        if not target_name:
            return None
        existing = find_room_by_name(target_name)
        if existing:
            return existing
        return _create_room_from_exit(current_room_path, direction_lower, target_name)

    return None


def move_player(phone: str, target_room: str) -> bool:
    """
    Move a player to a new room. Updates metadata.
    Returns True if successful.
    """
    clean = _clean_phone(phone)
    player_path = f"mudai.users.{clean}"
    player = db.get_artifact(player_path)
    if not player:
        return False

    import json
    meta = player.get("metadata_parsed", {})

    # Update current room
    meta["current_room"] = target_room

    # Track visited rooms
    visited = meta.get("rooms_visited", [])
    if target_room not in visited:
        visited.append(target_room)
        meta["rooms_visited"] = visited
        
        # Add to game log when someone new arrives
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M")
        log_entry = {
            "time": time_str,
            "text": f'<span class="log-accent">{meta.get("nickname", "Alguém")}</span> explorou este lugar pela primeira vez.',
            "type": "discovery"
        }
        world_state._add_to_game_log(target_room, log_entry)
    else:
        # Standard arrival log
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M")
        log_entry = {
            "time": time_str,
            "text": f'<span class="log-accent">{meta.get("nickname", "Alguém")}</span> entrou na sala.',
            "type": "arrival"
        }
        world_state._add_to_game_log(target_room, log_entry)

    db.put_artifact(
        path=player_path,
        content=player["content"],
        content_type=player["content_type"],
        metadata=meta,
        is_template=False,
        template_source=player.get("template_source"),
    )
    return True


# ─── Content Extraction ──────────────────────────────

def _extract_room_name(content: str) -> str:
    """Extract room name from first H1 heading."""
    for line in content.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return "Desconhecido"


def _extract_subtitle(content: str) -> str:
    """Extract subtitle from blockquote after H1."""
    lines = content.split("\n")
    found_h1 = False
    for line in lines:
        if line.startswith("# "):
            found_h1 = True
            continue
        if found_h1 and line.startswith("> "):
            return line[2:].strip()
        if found_h1 and line.strip() and not line.startswith(">"):
            break
    return ""


def _extract_narrative(content: str) -> str:
    """Extract a short narrative from the blockquote."""
    subtitle = _extract_subtitle(content)
    if subtitle:
        # Truncate to 120 chars
        return subtitle[:120] + ("..." if len(subtitle) > 120 else "")
    return "Um local para explorar."


def _extract_exits(content: str) -> list[dict]:
    """
    Parse exits from markdown content.
    Looks for ## Saídas section with lines like:
      - **norte** → Praça das Trocas
    """
    exits = []
    in_exits = False

    for line in content.split("\n"):
        if line.strip().startswith("## Saídas") or line.strip().startswith("## Saidas"):
            in_exits = True
            continue
        if in_exits:
            if line.startswith("## "):
                break  # Next section
            if "→" in line:
                # Parse: - **norte** → Praça das Trocas
                parts = line.split("→")
                if len(parts) >= 2:
                    direction_part = parts[0].strip().lstrip("- ")
                    direction = direction_part.replace("**", "").strip()
                    name = parts[1].strip().split("_")[0].strip().rstrip(")")
                    exits.append({"direction": direction, "name": name})

    return exits


def _extract_fragments(content: str) -> list[str]:
    """Extract fragments from ## Fragmentos section."""
    fragments = []
    in_fragments = False

    for line in content.split("\n"):
        if line.strip().startswith("## Fragmentos"):
            in_fragments = True
            continue
        if in_fragments:
            if line.startswith("## ") or line.startswith("---"):
                break
            if line.strip().startswith("- ") or line.strip().startswith("_"):
                fragments.append(line.strip().lstrip("- "))

    return fragments


# ─── Helpers ──────────────────────────────────────────

def _clean_phone(phone: str) -> str:
    return "".join(c for c in phone if c.isalnum())


def _social_matches_prefix(clean_phone: str) -> str:
    return f"mudai.users.{clean_phone}.social_matches."


def _social_match_path(clean_phone: str, other_phone: str) -> str:
    return f"{_social_matches_prefix(clean_phone)}{other_phone}"


def _score_profile_signal_affinity(player_signals: dict, other_signals: dict) -> dict:
    player_top = set(player_signals.get("top", []))
    other_top = set(other_signals.get("top", []))
    shared_top = sorted(player_top.intersection(other_top))

    player_normalized = player_signals.get("normalized", {})
    other_normalized = other_signals.get("normalized", {})
    shared_weighted = []
    for signal in sorted(set(player_normalized).intersection(other_normalized)):
        overlap = min(float(player_normalized.get(signal, 0.0) or 0.0), float(other_normalized.get(signal, 0.0) or 0.0))
        if overlap >= 0.4:
            shared_weighted.append((signal, overlap))

    shared_weighted.sort(key=lambda item: (-item[1], item[0]))
    weighted_names = [signal for signal, _ in shared_weighted[:3]]
    shared_signals = []
    for signal in shared_top + weighted_names:
        if signal not in shared_signals:
            shared_signals.append(signal)

    score_bonus = len(shared_top)
    score_bonus += sum(1 for _, overlap in shared_weighted if overlap >= 0.75)

    return {
        "shared_signals": shared_signals[:3],
        "score_bonus": score_bonus,
    }


def _score_profile_signal_complementarity(player_signals: dict, other_signals: dict) -> dict:
    player_normalized = player_signals.get("normalized", {}) if player_signals else {}
    other_normalized = other_signals.get("normalized", {}) if other_signals else {}
    if not player_normalized or not other_normalized:
        return {
            "complementary_signals": [],
            "score_bonus": 0,
        }

    complement_pairs = {
        "connection": ["technicality", "practicality"],
        "humanity": ["leadership", "practicality"],
        "reflection": ["leadership", "technicality"],
        "creativity": ["practicality", "technicality"],
        "support": ["leadership", "intensity"],
        "technicality": ["connection", "creativity", "humanity"],
        "leadership": ["support", "reflection", "humanity"],
        "practicality": ["creativity", "connection"],
        "intensity": ["support", "reflection"],
    }

    complementary = []
    score_bonus = 0
    for player_signal, complements in complement_pairs.items():
        player_strength = float(player_normalized.get(player_signal, 0.0) or 0.0)
        if player_strength < 0.6:
            continue
        for other_signal in complements:
            other_strength = float(other_normalized.get(other_signal, 0.0) or 0.0)
            if other_strength < 0.6:
                continue
            label = f"{player_signal}↔{other_signal}"
            if label not in complementary:
                complementary.append(label)
                score_bonus += 1
            break

    return {
        "complementary_signals": complementary[:3],
        "score_bonus": min(score_bonus, 3),
    }


def _tokenize_match_text(text: str) -> set[str]:
    normalized = _normalize_match_text(text)
    tokens = re.split(r"[^a-z0-9]+", normalized)
    stopwords = {
        "de", "da", "do", "das", "dos", "e", "ou", "com", "para", "por", "em", "na", "no",
        "uma", "um", "o", "a", "as", "os", "que", "me", "eu", "quero", "busco", "ofereco",
        "ofereço", "procuro", "ajuda", "apoio", "troca", "conexao", "conexao", "gente", "pessoas",
    }
    return {token for token in tokens if len(token) >= 3 and token not in stopwords}


def _normalize_match_text(text: str) -> str:
    normalized = (text or "").lower()
    normalized = normalized.replace("ç", "c")
    normalized = normalized.replace("á", "a").replace("à", "a").replace("ã", "a").replace("â", "a")
    normalized = normalized.replace("é", "e").replace("ê", "e")
    normalized = normalized.replace("í", "i")
    normalized = normalized.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    normalized = normalized.replace("ú", "u")
    return normalized


def _normalize_direction(direction: str) -> str:
    direction_map = {
        "n": "norte", "s": "sul", "l": "leste", "o": "oeste",
        "north": "norte", "south": "sul", "east": "leste", "west": "oeste",
    }
    direction_lower = direction.lower().strip()
    return direction_map.get(direction_lower, direction_lower)


def _reverse_direction(direction: str) -> str:
    reverse_map = {
        "norte": "sul",
        "sul": "norte",
        "leste": "oeste",
        "oeste": "leste",
    }
    return reverse_map.get(_normalize_direction(direction), "voltar")


def _slugify_room_name(name: str) -> str:
    normalized = name.lower().strip()
    normalized = normalized.replace("ç", "c")
    normalized = normalized.replace("á", "a").replace("à", "a").replace("ã", "a").replace("â", "a")
    normalized = normalized.replace("é", "e").replace("ê", "e")
    normalized = normalized.replace("í", "i")
    normalized = normalized.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    normalized = normalized.replace("ú", "u")
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "sala_nova"


def _can_expand_from_room(room: dict) -> bool:
    meta = room.get("metadata_parsed", {})
    if not meta.get("generated"):
        return True
    generated_depth = int(meta.get("generated_depth", 1) or 1)
    if generated_depth >= MAX_GENERATED_ROOM_DEPTH:
        return False
    generated_children_count = int(meta.get("generated_children_count", 0) or 0)
    return generated_children_count < MAX_GENERATED_CHILDREN_PER_ROOM


def _bump_generated_children_count(room_path: str, room: dict) -> None:
    meta = room.get("metadata_parsed", {}).copy()
    meta["generated_children_count"] = int(meta.get("generated_children_count", 0) or 0) + 1
    db.put_artifact(
        path=room_path,
        content=room["content"],
        content_type=room.get("content_type", "text/markdown"),
        metadata=meta,
        is_template=False,
        template_source=room.get("template_source"),
    )


def _create_room_from_exit(current_room_path: str, direction: str, target_name: str) -> str:
    base_slug = _slugify_room_name(target_name)
    room_path = f"mudai.places.{base_slug}"
    suffix = 2
    while db.get_artifact(room_path):
        room_path = f"mudai.places.{base_slug}_{suffix}"
        suffix += 1

    source_room = db.get_artifact(current_room_path)
    source_name = _extract_room_name(source_room["content"]) if source_room else "origem"
    source_meta = source_room.get("metadata_parsed", {}) if source_room else {}
    source_tags = source_meta.get("tags", [])
    generated_depth = int(source_meta.get("generated_depth", 0) or 0) + 1
    generated_root_room = source_meta.get("generated_root_room") or current_room_path
    reverse_direction = _reverse_direction(direction)
    purpose = f"Extensão de {source_name.replace('🌱 ', '').replace('📝 ', '')}".strip()
    tags = list(dict.fromkeys([*source_tags[:2], "expansao", _normalize_direction(direction)]))
    content = "\n".join([
        f"# 🚪 {target_name}",
        "",
        f"> Um espaço recém-descoberto que se abre a partir de {source_name}.",
        "",
        "## Atmosfera",
        f"Este lugar começou a ganhar forma quando alguém decidiu seguir para {direction}.",
        "",
        "## Saídas",
        f"- **{reverse_direction}** → {source_name}",
        "",
        "## Fragmentos",
        "_Seja a primeira pessoa a deixar uma marca aqui._",
    ])
    db.put_artifact(
        path=room_path,
        content=content,
        metadata={
            "emoji": "🚪",
            "purpose": purpose,
            "tags": tags,
            "unlock_level": source_meta.get("unlock_level", 1),
            "generated": True,
            "generated_from_room": current_room_path,
            "generated_from_direction": _normalize_direction(direction),
            "generated_root_room": generated_root_room,
            "generated_depth": generated_depth,
            "generated_children_count": 0,
        },
    )
    if source_room and source_meta.get("generated"):
        _bump_generated_children_count(current_room_path, source_room)
    world_state.ensure_room_state(
        room_path,
        room_name=f"🚪 {target_name}",
        purpose=purpose,
        tags=tags,
    )
    world_state.ensure_room_missions(
        room_path,
        room_name=f"🚪 {target_name}",
        purpose=purpose,
        tags=tags,
    )
    return room_path


def _calculate_relevance(
    player_interests: list[str],
    room_tags: list[str],
    player_signals: dict | None = None,
    player_structured_profile: dict | None = None,
    room_purpose: str = "",
) -> int:
    """Score how relevant a room is to a player."""
    score = 1

    if player_interests and room_tags:
        overlap = set(player_interests).intersection(set(room_tags))
        score += len(overlap) * 3

    signal_bonus = _score_room_signal_affinity(
        player_signals or {},
        room_tags,
        room_purpose,
    )
    score += signal_bonus
    score += _score_room_structured_profile_affinity(
        player_structured_profile or {},
        room_tags,
        room_purpose,
    )
    return score


def _score_room_signal_affinity(player_signals: dict, room_tags: list[str], room_purpose: str = "") -> int:
    normalized = player_signals.get("normalized", {}) if player_signals else {}
    if not normalized:
        return 0

    room_signal_map = {
        "technicality": ["tecnologia", "tech", "codigo", "produto", "dados", "ia", "digital", "startup"],
        "creativity": ["arte", "criatividade", "design", "escrita", "musica", "poesia", "estetica"],
        "humanity": ["cuidado", "acolhimento", "familia", "relacoes", "comunidade", "ajuda"],
        "connection": ["troca", "conexao", "relacoes", "comunidade", "conversa", "encontro"],
        "reflection": ["verdade", "filosofia", "reflexao", "contemplacao", "alma", "sentido"],
        "intensity": ["intenso", "provocacao", "desejo", "sombra", "tensao"],
        "support": ["ajuda", "escuta", "apoio", "acolhimento", "cuidado"],
        "leadership": ["lideranca", "negocios", "estrategia", "empreendedorismo", "direcao"],
        "practicality": ["negocios", "carreira", "trabalho", "objetivo", "oficio", "execucao"],
    }

    room_text = " ".join(room_tags + [room_purpose]).lower()
    replacements = {
        "ç": "c",
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
    }
    for old, new in replacements.items():
        room_text = room_text.replace(old, new)

    bonus = 0
    for signal, keywords in room_signal_map.items():
        if any(keyword in room_text for keyword in keywords):
            strength = float(normalized.get(signal, 0.0) or 0.0)
            if strength >= 0.75:
                bonus += 2
            elif strength >= 0.4:
                bonus += 1
    return bonus


def _score_room_structured_profile_affinity(player_structured_profile: dict, room_tags: list[str], room_purpose: str = "") -> int:
    if not player_structured_profile:
        return 0

    room_text = _normalize_match_text(" ".join(room_tags + [room_purpose]))
    profile_terms = []
    for key in ["current_moment", "worlds", "strengths"]:
        value = player_structured_profile.get(key, [])
        if isinstance(value, list):
            profile_terms.extend(str(item) for item in value if item)
        elif value:
            profile_terms.append(str(value))

    bonus = 0
    for term in profile_terms[:8]:
        normalized_term = _normalize_match_text(term)
        if not normalized_term:
            continue
        tokens = [token for token in normalized_term.split() if len(token) >= 4]
        if any(token in room_text for token in tokens[:3]):
            bonus += 1

    return min(bonus, 2)


def get_players_in_room(room_path: str) -> list[dict]:
    """
    Get a list of player names/nicknames in a room.
    """
    players = db.list_by_prefix("mudai.users.", direct_children_only=True)
    in_room = []
    for p in players:
        meta = p.get("metadata_parsed", {})
        if meta.get("current_room") == room_path:
            in_room.append({
                "nickname": meta.get("nickname", "Viajante"),
                "level": meta.get("level", 1),
                "avatar": meta.get("avatar", ""),
            })
    return in_room


def _count_players_in_room(room_path: str) -> int:
    """Count players in a room."""
    players = db.list_by_prefix("mudai.users.", direct_children_only=True)
    return sum(
        1 for p in players
        if p.get("metadata_parsed", {}).get("current_room") == room_path
        and p.get("metadata_parsed", {}).get("state") == "playing"
    )
