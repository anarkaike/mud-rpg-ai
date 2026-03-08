"""
MUD-AI — Search Router.

Full-text search and prefix listing endpoints.
"""

from fastapi import APIRouter, Query

from .. import database as db


router = APIRouter(prefix="/api/v1", tags=["search"])


@router.get("/search")
async def search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """Full-text search across artifact paths and content."""
    results = db.search_fulltext(q, limit=limit)
    return {
        "query": q,
        "count": len(results),
        "results": results,
    }


@router.get("/stats")
async def stats():
    """Get artifact statistics."""
    total = db.count_artifacts()
    users = db.count_artifacts("mudai.users.")
    places = db.count_artifacts("mudai.places.")
    templates = db.count_artifacts("mudai.templates.")

    return {
        "total": total,
        "users": users,
        "places": places,
        "templates": templates,
    }
