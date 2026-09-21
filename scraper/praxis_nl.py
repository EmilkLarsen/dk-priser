"""Praxis.nl (EUR, Netherlands #2, Maxeda) — product sitemap index
/praxisproductpagessitemapindex{N}.xml; URLs end /<id>; ld+json Offer parsed
by regex (page's ld+json block doesn't parse as a whole)."""
import re
from common import get, sitemap_urls, sane_price, valid_ean, write_jsonl

BASE = "https://www.praxis.nl"
OUT = "data/latest/praxis_nl.jsonl"
ID_RE = re.compile(r"/(\d{5,})$")
OFFER_RE = re.compile(
    r'"priceCurrency":"([A-Z]{3})","url":"[^"]*","price":([0-9.]+),'
    r'"availability":"https://schema\.org/(\w+)"')
NAME_RE = re.compile(r'itemprop="name" content="([^"]{5,150})"')


def fetch_url_list(limit=None):
    urls = []
    i = 1
    while True:
        try:
            idx = get(f"{BASE}/praxisproductpagessitemapindex{i}.xml")
        except Exception:
            break
        files = sitemap_urls(idx)
        for f in files:
            us = [u for u in sitemap_urls(get(f)) if ID_RE.search(u)]
            urls.extend(us)
            if limit and len(urls) >= limit:
                break
        i += 1
        if i > 10 or (limit and len(urls) >= limit):
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    m = OFFER_RE.search(html)
    if not m:
        return []
    p = sane_price(float(m.group(2)))
    if not p:
        return []
    avail = m.group(3)
    im = ID_RE.search(u)
    nm = NAME_RE.search(html)
    name = nm.group(1) if nm else u.rstrip("/").rsplit("/", 2)[-2].replace("-", " ").title()
    return [{
        "chain": "praxis_nl",
        "country": "nl",
        "currency": m.group(1),
        "sku": im.group(1) if im else None,
        "ean": None,
        "name": name,
        "url": u,
        "price": p,
        "in_stock": (avail == "InStock") if avail else None,
        "image": None,
    }]


def scrape(limit=None):
    from common import pmap

    def work(u):
        try:
            return handle(u, get(u))
        except Exception as e:
            print(f"  ! {u}: {e}")
            return []
    return pmap(work, fetch_url_list(limit))


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("praxis_nl: %d products -> %s" % (len(rows), OUT))
