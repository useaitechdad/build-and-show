"""One cheap call to confirm the key has advisor-tool beta access AND that the
advisor actually fires. Prints status, whether advisor was invoked, and the
executor-vs-advisor token split. No demo numbers depend on this run."""
import json
from _lib import load_key, call_messages, summarize_usage, BETA

SYSTEM = (
    "You have access to an `advisor` tool backed by a stronger reviewer model. "
    "It takes NO parameters. Call advisor() BEFORE substantive work, after a little "
    "orientation. On tasks longer than a few steps, call it at least once before "
    "committing to an approach."
)

body = {
    "model": "claude-sonnet-4-6",
    "max_tokens": 1024,
    "system": SYSTEM,
    "tools": [
        {"type": "advisor_20260301", "name": "advisor",
         "model": "claude-opus-4-8", "max_tokens": 2048},
    ],
    "messages": [{
        "role": "user",
        "content": "Outline (do not fully implement) a thread-safe bounded worker "
                   "pool with graceful shutdown in Python. (Advisor: keep guidance "
                   "under 80 words.)",
    }],
}

key = load_key()
print(f"key loaded: {len(key)} chars, prefix {key[:7]}…   beta={BETA}\n")
status, resp = call_messages(key, body)
print(f"HTTP status: {status}\n")

if status != 200:
    print("RESPONSE (error):")
    print(json.dumps(resp, indent=2)[:2000])
else:
    blocks = [b.get("type") for b in resp.get("content", [])]
    print("content block types:", blocks)
    advisor_fired = any(b.get("type") == "advisor_tool_result" for b in resp.get("content", []))
    print("advisor fired:", advisor_fired)
    for b in resp.get("content", []):
        if b.get("type") == "advisor_tool_result":
            c = b.get("content", {})
            print("  advisor result type:", c.get("type"))
            txt = c.get("text", "")
            if txt:
                print("  advisor said:", txt[:300].replace("\n", " "))
    print("\nusage split:", json.dumps(summarize_usage(resp.get("usage", {})), indent=2))
    print("\nraw usage.iterations:")
    print(json.dumps(resp.get("usage", {}).get("iterations", []), indent=2))
