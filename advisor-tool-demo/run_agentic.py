"""Act 2 orchestrator: run the agentic loop N times per config and aggregate
hidden-test success + real cost.

    python3 run_agentic.py --pilot          # 1 run per config (calibrate)
    python3 run_agentic.py --n 5
"""
import argparse
import json
import os

from _lib import load_key, PRICES, PRICES_SOURCE
from ag_agent import run_agent, MAX_TURNS
from ag_spec import CONFIGS

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
AG_DIR = os.path.join(RESULTS, "agentic")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--configs", default="sonnet_solo,advisor,opus_solo")
    args = ap.parse_args()

    n = 1 if args.pilot else args.n
    configs = args.configs.split(",")
    key = load_key()
    os.makedirs(AG_DIR, exist_ok=True)
    print(f"AGENTIC | configs={configs} | n={n} | max_turns={MAX_TURNS} | {PRICES_SOURCE}")

    runs = []
    for ck in configs:
        for i in range(n):
            workdir = os.path.join(AG_DIR, "runs", ck, f"run{i+1}")
            print(f"\n  [{CONFIGS[ck]['label']}] run {i+1}  ({CONFIGS[ck]['model']})")
            r = run_agent(key, ck, workdir)
            r["run"] = i
            hp, ht = r["hidden_score"], r["hidden_total"]
            vp = r["visible"].get("passed")
            print(f"      → visible {vp}/{r['visible'].get('total')}  "
                  f"HIDDEN {hp}/{ht}  turns={r['turns_used']}  "
                  f"adv_calls={r['advisor_calls']}  cost=${r['total_cost_usd']:.4f}")
            runs.append(r)
            # save transcript per run
            open(os.path.join(workdir, "_run.json"), "w").write(json.dumps(r, indent=2))

    # aggregate
    summary = {}
    for ck in configs:
        rs = [r for r in runs if r["config"] == ck and not r["error"]]
        if not rs:
            continue
        ht = rs[0]["hidden_total"] or 1
        summary[ck] = {
            "label": CONFIGS[ck]["label"], "model": CONFIGS[ck]["model"], "runs": len(rs),
            "mean_hidden_score": round(sum(r["hidden_score"] for r in rs) / len(rs), 2),
            "hidden_total": ht,
            "mean_hidden_pct": round(100 * sum(r["hidden_score"] for r in rs) / (len(rs) * ht), 1),
            "full_hidden_pass_runs": sum(1 for r in rs if r["hidden_score"] == ht),
            "mean_turns": round(sum(r["turns_used"] for r in rs) / len(rs), 1),
            "mean_cost_usd": round(sum(r["total_cost_usd"] for r in rs) / len(rs), 6),
            "mean_advisor_calls": round(sum(r["advisor_calls"] for r in rs) / len(rs), 1),
        }

    out = {"pricing": PRICES, "pricing_source": PRICES_SOURCE,
           "max_turns": MAX_TURNS, "summary": summary, "runs": runs}
    open(os.path.join(RESULTS, "agentic_run.json"), "w").write(json.dumps(out, indent=2))

    print("\n" + "=" * 72)
    for ck, s in summary.items():
        print(f"{s['label']:24s} hidden {s['mean_hidden_pct']:5.1f}%  "
              f"({s['full_hidden_pass_runs']}/{s['runs']} perfect)  "
              f"turns {s['mean_turns']:.1f}  ${s['mean_cost_usd']:.4f}/run")
    print("=" * 72)
    print(f"saved → {os.path.join(RESULTS, 'agentic_run.json')}")


if __name__ == "__main__":
    main()
