"""Shared helpers for the advisor-tool demo: key loading, one Messages API call,
and cost accounting. Pure Python standard library (urllib) — no SDK to install.

The API key is read from the ANTHROPIC_API_KEY environment variable, or from a
local `.env` file next to this script (gitignored). The advisor tool is in beta;
your key needs access to the `advisor-tool-2026-03-01` beta. Calls bill to YOUR key.
"""
import json
import os
import time
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
BETA = "advisor-tool-2026-03-01"

# --- Pricing (USD per 1M tokens), Claude API list rates (verified 2026-06-15). ---
PRICES = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-8":   {"input": 5.00, "output": 25.00},
}
PRICES_SOURCE = "Claude API list rates per 1M tokens (platform.claude.com/docs pricing)"


def load_key():
    """ANTHROPIC_API_KEY from env, or from a local .env (raw key or KEY=VALUE line)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"].strip()
    envpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(envpath):
        raw = open(envpath).read().strip()
        for line in raw.splitlines():
            if line.strip().startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
        return raw  # whole file is the key
    raise RuntimeError(
        "No API key. Set ANTHROPIC_API_KEY (a key with advisor-tool beta access), "
        "e.g.  export ANTHROPIC_API_KEY=sk-ant-..."
    )


def call_messages(api_key, body, max_retries=3):
    """POST /v1/messages with the advisor beta header. Returns (status, parsed_json)."""
    data = json.dumps(body).encode()
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": BETA,
        "content-type": "application/json",
    }
    last_err = None
    for attempt in range(max_retries):
        req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode()
            try:
                parsed = json.loads(body_txt)
            except Exception:
                parsed = {"raw": body_txt}
            if e.code in (429, 500, 503, 529) and attempt < max_retries - 1:
                wait = 2 ** attempt * 5
                print(f"  [retry] HTTP {e.code}, waiting {wait}s...")
                time.sleep(wait)
                last_err = (e.code, parsed)
                continue
            return e.code, parsed
        except Exception as e:
            last_err = (None, {"error": str(e)})
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt * 5)
                continue
            return None, {"error": str(e)}
    return last_err if last_err else (None, {"error": "unknown"})


def accumulate_cost(totals, usage, executor_model):
    """Add one API call's usage.iterations into running totals (across many turns).
    Executor input is billed per call (no caching used here)."""
    for it in usage.get("iterations", []):
        if it.get("type") == "advisor_message":
            p = PRICES[it.get("model", "claude-opus-4-8")]
            ti, to = it.get("input_tokens", 0), it.get("output_tokens", 0)
            totals["adv_in"] += ti
            totals["adv_out"] += to
            totals["adv_cost"] += ti / 1e6 * p["input"] + to / 1e6 * p["output"]
            totals["advisor_calls"] += 1
        elif it.get("type") == "message":
            p = PRICES[executor_model]
            ti, to = it.get("input_tokens", 0), it.get("output_tokens", 0)
            totals["exec_in"] += ti
            totals["exec_out"] += to
            totals["exec_cost"] += ti / 1e6 * p["input"] + to / 1e6 * p["output"]
    return totals


def new_totals():
    return {"exec_in": 0, "exec_out": 0, "adv_in": 0, "adv_out": 0,
            "exec_cost": 0.0, "adv_cost": 0.0, "advisor_calls": 0}


def summarize_usage(usage):
    """Split usage.iterations into executor vs advisor token totals."""
    execu_in = execu_out = adv_in = adv_out = adv_cache_read = 0
    advisor_calls = 0
    for it in usage.get("iterations", []):
        if it.get("type") == "advisor_message":
            advisor_calls += 1
            adv_in += it.get("input_tokens", 0)
            adv_out += it.get("output_tokens", 0)
            adv_cache_read += it.get("cache_read_input_tokens", 0)
        elif it.get("type") == "message":
            execu_in += it.get("input_tokens", 0)
            execu_out += it.get("output_tokens", 0)
    return {
        "advisor_calls": advisor_calls,
        "executor_input_tokens": execu_in,
        "executor_output_tokens": execu_out,
        "advisor_input_tokens": adv_in,
        "advisor_output_tokens": adv_out,
        "advisor_cache_read_tokens": adv_cache_read,
    }
