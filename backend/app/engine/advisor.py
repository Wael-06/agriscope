from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from app.engine import rotation as R
from app.engine import yield_estimation as Y
from app.schemas.contracts import EnvironmentalFeatures
from dotenv import load_dotenv

_MODULE_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _MODULE_DIR.parents[1]
_PROJECT_DIR = _BACKEND_DIR.parent
for _env_file in (
    _MODULE_DIR / ".env",
    _BACKEND_DIR / ".env",
    _PROJECT_DIR / ".env",
):
    if _env_file.is_file():
        load_dotenv(_env_file)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MAX_WORDS = 150
DEFAULT_MODEL = "gemini-flash-lite-latest"
FALLBACK_MODELS = ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-flash-latest", "gemini-3-flash-preview")
LANGS = {"en": "English", "ar": "Arabic (Modern Standard, simple words)"}

SYSTEM = (
    "You are an agronomy assistant for smallholder farmers. Use ONLY the numbers in the FACTS json for "
    "yield, rotation and water; never invent or change them. If a yield note says it is a country average, "
    "say so in plain words. Outside information (local calendars, pests, prices) is allowed only from web "
    "search results, and say 'check locally' when unsure. Give a concise answer of at most {words} words. "
    "Use exactly these headings: Summary, This season, Water, Soil and nutrients, Next seasons, Risks to watch. "
    "Under each heading give at most one short, practical bullet with timing; use two only when essential. "
    "Avoid introductions, repetition, and long paragraphs. In 'Next seasons', briefly explain the top rotation "
    "option. If rotation crops look unusual for the location, say the crop list was built for Egyptian "
    "conditions and ask the farmer to confirm locally. Do not give medical, legal or financial guarantees."
)


# ------------------------------------------------------------------ facts
def water_balance(f: EnvironmentalFeatures) -> dict:
    """Plain 7-day balance from the forecast. Not a trained model."""
    demand = f.forecast_et0_mm_day * 7
    gap = max(0.0, demand - f.forecast_precip_7d_mm)
    return {"et0_demand_7d_mm": round(demand, 1), "forecast_rain_7d_mm": round(f.forecast_precip_7d_mm, 1),
            "gap_7d_mm": round(gap, 1), "soil_moisture_root": round(f.soil_moisture_root, 2),
            "irrigation_availability": f.irrigation_availability,
            "status": ("dry soil and a water gap: irrigate soon" if gap > 15 and f.soil_moisture_root < 0.35
                       else "water gap: plan irrigation" if gap > 15
                       else "rain/soil moisture cover the next 7 days")}


def build_facts(f: EnvironmentalFeatures) -> dict:
    kg, conf, note = Y.estimate_yield(f)
    options = R.recommend_rotations(f)
    return {
        "crop_now": f.crop, "location": {"lat": f.lat, "lon": f.lon}, "planting_date": f.planting_date,
        "field_size_ha": f.field_size_ha, "soil": f.soil_texture,
        "weather_30d": {"avg_temp_c": f.avg_temp_c, "max_temp_c": f.max_temp_c, "rain_mm": f.total_precip_mm},
        "forecast_7d": {"max_temp_c": f.forecast_max_temp_c, "rain_mm": f.forecast_precip_7d_mm},
        "ndvi": {"current": f.ndvi_current, "trend_60d": f.ndvi_trend},
        "yield": {"kg_per_ha": kg, "confidence": conf, "note": note,
                  "field_total_kg": round(kg * f.field_size_ha) if kg else None},
        "rotation_options": [{"sequence": o.crop, "score": o.score, "reason": o.reason} for o in options],
        "water": water_balance(f),
    }


# ------------------------------------------------------------ fallback text
def rule_based_advice(facts: dict) -> str:
    y, w, rot = facts["yield"], facts["water"], facts["rotation_options"]
    best = rot[0] if rot else None
    lines = ["Summary: " + (f"expected yield about {y['kg_per_ha']:.0f} kg/ha ({y['confidence']} confidence)."
                             if y["kg_per_ha"] else "no yield estimate is available for this crop/location.")]
    lines.append("This season: " + ("NDVI is falling, check the field for stress, pests or water."
                                    if facts["ndvi"]["trend_60d"] < -0.05 else "crop greenness looks stable."))
    lines.append("Next seasons: " + (f"best option {best['sequence']} ({best['reason']})" if best
                                     else "no valid rotation found for these constraints."))
    lines.append(f"Water: {w['status']} (7-day gap {w['gap_7d_mm']} mm).")
    return "\n".join(lines)


# ------------------------------------------------------------------ Gemini
def _client():
    key = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    from google import genai
    return genai.Client(api_key=key)


def _sources(resp: Any) -> list[dict]:
    out = []
    try:
        for ch in resp.candidates[0].grounding_metadata.grounding_chunks or []:
            out.append({"title": getattr(ch.web, "title", ""), "url": getattr(ch.web, "uri", "")})
    except (AttributeError, IndexError, TypeError):
        pass
    return out


def _is_missing_model(e: Exception) -> bool:
    s = str(e)
    return "NOT_FOUND" in s or "404" in s


def _available_models(client) -> list[str]:
    """Models this API key can really use for generateContent, fast ones first."""
    names = []
    for m in client.models.list():
        acts = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", None) or []
        if "generateContent" in acts:
            names.append(m.name.removeprefix("models/"))
    rank = lambda n: (n.startswith(("gemini-2.5", "gemini-2.0", "gemini-1.")), 0 if "flash-lite" in n else 1, "preview" in n or "exp" in n, n)
    return sorted((n for n in names if "gemini" in n and "flash" in n), key=rank)


def _is_bad_argument(e: Exception) -> bool:
    s = str(e)
    return "INVALID_ARGUMENT" in s or "400" in s


def _config_variants(cfg: dict) -> list[tuple[str, dict]]:
    """Full config first, then simpler ones, because some models reject some options (400 INVALID_ARGUMENT)."""
    no_think = {k: v for k, v in cfg.items() if k != "thinking_config"}
    minimal = {k: cfg[k] for k in ("system_instruction", "max_output_tokens") if k in cfg}
    return [("full", cfg), ("no-thinking-option", no_think), ("minimal", minimal)]


def _generate(client, cfg: dict, prompt: str, types) -> tuple[Any, str, str]:
    """Call Gemini. Tries GEMINI_MODEL / DEFAULT_MODEL, then fallbacks, then asks the API which models exist.
    For each model, retries with simpler options if the API says INVALID_ARGUMENT. Returns (resp, model, variant)."""
    first = os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
    tried, queue, listed = [], [first, *[m for m in FALLBACK_MODELS if m != first]], False
    while queue:
        model = queue.pop(0)
        tried.append(model)
        try:
            last = None
            for name, variant in _config_variants(cfg):
                try:
                    return client.models.generate_content(model=model, contents=prompt,
                                                          config=types.GenerateContentConfig(**variant)), model, name
                except Exception as e:
                    last = e
                    if not _is_bad_argument(e) or _is_missing_model(e):
                        raise
            raise last
        except Exception as e:
            if not _is_missing_model(e):
                raise
            if not queue and not listed:                   # all known names failed: ask the API what exists
                listed = True
                queue = [m for m in _available_models(client) if m not in tried][:3]
    raise RuntimeError(f"no usable Gemini model found (tried {', '.join(tried)})")


def advise(f: EnvironmentalFeatures, language: str = "en", use_search: bool = False,
           question: str | None = None, client_factory: Callable[[], Any] = _client) -> dict:
    """Returns {"advice", "used_llm", "sources", "facts", "error"}. Never raises for LLM problems."""
    facts = build_facts(f)
    result = {"advice": rule_based_advice(facts), "used_llm": False, "sources": [], "facts": facts, "error": None, "seconds": None, "model": None}
    try:
        client = client_factory()
        if client is None:
            result["error"] = "GEMINI_API_KEY not set; showing rule-based advice"
            return result
        from google.genai import types
        cfg = dict(system_instruction=SYSTEM.format(words=MAX_WORDS) + f" Answer in {LANGS.get(language, 'English')}.",
                   max_output_tokens=1400, temperature=0.3,
                   thinking_config=types.ThinkingConfig(thinking_budget=0),          # no hidden 'thinking' = much faster
                   automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        if use_search:
            cfg["tools"] = [types.Tool(google_search=types.GoogleSearch())]
        prompt = "FACTS:\n" + json.dumps(facts, ensure_ascii=False) + (f"\n\nFarmer question: {question}" if question else "")
        t0 = perf_counter()
        resp, model, variant = _generate(client, cfg, prompt, types)
        result["seconds"] = round(perf_counter() - t0, 2)
        result["model"] = f"{model} ({variant} options)"
        text = (resp.text or "").strip()
        if not text:
            raise ValueError("empty response")
        words = text.split()
        if len(words) > MAX_WORDS:
            text = " ".join(words[:MAX_WORDS]).rstrip(".,;:") + "..."
        result.update(advice=text, used_llm=True, sources=_sources(resp))
    except Exception as e:                                  # network, quota, bad key, SDK missing...
        result["error"] = f"{type(e).__name__}: {e}; showing rule-based advice"
    return result