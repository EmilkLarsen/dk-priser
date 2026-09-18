"""Johannes Fog — /da-dk/sitemap/products/{1..N} -> ld+json (ProductGroup)."""
from common import html_gtin, valid_ean, first_str, sane_price, get, sitemap_urls, ldjson_products, offer_from_ld, write_jsonl, scrape_with_checkpoint

BASE = "https://www.johannesfog.dk"
OUT = "data/latest/fog.jsonl"


def fetch_url_list(limit=None):
    idx = get(BASE + "/sitemap.xml")
    files = [u for u in sitemap_urls(idx) if "/sitemap/products/" in u]
    urls = []
    for f in files:
        urls.extend(sitemap_urls(get(f)))
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    rows, seen = [], set()
    for p in ldjson_products(html):
        off = offer_from_ld(p)
        if off:
            off["price"] = sane_price(off["price"])
        if not off or not off["price"]:
            continue
        if not off:
            continue
        if u in seen:
            continue
        seen.add(u)
        rows.append({
            "chain": "fog",
            "sku": u.rstrip("/").rsplit("/", 1)[-1],
            "ean": valid_ean(p.get("gtin13") or p.get("gtin") or p.get("ean")) or html_gtin(html),
            "image": first_str(p.get("image")),
            "name": p.get("name"),
            "url": u,
            "price": off["price"],
            "in_stock": off["in_stock"],
        })
        break
    return rows


def scrape(limit=None, deadline=None):
    # Was scrape_urls (SCRAPE_BUDGET + SCRAPE_OFFSET resume) - confirmed
    # live (2026-09-18) that resume path is dead code end to end
    # (SCRAPE_OFFSET is never set anywhere in the workflow; run_daily.py
    # writes scrape_offsets.json but nothing reads it back), so any run
    # that ever hit its own time budget would restart from url #0 again
    # next time, forever, silently never reaching whatever was past that
    # cutoff. Only ever masked here by fog finishing within budget every
    # day so far. scrape_with_checkpoint is the same, already-proven
    # mechanism silvan/xlbyg/stark/skousen use instead.
    return scrape_with_checkpoint("fog", fetch_url_list(limit), handle, limit, deadline)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("fog: %d products -> %s" % (len(rows), OUT))
