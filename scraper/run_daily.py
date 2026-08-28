#!/usr/bin/env python3
"""Nightly orchestrator: run all chain scrapers, write snapshots + diffs.

Usage:
  python3 run_daily.py            # full run (all products)
  python3 run_daily.py 200        # smoke run (N products per chain)

Outputs:
  data/latest/<chain>.jsonl          full snapshot (overwritten each run)
  data/history/<chain>/<date>.jsonl  ONLY rows whose price changed vs yesterday
  data/latest/prices.jsonl           merged all chains (what the API reads)
  data/latest/summary.json           counts per chain for monitoring
"""
import sys
import os
import json
import importlib
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CHAINS = ["silvan", "xlbyg", "stark", "bauhaus", "davidsen",
          "fog", "haraldnyborg", "power", "skousen"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_prev(chain: str) -> dict[str, dict]:
    """Previous snapshot keyed by (sku or url)."""
    path = os.path.join(ROOT, "data", "latest", f"{chain}.jsonl")
    prev = {}
    if not os.path.exists(path):
        return prev
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = r.get("sku") or r.get("url")
            prev[key] = r
    return prev


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    today = date.today().isoformat()
    summary = {}

    for chain in CHAINS:
        print(f"=== {chain} ===")
        try:
            mod = importlib.import_module(chain)
            rows = mod.scrape(limit)
        except Exception as e:
            print(f"  FAILED: {e}")
            summary[chain] = {"error": str(e)}
            continue

        out = os.path.join(ROOT, "data", "latest", f"{chain}.jsonl")
        from common import write_jsonl
        write_jsonl(out, rows)

        # diff vs previous snapshot -> history file (changes only)
        prev = load_prev(chain)
        changes = []
        for r in rows:
            key = r.get("sku") or r.get("url")
            old = prev.get(key)
            if old and old.get("price") != r.get("price"):
                changes.append({"key": key, "old_price": old.get("price"),
                                "new_price": r.get("price"),
                                "date": today, "url": r.get("url")})
        if changes:
            hdir = os.path.join(ROOT, "data", "history", chain)
            os.makedirs(hdir, exist_ok=True)
            # append to today's file if it exists (retry runs)
            hpath = os.path.join(hdir, f"{today}.jsonl")
            mode = "a" if os.path.exists(hpath) else "w"
            with open(hpath, mode, encoding="utf-8") as f:
                for c in changes:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")

        summary[chain] = {"products": len(rows), "price_changes": len(changes)}
        print(f"  {len(rows)} products, {len(changes)} price changes")

    # merged file + summary
    merged = os.path.join(ROOT, "data", "latest", "prices.jsonl")
    with open(merged, "w", encoding="utf-8") as out:
        for chain in CHAINS:
            p = os.path.join(ROOT, "data", "latest", f"{chain}.jsonl")
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as f:
                for line in f:
                    out.write(line)
    with open(os.path.join(ROOT, "data", "latest", "summary.json"), "w") as f:
        json.dump({"date": today, "chains": summary}, f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
