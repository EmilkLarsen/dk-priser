"""STARK.dk — variant sitemaps -> product pages -> embedded GrossPrice JSON.

Prices live in an HTML-escaped JSON blob:
  "GrossPrice":{"StandardPriceInVat":"100000","CampaignPriceInVat":90000, ...}
Amounts are in oere (1 DKK = 100 oere).
"""
import re
import html as htmllib
from common import get, sitemap_urls, write_jsonl

BASE = "https://www.stark.dk"
OUT = "data/latest/stark.jsonl"

GROSS_RE = re.compile(
    r'"GrossPrice":\{[^}]*?"StandardPriceInVat":"?(\d+)"?'
    r'[^}]*?"CampaignPriceInVat":(\d+)'
)
NAME_RE = re.compile(r'"Name":"([^"]{3,180})"')


def fetch_url_list(limit):
    urls = []
    for f in ("sitemapvariants1.xml", "sitemapvariants2.xml"):
        xml = get(f"{BASE}/{f}")
        urls.extend(sitemap_urls(xml))
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def scrape(limit= None) :
    rows = []
    for u in fetch_url_list(limit):
        try:
            raw = get(u)
        except Exception as e:
            print(f"  ! {u}: {e}")
            continue
        text = htmllib.unescape(raw)
        m = GROSS_RE.search(text)
        if not m:
            continue
        std_ore, camp_ore = int(m.group(1)), int(m.group(2))
        # campaign price 0 = no campaign
        price_ore = camp_ore if camp_ore > 0 else std_ore
        if price_ore <= 0:
            continue
        nm = NAME_RE.search(text)
        # Name field is unreliable (store name) — derive from URL slug
        slug = u.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
        name = slug.replace("-", " ").title()
        rows.append({
            "chain": "stark",
            "sku": u.split("id=")[-1] if "id=" in u else u.rsplit("-", 1)[-1],
            "ean": None,
            "name": name,
            "url": u,
            "price": price_ore / 100.0,
            "in_stock": None,  # stock is per-store; not on public page
            "campaign": bool(camp_ore > 0),
        })
    return rows


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print(f"stark: {len(rows)} products -> {OUT}")
