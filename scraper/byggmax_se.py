"""Byggmax.se (SEK) — Magento sitemaps -> product pages -> itemprop price.
Sitemaps: robots.txt lists Sitemap_sv_se_product_00X.xml chunks.
Product URLs end in -p<digits>. Prices: itemprop="price" microdata (SEK)."""
import re
from common import get, sitemap_urls, sane_price, write_jsonl, scrape_urls

BASE = "https://www.byggmax.se"
OUT = "data/latest/byggmax_se.jsonl"
PRODUCT_PAT = re.compile(r"-p(\d+)$")
OG_RE = re.compile(r'og:image"\s*content="([^"]+)"')


def fetch_url_list(limit=None):
    robots = get(BASE + "/robots.txt")
    sm_urls = re.findall(r"Sitemap:\s*(\S+product\S*\.xml)", robots)
    urls = []
    for sm in sm_urls:
        xml = get(sm)
        chunks = re.findall(r"<loc>([^<]+)</loc>", xml)
        # the robots entry may itself be the chunk (direct) or an index of chunks
        for target in (chunks if chunks else [sm]):
            us = [u for u in sitemap_urls(get(target)) if PRODUCT_PAT.search(u)]
            urls.extend(us)
            if limit and len(urls) >= limit:
                break
        if limit and len(urls) >= limit:
            break
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
        "chain": "byggmax_se",
        "country": "se",
        "currency": "SEK",
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
    print("byggmax_se: %d products -> %s" % (len(rows), OUT))
