"""Incremental scraping: only re-fetch products whose sitemap lastmod changed
since the last run. Falls back to full scrape for chains without lastmod.

State file: data/latest/scrape_state.json  {url: lastmod}
On first run (no state) -> full scrape, as today. Later runs typically touch
only 1-5% of products (campaigns/price edits), making the nightly job fast
enough for free CI minutes.

Chains with lastmod: silvan, haraldnyborg, xlbyg, bauhaus, fog(no), stark(no),
davidsen(no), power(?), skousen(yes). Chains without it still get a smart
rotation: 1/N of the catalog each night so everything refreshes weekly.
"""
import re

# parse (loc, lastmod) pairs from a sitemap
PAIR_RE = re.compile(
    r"<loc>\s*([^<\s]+)\s*</loc>(?:\s*<lastmod>([^<]*)</lastmod>)?", re.S)


def sitemap_pairs(xml):
    """-> list[(url, lastmod_or_None)]"""
    return PAIR_RE.findall(xml)


def select_changed(pairs, state, full=False, rotation_days=7):
    """Choose which URLs to fetch this run.

    full=True or no prior state: everything.
    Else: URLs new or with changed lastmod. If a chain has no lastmod at all,
    return a deterministic 1/N slice (rotation) so coverage refreshes weekly.
    """
    if full or not state:
        return [u for u, _ in pairs], False

    has_lastmod = any(lm for _, lm in pairs)
    if has_lastmod:
        changed = [u for u, lm in pairs
                   if lm and state.get(u) != lm]
        return changed, True  # incremental=True: unchanged entries keep old rows

    # no lastmod -> rotate deterministic slice by day-of-epoch
    import time
    day = int(time.time() // 86400)
    nth = day % rotation_days
    return [u for i, u in enumerate(sorted(u for u, _ in pairs))
            if i % rotation_days == nth], False


def update_state(state, pairs, fetched_urls, incremental):
    """Store new lastmods for fetched URLs. On incremental runs, URLs not
    fetched keep their old state (data for them is retained downstream)."""
    for u, lm in pairs:
        if lm and (not incremental or u in set(fetched_urls)):
            state[u] = lm
    return state
