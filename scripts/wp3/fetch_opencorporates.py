"""
WP3 — fetch_opencorporates.py
==============================
Research purpose: Resolve operator and owner company names from the facility
index against the OpenCorporates registry to obtain formal registration data.
This is a prerequisite for building the ownership graph: we need canonical
legal identities, jurisdictions, and officer networks to trace the chain from
a facility through to its ultimate beneficial owner.

API: OpenCorporates REST API (https://api.opencorporates.com/documentation)
  - Free tier: ~50 requests/minute, results limited per page.
  - Authenticated tier: higher rate limits; recommended for bulk runs.

API key setup
-------------
1. Register at https://opencorporates.com/users/sign_up
2. Generate an API token at https://app.opencorporates.com/users/account
3. Set the environment variable:
       export OPENCORPORATES_API_KEY="your_token_here"
   or pass --api-key on the command line.
   The script works without a key (anonymous tier) but is more aggressively
   rate-limited and returns fewer search results per page.

Input:  scripts/wp3/config_template.csv  (or a populated copy)
        Columns used: company_name, opencorporates_jurisdiction, country

Output: data/raw/financial/opencorporates/{slug}/
        - search_results.json   raw search response (top matches)
        - company.json          full company record for the best match
        - officers.json         officer list (if available at free tier)
        - fetch_log.json        per-company status and metadata

Usage:
    python -m scripts.wp3.fetch_opencorporates \\
        --config scripts/wp3/config_template.csv \\
        --output data/raw/financial/opencorporates \\
        [--api-key YOUR_KEY] \\
        [--delay 1.5] \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://api.opencorporates.com/v0.4"
DEFAULT_DELAY = 1.5          # seconds between requests (free tier: ~50 req/min)
DEFAULT_TIMEOUT = 20
USER_AGENT = (
    "DatacenteringCartographyBot/1.0 "
    "(research project; +https://github.com/datacentering-cartography)"
)

# Fields to extract from a company record
COMPANY_FIELDS = [
    "name",
    "company_number",
    "jurisdiction_code",
    "incorporation_date",
    "dissolution_date",
    "company_type",
    "current_status",
    "registered_address",
    "agent_name",
    "agent_address",
    "opencorporates_url",
    "source",
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def build_session(api_key: str | None) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    if api_key:
        session.headers.update({"Authorization": f"Token token={api_key}"})
    return session


def _get(
    session: requests.Session,
    url: str,
    params: dict,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict | None:
    """
    Make a GET request and return the parsed JSON body, or None on failure.
    Handles 429 rate-limit responses with a back-off retry.
    """
    for attempt in (1, 2, 3):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:
                wait = 60 * attempt
                log.warning("Rate limited (429). Waiting %ds before retry %d/3.", wait, attempt)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            log.warning("HTTP error %s for %s: %s", exc.response.status_code, url, exc)
            return None
        except requests.exceptions.RequestException as exc:
            log.warning("Request error for %s: %s", url, exc)
            return None
    log.error("Exhausted retries for %s", url)
    return None


# ---------------------------------------------------------------------------
# OpenCorporates API wrappers
# ---------------------------------------------------------------------------

def search_companies(
    session: requests.Session,
    company_name: str,
    jurisdiction: str | None,
    per_page: int = 5,
) -> list[dict]:
    """
    Search for companies by name (and optionally jurisdiction).
    Returns a list of company stub dicts from the search results.
    """
    params: dict[str, Any] = {
        "q": company_name,
        "per_page": per_page,
        "format": "json",
    }
    if jurisdiction:
        params["jurisdiction_code"] = jurisdiction.lower()

    data = _get(session, f"{BASE_URL}/companies/search", params)
    if not data:
        return []

    try:
        return [
            item["company"]
            for item in data["results"]["companies"]
        ]
    except (KeyError, TypeError) as exc:
        log.warning("Unexpected search response structure: %s", exc)
        return []


def fetch_company(
    session: requests.Session,
    jurisdiction_code: str,
    company_number: str,
) -> dict | None:
    """
    Fetch the full company record for a known jurisdiction + company number.
    Returns the company dict, or None on failure.
    """
    url = f"{BASE_URL}/companies/{jurisdiction_code}/{company_number}"
    data = _get(session, url, params={"format": "json"})
    if not data:
        return None
    try:
        return data["results"]["company"]
    except (KeyError, TypeError) as exc:
        log.warning("Unexpected company record structure: %s", exc)
        return None


def fetch_officers(
    session: requests.Session,
    jurisdiction_code: str,
    company_number: str,
) -> list[dict]:
    """
    Fetch the officer list for a company.
    Note: officer detail may be restricted on the free API tier for some
    jurisdictions. Returns an empty list if unavailable.
    """
    url = f"{BASE_URL}/companies/{jurisdiction_code}/{company_number}/officers"
    data = _get(session, url, params={"format": "json", "per_page": 100})
    if not data:
        return []
    try:
        return [
            item["officer"]
            for item in data["results"]["officers"]
        ]
    except (KeyError, TypeError):
        return []


# ---------------------------------------------------------------------------
# Matching heuristic
# ---------------------------------------------------------------------------

def _normalise_name(name: str) -> str:
    """Lower-case, strip common legal suffixes and punctuation for fuzzy match."""
    suffixes = r"\b(inc|ltd|llc|plc|gmbh|bv|sa|sas|nv|ag|corp|co|group|holdings?)\b"
    name = re.sub(suffixes, "", name.lower())
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def best_match(candidates: list[dict], target_name: str) -> dict | None:
    """
    Return the candidate whose name best matches target_name, or the first
    candidate if no normalised name match is found.
    """
    if not candidates:
        return None
    target_norm = _normalise_name(target_name)
    for candidate in candidates:
        if _normalise_name(candidate.get("name", "")) == target_norm:
            return candidate
    # Fall back to first result
    return candidates[0]


# ---------------------------------------------------------------------------
# Per-company pipeline
# ---------------------------------------------------------------------------

def process_company(
    row: dict,
    output_root: Path,
    session: requests.Session,
    delay: float,
    dry_run: bool,
) -> dict:
    """
    Run the full fetch pipeline for one company row from the config CSV.
    Returns a log dict recording what was retrieved.
    """
    company_name = row["company_name"].strip()
    jurisdiction = row.get("opencorporates_jurisdiction", "").strip() or None
    slug = re.sub(r"[^\w]", "_", company_name.lower())

    log.info("=== Processing: %s ===", company_name)

    fetch_record: dict[str, Any] = {
        "company_name": company_name,
        "slug": slug,
        "jurisdiction_hint": jurisdiction,
        "search_hits": 0,
        "matched_company_number": None,
        "matched_jurisdiction": None,
        "officers_fetched": 0,
        "status": "pending",
    }

    if dry_run:
        log.info("[dry-run] Would search OpenCorporates for: %s (jurisdiction=%s)",
                 company_name, jurisdiction)
        fetch_record["status"] = "dry-run"
        return fetch_record

    company_dir = output_root / slug
    company_dir.mkdir(parents=True, exist_ok=True)

    # 1. Search
    time.sleep(delay)
    candidates = search_companies(session, company_name, jurisdiction)
    fetch_record["search_hits"] = len(candidates)

    if not candidates:
        log.warning("No results for '%s'.", company_name)
        fetch_record["status"] = "no_results"
        (company_dir / "search_results.json").write_text(
            json.dumps([], indent=2), encoding="utf-8"
        )
        _write_fetch_log(company_dir, fetch_record)
        return fetch_record

    (company_dir / "search_results.json").write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("  Found %d candidate(s) for '%s'.", len(candidates), company_name)

    # 2. Select best match
    match = best_match(candidates, company_name)
    if not match:
        fetch_record["status"] = "no_match"
        _write_fetch_log(company_dir, fetch_record)
        return fetch_record

    jcode = match.get("jurisdiction_code", "")
    cnum = match.get("company_number", "")
    fetch_record["matched_company_number"] = cnum
    fetch_record["matched_jurisdiction"] = jcode
    log.info("  Best match: %s / %s  (%s)", jcode, cnum, match.get("name"))

    # 3. Full company record
    time.sleep(delay)
    full_record = fetch_company(session, jcode, cnum)
    if full_record:
        extracted = {field: full_record.get(field) for field in COMPANY_FIELDS}
        (company_dir / "company.json").write_text(
            json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log.info("  Company record saved.")
    else:
        log.warning("  Could not fetch full record for %s/%s.", jcode, cnum)
        fetch_record["status"] = "company_fetch_failed"
        _write_fetch_log(company_dir, fetch_record)
        return fetch_record

    # 4. Officers
    time.sleep(delay)
    officers = fetch_officers(session, jcode, cnum)
    fetch_record["officers_fetched"] = len(officers)
    if officers:
        (company_dir / "officers.json").write_text(
            json.dumps(officers, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log.info("  %d officer(s) saved.", len(officers))
    else:
        log.info("  No officer data returned (may be restricted at free tier).")

    fetch_record["status"] = "ok"
    _write_fetch_log(company_dir, fetch_record)
    return fetch_record


def _write_fetch_log(company_dir: Path, record: dict) -> None:
    (company_dir / "fetch_log.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="WP3: Fetch company registration data from OpenCorporates."
    )
    parser.add_argument(
        "--config",
        default="scripts/wp3/config_template.csv",
        help="Path to company config CSV (default: scripts/wp3/config_template.csv)",
    )
    parser.add_argument(
        "--output",
        default="data/raw/financial/opencorporates",
        help="Root output directory (default: data/raw/financial/opencorporates)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help=(
            "OpenCorporates API token. Overrides OPENCORPORATES_API_KEY env var. "
            "Free-tier anonymous access is used if neither is provided."
        ),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Seconds between API requests (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be fetched without making any HTTP requests.",
    )
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("OPENCORPORATES_API_KEY")
    if not api_key:
        log.info(
            "No API key found. Using anonymous tier (rate-limited). "
            "Set OPENCORPORATES_API_KEY for higher limits."
        )

    config_path = Path(args.config)
    if not config_path.exists():
        log.error("Config CSV not found: %s", config_path)
        raise SystemExit(1)

    with config_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    log.info("Loaded %d company rows from %s", len(rows), config_path)

    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)
    session = build_session(api_key)
    all_logs: list[dict] = []

    for row in rows:
        if not row.get("company_name", "").strip():
            log.warning("Skipping row with missing company_name: %s", row)
            continue
        result = process_company(
            row=row,
            output_root=output_root,
            session=session,
            delay=args.delay,
            dry_run=args.dry_run,
        )
        all_logs.append(result)

    summary_path = output_root / "fetch_summary.json"
    summary_path.write_text(
        json.dumps(all_logs, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("Summary written to %s", summary_path)
    ok = sum(1 for r in all_logs if r["status"] == "ok")
    log.info("Done. %d/%d companies fetched successfully.", ok, len(all_logs))


if __name__ == "__main__":
    main()
