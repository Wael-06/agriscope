"""Manual test for the Gemini advisor.  Run from the backend folder (the one that contains `app/`):

    export GEMINI_API_KEY=your_key            (Windows PowerShell:  $env:GEMINI_API_KEY="your_key")
    python test_llm_main.py                   # Iowa maize, English, no web search
    python test_llm_main.py --place china --lang ar --search
    python test_llm_main.py --question "Should I plant earlier next year?"

It prints the facts sent to Gemini, then Gemini's answer, and says clearly whether Gemini was really used.
"""
import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):          # Windows consoles (cp1252) cannot print the arrow in rotation names
    sys.stdout.reconfigure(encoding="utf-8")

from app.engine.advisor import DEFAULT_MODEL, advise
from app.schemas.contracts import EnvironmentalFeatures

PLACES = {   # lat, lon, crop, planting date
    "usa":   (42.0, -93.6, "maize", "2026-04-15"),
    "china": (34.7, 113.6, "wheat", "2026-10-20"),
    "egypt": (31.1, 30.9, "wheat", "2026-11-15"),
}


def make_features(place: str) -> EnvironmentalFeatures:
    lat, lon, crop, day = PLACES[place]
    return EnvironmentalFeatures(
        lat=lat, lon=lon, crop=crop, field_size_ha=2.0, planting_date=day,
        avg_temp_c=18.0, max_temp_c=25.0, total_precip_mm=60.0, avg_solar_rad=20.0,
        soil_moisture_root=0.30, soil_moisture_top=0.25, ndvi_current=0.55, ndvi_trend=-0.08,
        forecast_precip_7d_mm=4.0, forecast_max_temp_c=27.0, forecast_et0_mm_day=4.5,
        soil_texture="clay", irrigation_availability="limited", planning_horizon_seasons=3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--place", choices=PLACES, default="usa")
    ap.add_argument("--lang", choices=["en", "ar"], default="en")
    ap.add_argument("--search", action="store_true", help="let Gemini use Google Search")
    ap.add_argument("--question", default=None)
    ap.add_argument("--list-models", action="store_true", help="print the Gemini models your key can use, then exit")
    a = ap.parse_args()
    if a.list_models:
        from app.engine.advisor import _available_models, _client
        c = _client()
        print(_available_models(c) if c else "GEMINI_API_KEY not set")
        return 0

    print("GEMINI_API_KEY set:", bool(os.environ.get("GEMINI_API_KEY")),
          "| model:", os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))
    r = advise(make_features(a.place), language=a.lang, use_search=a.search, question=a.question)

    print("\n=== FACTS sent to Gemini ===")
    print(json.dumps(r["facts"], indent=2, ensure_ascii=False))
    print("\n=== ADVICE ===")
    print(r["advice"])
    print(f"\n({len(r['advice'].split())} words)")
    print(f"Gemini call time: {r['seconds']} s" if r["seconds"] is not None else "")
    if r["sources"]:
        print("\n=== SOURCES ===")
        for s in r["sources"]:
            print("-", s["title"], s["url"])
    print("\n=== RESULT ===")
    print("model used:", r.get("model"))
    if r["used_llm"]:
        print("OK: Gemini answered.")
        return 0
    print("Gemini was NOT used ->", r["error"])
    return 1


if __name__ == "__main__":
    sys.exit(main())