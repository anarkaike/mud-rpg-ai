"""
MUD-AI — AI Client Wrapper.

Unified interface for OpenAI and Gemini API calls.
Handles structured JSON responses for game logic.
"""

import os
import json
import httpx
from typing import Optional


OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 300


def _openai_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "")


def _gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "")


async def chat_completion(
    system_prompt: str,
    user_message: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    json_mode: bool = False,
) -> str:
    """
    Send a chat completion request to OpenAI.
    Returns the assistant's response text.
    Falls back to Gemini if OpenAI fails.
    """
    openai_api_key = _openai_api_key()
    gemini_api_key = _gemini_api_key()

    if not openai_api_key and not gemini_api_key:
        raise RuntimeError("No AI provider API key configured. Set OPENAI_API_KEY or GEMINI_API_KEY.")

    try:
        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        return await _openai_chat(system_prompt, user_message, model, temperature, max_tokens, json_mode, openai_api_key)
    except Exception as e:
        print(f"⚠️ OpenAI failed: {e}")
        if gemini_api_key:
            try:
                return await _gemini_chat(system_prompt, user_message, temperature, max_tokens, gemini_api_key)
            except Exception as ge:
                print(f"⚠️ Gemini also failed: {ge}")
        raise


async def chat_completion_json(
    system_prompt: str,
    user_message: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """
    Like chat_completion but parses the response as JSON.
    The system prompt MUST instruct the model to return JSON.
    """
    raw = await chat_completion(
        system_prompt=system_prompt,
        user_message=user_message,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
    )
    # Clean markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove ```json
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    return json.loads(text)


# ─── OpenAI ───────────────────────────────────────────

async def _openai_chat(
    system_prompt: str,
    user_message: str,
    model: str,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
    openai_api_key: str,
) -> str:
    """Call OpenAI Chat Completions API."""
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(OPENAI_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ─── Gemini ───────────────────────────────────────────

async def _gemini_chat(
    system_prompt: str,
    user_message: str,
    temperature: float,
    max_tokens: int,
    gemini_api_key: str,
) -> str:
    """Call Google Gemini API as fallback."""
    url = f"{GEMINI_URL}?key={gemini_api_key}"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_prompt}\n\n---\n\nUser message: {user_message}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
