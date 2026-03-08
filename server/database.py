"""
MUD-AI — SQLite Key-Value Store with Path-Based Access.

Every piece of game data is an "artifact" accessible by a dot-notation path.
Examples:
    mudai.users.junio           → player profile (markdown)
    mudai.users.junio.history   → player history
    mudai.places.start          → starting room
    mudai.templates.player      → player template (is_template=1)
"""

import json
import sqlite3
import os
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional


DB_PATH = os.environ.get("MUDAI_DB_PATH", os.path.join(os.path.dirname(__file__), "data", "mudai.db"))

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS artifacts (
    path TEXT PRIMARY KEY,
    content TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL DEFAULT 'md',
    metadata TEXT NOT NULL DEFAULT '{}',
    is_template INTEGER NOT NULL DEFAULT 0,
    template_source TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_artifacts_prefix ON artifacts(path);
CREATE INDEX IF NOT EXISTS idx_artifacts_template ON artifacts(is_template) WHERE is_template = 1;
"""

_ENABLE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS artifacts_fts USING fts5(
    path,
    content,
    content='artifacts',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS artifacts_ai AFTER INSERT ON artifacts BEGIN
    INSERT INTO artifacts_fts(rowid, path, content)
    VALUES (new.rowid, new.path, new.content);
END;

CREATE TRIGGER IF NOT EXISTS artifacts_ad AFTER DELETE ON artifacts BEGIN
    INSERT INTO artifacts_fts(artifacts_fts, rowid, path, content)
    VALUES ('delete', old.rowid, old.path, old.content);
END;

CREATE TRIGGER IF NOT EXISTS artifacts_au AFTER UPDATE ON artifacts BEGIN
    INSERT INTO artifacts_fts(artifacts_fts, rowid, path, content)
    VALUES ('delete', old.rowid, old.path, old.content);
    INSERT INTO artifacts_fts(rowid, path, content)
    VALUES (new.rowid, new.path, new.content);
END;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db():
    """Initialize database and create tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(_CREATE_TABLE)
    conn.executescript(_CREATE_INDEXES)
    conn.executescript(_ENABLE_FTS)
    conn.commit()
    conn.close()


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── CRUD ─────────────────────────────────────────────

def get_artifact(path: str) -> Optional[dict]:
    """Get a single artifact by exact path."""
    with get_db() as db:
        row = db.execute("SELECT * FROM artifacts WHERE path = ?", (path,)).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)


def put_artifact(
    path: str,
    content: str,
    content_type: str = "md",
    metadata: Optional[dict] = None,
    is_template: bool = False,
    template_source: Optional[str] = None,
) -> dict:
    """Create or update an artifact."""
    now = _now()
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)

    with get_db() as db:
        existing = db.execute("SELECT created_at FROM artifacts WHERE path = ?", (path,)).fetchone()
        created = existing["created_at"] if existing else now

        db.execute(
            """
            INSERT INTO artifacts (path, content, content_type, metadata, is_template, template_source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                content = excluded.content,
                content_type = excluded.content_type,
                metadata = excluded.metadata,
                is_template = excluded.is_template,
                template_source = excluded.template_source,
                updated_at = excluded.updated_at
            """,
            (path, content, content_type, meta_json, int(is_template), template_source, created, now),
        )

    return get_artifact(path)


def delete_artifact(path: str) -> bool:
    """Delete an artifact. Returns True if it existed."""
    with get_db() as db:
        cursor = db.execute("DELETE FROM artifacts WHERE path = ?", (path,))
        return cursor.rowcount > 0


def delete_by_prefix(prefix: str) -> int:
    """Delete all artifacts matching a prefix. Returns count deleted."""
    with get_db() as db:
        cursor = db.execute("DELETE FROM artifacts WHERE path LIKE ?", (prefix + "%",))
        return cursor.rowcount


# ─── QUERIES ──────────────────────────────────────────

def list_by_prefix(prefix: str, direct_children_only: bool = False) -> list[dict]:
    """
    List artifacts by path prefix.

    If direct_children_only=True, returns only immediate children
    (e.g. prefix='mudai.users' returns 'mudai.users.junio' but NOT 'mudai.users.junio.history').
    """
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM artifacts WHERE path LIKE ? ORDER BY path",
            (prefix + "%",),
        ).fetchall()

    results = [_row_to_dict(r) for r in rows]

    if direct_children_only and prefix:
        depth = prefix.rstrip(".").count(".") + 1
        results = [r for r in results if r["path"].count(".") == depth]

    return results


def list_templates() -> list[dict]:
    """List all template artifacts."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM artifacts WHERE is_template = 1 ORDER BY path"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def search_fulltext(query: str, limit: int = 50) -> list[dict]:
    """Full-text search across artifact paths and content."""
    with get_db() as db:
        rows = db.execute(
            """
            SELECT a.* FROM artifacts a
            JOIN artifacts_fts fts ON a.rowid = fts.rowid
            WHERE artifacts_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def copy_artifact(source_path: str, target_path: str) -> Optional[dict]:
    """
    Copy an artifact to a new path.
    If source is a template, sets template_source on the copy.
    Returns the new artifact or None if source doesn't exist.
    """
    source = get_artifact(source_path)
    if source is None:
        return None

    return put_artifact(
        path=target_path,
        content=source["content"],
        content_type=source["content_type"],
        metadata=source.get("metadata_parsed", {}),
        is_template=False,
        template_source=source_path if source["is_template"] else source.get("template_source"),
    )


def count_artifacts(prefix: str = "") -> int:
    """Count artifacts, optionally filtered by prefix."""
    with get_db() as db:
        if prefix:
            row = db.execute("SELECT COUNT(*) as cnt FROM artifacts WHERE path LIKE ?", (prefix + "%",)).fetchone()
        else:
            row = db.execute("SELECT COUNT(*) as cnt FROM artifacts").fetchone()
        return row["cnt"]


# ─── HELPERS ──────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["is_template"] = bool(d["is_template"])
    try:
        d["metadata_parsed"] = json.loads(d.get("metadata", "{}"))
    except (json.JSONDecodeError, TypeError):
        d["metadata_parsed"] = {}
    return d
