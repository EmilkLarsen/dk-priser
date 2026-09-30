"""OBI.de (EUR, Germany #2) — gzipped sitemap index -> product sitemaps
(sitemap_obi-products_N.xml); URLs /p/<id>/<slug>; ld+json offers list with
price + priceCurrency + availability."""
import re
import gzip
from common import get, sitemap_urls, sane_price, valid_ean, write_jsonl, pmap, scrape_with_checkpoint

BASE = "https://www.obi.de"
OUT = "data/latest/obi_de.jsonl"
PROD_RE = re.compile(r"/p/\d+")
OFFER_RE = re.compile(
    r'"priceCurrency":\s*"([A-Z]{3})",\s*"price":\s*([0-9.]+),'
    r'.*?"availability":\s*"http://schema\.org/(\w+)"')


def _get_maybe_gz(url):
    """Some OBI sitemap endpoints return gzip regardless of extension."""
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="replace")


def fetch_url_list(limit=None):
    idx = _get_maybe_gz(f"{BASE}/sitemaps/obi_de_de/de_pdp_index.xml")
    files = sitemap_urls(idx)
    urls = []
    for f in files:
        us = [u for u in sitemap_urls(_get_maybe_gz(f)) if PROD_RE.search(u)]
        urls.extend(us)
        if limit and len(urls) >= limit:
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
    sku = u.rstrip("/").split("/p/")[-1].split("/")[0]
    og = re.search(r'(https://bilder\.obi\.[a-z.]*/[^"\s>]+)', html)
    image = og.group(1) if og else None
    t = re.search(r"<title[^>]*>([^<]+)</title>", html)
    name = (t.group(1).split("|")[0].strip() if t else u.rsplit("/", 1)[-1])
    return [{
        "chain": "obi_de",
        "country": "de",
        "currency": m.group(1),
        "sku": sku,
        "ean": None,
        "name": name,
        "url": u,
        "price": p,
        "in_stock": (avail == "InStock") if avail else None,
        "image": image,
    }]


def scrape(limit=None, deadline=None):
    return scrape_with_checkpoint("obi_de", fetch_url_list(limit), handle, limit, deadline)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("obi_de: %d products -> %s" % (len(rows), OUT))
