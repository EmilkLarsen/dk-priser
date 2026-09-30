"""OBI.hu (HUF, Hungary) — same OBI platform as .de; gzipped sitemap
index -> product sitemaps; URLs /<cat>/<slug>/p/<id>; JSON price blob."""
import re
import gzip
import urllib.request
from common import get, sitemap_urls, sane_price, valid_ean, write_jsonl, pmap, scrape_with_checkpoint

BASE = "https://www.obi.hu"
OUT = "data/latest/obi_hu.jsonl"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 Chrome/126 Safari/537.36")


def _gz(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="replace")


def fetch_url_list(limit=None):
    idx = _gz(f"{BASE}/sitemaps/obi_hu_hu/sitemap_index.xml")
    files = [u for u in sitemap_urls(idx) if "pdp" in u.lower() or "product" in u.lower()]
    if not files:
        # fallback: scan all sitemap files for /p/ URLs
        files = [u for u in sitemap_urls(idx) if "sitemap_" in u]
    urls = []
    for f in files:
        us = [u for u in sitemap_urls(_gz(f)) if "/p/" in u]
        urls.extend(us)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    m = re.search(r'"price"\s*:\s*"?([0-9.]+)"?', html)
    if not m:
        return []
    p = sane_price(float(m.group(1)))
    if not p:
        return []
    nm = re.search(r'"name"\s*:\s*"([^"]{5,120})"', html)
    sku = u.rstrip("/").split("/p/")[-1]
    og = re.search(r'(https://bilder\.obi\.[a-z.]*/[^"\s>]+)', html)
    image = og.group(1) if og else None
    return [{
        "chain": "obi_hu",
        "country": "hu",
        "currency": "HUF",
        "sku": sku,
        "ean": None,
        "name": nm.group(1) if nm else u.rsplit("/", 1)[-1],
        "url": u,
        "price": p,
        "in_stock": None,
        "image": image,
    }]


def scrape(limit=None, deadline=None):
    return scrape_with_checkpoint("obi_hu", fetch_url_list(limit), handle, limit, deadline)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("obi_hu: %d products -> %s" % (len(rows), OUT))
