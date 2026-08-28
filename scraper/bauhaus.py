"""Bauhaus.dk — Magento sitemap -> product pages -> data-price-amount.

Magento prints the price box server-side:
  <span ... data-price-amount="179.95" ...>179,95&nbsp;kr.</span>
The FIRST data-price-amount on a product page is the main price.
URLs in the sitemap include categories; product slugs contain dimension
patterns or at least 2 hyphens and are not category roots. We keep the
sitemap files' URLs and detect product pages by looking for a price box.
"""
import re
from common import get, sitemap_urls, write_jsonl

BASE = "https://www.bauhaus.dk"
OUT = "data/latest/bauhaus.jsonl"
PRICE_RE = re.compile(r'data-price-amount="([0-9.]+)"')
NAME_RE = re.compile(r'<title[^>]*>([^<]+)</title>')


def fetch_url_list(limit):
    idx = get(f"{BASE}/media/sitemap_dk/sitemap.xml")
    files = sitemap_urls(idx)
    urls = []
    for f in files:
        xml = get(f)
        us = [u for u in sitemap_urls(xml)
              if u.count("/") >= 3 and u != BASE + "/"]
        urls.extend(us)
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def scrape(limit= None) :
    rows = []
    for u in fetch_url_list(limit):
        try:
            html = get(u)
        except Exception:
            continue
        prices = PRICE_RE.findall(html)
        if not prices:
            continue  # category / CMS page without price box
        t = NAME_RE.search(html)
        rows.append({
            "chain": "bauhaus",
            "sku": None,
            "ean": None,
            "name": (t.group(1).strip().split("|")[0] if t else u.rsplit("/", 1)[-1]),
            "url": u,
            "price": float(prices[0]),
            "in_stock": None,
        })
    return rows


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print(f"bauhaus: {len(rows)} products -> {OUT}")
