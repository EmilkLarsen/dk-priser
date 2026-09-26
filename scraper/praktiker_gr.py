"""Praktiker.gr (EUR, Greece) — /media/sitemap/sitemap.xml is a meta-index
pointing to Auto/SitemapCollection.xml etc. Product URLs end /p/<id>;
Magento itemprop price + sku (same pattern as Dedeman)."""
import re
from common import get, sitemap_urls, sane_price, valid_ean, write_jsonl, scrape_urls

BASE = "https://www.praktiker.gr"
OUT = "data/latest/praktiker_gr.jsonl"
# Markup updated 2026-09-26: itemprop attrs are gone; ld+json Offer now carries
# "price":1099 next to priceCurrency, and the SKU lives in a JSON "sku" field.
PRICE_RE = re.compile(r'"priceCurrency"\s*:\s*"EUR"\s*,\s*"price"\s*:\s*([0-9.]+)')
SKU_RE = re.compile(r'"sku"\s*:\s*"([^"]+)"')


def fetch_url_list(limit=None):
    """3-level sitemap: sitemap.xml -> SitemapCollection.xml -> product sitemaps."""
    meta = get(f"{BASE}/media/sitemap/sitemap.xml")
    collections = [u for u in sitemap_urls(meta) if "SitemapCollection" in u]
    urls = []
    for c in collections[:3]:
        try:
            sub = sitemap_urls(get(c))
        except Exception:
            continue
        for sf in sub:
            try:
                us = [u for u in sitemap_urls(get(sf)) if "/p/" in u]
                urls.extend(us)
            except Exception:
                continue
            if limit and len(urls) >= limit:
                break
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls

def _old_fetch(limit=None):
    # meta-index -> actual sitemap files
    meta = get(f"{BASE}/media/sitemap/sitemap.xml")
    files = sitemap_urls(meta)
    urls = []
    for f in files:
        try:
            sub = sitemap_urls(get(f))
        except Exception:
            continue
        for sf in sub:
            try:
                us = [u for u in sitemap_urls(get(sf)) if "/p/" in u]
                urls.extend(us)
            except Exception:
                continue
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
    sk = SKU_RE.search(html)
    t = re.search(r"<title[^>]*>([^<]+)</title>", html)
    name = (t.group(1).split("|")[0].strip() if t else u.rsplit("/", 1)[-1])
    im = (re.search(r'"image"\s*:\s*\[?"?(https://[^"\]\\]+)', html)
          or re.search(r'property="og:image"\s+content="([^"]+)"', html))
    return [{
        "chain": "praktiker_gr",
        "country": "gr",
        "currency": "EUR",
        "sku": sk.group(1) if sk else None,
        "ean": None,
        "name": name,
        "url": u,
        "price": p,
        "in_stock": None,
        "image": im.group(1).strip() if im else None,
    }]


def scrape(limit=None):
    return scrape_urls(fetch_url_list(limit), handle)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("praktiker_gr: %d products -> %s" % (len(rows), OUT))
