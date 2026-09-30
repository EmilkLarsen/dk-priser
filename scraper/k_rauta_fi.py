"""K-Rauta.fi (EUR, Kesko — Finland's market leader) — product sitemaps
/sitemap/products{0..N}.xml; product URLs end with /<EAN>; ld+json Offer
via regex (site's ld+json block isn't reliably parseable as a whole)."""
import re
from common import get, sitemap_urls, sane_price, write_jsonl, scrape_with_checkpoint

BASE = "https://www.k-rauta.fi"
OUT = "data/latest/k_rauta_fi.jsonl"
EAN_RE = re.compile(r"/(\d{8,14})$")
OFFER_RE = re.compile(
    r'"priceCurrency":"([A-Z]{3})","price":([0-9.]+)'
    r'(?:,"priceValidUntil":"[^"]*","availability":"(\w+)")?')


def fetch_url_list(limit=None):
    urls = []
    i = 0
    while True:
        try:
            xml = get(f"{BASE}/sitemap/products{i}.xml")
        except Exception as e:
            # 404 on products{i} = clean end of chunks. ANY other failure must
            # be visible — a silent break here reads as "full catalog covered
            # (0 rows)" and the chain reports complete-ish with zero data
            # (verified live in CI 2026-09-30: k_rauta_fi 0 products).
            print(f"  ! k_rauta_fi: sitemap products{i}.xml failed: {e}")
            if i == 0:
                raise   # can't even fetch the first chunk = nothing to scrape
            break
        us = [u for u in sitemap_urls(xml) if EAN_RE.search(u)]
        urls.extend(us)
        i += 1
        if i > 30 or (limit and len(urls) >= limit):
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    m = OFFER_RE.search(html)
    if not m:
        return []
    p = sane_price(float(m.group(2)))
    if not p:
        return []
    ean_m = EAN_RE.search(u)
    slug = u.rstrip("/").rsplit("/", 2)[-2].replace("-", " ").title()
    avail = m.group(3)
    return [{
        "chain": "k_rauta_fi",
        "country": "fi",
        "currency": m.group(1),
        "sku": None,
        "ean": ean_m.group(1) if ean_m else None,
        "name": slug,
        "url": u,
        "price": p,
        "in_stock": (avail == "InStock") if avail else None,
        "image": None,
    }]


def scrape(limit=None, deadline=None):
    return scrape_with_checkpoint("k_rauta_fi", fetch_url_list(limit), handle, limit, deadline)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("k_rauta_fi: %d products -> %s" % (len(rows), OUT))
