"""One place for every Gemini call: structured output + automatic model fallback.

The free tier allows only a few requests per model per day. When a model is out of quota
(HTTP 429) or overloaded (503), we skip it and try the next model in the list, and remember
the exhausted model for a while so the next request doesn't waste time on it.
"""
import asyncio
import time

from google import genai
from google.genai import types

from . import config

_cooldown: dict[str, float] = {}   # model -> time.time() until which we skip it
DAILY_COOLDOWN = 60 * 60           # out of daily quota: skip for an hour
BUSY_COOLDOWN = 60                 # overloaded / per-minute limit: skip for a minute
CALL_TIMEOUT = 20                  # seconds; a slow model must not freeze the demo (normal calls take 1-6 s)


_client: genai.Client | None = None


class AIUnavailable(Exception):
    """Every model failed. The message is safe to show to staff."""


def get_client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise AIUnavailable("No GEMINI_API_KEY in scanner/.env")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _classify(e: Exception) -> str:
    msg = str(e)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return "daily" if "PerDay" in msg or "per day" in msg.lower() else "busy"
    if "503" in msg or "UNAVAILABLE" in msg or "overloaded" in msg.lower():
        return "busy"
    if "404" in msg or "NOT_FOUND" in msg or "not supported" in msg.lower():
        return "missing"
    return "other"


async def _call(model: str, contents, schema, system: str | None, thinking: str):
    try:
        return await asyncio.wait_for(get_client().aio.models.generate_content(
            model=model, contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_level=thinking),
            ),
        ), timeout=CALL_TIMEOUT)
    except asyncio.TimeoutError:
        raise TimeoutError(f"503 UNAVAILABLE: {model} took longer than {CALL_TIMEOUT}s") from None


async def generate(models: list[str], contents, schema, system: str | None = None, thinking: str = "low"):
    """Returns (parsed_result, model_used). Tries each model in order."""
    now, errors, last = time.time(), [], None
    candidates = [m for m in models if _cooldown.get(m, 0) <= now] or list(models)
    for model in candidates:
        try:
            try:
                response = await _call(model, contents, schema, system, thinking)
            except Exception as e:  # some models don't accept "minimal" thinking; retry once with "low"
                if "thinking level" not in str(e).lower() or thinking == "low":
                    raise
                response = await _call(model, contents, schema, system, "low")
            if response.parsed is None:
                raise ValueError("unreadable response")
            _cooldown.pop(model, None)
            return response.parsed, model
        except Exception as e:  # try the next model
            last = e
            kind = _classify(e)
            errors.append(kind)
            print(f"[ai] {model} failed ({kind}): {str(e)[:160]}", flush=True)
            if kind == "daily":
                _cooldown[model] = time.time() + DAILY_COOLDOWN
            elif kind in ("busy", "missing"):
                _cooldown[model] = time.time() + (BUSY_COOLDOWN if kind == "busy" else DAILY_COOLDOWN)
            elif kind == "other" and len(errors) >= 2:
                break
    if errors and all(k == "daily" for k in errors):
        raise AIUnavailable("The free AI plan's daily limit is used up for every model (it resets at midnight Pacific). "
                            "Turn on billing for the Gemini API key in Google AI Studio to remove the limit.")
    if "busy" in errors:
        raise AIUnavailable("The AI service is busy right now. Wait a minute and try again.")
    raise AIUnavailable(f"AI request failed: {str(last)[:200]}")
