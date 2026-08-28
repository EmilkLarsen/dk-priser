#!/usr/bin/env python3
"""Full-refresh strategy for CI time limits.

A complete catalog pass takes hours, so the nightly job runs chains in
PARALLEL JOBS (one per chain, matrix strategy) — each chain easily fits
its own 300-min limit, and GitHub runs them simultaneously on free
public runners. run_daily.py gets --only <chain> to support this.
"""
import sys
import os
import json
import time
import importlib
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAINS = ["silvan", "xlbyg", "stark", "bauhaus", "davidsen",
          "fog", "haraldnyborg", "power", "skousen"]


def load_prev(chain):
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
    args = sys.argv[1:]
    limit = None
    only = None
    if "--only" in args:
        only = args[args.index("--only") + 1]
        args = args[:args.index("--only")] + args[args.index("--only") + 2:]
    limit = int(args[0]) if args else None
    chains = [only] if only else CHAINS
    if only and only not in CHAINS:
        raise SystemExit(f"unknown chain: {only}")

    today = date.today().isoformat()
    summary = {}

    for chain in chains:
        print(f"=== {chain} ===")
        started = time.time()
        try:
            mod = importlib.import_module(chain)
            rows = mod.scrape(limit)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            summary[chain] = {"error": f"{type(e).__name__}: {e}"}
            continue

        out = os.path.join(ROOT, "data", "latest", f"{chain}.jsonl")
        prev_count = 0
        if os.path.exists(out):
            with open(out, encoding="utf-8") as f:
                prev_count = sum(1 for _ in f)
        if prev_count and len(rows) < prev_count * 0.3:
            summary[chain] = {
                "error": f"collapse guard: {len(rows)} rows vs {prev_count} before",
                "kept_previous": True,
            }
            print(f"  !! kept previous snapshot ({len(rows)} new vs {prev_count})")
            continue

        from common import write_jsonl
        write_jsonl(out, rows)

        prev = load_prev(chain)
        changes, suspicious = [], 0
        for r in rows:
            key = r.get("sku") or r.get("url")
            old = prev.get(key)
            if old and old.get("price") != r.get("price"):
                old_p, new_p = old.get("price") or 0, r.get("price") or 0
                ratio = (new_p / old_p) if old_p else 999
                # >8x jump in one day is almost always a parse error, not a price
                flag = {"suspicious": True} if ratio > 8 or ratio < 0.125 else {}
                if flag:
                    suspicious += 1
                changes.append(dict({"key": key, "old_price": old.get("price"),
                                "new_price": r.get("price"),
                                "date": today, "url": r.get("url")}, **flag))
        if changes:
            hdir = os.path.join(ROOT, "data", "history", chain)
            os.makedirs(hdir, exist_ok=True)
            hpath = os.path.join(hdir, f"{today}.jsonl")
            mode = "a" if os.path.exists(hpath) else "w"
            with open(hpath, mode, encoding="utf-8") as f:
                for c in changes:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")

        summary[chain] = {
            "products": len(rows),
            "price_changes": len(changes),
            "suspicious_changes": suspicious,
            "seconds": round(time.time() - started, 1),
        }
        print(f"  {len(rows)} products, {len(changes)} price changes")

    if only:
        spath = os.path.join(ROOT, "data", "latest", f"summary-{only}.json")
        json.dump({"date": today, "chains": summary}, open(spath, "w"), indent=1)
    else:
        merged = os.path.join(ROOT, "data", "latest", "prices.jsonl")
        n = 0
        with open(merged, "w", encoding="utf-8") as out:
            for chain in CHAINS:
                p = os.path.join(ROOT, "data", "latest", f"{chain}.jsonl")
                if not os.path.exists(p):
                    continue
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        out.write(line)
                        n += 1
        json.dump({"date": today, "total_rows": n, "chains": summary},
                  open(os.path.join(ROOT, "data", "latest", "summary.json"), "w"),
                  indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
