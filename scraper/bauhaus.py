"""Bauhaus.dk — Magento sitemap -> product pages -> data-price-amount."""
import re
from common import get, sitemap_urls, write_jsonl

BASE = "https://www.bauhaus.dk"
OUT = "data/latest/bauhaus.jsonl"
PRICE_RE = re.compile(r'data-price-amount="([0-9.]+)"')
MD_PRICE_RE = re.compile(r'itemprop="price" content="([0-9.]+)"')
MD_SKU_RE = re.compile(r'itemprop="sku" content="([^"]+)"')
NAME_RE = re.compile(r'<title[^>]*>([^<]+)</title>')


def fetch_url_list(limit=None):
    idx = get(f"{BASE}/media/sitemap_dk/sitemap.xml")
    files = sitemap_urls(idx)
    urls = []
    for f in files:
        us = [u for u in sitemap_urls(get(f))
              if u.count("/") >= 3 and u != BASE + "/"]
        urls.extend(us)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, html):
    # itemprop microdata is emitted once per page = the MAIN product.
    # data-price-amount also matches related-product boxes -> fallback only.
    m = MD_PRICE_RE.search(html)
    if m:
        price = float(m.group(1))
    else:
        prices = PRICE_RE.findall(html)
        if not prices:
            return []
        price = float(prices[0])
    if not (0.5 <= price <= 250000):
        return []
    sk = MD_SKU_RE.search(html)
    t = NAME_RE.search(html)
    title = t.group(1).strip() if t else ""
    # category pages repeat a featured product's microdata; their titles
    # look like "X - Køb produkter til X hos BAUHAUS" -> skip them
    if "hos BAUHAUS" in title or "Køb produkter" in title:
        return []
    if not sk:
        return []  # real product pages always carry itemprop sku
    return [{
        "chain": "bauhaus",
        "sku": sk.group(1) if sk else None,
        "ean": None,
        "name": title.split("|")[0] or u.rsplit("/", 1)[-1],
        "url": u,
        "price": price,
        "in_stock": None,
    }]


def scrape(limit=None):
    from common import pmap

    def work(u):
        try:
            return handle(u, get(u))
        except Exception:
            return []
    return pmap(work, fetch_url_list(limit))


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("bauhaus: %d products -> %s" % (len(rows), OUT))
