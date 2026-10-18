#!/usr/bin/env python3
"""fleet_audit.py — cross-check scraper/config consistency in one country repo.

Catches the bug class that has bitten repeatedly (DK-poisoned lists after bulk
syncs): every country-specific config must agree with every other. Exits 1 on
any inconsistency, printing exactly what disagrees.
"""
import os, re, sys, glob

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRAPER = os.path.join(ROOT, "scraper")
WF = os.path.join(ROOT, ".github", "workflows", "daily-prices.yml")
errors = []

def read(p):
    try:
        return open(p, encoding="utf-8").read()
    except OSError:
        return ""

# 1) chains in run_daily
s = read(os.path.join(SCRAPER, "run_daily.py"))
m = re.search(r"CHAINS\s*=\s*\[([^\]]*)\]", s, re.S)
daily_chains = re.findall(r'"([a-z_0-9]+)"', m.group(1)) if m else []
if not daily_chains:
    errors.append("run_daily.py: CHAINS list empty/unparseable")

# 2) chains in check_incomplete + EXPECTED keys
s = read(os.path.join(SCRAPER, "check_incomplete.py"))
m = re.search(r"CHAINS\s*=\s*\[([^\]]*)\]", s, re.S)
inc_chains = re.findall(r'"([a-z_0-9]+)"', m.group(1)) if m else []
m = re.search(r"EXPECTED\s*=\s*\{([^}]*)\}", s, re.S)
exp_keys = re.findall(r'"([a-z_0-9]+)"\s*:', m.group(1)) if m else []
if sorted(inc_chains) != sorted(daily_chains):
    errors.append(f"check_incomplete CHAINS {inc_chains} != run_daily CHAINS {daily_chains}")
if sorted(exp_keys) != sorted(daily_chains):
    errors.append(f"check_incomplete EXPECTED keys {exp_keys} != run_daily CHAINS {daily_chains}")
if "0.6" not in s:
    errors.append("check_incomplete: 60% floor missing")

# 3) scraper modules exist for every chain; checkpoint-aware for ckpt chains
for c in daily_chains:
    if not os.path.exists(os.path.join(SCRAPER, f"{c}.py")):
        errors.append(f"chain {c}: scraper/{c}.py missing")
    else:
        mod = read(os.path.join(SCRAPER, f"{c}.py"))
        if "scrape_with_checkpoint" not in mod:
            errors.append(f"chain {c}: not checkpointed (plain scrape_urls)")
        elif "deadline" not in mod:
            errors.append(f"chain {c}: checkpointed but scrape() lacks deadline kwarg")

# 4) workflow matrix matches CHAINS
wf = read(WF)
m = re.search(r"chain:\s*\[([^\]]*)\]", wf)
wf_chains = re.findall(r"([a-z_0-9]+)", m.group(1)) if m else []
if sorted(wf_chains) != sorted(daily_chains):
    errors.append(f"workflow matrix {wf_chains} != run_daily CHAINS {daily_chains}")
if 'SCRAPE_DEADLINE_SECONDS: "18000"' not in wf:
    errors.append("workflow: SCRAPE_DEADLINE_SECONDS missing")
if 'inputs.full' in wf and not re.search(r"if:.*inputs\.full|inputs\.full ==", wf):
    errors.append("workflow: stale-guard gate missing")
# 2026-10-14 bugs: bare ${{ inputs.full }} in shell steps is EMPTY on
# workflow_dispatch; && binds tighter than || in GitHub expressions, so an
# unparenthesized group split schedule/full runs into different concurrency
# groups. Both slipped past yaml.safe_load and this auditor once — grep hard.
if re.search(r"\$\{\{\s*inputs\.full\b", wf):
    errors.append("workflow: bare ${{ inputs.full }} used (empty on workflow_dispatch) - use github.event.inputs.full")
if re.search(r"github\.event_name == 'schedule'\s*\|\|\s*github\.event\.inputs\.full == 'true'\s*&&", wf):
    errors.append("workflow: unparenthesized (schedule || full) && group - precedence bug")
if not re.search(r"\) && 'daily-prices' \|\| 'daily-prices-smoke'", wf):
    errors.append("workflow: concurrency group pattern missing/changed")
# continuation case-match must be whitespace-proof: check_incomplete prints
# ', '-joined names but the case matches ',<chain>,' — without normalization
# every chain AFTER THE FIRST in the incomplete list is silently skipped
# (nl/hubo_nl live 2026-10-18: stalled 5 days while flagged incomplete daily)
if 'case ",$INC," in' in wf and "tr -d ' '" not in wf:
    errors.append("workflow: continuation case-match not whitespace-normalized (skips non-first incomplete chains)")

if "  healer:" not in wf:
    errors.append("workflow: auto-heal job missing")
if "needs: [scrape, merge, continue-check, healer]" not in wf:
    errors.append("workflow: alert does not gate on healer result")
if not os.path.exists(os.path.join(ROOT, "data", "latest", "schema.json")):
    errors.append("data/latest/schema.json missing (merge git add depends on it)")

# 4b) run_daily must never delete the snapshot it just wrote (2026-10-14:
# pasted legacy-twin-removal blocks deleted f"{chain}.jsonl.gz" right after
# write_jsonl, so no snapshot reached main and every merge collapsed to 0
# rows — collapse guard kept the feed but the run failed and the healer
# burned its cap nightly, dk + se)
s = read(os.path.join(SCRAPER, "run_daily.py"))
if re.search(r'os\.remove\([^)]*chain\}\.jsonl\.gz', s):
    errors.append("run_daily: deletes <chain>.jsonl.gz (snapshot never reaches main, merge = 0 rows)")

# 5) check_stale is checkpoint-aware and does not alert on KNOWN_BLOCKED chains
s = read(os.path.join(SCRAPER, "check_stale.py"))
if "checkpoint build in progress" not in s:
    errors.append("check_stale: not checkpoint-aware (false alerts on multi-night builds)")
if re.search(r"KNOWN_BLOCKED\s*=\s*\{", s) and "known-blocked (bot-walled from CI IPs), stale" not in s:
    errors.append("check_stale: KNOWN_BLOCKED set present but age>MAX branch not exempted (healer caps burned nightly)")
if "KNOWN_BLOCKED" in s and not re.search(r"^KNOWN_BLOCKED\s*=", s, re.M):
    errors.append("check_stale: references KNOWN_BLOCKED without defining it (NameError in every run)")

# 6) no DK-poisoned DEFAULT_CHAINS in country repos (dk is allowed its 9)
is_dk = os.path.basename(ROOT).startswith("dk-byggepriser")
s = read(os.path.join(SCRAPER, "check_incomplete.py"))
if not is_dk and any(c in s for c in ('"silvan"', '"xlbyg"', '"skousen"')):
    errors.append("check_incomplete: DK chain names present in non-DK repo")
s = read(os.path.join(SCRAPER, "check_stale.py"))
m = re.search(r"DEFAULT_CHAINS\s*=\s*\[([^\]]*)\]", s, re.S)
dc = re.findall(r'"([a-z_0-9]+)"', m.group(1)) if m else []
if not is_dk and dc and set(dc) & {"silvan","xlbyg","stark","bauhaus","davidsen","fog","haraldnyborg","power","skousen"} and set(dc) - {c for c in dc if c in daily_chains}:
    errors.append(f"check_stale DEFAULT_CHAINS contains foreign chains: {set(dc)-set(daily_chains)}")

if errors:
    print(f"AUDIT FAIL ({os.path.basename(ROOT)}):")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print(f"AUDIT OK ({os.path.basename(ROOT)}): {len(daily_chains)} chains consistent")
