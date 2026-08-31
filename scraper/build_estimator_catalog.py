#!/usr/bin/env python3
"""Build data/latest/estimator_catalog.json — the small, BOM-matchable catalog
the Fixer app fetches at runtime (MaterialCatalogStore.remoteCatalogURL).

The app already ships ~707 canonical building-material keys it knows how to
match an AI material list against (scraper/estimator_keys.json, mirrored from
the app's material_catalog_v1.json). For each key this script finds the real
matching products in prices.jsonl and sets the unit price to the median across
chains — but ONLY when the match is confident AND the scraped median sits
within a sane ratio of the app's own fallback price. That guard is what stops
a unit mismatch (per-tile vs per-m2 vs per-pallet) from poisoning an estimate:
if the scraped number looks wrong, the hand-tuned fallback is kept.

Output is a bare JSON array, schema-identical to material_catalog_v1.json plus
optional provenance fields (the Swift decoder ignores unknown keys):
  {key,name,synonyms,unit,unitPriceDKK,source,
   sources?:[chain], sampleCount?:int, priceRange?:[min,max], updated?:YYYY-MM-DD}

~200 KB. The app caches it to disk, refreshes daily in the background, and
falls back to its bundled catalog if this file is missing or fails validation.
"""
import json
import os
import re
import statistics
import unicodedata
from collections import defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATEST = os.path.join(ROOT, "data", "latest")
HERE = os.path.dirname(os.path.abspath(__file__))

# Conservative on purpose: a wrong "live" price is worse than a rough hand-tuned
# one. A key is only refined when several chains independently agree AND the
# result is a sane multiple of the app's own fallback.
RATIO_LOW, RATIO_HIGH = 0.5, 2.0     # scraped median must be 0.5x-2x the fallback
MIN_CHAINS = 3                        # >= 3 chains must have a matching product
MIN_SAMPLES, MAX_SAMPLES = 3, 40      # too few = fragile, too many = match too broad
MAX_IQR_SPREAD = 0.65                # interquartile spread / median, after trimming
MAX_PRICE = 20000                     # skip obvious bundles/appliances/sheds early

# Units where a raw retail price is directly comparable to a catalog unit price.
# "m2" (tiles, boards) and "m" (gutters, battens) need pack-size parsing to be
# trustworthy, so they keep their hand-tuned fallback for now.
COMPARABLE_UNITS = {"roll", "bag", "box", "set", "pcs", "liter"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_products():
    path = os.path.join(LATEST, "prices.jsonl")
    prods = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = r.get("price")
            if not isinstance(p, (int, float)) or p <= 0 or p > MAX_PRICE:
                continue
            r["_norm"] = norm(r.get("name", ""))
            prods.append(r)
    return prods


def match_products(item, prods):
    """A product matches when every token of at least one phrase (the canonical
    name or a synonym) is a substring of the product's normalised title."""
    phrases = sorted(
        {norm(item["name"])} | {norm(s) for s in item.get("synonyms", [])},
        key=len,
    )
    phrase_toks = [p.split() for p in phrases if len(p) >= 3]
    hits = []
    for pr in prods:
        title = pr["_norm"]
        for toks in phrase_toks:
            if toks and all(t in title for t in toks):
                hits.append(pr)
                break
    return hits


def main():
    keys = json.load(open(os.path.join(HERE, "estimator_keys.json"), encoding="utf-8"))
    prods = load_products()
    today = date.today().isoformat()

    out = []
    refined = 0
    for item in keys:
        fallback = float(item["fallbackPriceDKK"])
        entry = {
            "key": item["key"],
            "name": item["name"],
            "synonyms": item.get("synonyms", []),
            "unit": item["unit"],
            "unitPriceDKK": round(fallback),
            "source": "catalog:v1",
        }

        if item["unit"] in COMPARABLE_UNITS:
            hits = match_products(item, prods)
            by_chain = defaultdict(list)
            for h in hits:
                by_chain[h["chain"]].append(h["price"])
            # one representative price per chain (the median of that chain's
            # matches), so a chain with many noisy hits can't dominate.
            chain_prices = {c: statistics.median(sorted(v)) for c, v in by_chain.items()}
            samples = sorted(chain_prices.values())

            if (MIN_CHAINS <= len(chain_prices)
                    and MIN_SAMPLES <= len(hits) <= MAX_SAMPLES):
                # drop the single lowest+highest chain before measuring agreement
                core = samples[1:-1] if len(samples) >= 4 else samples
                med = statistics.median(core)
                iqr = (core[-1] - core[0]) / med if med else 99
                if (iqr <= MAX_IQR_SPREAD
                        and RATIO_LOW * fallback <= med <= RATIO_HIGH * fallback):
                    entry["unitPriceDKK"] = round(med)
                    entry["source"] = f"dk-priser:{today}"
                    entry["sources"] = sorted(chain_prices.keys())
                    entry["sampleCount"] = len(hits)
                    entry["priceRange"] = [round(samples[0]), round(samples[-1])]
                    entry["updated"] = today
                    refined += 1

        out.append(entry)

    dst = os.path.join(LATEST, "estimator_catalog.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    pct = refined * 100 // max(1, len(out))
    print(f"estimator_catalog.json: {len(out)} items, {refined} refined with "
          f"live prices ({pct}%)  ->  {os.path.getsize(dst) // 1024} KB")


if __name__ == "__main__":
    main()
