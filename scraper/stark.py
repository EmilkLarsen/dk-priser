"""STARK.dk — variant sitemaps -> product pages -> embedded GrossPrice JSON.
Amounts in oere. Campaign price 0 = no campaign."""
import re
import os
import json
import time
import html as htmllib
from common import get, sitemap_urls, write_jsonl, scrape_with_checkpoint, rotate_slice

BASE = "https://www.stark.dk"
OUT = "data/latest/stark.jsonl"
# ~85k real sitemap urls (verified live, 2026-09-17), a huge share dead
# 404s - no realistic CI time budget scrapes all of them daily. See
# rotate_slice's own doc comment for why this is a deterministic day-of-
# epoch rotation, not a lastmod/etag-based "only fetch what changed"
# scheme (checked both live first; neither is trustworthy on this site).
ROTATION_DAYS = int(os.environ.get("STARK_ROTATION_DAYS", "7"))
ROTATION_MARKER = "data/latest/.stark-rotation-day"

GROSS_RE = re.compile(
    r'"GrossPrice":\{[^}]*?"StandardPriceInVat":"?(\d+)"?'
    r'[^}]*?"CampaignPriceInVat":(\d+)'
)


def fetch_url_list(limit=None):
    urls = []
    for f in ("sitemapvariants1.xml", "sitemapvariants2.xml"):
        urls.extend(sitemap_urls(get(f"{BASE}/{f}")))
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


OG_RE = re.compile(r'og:image"\s*content="([^"]+)"')


def handle(u, raw):
    text = htmllib.unescape(raw)
    og = OG_RE.search(text)
    img = og.group(1) if og else None
    m = GROSS_RE.search(text)
    if not m:
        return []
    std_ore, camp_ore = int(m.group(1)), int(m.group(2))
    price_ore = camp_ore if camp_ore > 0 else std_ore
    if not (50 <= price_ore <= 25000000):
        return []
    slug = u.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return [{
        "chain": "stark",
        "sku": u.split("id=")[-1] if "id=" in u else u.rsplit("-", 1)[-1],
        "ean": None,
        "name": slug.replace("-", " ").title(),
        "url": u,
        "image": img,
        "price": price_ore / 100.0,
        "in_stock": None,
        "campaign": camp_ore > 0,
    }]


def _reset_checkpoint_if_new_rotation(today_slice):
    # scrape_with_checkpoint's own seen/checkpoint files persist across
    # invocations so an interrupted run resumes into the SAME target list -
    # correct when that list is stable, but rotation changes WHICH urls are
    # today's target daily. A stale seen-set from a DIFFERENT (disjoint)
    # day's slice would never satisfy scrape_with_checkpoint's own "seen >=
    # len(urls)" reset condition (every url in a new day's slice is new to
    # it), so it would just accumulate forever without ever cleanly
    # resetting. Detect a rotation change and clear it explicitly instead -
    # safe either way this can be "wrong": at worst (a same-day continue-
    # check redispatch that happens to cross UTC midnight) it means
    # redoing a handful of urls already fetched a few hours earlier, never
    # silently skipping one.
    last_slice = None
    if os.path.exists(ROTATION_MARKER):
        try:
            last_slice = int(open(ROTATION_MARKER).read().strip())
        except (ValueError, OSError):
            last_slice = None
    if last_slice != today_slice:
        for p in ("data/latest/.seen-stark.txt", "data/latest/.checkpoint-stark.jsonl"):
            if os.path.exists(p):
                os.remove(p)
        with open(ROTATION_MARKER, "w") as f:
            f.write(str(today_slice))


def scrape(limit=None, deadline=None):
    all_urls = fetch_url_list(limit)
    if limit:
        # Smoke-test slice: behaves exactly like before, no rotation - a
        # deliberate small test run should never be confused with (or
        # skew) real day-to-day rotation state.
        return scrape_with_checkpoint("stark", all_urls, handle, limit, deadline)

    today_epoch_day = int(time.time() // 86400)
    today_slice = today_epoch_day % ROTATION_DAYS
    _reset_checkpoint_if_new_rotation(today_slice)
    todays_urls = rotate_slice(all_urls, ROTATION_DAYS, today_epoch_day=today_epoch_day)
    fresh_rows = scrape_with_checkpoint("stark", todays_urls, handle, None, deadline)

    # Merge with whatever's already on disk from the OTHER rotation_days-1
    # slices so the caller (run_daily.py) always sees one complete, full-
    # catalog-sized view - transparent either way, exactly like a full
    # scrape's return value, so its own collapse guard and merge-by-key
    # logic need no special-casing for rotation at all.
    existing_by_key = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                existing_by_key[r.get("sku") or r.get("url")] = r
    for r in fresh_rows:
        existing_by_key[r.get("sku") or r.get("url")] = r
    return list(existing_by_key.values())


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("stark: %d products -> %s" % (len(rows), OUT))
