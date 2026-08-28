#!/usr/bin/env python3
"""Merge per-chain snapshots (written by parallel CI jobs) into the final
feed: prices.jsonl, comparison.json, summary.json, ages.json."""
import os
import sys
import json
import glob
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from build_comparison import main as build_comparison  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAINS = ["silvan", "xlbyg", "stark", "bauhaus", "davidsen",
          "fog", "haraldnyborg", "power", "skousen"]
LATEST = os.path.join(ROOT, "data", "latest")


def main():
    today = date.today().isoformat()
    merged_path = os.path.join(LATEST, "prices.jsonl")
    n = 0
    with open(merged_path, "w", encoding="utf-8") as out:
        for chain in CHAINS:
            p = os.path.join(LATEST, f"{chain}.jsonl")
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as f:
                for line in f:
                    out.write(line)
                    n += 1

    # merge per-chain summary files
    summary = {}
    for sp in glob.glob(os.path.join(LATEST, "summary-*.json")):
        try:
            d = json.load(open(sp))
        except json.JSONDecodeError:
            continue
        summary.update(d.get("chains", {}))

    json.dump({"date": today, "total_rows": n, "chains": summary},
              open(os.path.join(LATEST, "summary.json"), "w"), indent=1)

    # staleness ledger
    ages_path = os.path.join(LATEST, "ages.json")
    ages = {}
    if os.path.exists(ages_path):
        try:
            ages = json.load(open(ages_path))
        except json.JSONDecodeError:
            ages = {}
    for chain in CHAINS:
        d = summary.get(chain, {})
        if "products" in d:  # success this run
            ages[chain] = today
    json.dump(ages, open(ages_path, "w"), indent=1)

    build_comparison()
    print(f"merged {n} rows; comparison rebuilt")


if __name__ == "__main__":
    main()
