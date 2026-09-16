"""STARK.dk — variant sitemaps -> product pages -> embedded GrossPrice JSON.
Amounts in oere. Campaign price 0 = no campaign."""
import re
import html as htmllib
from common import get, sitemap_urls, write_jsonl, scrape_with_checkpoint

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


OG_RE = re.compile(r'og:image"\s*content="([^"]+)"')


def handle(u, raw):
    text = htmllib.unescape(raw)
    og = OG_RE.search(text)
    img = og.group(1) if og else None
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
        "image": img,
        "price": price_ore / 100.0,
        "in_stock": None,
        "campaign": camp_ore > 0,
    }]


def scrape(limit=None):
    # Two variant sitemaps, 50k+ urls each (verified live) - a huge share
    # are dead 404s (documented above/in the repo README), but even a
    # cheap 404 costs a request, and 100k+ requests at the deliberately
    # polite rate is still no single-CI-job's worth of time. See
    # scrape_with_checkpoint's own doc comment for why this isn't a plain
    # scrape_urls (or, as before, hand-rolled pmap) call.
    return scrape_with_checkpoint("stark", fetch_url_list(limit), handle, limit)


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    rows = scrape(lim)
    write_jsonl(OUT, rows)
    print("stark: %d products -> %s" % (len(rows), OUT))
