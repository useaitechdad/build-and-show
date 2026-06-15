"""One agentic run: a real multi-turn tool loop. The executor reads SPEC.md,
writes solution.py, runs the visible tests, and iterates. The advisor config adds
the server-side advisor tool. Cost is accumulated across every turn from real
usage.iterations; the candidate is graded on HIDDEN tests at the end.
"""
import json
import os
import sys
import subprocess

from _lib import call_messages, accumulate_cost, new_totals
from ag_spec import (TOOLS, ADVISOR_TOOL, ADVISOR_TRIM, CONFIGS)
import ag_spec

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_TURNS = 16
TEST_TIMEOUT = 20


def _safe_path(workdir, path):
    full = os.path.normpath(os.path.join(workdir, path))
    if not full.startswith(os.path.normpath(workdir)):
        raise ValueError("path escapes workdir")
    return full


def run_grader(workdir, which, grader_script="ag_grader.py"):
    sol = os.path.join(workdir, "solution.py")
    if not os.path.exists(sol):
        return {"passed": 0, "total": None, "failures": [{"error": "solution.py not written"}]}
    try:
        out = subprocess.run([sys.executable, os.path.join(HERE, grader_script), sol, which],
                             capture_output=True, text=True, timeout=TEST_TIMEOUT, cwd=HERE)
        return json.loads(out.stdout.strip().splitlines()[-1])
    except subprocess.TimeoutExpired:
        return {"passed": 0, "total": None, "failures": [{"error": "tests timed out"}]}
    except Exception as e:
        return {"passed": 0, "total": None, "failures": [{"error": f"grader crash: {e}"}]}


def exec_tool(workdir, name, inp, grader_script="ag_grader.py"):
    try:
        if name == "read_file":
            return open(_safe_path(workdir, inp["path"])).read()[:8000]
        if name == "write_file":
            p = _safe_path(workdir, inp["path"])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(inp["content"])
            return f"wrote {inp['path']} ({len(inp['content'])} bytes)"
        if name == "run_tests":
            r = run_grader(workdir, "visible", grader_script)
            return json.dumps(r)
        return f"unknown tool {name}"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


def run_agent(key, config_key, workdir, spec_md=None, initial_user=None,
              grader_script="ag_grader.py", log=print):
    cfg = CONFIGS[config_key]
    spec_md = spec_md if spec_md is not None else ag_spec.SPEC_MD
    initial_user = initial_user if initial_user is not None else ag_spec.INITIAL_USER
    os.makedirs(workdir, exist_ok=True)
    open(os.path.join(workdir, "SPEC.md"), "w").write(spec_md)

    tools = list(TOOLS) + ([ADVISOR_TOOL] if cfg["use_advisor"] else [])
    user0 = initial_user + (ADVISOR_TRIM if cfg["use_advisor"] else "")
    messages = [{"role": "user", "content": user0}]
    totals = new_totals()
    turns = []
    advisor_plans = []
    error = None

    for turn in range(MAX_TURNS):
        body = {"model": cfg["model"], "max_tokens": 8192, "system": cfg["system"],
                "tools": tools, "messages": messages}
        status, resp = call_messages(key, body)
        if status != 200:
            error = f"http_{status}: {json.dumps(resp)[:200]}"
            log(f"      ✗ {error}")
            break
        accumulate_cost(totals, resp.get("usage", {}), cfg["model"])
        content = resp.get("content", [])
        messages.append({"role": "assistant", "content": content})

        text_bits, tool_calls, fired = [], [], False
        for b in content:
            t = b.get("type")
            if t == "text":
                text_bits.append(b["text"])
            elif t == "tool_use":
                tool_calls.append(b)
            elif t == "advisor_tool_result":
                fired = True
                c = b.get("content", {})
                if c.get("type") == "advisor_result":
                    advisor_plans.append({"turn": turn, "text": c.get("text", "")})

        called = [b["name"] for b in tool_calls]
        if fired:
            plan = advisor_plans[-1]["text"]
            log(f"      ⏸  advisor consulted → {plan[:140].strip()}…")
        log(f"      turn {turn+1}: {('+'.join(called) if called else '(end)')}")
        turns.append({"n": turn, "text": " ".join(text_bits)[:600],
                      "tools": called, "advisor_fired": fired})

        if resp.get("stop_reason") != "tool_use":
            break

        # execute client tool calls -> tool_result blocks
        results = []
        for tu in tool_calls:
            out = exec_tool(workdir, tu["name"], tu.get("input", {}), grader_script)
            results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": out})
        messages.append({"role": "user", "content": results})

    visible = run_grader(workdir, "visible", grader_script)
    hidden = run_grader(workdir, "hidden", grader_script)
    sol_path = os.path.join(workdir, "solution.py")
    return {
        "config": config_key, "label": cfg["label"], "model": cfg["model"],
        "error": error, "turns_used": len(turns),
        "advisor_calls": totals["advisor_calls"], "advisor_plans": advisor_plans,
        "visible": visible, "hidden": hidden,
        "hidden_score": hidden.get("passed", 0), "hidden_total": hidden.get("total"),
        "totals": totals,
        "exec_cost_usd": round(totals["exec_cost"], 6),
        "advisor_cost_usd": round(totals["adv_cost"], 6),
        "total_cost_usd": round(totals["exec_cost"] + totals["adv_cost"], 6),
        "solution_exists": os.path.exists(sol_path),
        "turn_log": turns,
    }
