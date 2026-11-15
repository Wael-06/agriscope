"""Smallest possible Gemini call, to separate key/model problems from the advisor code.
Run:  python gemini_ping.py            (needs GEMINI_API_KEY in the environment or in .env)
"""
import os
import sys

from dotenv import load_dotenv
from google import genai

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
if not key:
    sys.exit("GEMINI_API_KEY not set")
client = genai.Client(api_key=key)
usable = [m.name for m in client.models.list()
          if "generateContent" in (getattr(m, "supported_actions", None) or []) and "gemini" in m.name]
print("models your key can use:", usable[:15])
for name in ("gemini-2.5-flash-lite", "gemini-2.5-flash"):
    try:
        r = client.models.generate_content(model=name, contents="Say OK in one word.")
        print(f"{name}: works -> {r.text.strip()!r}")
    except Exception as e:
        print(f"{name}: FAILED -> {e}")