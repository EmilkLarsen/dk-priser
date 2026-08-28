# DK Byggepriser — daglige prisSnapshots fra danske byggemarkeder

Nightlig price snapshots from 9 Danish building-supply & home-improvement
chains, published as data files in this repo. Built to give the Fixer AI
estimator real, current DKK prices.

## Chains covered

| Chain | Products | What we scrape | Notes |
|---|---|---|---|
| silvan.dk | 39.491 | sitemap → ld+json price | nightly sitemap 03:00 |
| xl-byg.dk | ~50.000+ | product sitemaps → ld+json | |
| stark.dk | variants sitemap | HTML price JSON (øre) | some 404s (dead variants) |
| bauhaus.dk | ~100.000 | Magento sitemap → data-price-amount | 11 sitemap files |
| davidsen.dk | category-walk | embedded product JSON | 21.008 categories indexed |
| johannesfog.dk | 29.887 | sitemap → ld+json (ProductGroup) | |
| harald-nyborg.dk | 10.890 | sitemap → ld+json | |
| power.dk | 30.000+ | product sitemaps → ld+json | appliances/electronics |
| skousen.dk | 5.350 | sitemap → ld+json | premium appliances |
| bygma.dk | — | **login-only webshop** | not scrapeable, see notes |

**Not covered (backlog):** Elgiganten (Vercel bot-challenge), jem & fix
(TLS-blocks datacenter IPs; works from residential), IKEA (global sitemap,
different structure — needs its own parser).

## Data layout

```
data/latest/<chain>.jsonl      full snapshot per chain (overwritten nightly)
data/latest/prices.jsonl       all chains merged — this is what the API reads
data/latest/comparison.json    products matched across ≥2 chains, sorted by spread
data/latest/summary.json       run stats (counts, errors) for monitoring
data/history/<chain>/<date>.jsonl  price CHANGES only (append-only log)
```

Row format: `{"chain","sku","ean","name","url","price","in_stock","campaign"}`

## Run it

```bash
python3 scraper/run_daily.py          # full run (~150k+ products, hours)
python3 scraper/run_daily.py 200      # smoke: 200 products per chain
python3 scraper/build_comparison.py   # cross-chain comparison + API package
```

## Automation

GitHub Actions runs the full scrape daily at 04:00 Danish time
(`.github/workflows/daily-prices.yml`) and commits the new snapshots.
Zero infra: the repo IS the database. The Fixer backend reads
`data/latest/prices.jsonl` via raw.githubusercontent / jsDelivr.

## How the estimator uses this

1. AI vision/RoomPlan produces a **material BOM** for the project
2. Each BOM line is matched (EAN when present, else normalized name) to
   `prices.jsonl`
3. Quote shows min/median across chains + honest spread:
   *"Terrassebrædder: 8.400–11.200 kr. i materialer (priser fra Silvan,
   XL-BYG og Bauhaus, hentet i dag)"*

## Legal/ethical

- Only public retail prices (facts — not copyrightable in DK/EU)
- Per-host rate limiting (1.2–2 s) + jitter, realistic UA, robots.txt checked
- No logins, no personal data, no circumvention of bot protection
