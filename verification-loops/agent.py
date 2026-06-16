"""One agentic run: a real multi-turn tool loop. The model reads SPEC.md, writes
solution.py, and — depending on MODE — gets a different feedback tool:

  trust   read_file, write_file                       (no execution; ship on self-belief)
  test    read_file, write_file, run_tests(visible)   (run the example tests, fix, repeat)
  verify  read_file, write_file, verify(probe)        (differential check vs oracle, fix all, repeat)

The MODE is the ONLY thing that changes between configs — same model, same task, same
turn budget. At the end the candidate is graded on the HIDDEN set it never saw.
"""
import json
import os
import subprocess
import sys

from _lib import call_messages, add_usage, new_totals
import task

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_TURNS = 16
TIMEOUT = 20

READ = {"name": "read_file", "description": "Read a file from the workspace.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}
WRITE = {"name": "write_file", "description": "Write (overwrite) a file in the workspace.",
         "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                          "required": ["path", "content"]}}
RUN_TESTS = {"name": "run_tests", "description": "Run the example tests against your solution.py and return pass/fail with failing cases.",
             "input_schema": {"type": "object", "properties": {}}}
VERIFY = {"name": "verify", "description": "Check your solution.py against a broad set of cases and return pass/fail with failing cases (the query, the expected result, and what you produced).",
          "input_schema": {"type": "object", "properties": {}}}

MODES = {
    "trust": {
        "tools": [READ, WRITE],
        "system": ("You are a coding agent. Implement solution.py to satisfy SPEC.md. "
                   "You CANNOT run code in this environment. Read the spec carefully, write the "
                   "complete solution, and when you are confident it is correct, stop."),
    },
    "test": {
        "tools": [READ, WRITE, RUN_TESTS],
        "system": ("You are a coding agent. Implement solution.py to satisfy SPEC.md. "
                   "After writing it, call run_tests to run the example tests. Fix any failures and "
                   "re-run until all the example tests pass, then stop."),
    },
    "verify": {
        "tools": [READ, WRITE, VERIFY],
        "system": ("You are a coding agent. Implement solution.py to satisfy SPEC.md. "
                   "After writing it, call verify to check your implementation against a broad set of "
                   "cases. Read every failing case (query, expected, got), fix the root cause, and "
                   "re-run verify until it reports ZERO failures, then stop."),
    },
}


def _safe(workdir, path):
    full = os.path.normpath(os.path.join(workdir, path))
    if not full.startswith(os.path.normpath(workdir)):
        raise ValueError("path escapes workdir")
    return full


def grade(workdir, which):
    sol = os.path.join(workdir, "solution.py")
    if not os.path.exists(sol):
        return {"passed": 0, "total": len(task.SETS[which]), "failures": [{"error": "solution.py not written"}]}
    try:
        out = subprocess.run([sys.executable, os.path.join(HERE, "grader.py"), sol, which],
                             capture_output=True, text=True, timeout=TIMEOUT, cwd=HERE)
        return json.loads(out.stdout.strip().splitlines()[-1])
    except subprocess.TimeoutExpired:
        return {"passed": 0, "total": len(task.SETS[which]), "failures": [{"error": "timed out"}]}
    except Exception as e:
        return {"passed": 0, "total": len(task.SETS[which]), "failures": [{"error": f"grader crash: {e}"}]}


def exec_tool(workdir, name, inp):
    try:
        if name == "read_file":
            return open(_safe(workdir, inp["path"])).read()[:8000]
        if name == "write_file":
            p = _safe(workdir, inp["path"])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(inp["content"])
            return f"wrote {inp['path']} ({len(inp['content'])} bytes)"
        if name == "run_tests":
            return json.dumps(grade(workdir, "visible"))
        if name == "verify":
            return json.dumps(grade(workdir, "probe"))
        return f"unknown tool {name}"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


def run_agent(key, mode, model, workdir, log=print):
    cfg = MODES[mode]
    os.makedirs(workdir, exist_ok=True)
    open(os.path.join(workdir, "SPEC.md"), "w").write(task.SPEC_MD)

    messages = [{"role": "user", "content": task.INITIAL_USER}]
    totals = new_totals()
    turns = []
    error = None

    for turn in range(MAX_TURNS):
        body = {"model": model, "max_tokens": 8192, "system": cfg["system"],
                "tools": cfg["tools"], "messages": messages}
        status, resp = call_messages(key, body)
        if status != 200:
            error = f"http_{status}: {json.dumps(resp)[:200]}"
            log(f"      x {error}")
            break
        add_usage(totals, resp.get("usage", {}), model)
        content = resp.get("content", [])
        messages.append({"role": "assistant", "content": content})

        tool_calls, checks = [], []
        for b in content:
            if b.get("type") == "tool_use":
                tool_calls.append(b)
        called = [b["name"] for b in tool_calls]
        log(f"      turn {turn+1}: {('+'.join(called) if called else '(end)')}")

        if resp.get("stop_reason") != "tool_use":
            turns.append({"n": turn, "tools": called, "check": None})
            break

        results = []
        for tu in tool_calls:
            out = exec_tool(workdir, tu["name"], tu.get("input", {}))
            if tu["name"] in ("run_tests", "verify"):
                try:
                    r = json.loads(out)
                    checks.append({"tool": tu["name"], "passed": r.get("passed"), "total": r.get("total"),
                                   "n_fail": len(r.get("failures", []))})
                except Exception:
                    pass
            results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": out})
        messages.append({"role": "user", "content": results})
        turns.append({"n": turn, "tools": called, "check": checks[-1] if checks else None})

    visible = grade(workdir, "visible")
    hidden = grade(workdir, "hidden")
    return {
        "mode": mode, "model": model, "error": error, "turns_used": len(turns),
        "visible": visible, "hidden": hidden,
        "hidden_score": hidden.get("passed", 0), "hidden_total": hidden.get("total"),
        "cost_usd": round(totals["cost"], 6), "tokens_in": totals["in"], "tokens_out": totals["out"],
        "api_calls": totals["calls"], "turn_log": turns,
        "solution_exists": os.path.exists(os.path.join(workdir, "solution.py")),
    }
