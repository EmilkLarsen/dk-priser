#!/usr/bin/env python3
"""Build price comparison across chains + package JSON for the Fixer API.

Reads data/latest/prices.jsonl -> writes:
  data/latest/comparison.json   {name-key: {chain: price}} for matched products
  data/latest/api/prices.json   compact flat file for the estimator backend
"""
import json
import os
import re
import unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm_key(name: str) -> str:
    """Fuzzy match key: lowercase, strip accents/sizes noise, collapse."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9x ]+", " ", s)
    # strip size tokens like 25 l, 240 cm etc that differ per packaging
    s = re.sub(r"\b\d+[.,]?\d*\s*(mm|cm|m|l|ml|g|kg|stk|pack|rul)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main():
    src = os.path.join(ROOT, "data", "latest", "prices.jsonl")
    by_key = defaultdict(dict)
    meta = {}
    n = 0
    with open(src, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            n += 1
            k = norm_key(r.get("name", ""))
            if len(k) < 8:
                continue
            if r["chain"] not in by_key[k] or r["price"] < by_key[k][r["chain"]]:
                by_key[k][r["chain"]] = r["price"]
            meta.setdefault(k, {"name": r.get("name"), "url": r.get("url")})

    comparison = []
    for k, chains in by_key.items():
        if len(chains) < 2:
            continue  # only multi-chain matches are interesting
        prices = list(chains.values())
        comparison.append({
            "key": k, "name": meta[k]["name"],
            "prices": chains,
            "min": min(prices), "max": max(prices),
            "spread_pct": round((max(prices) - min(prices)) / min(prices) * 100, 1),
        })
    comparison.sort(key=lambda x: -x["spread_pct"])

    with open(os.path.join(ROOT, "data", "latest", "comparison.json"), "w",
              encoding="utf-8") as f:
        json.dump(comparison[:5000], f, ensure_ascii=False, indent=1)

    print(f"{n} rows in, {len(by_key)} unique keys, "
          f"{len(comparison)} multi-chain comparisons")


if __name__ == "__main__":
    main()
