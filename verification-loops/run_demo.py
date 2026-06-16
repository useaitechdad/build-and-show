"""Run the blind-vs-verify demo: the SAME model under three modes, N runs each,
graded on the HIDDEN set. Writes results/verify_run.json + per-run traces.

    python3 run_demo.py --n 3
    python3 run_demo.py --n 3 --model claude-haiku-4-5-20251001 --modes trust,test,verify
"""
import argparse
import json
import os

from _lib import load_key, PRICES, PRICES_SOURCE
from agent import run_agent, MAX_TURNS
import task

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

LABELS = {"trust": "Trust it (no checks)", "test": "Test it (example tests)",
          "verify": "Verify it (differential)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--modes", default="trust,test,verify")
    args = ap.parse_args()

    modes = args.modes.split(",")
    key = load_key()
    os.makedirs(os.path.join(RESULTS, "runs"), exist_ok=True)
    print(f"VERIFY DEMO | model={args.model} | modes={modes} | n={args.n} | "
          f"max_turns={MAX_TURNS}\n{PRICES_SOURCE}")
    print(f"sets: visible={len(task.VISIBLE_SQL)}  probe={len(task.PROBE_SQL)}  hidden={len(task.HIDDEN_SQL)}")

    runs = []
    for mode in modes:
        for i in range(args.n):
            workdir = os.path.join(RESULTS, "runs", mode, f"run{i+1}")
            print(f"\n  [{LABELS[mode]}] run {i+1}  ({args.model})")
            r = run_agent(key, mode, args.model, workdir)
            r["run"] = i
            print(f"      -> visible {r['visible'].get('passed')}/{r['visible'].get('total')}  "
                  f"HIDDEN {r['hidden_score']}/{r['hidden_total']}  turns={r['turns_used']}  "
                  f"cost=${r['cost_usd']:.4f}")
            runs.append(r)
            open(os.path.join(workdir, "_run.json"), "w").write(json.dumps(r, indent=2))

    summary = {}
    for mode in modes:
        rs = [r for r in runs if r["mode"] == mode and not r["error"]]
        if not rs:
            continue
        ht = rs[0]["hidden_total"] or 1
        summary[mode] = {
            "label": LABELS[mode], "runs": len(rs), "hidden_total": ht,
            "mean_hidden_pct": round(100 * sum(r["hidden_score"] for r in rs) / (len(rs) * ht), 1),
            "min_hidden": min(r["hidden_score"] for r in rs),
            "max_hidden": max(r["hidden_score"] for r in rs),
            "perfect_runs": sum(1 for r in rs if r["hidden_score"] == ht),
            "mean_turns": round(sum(r["turns_used"] for r in rs) / len(rs), 1),
            "mean_cost_usd": round(sum(r["cost_usd"] for r in rs) / len(rs), 6),
        }

    out = {"model": args.model, "pricing": PRICES, "pricing_source": PRICES_SOURCE,
           "max_turns": MAX_TURNS, "n": args.n, "task": "mini-SQL",
           "sets": {"visible": len(task.VISIBLE_SQL), "probe": len(task.PROBE_SQL),
                    "hidden": len(task.HIDDEN_SQL)},
           "summary": summary, "runs": runs}
    open(os.path.join(RESULTS, "verify_run.json"), "w").write(json.dumps(out, indent=2))

    print("\n" + "=" * 72)
    for mode in modes:
        s = summary.get(mode)
        if s:
            print(f"{s['label']:28s} hidden {s['mean_hidden_pct']:5.1f}%  "
                  f"(range {s['min_hidden']}-{s['max_hidden']}/{s['hidden_total']}, "
                  f"{s['perfect_runs']}/{s['runs']} perfect)  turns {s['mean_turns']:.1f}  "
                  f"${s['mean_cost_usd']:.4f}/run")
    print("=" * 72)
    print(f"saved -> {os.path.join(RESULTS, 'verify_run.json')}")


if __name__ == "__main__":
    main()
