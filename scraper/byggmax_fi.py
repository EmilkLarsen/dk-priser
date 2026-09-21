"""Byggmax.fi (EUR) — same Magento platform as byggmax.se; sitemap name from
robots.txt (Sitemap_fi_fi_product*.xml); itemprop price microdata (EUR)."""
import re
from common import get, sitemap_urls, sane_price, write_jsonl, scrape_urls

BASE = "https://www.byggmax.fi"
OUT = "data/latest/byggmax_fi.jsonl"
PRODUCT_PAT = re.compile(r"-p(\d+)$")
OG_RE = re.compile(r'og:image"\s*content="([^"]+)"')


def fetch_url_list(limit=None):
    robots = get(BASE + "/robots.txt")
    sm_urls = re.findall(r"Sitemap:\s*(\S+product\S*\.xml)", robots)
    urls = []
    for sm in sm_urls:
        xml = get(sm)
        us = [u for u in sitemap_urls(xml) if PRODUCT_PAT.search(u)]
        urls.extend(us)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    m = re.search(r'itemprop="price" content="([0-9.]+)"', html)
    if not m:
        return []
    p = sane_price(float(m.group(1)))
    if not p:
        return []
    sku = PRODUCT_PAT.search(u)
    og = OG_RE.search(html)
    return [{
        "chain": "byggmax_fi",
        "country": "fi",
        "currency": "EUR",
        "sku": sku.group(1) if sku else None,
        "ean": None,
        "name": u.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title(),
        "url": u,
        "price": p,
        "in_stock": None,
        "image": og.group(1) if og else None,
    }]


def scrape(limit=None):
    return scrape_urls(fetch_url_list(limit), handle)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("byggmax_fi: %d products -> %s" % (len(rows), OUT))
