"""
MUD-AI — Artifact CRUD Router.

Endpoints for creating, reading, updating, deleting, copying,
and listing artifacts by path.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from .. import database as db


router = APIRouter(prefix="/api/v1", tags=["artifacts"])


# ─── Models ───────────────────────────────────────────

class ArtifactBody(BaseModel):
    content: str = ""
    content_type: str = "md"
    metadata: Optional[dict] = None
    is_template: bool = False

class CopyBody(BaseModel):
    target_path: str = Field(..., description="Destination path for the copy")


# ─── Endpoints ────────────────────────────────────────

@router.get("/artifacts")
async def list_artifacts(
    prefix: str = Query("", description="Filter by path prefix (e.g. 'mudai.users')"),
    direct: bool = Query(False, description="Only direct children (no nested)"),
):
    """List artifacts by prefix."""
    results = db.list_by_prefix(prefix, direct_children_only=direct)
    return {
        "count": len(results),
        "prefix": prefix,
        "artifacts": results,
    }


@router.get("/artifacts/{path:path}")
async def get_artifact(path: str):
    """Get a single artifact by exact path."""
    artifact = db.get_artifact(path)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {path}")
    return artifact


@router.put("/artifacts/{path:path}")
async def put_artifact(path: str, body: ArtifactBody):
    """Create or update an artifact."""
    result = db.put_artifact(
        path=path,
        content=body.content,
        content_type=body.content_type,
        metadata=body.metadata,
        is_template=body.is_template,
    )
    return result


@router.delete("/artifacts/{path:path}")
async def delete_artifact(
    path: str,
    recursive: bool = Query(False, description="Delete all children too"),
):
    """Delete an artifact (optionally with all children)."""
    if recursive:
        count = db.delete_by_prefix(path)
        if count == 0:
            raise HTTPException(status_code=404, detail=f"No artifacts found with prefix: {path}")
        return {"deleted": count, "prefix": path}
    else:
        found = db.delete_artifact(path)
        if not found:
            raise HTTPException(status_code=404, detail=f"Artifact not found: {path}")
        return {"deleted": 1, "path": path}


@router.post("/artifacts/{path:path}/copy")
async def copy_artifact(path: str, body: CopyBody):
    """Copy an artifact to a new path. Works for templates and regular artifacts."""
    # Check target doesn't already exist
    if db.get_artifact(body.target_path):
        raise HTTPException(status_code=409, detail=f"Target already exists: {body.target_path}")

    result = db.copy_artifact(path, body.target_path)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Source artifact not found: {path}")
    return result


@router.get("/templates")
async def list_templates():
    """List all template artifacts."""
    templates = db.list_templates()
    return {
        "count": len(templates),
        "templates": templates,
    }
