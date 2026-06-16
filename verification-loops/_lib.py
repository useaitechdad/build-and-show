"""Shared helpers: API key loading, one Messages API call, token-cost accounting.

Pure standard library (urllib) so the repo is clone-and-run with no SDK.

Key resolution order:
  1. ANTHROPIC_API_KEY environment variable
  2. a local `.env` file in this folder (raw key, or a KEY=VALUE line)
No key is committed; `.env` is gitignored.
"""
import json
import os
import time
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
HERE = os.path.dirname(os.path.abspath(__file__))


def load_key():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"].strip()
    env = os.path.join(HERE, ".env")
    if os.path.exists(env):
        raw = open(env).read().strip()
        for line in raw.splitlines():
            if line.strip().startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
        return raw  # whole file is the key
    raise SystemExit("No API key: set ANTHROPIC_API_KEY or create a local .env")


def call_messages(api_key, body, max_retries=4):
    """POST /v1/messages. Returns (status, parsed_json)."""
    data = json.dumps(body).encode()
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    last = None
    for attempt in range(max_retries):
        req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            txt = e.read().decode()
            try:
                parsed = json.loads(txt)
            except Exception:
                parsed = {"raw": txt}
            if e.code in (429, 500, 503, 529) and attempt < max_retries - 1:
                wait = 2 ** attempt * 5
                print(f"  [retry] HTTP {e.code}, waiting {wait}s...")
                time.sleep(wait)
                last = (e.code, parsed)
                continue
            return e.code, parsed
        except Exception as e:
            last = (None, {"error": str(e)})
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt * 5)
                continue
            return None, {"error": str(e)}
    return last or (None, {"error": "unknown"})


# --- Pricing (USD per 1M tokens). List rates, verified platform.claude.com 2026-06-15 ---
PRICES = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
}
PRICES_SOURCE = "list rates per 1M tok, verified platform.claude.com 2026-06-15"


def new_totals():
    return {"in": 0, "out": 0, "cost": 0.0, "calls": 0}


def add_usage(totals, usage, model):
    """Add one Messages call's top-level usage to running totals (no advisor here)."""
    p = PRICES[model]
    ti = usage.get("input_tokens", 0)
    to = usage.get("output_tokens", 0)
    totals["in"] += ti
    totals["out"] += to
    totals["cost"] += ti / 1e6 * p["input"] + to / 1e6 * p["output"]
    totals["calls"] += 1
    return totals
