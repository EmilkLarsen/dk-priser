"""Globus Baumarkt.de (EUR) — Shopware; gzipped product sitemaps under
/sitemap/salesChannel-...; URLs /p/<slug>-<sku>/; clean ld+json Product."""
import re
import gzip
import urllib.request
from common import get, sitemap_urls, sane_price, valid_ean, first_str, write_jsonl, scrape_urls, scrape_with_checkpoint

BASE = "https://www.globus-baumarkt.de"
OUT = "data/latest/globus_de.jsonl"


def fetch_url_list(limit=None):
    idx = get(f"{BASE}/sitemap.xml")
    files = [u for u in sitemap_urls(idx) if "-products-" in u]
    urls = []
    for f in files:
        req = urllib.request.Request(f, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 Chrome/126 Safari/537.36"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        us = [u for u in re.findall(r"<loc>([^<]+)</loc>", data.decode("utf-8", errors="replace"))
              if "/p/" in u]
        urls.extend(us)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    rows = []
    from common import ldjson_products
    for p in ldjson_products(html):
        off = p.get("offers") or {}
        if isinstance(off, list):
            off = off[0] if off and isinstance(off[0], dict) else {}
        amt = off.get("price")
        if not amt:
            continue
        price = sane_price(amt)
        if not price:
            continue
        avail = str(off.get("availability") or "")
        sku = u.rstrip("/").rsplit("-", 1)[-1]
        rows.append({
            "chain": "globus_de",
            "country": "de",
            "currency": off.get("priceCurrency", "EUR"),
            "sku": sku,
            "ean": valid_ean(p.get("gtin13") or p.get("gtin") or p.get("ean")),
            "name": p.get("name"),
            "url": u,
            "price": price,
            "in_stock": ("InStock" in avail) if avail else None,
            "image": first_str(p.get("image")),
        })
        break
    return rows


def scrape(limit=None, deadline=None):
    return scrape_with_checkpoint("globus_de", fetch_url_list(limit), handle, limit, deadline)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("globus_de: %d products -> %s" % (len(rows), OUT))
