"""Grade a candidate solution.py by differential comparison against the oracle
(oracle.query) over a named query set.

    python3 grader.py <solution.py> visible|probe|hidden   -> prints JSON verdict

Used two ways: as the agent's in-loop tool (visible / probe) and as the final,
never-seen scoreboard (hidden).
"""
import importlib.util
import json
import math
import sys

import oracle
from oracle import DATASET
from task import SETS


def load_query(path):
    spec = importlib.util.spec_from_file_location("solution", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "query")


def val_eq(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    return a == b


def rows_eq(got, want):
    if not isinstance(got, list) or len(got) != len(want):
        return False
    for g, w in zip(got, want):
        if not isinstance(g, dict) or set(g.keys()) != set(w.keys()):
            return False
        for k in w:
            if not val_eq(g[k], w[k]):
                return False
    return True


def main():
    path, which = sys.argv[1], sys.argv[2]
    sqls = SETS[which]
    try:
        cand = load_query(path)
    except Exception as e:
        print(json.dumps({"passed": 0, "total": len(sqls),
                          "failures": [{"error": f"import failed: {type(e).__name__}: {e}"}]}))
        return

    passed, failures = 0, []
    for sql in sqls:
        want = oracle.query(sql, [dict(r) for r in DATASET])
        try:
            got = cand(sql, [dict(r) for r in DATASET])
        except Exception as e:
            failures.append({"sql": sql, "error": f"{type(e).__name__}: {e}", "expected": want})
            continue
        if rows_eq(got, want):
            passed += 1
        else:
            failures.append({"sql": sql, "expected": want, "got": got})

    print(json.dumps({"passed": passed, "total": len(sqls), "failures": failures[:6]}))


if __name__ == "__main__":
    main()
