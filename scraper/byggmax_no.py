"""Byggmax.se (SEK) — Magento sitemaps -> product pages -> itemprop price.
Sitemaps: robots.txt lists Sitemap_sv_se_product_00X.xml chunks.
Product URLs end in -p<digits>. Prices: itemprop="price" microdata (SEK)."""
import re
from common import get, sitemap_urls, sane_price, write_jsonl, scrape_urls

BASE = "https://www.byggmax.no"
OUT = "data/latest/byggmax_no.jsonl"
PRODUCT_PAT = re.compile(r"-p(\d+)$")
OG_RE = re.compile(r'og:image"\s*content="([^"]+)"')


def fetch_url_list(limit=None):
    # robots.txt lists a FLAT product sitemap (verified 2026-09-30: single
    # Sitemap_nb_no_product.xml, ~6,600 <loc> page URLs, 5,518 matching
    # -p<digits> — NOT an index of sitemap chunks like byggmax.se).
    # Product URLs contain raw ø/æ (e.g. /lage-døråpning-...) — percent-encode
    # the path so urllib doesn't raise UnicodeEncodeError.
    robots = get(BASE + "/robots.txt")
    sm_urls = re.findall(r"Sitemap:\s*(\S+product\S*\.xml)", robots)
    urls = []
    for sm in sm_urls:
        xml = get(sm)
        locs = re.findall(r"<loc>([^<]+)</loc>", xml)
        if any(l.strip().endswith(".xml") for l in locs):
            # index of chunks (byggmax.se style) — recurse
            for target in (locs or [sm]):
                for u in sitemap_urls(get(target)):
                    if PRODUCT_PAT.search(u):
                        urls.append(_enc(u))
                    if limit and len(urls) >= limit:
                        break
                if limit and len(urls) >= limit:
                    break
        else:
            # flat page list (byggmax.no style) — filter directly
            for u in locs:
                if PRODUCT_PAT.search(u):
                    urls.append(_enc(u))
        if limit and len(urls) >= limit:
            break
    return urls[:limit] if limit else urls


def _enc(u):
    """Percent-encode non-ASCII chars in the path part of a URL."""
    import urllib.parse
    return urllib.parse.quote(u, safe=":/%?#=&[]@!$'()*+,;~-._")


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
        "chain": "byggmax_no",
        "country": "no",
        "currency": "NOK",
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
    print("byggmax_no: %d products -> %s" % (len(rows), OUT))
