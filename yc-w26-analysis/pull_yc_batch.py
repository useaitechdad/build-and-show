#!/usr/bin/env python3
"""Pull a Y Combinator batch from the public yc-oss API and find the solo builders.

Primary-source data: the yc-oss API mirrors YC's own public Algolia directory
index (the one that powers ycombinator.com/companies). No credentials, no PII
beyond what YC already publishes. We only assert numbers this script reproduces.

The public directory exposes `team_size` (total headcount) but NOT founder count,
so we count companies that are a single person total -- team_size == 1 -- the
strongest claim we can stand behind from primary data.

Usage:
    python3 pull_yc_batch.py --batch winter-2026
    python3 pull_yc_batch.py --batch winter-2026 --demo   # cinematic, paced output
"""
import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.request import urlopen

API = "https://yc-oss.github.io/api/batches/{slug}.json"
RESULTS = Path(__file__).resolve().parent.parent / "results"
# Whole-word match so "AI" doesn't fire inside "maintain", "chair", etc.
AI_RE = re.compile(
    r"\b(ai|a\.i\.|artificial intelligence|machine learning|"
    r"llm|llms|agent|agents|agentic|neural|deep learning)\b",
    re.IGNORECASE,
)


def fetch(slug: str) -> list:
    url = API.format(slug=slug)
    with urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())


def is_ai(c: dict) -> bool:
    hay = " ".join([
        c.get("one_liner", "") or "",
        c.get("long_description", "") or "",
        " ".join(c.get("tags", []) or []),
        " ".join(c.get("industries", []) or []),
    ])
    return bool(AI_RE.search(hay))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="winter-2026")
    ap.add_argument("--demo", action="store_true",
                    help="Paced, cinematic output for screen capture")
    args = ap.parse_args()
    pause = (lambda s: time.sleep(s)) if args.demo else (lambda s: None)

    print(f"$ pull Y Combinator {args.batch.replace('-', ' ').title()} batch")
    print("  source: yc-oss.github.io/api  (mirror of YC's public directory)")
    pause(0.8)
    companies = fetch(args.batch)
    total = len(companies)
    print(f"  fetched {total} companies\n")
    pause(0.6)

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{args.batch}_raw.json").write_text(json.dumps(companies, indent=2))

    # --- AI share (our own count, not a third party's) ---
    ai = [c for c in companies if is_ai(c)]
    print(f"  scanning for AI companies ...")
    pause(0.7)
    print(f"  {len(ai)}/{total} mention AI  ({round(100*len(ai)/total)}%)\n")
    pause(0.6)

    # --- team-size distribution ---
    sizes = Counter(c.get("team_size") for c in companies if c.get("team_size") is not None)
    solo = sorted((c for c in companies if c.get("team_size") == 1),
                  key=lambda c: c["name"].lower())
    print("  team size   companies")
    for n in range(1, 6):
        bar = "#" * sizes.get(n, 0)
        print(f"     {n:>2}        {sizes.get(n,0):>3}  {bar}")
    print(f"     6+        {sum(v for k,v in sizes.items() if k and k>=6):>3}\n")
    pause(0.9)

    print(f"  >>> {len(solo)} companies are ONE person. No cofounder. No employees.\n")
    pause(1.0)
    for c in solo:
        print(f"    - {c['name']}: {c['one_liner']}")
        pause(0.25)
    print()

    # --- what the solo builders are building ---
    solo_industries = Counter()
    for c in solo:
        for i in c.get("industries", []) or []:
            solo_industries[i] += 1

    # --- trend: is one-person building actually rising? ---
    trend_slugs = ["winter-2024", "summer-2024", "winter-2025",
                   "summer-2025", "fall-2025", "winter-2026"]
    print("  one-person companies, batch over batch:")
    trend = []
    for slug in trend_slugs:
        d = fetch(slug)
        n = sum(1 for c in d if c.get("team_size") == 1)
        pct = round(100 * n / len(d))
        trend.append({"batch": slug, "total": len(d), "solo": n, "pct": pct})
        label = slug.replace("-", " ").title()
        print(f"     {label:14} {n:>2}/{len(d):<3} ({pct}%)  {'#'*n}")
        pause(0.3)
    print()

    out = {
        "batch": args.batch,
        "total": total,
        "ai_count": len(ai),
        "ai_pct": round(100 * len(ai) / total),
        "team_size_distribution": {str(k): v for k, v in sorted(sizes.items(), key=lambda x: (x[0] is None, x[0]))},
        "solo_count": len(solo),
        "solo_pct": round(100 * len(solo) / total),
        "solo_companies": [
            {"name": c["name"], "one_liner": c["one_liner"],
             "industries": c.get("industries", []), "url": c.get("url", "")}
            for c in solo
        ],
        "solo_top_industries": solo_industries.most_common(),
        "solo_trend": trend,
    }
    (RESULTS / f"{args.batch}_analysis.json").write_text(json.dumps(out, indent=2))
    print(f"  wrote results/{args.batch}_analysis.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
