"""
MUD-AI — Room Manager.

Handles room discovery, filtering by player profile,
navigation, and room data enrichment.
"""

from typing import Optional
from . import database as db
from . import message_formatter as fmt
from . import world_state


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
        relevance = _calculate_relevance(player_interests, tags)

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


def _calculate_relevance(player_interests: list[str], room_tags: list[str]) -> int:
    """Score how relevant a room is to a player."""
    if not player_interests or not room_tags:
        return 1
    overlap = set(player_interests).intersection(set(room_tags))
    return len(overlap) * 3 + 1


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
