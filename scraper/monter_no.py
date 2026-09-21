"""Montér.no (NOK) — batched sitemaps sitemap.xml?batch=N; product URLs are
deep category-path slugs; price via embedded JSON "price":N,"priceCurrency":"NOK".
Pages without a price block (categories) are skipped."""
import re
from common import get, sitemap_urls, sane_price, write_jsonl

BASE = "https://www.monter.no"
OUT = "data/latest/monter_no.jsonl"
PRICE_RE = re.compile(r'"price"\s*:\s*"?([0-9.]+)"?,\s*"priceCurrency"\s*:\s*"NOK"')
TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>")
MAX_BATCHES = 25


def fetch_url_list(limit=None):
    urls = []
    for b in range(MAX_BATCHES):
        try:
            xml = get(f"{BASE}/sitemap.xml?batch={b}&language=nb-no")
        except Exception:
            break
        urls.extend(sitemap_urls(xml))
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    m = PRICE_RE.search(html)
    if not m:
        return []
    p = sane_price(float(m.group(1)))
    if not p:
        return []
    t = TITLE_RE.search(html)
    name = (t.group(1).split("|")[0].strip() if t else u.rsplit("/", 1)[-1])
    return [{
        "chain": "monter_no",
        "country": "no",
        "currency": "NOK",
        "sku": None,
        "ean": None,
        "name": name,
        "url": u,
        "price": p,
        "in_stock": None,
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
    print("monter_no: %d products -> %s" % (len(rows), OUT))
