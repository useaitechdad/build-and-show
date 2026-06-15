"""Act 2 (extensive) orchestrator: the mini-SQL task across configs, N runs each.

    python3 run_sql.py --pilot --configs haiku_solo      # difficulty probe
    python3 run_sql.py --n 5 --configs haiku_solo,haiku_advisor,opus_solo
"""
import argparse
import json
import os

from _lib import load_key, PRICES, PRICES_SOURCE
from ag_agent import run_agent, MAX_TURNS
from ag_spec import CONFIGS
import sql_spec

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
SQL_DIR = os.path.join(RESULTS, "sql")
GRADER = "sql_grader.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--configs", default="haiku_solo,haiku_advisor,opus_solo")
    args = ap.parse_args()

    n = 1 if args.pilot else args.n
    configs = args.configs.split(",")
    key = load_key()
    os.makedirs(SQL_DIR, exist_ok=True)
    print(f"SQL TASK | configs={configs} | n={n} | max_turns={MAX_TURNS} | {PRICES_SOURCE}")

    runs = []
    for ck in configs:
        for i in range(n):
            workdir = os.path.join(SQL_DIR, "runs", ck, f"run{i+1}")
            print(f"\n  [{CONFIGS[ck]['label']}] run {i+1}  ({CONFIGS[ck]['model']})")
            r = run_agent(key, ck, workdir, spec_md=sql_spec.SPEC_MD,
                          initial_user=sql_spec.INITIAL_USER, grader_script=GRADER)
            r["run"] = i
            print(f"      → visible {r['visible'].get('passed')}/{r['visible'].get('total')}  "
                  f"HIDDEN {r['hidden_score']}/{r['hidden_total']}  turns={r['turns_used']}  "
                  f"adv_calls={r['advisor_calls']}  cost=${r['total_cost_usd']:.4f}")
            runs.append(r)
            open(os.path.join(workdir, "_run.json"), "w").write(json.dumps(r, indent=2))

    summary = {}
    for ck in configs:
        rs = [r for r in runs if r["config"] == ck and not r["error"]]
        if not rs:
            continue
        ht = rs[0]["hidden_total"] or 1
        summary[ck] = {
            "label": CONFIGS[ck]["label"], "model": CONFIGS[ck]["model"], "runs": len(rs),
            "mean_hidden_pct": round(100 * sum(r["hidden_score"] for r in rs) / (len(rs) * ht), 1),
            "hidden_total": ht,
            "full_pass_runs": sum(1 for r in rs if r["hidden_score"] == ht),
            "mean_turns": round(sum(r["turns_used"] for r in rs) / len(rs), 1),
            "mean_cost_usd": round(sum(r["total_cost_usd"] for r in rs) / len(rs), 6),
            "mean_advisor_calls": round(sum(r["advisor_calls"] for r in rs) / len(rs), 1),
        }

    out = {"pricing": PRICES, "pricing_source": PRICES_SOURCE, "max_turns": MAX_TURNS,
           "task": "mini-SQL", "summary": summary, "runs": runs}
    open(os.path.join(RESULTS, "sql_run.json"), "w").write(json.dumps(out, indent=2))

    print("\n" + "=" * 72)
    for ck, s in summary.items():
        print(f"{s['label']:24s} hidden {s['mean_hidden_pct']:5.1f}%  "
              f"({s['full_pass_runs']}/{s['runs']} perfect)  turns {s['mean_turns']:.1f}  "
              f"adv {s['mean_advisor_calls']}  ${s['mean_cost_usd']:.4f}/run")
    print("=" * 72)
    print(f"saved → {os.path.join(RESULTS, 'sql_run.json')}")


if __name__ == "__main__":
    main()
