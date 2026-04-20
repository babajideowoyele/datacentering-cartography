"""
OpenAlex bibliometric audit — data center literature, 2010-2025.

Queries:
  1. Total corpus: title contains "data center" OR "data centre"
  2. Growth: annual counts 2010 vs 2024
  3. Silo classification via OpenAlex concepts
  4. Innovation studies check: MLP / TIS / SNM keyword co-occurrence

Run from repo root:
    python scripts/bibliometric/openalex_audit.py

Outputs results to stdout and saves raw counts to
    data/processed/bibliometric/openalex_audit.json
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

MAILTO = "babajide.owoyele@gmail.com"
BASE = "https://api.openalex.org"


def get(endpoint, params):
    params["mailto"] = MAILTO
    url = f"{BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def count(filter_str):
    d = get("works", {"filter": filter_str, "per_page": 1})
    return d["meta"]["count"]


# ---------------------------------------------------------------------------
# 1. Total corpus
# ---------------------------------------------------------------------------
print("=" * 60)
print("OpenAlex Bibliometric Audit — Data Centers, 2010-2025")
print("=" * 60)

# "data center" (US) and "data centre" (UK) combined
total_us = count("title.search:\"data center\",publication_year:2010-2025")
time.sleep(0.5)
total_uk = count("title.search:\"data centre\",publication_year:2010-2025")
time.sleep(0.5)

# OpenAlex title.search with OR isn't straightforward — sum minus overlap
# Get overlap (both spellings in title — rare but possible)
# For simplicity, report both and their union estimate
print(f"\n1. CORPUS SIZE")
print(f"   'data center' in title (2010-2025): {total_us:,}")
print(f"   'data centre' in title (2010-2025): {total_uk:,}")
print(f"   Combined (approx, may double-count bilingual titles): ~{total_us + total_uk:,}")

# ---------------------------------------------------------------------------
# 2. Growth rate — annual counts
# ---------------------------------------------------------------------------
print(f"\n2. GROWTH")
y2010 = count("title.search:\"data center\",publication_year:2010")
time.sleep(0.5)
y2024 = count("title.search:\"data center\",publication_year:2024")
time.sleep(0.5)
y2025 = count("title.search:\"data center\",publication_year:2025")
time.sleep(0.5)
growth_pct = round((y2024 - y2010) / y2010 * 100) if y2010 else None
print(f"   2010: {y2010:,}")
print(f"   2024: {y2024:,}")
print(f"   2025 (partial): {y2025:,}")
print(f"   Growth 2010 to 2024: {growth_pct}%")

# ---------------------------------------------------------------------------
# 3. Silo classification via OpenAlex concept IDs
#    Computer Science    : C41008148
#    Engineering         : C127413603
#    Environmental Sci   : C39432304
#    Social Sciences     : C144024400
#    Business/Management : C144133560
# ---------------------------------------------------------------------------
print(f"\n3. SILO BREAKDOWN (US spelling, 2010-2025)")

dc_filter = "title.search:\"data center\",publication_year:2010-2025"

# Technical efficiency: CS or Engineering concept
tech = count(f"{dc_filter},concepts.id:C41008148|C127413603")
time.sleep(0.5)

# Environmental impact: Environmental Science concept
env = count(f"{dc_filter},concepts.id:C39432304")
time.sleep(0.5)

# Social Sciences: sociology, political science, geography, anthropology
soc = count(f"{dc_filter},concepts.id:C144024400|C17744445|C205649164|C142362112")
time.sleep(0.5)

print(f"   Technical (CS + Engineering concepts): {tech:,}")
print(f"   Environmental (Environmental Science concept): {env:,}")
print(f"   Social/political (Social Science concepts): {soc:,}")
print(f"   Note: concepts overlap; papers may appear in multiple silos")

# ---------------------------------------------------------------------------
# 4. Innovation studies — MLP / TIS / SNM co-occurrence
#    Search for papers with BOTH "data center" in title AND
#    innovation-studies keywords in abstract/title
# ---------------------------------------------------------------------------
print(f"\n4. INNOVATION STUDIES CO-OCCURRENCE")

innov_terms = [
    ("multi-level perspective", "multi-level+perspective"),
    ("technological innovation system", "technological+innovation+system"),
    ("strategic niche management", "strategic+niche+management"),
    ("sociotechnical regime", "sociotechnical+regime"),
    ("sustainability transition", "sustainability+transition"),
]

innov_total = 0
for label, term in innov_terms:
    n = count(f"title.search:\"data center\",abstract.search:{term},publication_year:2010-2025")
    time.sleep(0.5)
    print(f"   + '{label}' in abstract: {n}")
    innov_total += n

print(f"   Total (with double-counting): {innov_total}")

# ---------------------------------------------------------------------------
# 5. Save results
# ---------------------------------------------------------------------------
out_dir = Path("data/processed/bibliometric")
out_dir.mkdir(parents=True, exist_ok=True)

results = {
    "query_date": "2026-04-20",
    "source": "OpenAlex API",
    "corpus": {
        "data_center_US_2010_2025": total_us,
        "data_centre_UK_2010_2025": total_uk,
    },
    "growth": {
        "2010": y2010,
        "2024": y2024,
        "2025_partial": y2025,
        "growth_pct_2010_to_2024": growth_pct,
    },
    "silos": {
        "technical_CS_engineering": tech,
        "environmental": env,
        "social_political": soc,
    },
    "innovation_studies_cooccurrence": {
        label: count(f"title.search:\"data center\",abstract.search:{term},publication_year:2010-2025")
        for label, term in innov_terms
    },
}

out_path = out_dir / "openalex_audit.json"
out_path.write_text(json.dumps(results, indent=2))
print(f"\nSaved to {out_path}")
