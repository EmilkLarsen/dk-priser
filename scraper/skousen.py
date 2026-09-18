"""Skousen.dk — premium appliances. sitemap-skou-products.xml -> ld+json."""
from common import html_gtin, valid_ean, first_str, sane_price, get, sitemap_urls, ldjson_products, offer_from_ld, write_jsonl, scrape_with_checkpoint

BASE = "https://www.skousen.dk"
OUT = "data/latest/skousen.jsonl"


def fetch_url_list(limit=None):
    urls = [u for u in sitemap_urls(get(BASE + "/seo/sitemap-skou-products.xml"))
            if "/product/" in u]
    return urls[:limit] if limit else urls


def handle(u, html):
    rows = []
    for p in ldjson_products(html):
        off = offer_from_ld(p)
        if off:
            off["price"] = sane_price(off["price"])
        if not off or not off["price"]:
            continue
        if not off:
            continue
        rows.append({
            "chain": "skousen",
            "sku": None,
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
    # live (2026-09-18) that mechanism is dead code end to end: SCRAPE_OFFSET
    # is never set anywhere in the workflow (run_daily.py writes
    # scrape_offsets.json but nothing ever reads it back into the env), so
    # every run always started this chain over from url #0. Only masked
    # for skousen because its real catalog (~5,341 urls, verified live) is
    # small enough that even a full from-scratch pass usually finishes
    # within budget despite heavy rate-limiting - a bigger catalog, or
    # worse rate-limiting, would have meant silently never discovering
    # anything past wherever the time budget cut off, forever, every
    # single day. scrape_with_checkpoint is the same, already-proven
    # mechanism silvan/xlbyg/stark use: real committed per-url progress
    # instead of a numeric offset that depends on the url list staying in
    # identical order across separate fetches of the sitemap.
    return scrape_with_checkpoint("skousen", fetch_url_list(limit), handle, limit, deadline)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("skousen: %d products -> %s" % (len(rows), OUT))
