"""STARK.dk — variant sitemaps -> product pages -> embedded GrossPrice JSON.
Amounts in oere. Campaign price 0 = no campaign."""
import re
import html as htmllib
from common import get, sitemap_urls, write_jsonl, scrape_urls

BASE = "https://www.stark.dk"
OUT = "data/latest/stark.jsonl"

GROSS_RE = re.compile(
    r'"GrossPrice":\{[^}]*?"StandardPriceInVat":"?(\d+)"?'
    r'[^}]*?"CampaignPriceInVat":(\d+)'
)


def fetch_url_list(limit=None):
    urls = []
    for f in ("sitemapvariants1.xml", "sitemapvariants2.xml"):
        urls.extend(sitemap_urls(get(f"{BASE}/{f}")))
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def handle(u, raw):
    text = htmllib.unescape(raw)
    m = GROSS_RE.search(text)
    if not m:
        return []
    std_ore, camp_ore = int(m.group(1)), int(m.group(2))
    price_ore = camp_ore if camp_ore > 0 else std_ore
    if not (50 <= price_ore <= 25000000):
        return []
    slug = u.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return [{
        "chain": "stark",
        "sku": u.split("id=")[-1] if "id=" in u else u.rsplit("-", 1)[-1],
        "ean": None,
        "name": slug.replace("-", " ").title(),
        "url": u,
        "price": (price_ore / 100.0) if 50 <= price_ore <= 25000000 else None,
        "in_stock": None,
        "campaign": camp_ore > 0,
    }]


def scrape(limit=None):
    def work(u):
        try:
            return handle(u, get(u))
        except Exception as e:
            print(f"  ! {u}: {e}")
            return []
    from common import pmap
    return pmap(work, fetch_url_list(limit))


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("stark: %d products -> %s" % (len(rows), OUT))
