"""
DK Byggepriser — nightly price snapshots from Danish building-supply chains.

Verified data sources (probed 2026-08-28):
  silvan.dk    : sitemapvariantfeed.xml (39.491 product URLs, lastmod 03:00 nightly)
                 -> schema.org Product ld+json on each product page (price, DKK)
  xl-byg.dk    : /sitemap/b2c-{1..N}-product-sitemap.xml
                 -> schema.org Product ld+json on each product page
  stark.dk     : /sitemapvariants1.xml + variants2 (product URLs w/ ?id=variant)
                 -> HTML-embedded JSON: GrossPrice.StandardPriceInVat /
                    CampaignPriceInVat (prices in oere = DKK*100)
  bauhaus.dk   : /media/sitemap_dk/sitemap-{7}-{1..11}.xml (Magento)
                 -> data-price-amount="..." in product HTML (main price box)
  davidsen.dk  : category pages embed product JSON incl. priceInformation
                 -> we walk category pages, not every product page (cheaper)
                 product URLs end in -p-<id>; categories in -c-id<id>
  johannesfog.dk: /da-dk/sitemap/products/{1..N}
                 -> schema.org Product ld+json on each product page
  bygma.dk     : LOGIN-ONLY webshop — no public prices. Not scraped.

Output:
  data/latest/<chain>.jsonl      full snapshot, overwritten each run
  data/history/<chain>/<date>.jsonl  only price CHANGES vs previous day
"""
