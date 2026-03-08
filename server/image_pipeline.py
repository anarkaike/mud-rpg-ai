import asyncio
import base64
import os
from pathlib import Path

import httpx

from . import database as db
from . import world_state


OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"
MEDIA_ROOT = Path(__file__).resolve().parent / "data" / "generated" / "room_images"
MEDIA_URL_PREFIX = "/media/room-images"
_RUNNING_IMAGE_TASKS: set[str] = set()


def _openai_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "")


def _openai_image_model() -> str:
    return os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")


def _public_base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")


def _public_image_url(filename: str) -> str:
    relative = f"{MEDIA_URL_PREFIX}/{filename}"
    public_base_url = _public_base_url()
    return f"{public_base_url}{relative}" if public_base_url else relative


def _artifact_filename(room_path: str, image_path: str) -> str:
    room_slug = world_state.room_slug(room_path)
    image_id = image_path.split(".")[-1]
    return f"{room_slug}-{image_id}.png"


async def enqueue_room_image_generation(room_path: str, reason: str = "room evolution") -> dict:
    image = world_state.ensure_room_image_stub(room_path, reason=reason)
    if not image:
        return {}
    image_path = image.get("path", "")
    if not image_path or image_path in _RUNNING_IMAGE_TASKS:
        return image
    _RUNNING_IMAGE_TASKS.add(image_path)
    asyncio.create_task(_run_room_image_generation(image_path))
    return image


async def _run_room_image_generation(image_path: str):
    try:
        await generate_room_image(image_path)
    finally:
        _RUNNING_IMAGE_TASKS.discard(image_path)


async def generate_room_image(image_path: str) -> dict:
    image = db.get_artifact(image_path)
    if not image:
        return {}

    meta = image.get("metadata_parsed", {}).copy()
    room_path = meta.get("room_path", "")
    prompt = meta.get("prompt", image.get("content", ""))
    openai_api_key = _openai_api_key()
    openai_image_model = _openai_image_model()

    if meta.get("status") == "ready" and meta.get("url"):
        return image

    if not openai_api_key:
        meta["status"] = "failed"
        meta["error"] = "OPENAI_API_KEY não configurada para geração de imagem"
        return db.put_artifact(path=image["path"], content=image.get("content", ""), metadata=meta)

    meta["status"] = "generating"
    meta["error"] = ""
    meta["provider"] = "openai"
    db.put_artifact(path=image["path"], content=image.get("content", ""), metadata=meta)

    try:
        payload = {
            "model": openai_image_model,
            "prompt": prompt,
            "size": "1024x1024",
        }
        headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(OPENAI_IMAGES_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        item = (data.get("data") or [{}])[0]
        b64_data = item.get("b64_json")
        if not b64_data:
            raise RuntimeError("Resposta sem b64_json do provedor de imagem")

        binary = base64.b64decode(b64_data)
        MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
        filename = _artifact_filename(room_path or "mudai.places.unknown", image_path)
        file_path = MEDIA_ROOT / filename
        file_path.write_bytes(binary)

        meta["status"] = "ready"
        meta["url"] = _public_image_url(filename)
        meta["storage_path"] = str(file_path)
        meta["mime_type"] = "image/png"
        meta["error"] = ""
        saved = db.put_artifact(path=image["path"], content=image.get("content", ""), metadata=meta)
        if room_path:
            world_state.mark_room_image_ready(room_path, image["path"])
        return saved
    except Exception as exc:
        meta["status"] = "failed"
        meta["error"] = str(exc)[:500]
        return db.put_artifact(path=image["path"], content=image.get("content", ""), metadata=meta)
