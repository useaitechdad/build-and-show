"""Grade a candidate solution.py against a test set. Runs as a subprocess so the
model's code is imported in isolation.

    python3 ag_grader.py <solution.py> visible|hidden   -> prints JSON verdict
"""
import importlib.util
import json
import math
import sys

from ag_spec import VISIBLE_TESTS, HIDDEN_TESTS


def load_eval(path):
    spec = importlib.util.spec_from_file_location("solution", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "evaluate")


def check(got, expected):
    if isinstance(expected, dict) and "raises" in expected:
        return False, f"expected raise {expected['raises']}, got {got!r}"
    if isinstance(expected, bool):
        if isinstance(got, bool) and got == expected:
            return True, ""
        return False, f"expected bool {expected}, got {got!r}"
    # numeric
    try:
        if math.isclose(float(got), float(expected), rel_tol=1e-9, abs_tol=1e-9):
            return True, ""
    except Exception:
        pass
    return False, f"expected {expected}, got {got!r}"


def main():
    path, which = sys.argv[1], sys.argv[2]
    tests = VISIBLE_TESTS if which == "visible" else HIDDEN_TESTS
    try:
        evaluate = load_eval(path)
    except Exception as e:
        print(json.dumps({"passed": 0, "total": len(tests),
                          "failures": [{"error": f"import failed: {type(e).__name__}: {e}"}]}))
        return

    passed, failures = 0, []
    for expr, variables, expected in tests:
        want_exc = expected.get("raises") if isinstance(expected, dict) else None
        try:
            got = evaluate(expr, variables) if variables is not None else evaluate(expr)
        except Exception as e:
            if want_exc and type(e).__name__ == want_exc:
                passed += 1
            else:
                failures.append({"expr": expr, "expected": want_exc or expected,
                                 "error": f"{type(e).__name__}: {e}"})
            continue
        if want_exc:
            failures.append({"expr": expr, "expected": f"raise {want_exc}", "got": repr(got)})
            continue
        ok, msg = check(got, expected)
        if ok:
            passed += 1
        else:
            failures.append({"expr": expr, "detail": msg})

    print(json.dumps({"passed": passed, "total": len(tests), "failures": failures[:12]}))


if __name__ == "__main__":
    main()
