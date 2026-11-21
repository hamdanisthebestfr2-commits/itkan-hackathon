"""Reads a card image with Gemini and returns one reading per field.

Swappable: anything exposing `async read_card(jpeg_bytes) -> dict` can replace this
(e.g. a Claude reader) without touching validation, the review UI, or the CRM.
"""
import asyncio
import io
import re

from google.genai import types
from PIL import Image, ImageOps

from . import ai, config
from .schema import FIELDS, CardReading

SYSTEM_PROMPT = """You transcribe handwritten "Patient Health Record" cards from a community health fair into structured data.
Accuracy matters more than completeness: a wrong medical value is worse than a blank one, because blank values get reviewed by a person.

Rules:
1. Copy exactly what is written. Do not fix spelling (keep "Jhon" as "Jhon"). Never calculate or infer a value that is not written (for example, never compute BMI from height and weight).
2. A field that is empty, crossed out, an X, a dash, or "N/A" -> value null, confidence "high".
3. Checkboxes: return the label of the checked option (a check mark, X, or filled box all count, even if the mark extends past the box). If no box or more than one box is marked, return null with confidence "low" and explain in note.
4. Dates: return MM/DD/YYYY. Keep the year as written.
5. Phone: return as XXX-XXX-XXXX.
6. Numbers: digits only, no units. Keep decimal points.
7. Free text: transcribe all lines in the area, joined with "; ".
8. Confidence: "high" = you would bet on it; "medium" = probably right but a character is ambiguous; "low" = a guess. When not "high", list other plausible readings in alternatives and give a short reason in note.
9. Use each field's typical range only to choose between ambiguous characters. If the handwriting clearly shows an unusual value, report what is written.
10. The card may be rotated or photographed at an angle; read it in its correct orientation."""


def _field_guide() -> str:
    lines = [f"- {f.key} ({f.label}, section '{f.section}'): {f.hint}" for f in FIELDS]
    return "Fields on this card:\n" + "\n".join(lines)


USER_PROMPT = "Transcribe this patient health record card.\n\n" + _field_guide()

class ReaderError(Exception):
    pass


def prepare_image(raw: bytes, max_edge: int = 1600) -> bytes:
    """Fix phone-photo rotation, shrink to a sensible size, re-encode as JPEG."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    img.thumbnail((max_edge, max_edge))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()


async def _read_once(jpeg: bytes, model: str) -> dict:
    models = [model] + [m for m in config.READ_FALLBACKS if m != model]
    try:
        parsed, _ = await ai.generate(models, [types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"), USER_PROMPT],
                                      CardReading, system=SYSTEM_PROMPT, thinking=config.THINKING_LEVEL)
    except ai.AIUnavailable as e:
        raise ReaderError(str(e)) from e
    reading = parsed.model_dump()
    for r in reading.values():
        r["value"] = _clean(r["value"])
    return reading


_BLANK_MARKS = {"x", "-", "--", "n/a", "na", "/", ""}


def _clean(value: str | None) -> str | None:
    """Strip empty free-text lines and treat crossed-out / dash answers as blank."""
    if value is None:
        return None
    parts = [p.strip() for p in value.split(";")]
    value = "; ".join(p for p in parts if p)
    return None if value.lower() in _BLANK_MARKS else value


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9.]", "", (value or "").lower())


_RANK = {"low": 0, "medium": 1, "high": 2}


def _merge(a: dict, b: dict) -> dict:
    """Combine two independent reads; any disagreement becomes a low-confidence field."""
    merged = {}
    for f in FIELDS:
        ra, rb = a[f.key], b[f.key]
        if _norm(ra["value"]) == _norm(rb["value"]):
            best = ra if _RANK[ra["confidence"]] >= _RANK[rb["confidence"]] else rb
            merged[f.key] = {**best, "agree": True}
        else:
            alts = [v for v in [rb["value"], *ra["alternatives"], *rb["alternatives"]] if v and _norm(v) != _norm(ra["value"])]
            merged[f.key] = {
                "value": ra["value"],
                "confidence": "low",
                "alternatives": list(dict.fromkeys(alts)),
                "note": f"Two reads disagreed: '{ra['value']}' vs '{rb['value']}'",
                "agree": False,
            }
    return merged


async def read_card(jpeg: bytes) -> dict:
    try:
        if not config.DOUBLE_READ:
            single = await _read_once(jpeg, config.GEMINI_MODEL)
            return {k: {**v, "agree": True} for k, v in single.items()}
        results = await asyncio.gather(
            _read_once(jpeg, config.GEMINI_MODEL), _read_once(jpeg, config.GEMINI_MODEL_2), return_exceptions=True
        )
    except ReaderError:
        raise
    except Exception as e:  # network / quota / API errors
        raise ReaderError(f"AI request failed: {e}") from e

    ok = [r for r in results if not isinstance(r, Exception)]
    if not ok:
        raise ReaderError(f"AI request failed: {results[0]}")
    if len(ok) == 1:  # one read failed (e.g. rate limit) - still usable
        return {k: {**v, "agree": True} for k, v in ok[0].items()}
    return _merge(ok[0], ok[1])
