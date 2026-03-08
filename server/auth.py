"""
MUD-AI — Simple Bearer Token Authentication.

Reads API_TOKEN from environment. All /api/v1/* endpoints require:
    Authorization: Bearer <token>

Public endpoints (/p/*, /health) skip auth.
"""

import os
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


API_TOKEN = os.environ.get("API_TOKEN", "mudai-dev-token-2026")

PUBLIC_PATHS = ("/", "/auth/request-code", "/auth/verify-code")
PUBLIC_PREFIXES = (
    "/p/",
    "/p",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/media/",
    "/api/v1/game/web-action",
    "/api/v1/game/web-sync/",
)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing Authorization header"},
            )

        token = auth_header[7:]  # Remove "Bearer "
        if token != API_TOKEN:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid token"},
            )

        return await call_next(request)
