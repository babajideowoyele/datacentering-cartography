"""
WP4 — Contestation Corpus Builder
===================================
Research purpose: Assemble a news-media corpus of data center contestation
events for each facility city in the facility index. The corpus tracks how
public discourse around data center siting and operation has evolved over
time, and where a measurable "signal onset" — a sustained uptick in media
attention — first appeared.

Data source: GDELT DOC 2.0 API (https://api.gdeltproject.org/api/v2/doc/doc)
  - No authentication required; rate-limited to ~1 req/s (we use 2 s delay).
  - ArtList mode: returns individual articles matching the query.
  - TimelineVol mode: returns a normalised daily volume time series.

A BigQuery path (GDELT GKG table) is stubbed for future use when credentials
are available; the script defaults to the free DOC API.

Inputs:
    data/facility_index/facilities.csv
        Required columns: city, country, facility_id

Outputs (data/processed/wp4_contestation_corpus/):
    {city_slug}_articles.csv    — article-level: date, title, url, source, tone
    wp4_signal_summary.csv      — yearly event counts per city + signal_onset_year

Signal onset heuristic:
    First year whose normalised volume exceeds mean(all years) + 1 × std(all years).
    This is a simple statistical threshold; it flags years where media attention
    is meaningfully above baseline rather than ordinary year-to-year fluctuation.

Usage:
    python -m scripts.wp4.build_contestation_corpus [options]

    --facility-index PATH    Path to facilities CSV (default: data/facility_index/facilities.csv)
    --output DIR             Output directory (default: data/processed/wp4_contestation_corpus)
    --delay SECONDS          Pause between API requests (default: 2.0)
    --city CITY              Run for a single city only (matched case-insensitively)
    --dry-run                Print planned requests without calling the API
    --start-year YEAR        First year of the analysis window (default: 2015)
    --end-year YEAR          Last year of the analysis window (default: 2026)
"""

import argparse
import csv
import json
import logging
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path

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
GDELT_DOC_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_DELAY = 2.0          # seconds between API requests
DEFAULT_START_YEAR = 2015
DEFAULT_END_YEAR = 2026
MAX_ARTLIST_RECORDS = 250    # GDELT DOC API hard cap per request
SIGNAL_THRESHOLD_STD = 1.0   # multiplier on std for onset detection

USER_AGENT = (
    "DatacenteringCartographyBot/1.0 "
    "(research; +https://github.com/datacentering-cartography)"
)

# ---------------------------------------------------------------------------
# GDELT DOC API helpers
# ---------------------------------------------------------------------------


def _gdelt_request(params: dict) -> dict | None:
    """
    Issue a GET request to the GDELT DOC 2.0 API and return parsed JSON.

    Returns None on network error, timeout, or malformed response.
    GDELT occasionally returns empty bodies or HTML error pages — both
    are caught and logged rather than raised.
    """
    query_string = urllib.parse.urlencode(params)
    url = f"{GDELT_DOC_BASE}?{query_string}"
    log.debug("GET %s", url)

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        log.warning("Request failed: %s — %s", url, exc)
        return None

    if not raw.strip():
        log.warning("Empty response from GDELT for params: %s", params)
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        # GDELT sometimes returns truncated JSON or an HTML error page.
        log.warning("JSON parse error (%s) for params: %s", exc, params)
        return None


def build_query_string(city: str) -> str:
    """
    Construct the GDELT search query for data center discourse in a city.

    Uses OR logic between the two spellings and anchors to the city name.
    The parenthesised OR must be quoted for GDELT's query parser.
    """
    return f'"data center" OR "data centre" {city}'


def fetch_article_list(city: str, delay: float) -> list[dict]:
    """
    Fetch up to MAX_ARTLIST_RECORDS articles mentioning data centers in city.

    Returns a list of article dicts with keys: date, title, url, source, tone.
    """
    params = {
        "query": build_query_string(city),
        "mode": "ArtList",
        "maxrecords": MAX_ARTLIST_RECORDS,
        "timespan": "FULL",
        "format": "json",
    }
    log.info("  [ArtList] city=%s, query=%r", city, params["query"])
    time.sleep(delay)
    data = _gdelt_request(params)

    if data is None:
        return []

    articles_raw = data.get("articles", [])
    articles = []
    for art in articles_raw:
        # GDELT article fields vary; use .get() with safe defaults throughout.
        articles.append(
            {
                "date": art.get("seendate", ""),
                "title": art.get("title", ""),
                "url": art.get("url", ""),
                "source": art.get("domain", ""),
                "tone": art.get("tone", ""),
            }
        )
    log.info("    Retrieved %d articles.", len(articles))
    return articles


def fetch_timeline_volume(city: str, delay: float) -> list[dict]:
    """
    Fetch a smoothed daily normalised volume timeline for data center discourse
    in city.

    Returns a list of dicts with keys: date (YYYYMMDDHHMMSS or YYYYMMDD),
    value (float).
    """
    params = {
        "query": build_query_string(city),
        "mode": "TimelineVol",
        "smoothing": 7,
        "timespan": "FULL",
        "format": "json",
    }
    log.info("  [TimelineVol] city=%s", city)
    time.sleep(delay)
    data = _gdelt_request(params)

    if data is None:
        return []

    # GDELT TimelineVol wraps the series under a top-level key that varies;
    # try "timeline" first, then iterate over the first list-valued key.
    timeline = data.get("timeline", [])
    if not timeline:
        for key, val in data.items():
            if isinstance(val, list) and val:
                # Each element should be a dict with "date" and "value"
                if isinstance(val[0], dict) and "date" in val[0]:
                    timeline = val
                    break

    points = []
    for point in timeline:
        if isinstance(point, dict):
            points.append(
                {
                    "date": str(point.get("date", "")),
                    "value": float(point.get("value", 0.0)),
                }
            )
    log.info("    Retrieved %d timeline points.", len(points))
    return points


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def aggregate_yearly(
    timeline: list[dict],
    start_year: int,
    end_year: int,
) -> dict[int, float]:
    """
    Sum normalised volume values by year over [start_year, end_year].

    GDELT date strings are typically "YYYYMMDDHHMMSS" or "YYYYMMDD"; we
    extract the leading four characters as the year.

    Returns {year: total_volume} for every year in the window.
    """
    counts: dict[int, float] = {y: 0.0 for y in range(start_year, end_year + 1)}
    for point in timeline:
        date_str = point.get("date", "")
        if len(date_str) < 4:
            continue
        try:
            year = int(date_str[:4])
        except ValueError:
            continue
        if start_year <= year <= end_year:
            counts[year] += point.get("value", 0.0)
    return counts


def compute_signal_onset(yearly_counts: dict[int, float]) -> int | None:
    """
    Return the first year whose volume exceeds mean + SIGNAL_THRESHOLD_STD × std.

    Uses population statistics over all years in the window. Returns None if
    there are fewer than two data points or no year clears the threshold.
    """
    years = sorted(yearly_counts.keys())
    values = [yearly_counts[y] for y in years]

    if len(values) < 2:
        return None

    mean = statistics.mean(values)
    std = statistics.pstdev(values)

    if std == 0:
        return None

    threshold = mean + SIGNAL_THRESHOLD_STD * std
    for year in years:
        if yearly_counts[year] > threshold:
            return year
    return None


# ---------------------------------------------------------------------------
# BigQuery stub (future use)
# ---------------------------------------------------------------------------


def fetch_via_bigquery(city: str) -> list[dict]:
    """
    Stub for querying the GDELT GKG table on Google BigQuery.

    Requires google-cloud-bigquery and valid Application Default Credentials.
    This function raises ImportError immediately if the library is absent,
    allowing the caller to fall back to the DOC API.

    The intended query pattern would be:
        SELECT DATE, V2Tone, DocumentIdentifier, Extras
        FROM `gdelt-bq.gdeltv2.gkg_partitioned`
        WHERE _PARTITIONTIME BETWEEN '2015-01-01' AND '2026-12-31'
          AND LOWER(V2Locations) LIKE '%{city}%'
          AND (LOWER(Themes) LIKE '%data_center%'
               OR LOWER(DocumentIdentifier) LIKE '%data-center%')
    """
    try:
        from google.cloud import bigquery  # type: ignore  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "google-cloud-bigquery is not installed. "
            "Run `pip install google-cloud-bigquery` and configure "
            "Application Default Credentials to use BigQuery."
        ) from exc

    # Full implementation deferred until credentials are available.
    raise NotImplementedError(
        "BigQuery path is not yet implemented. "
        "The script currently uses the GDELT DOC 2.0 API."
    )


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------


def write_articles_csv(articles: list[dict], path: Path) -> None:
    """Write article-level data to a CSV file."""
    fieldnames = ["date", "title", "url", "source", "tone"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(articles)
    log.info("    Wrote %d articles → %s", len(articles), path)


def write_signal_summary_csv(
    rows: list[dict],
    path: Path,
    start_year: int,
    end_year: int,
) -> None:
    """
    Write the cross-city signal summary CSV.

    Columns: city, country, facility_id, signal_onset_year,
             year_{start_year} … year_{end_year}
    """
    year_cols = [f"year_{y}" for y in range(start_year, end_year + 1)]
    fieldnames = ["city", "country", "facility_id", "signal_onset_year"] + year_cols

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("Signal summary written → %s", path)


# ---------------------------------------------------------------------------
# Per-city processing
# ---------------------------------------------------------------------------


def process_city(
    facility: dict,
    output_dir: Path,
    delay: float,
    start_year: int,
    end_year: int,
    dry_run: bool,
) -> dict:
    """
    Run the full pipeline for one facility row and return its summary dict.

    Orchestrates:
      1. ArtList fetch → city articles CSV
      2. TimelineVol fetch → yearly aggregation → signal onset
    """
    city = facility["city"].strip()
    country = facility.get("country", "").strip()
    facility_id = facility.get("facility_id", "").strip()
    city_slug = city.lower().replace(" ", "_").replace(",", "")

    log.info("=== Processing: %s (%s) [%s] ===", city, country, facility_id)

    if dry_run:
        log.info(
            "[dry-run] Would query GDELT ArtList + TimelineVol for %r", city
        )
        summary = {"city": city, "country": country, "facility_id": facility_id,
                   "signal_onset_year": None}
        for y in range(start_year, end_year + 1):
            summary[f"year_{y}"] = 0.0
        return summary

    # --- 1. Article list ---
    articles = fetch_article_list(city, delay)
    articles_path = output_dir / f"{city_slug}_articles.csv"
    write_articles_csv(articles, articles_path)

    # --- 2. Timeline volume ---
    timeline = fetch_timeline_volume(city, delay)
    yearly_counts = aggregate_yearly(timeline, start_year, end_year)
    signal_onset = compute_signal_onset(yearly_counts)

    log.info(
        "  Yearly totals: %s",
        ", ".join(f"{y}={v:.2f}" for y, v in sorted(yearly_counts.items())),
    )
    log.info("  Signal onset year: %s", signal_onset)

    summary = {
        "city": city,
        "country": country,
        "facility_id": facility_id,
        "signal_onset_year": signal_onset if signal_onset is not None else "",
    }
    for y in range(start_year, end_year + 1):
        summary[f"year_{y}"] = round(yearly_counts.get(y, 0.0), 4)

    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def load_facilities(path: Path, city_filter: str | None) -> list[dict]:
    """
    Load and optionally filter the facility index CSV.

    Validates that required columns are present. Deduplicates by city so each
    city is queried only once (multiple facilities in the same city would
    otherwise generate duplicate API calls).
    """
    required_cols = {"city", "country", "facility_id"}

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        log.error("Facility index is empty: %s", path)
        raise SystemExit(1)

    missing = required_cols - set(rows[0].keys())
    if missing:
        log.error(
            "Facility index missing required columns: %s (found: %s)",
            missing,
            list(rows[0].keys()),
        )
        raise SystemExit(1)

    if city_filter:
        filter_lower = city_filter.lower()
        rows = [r for r in rows if r["city"].strip().lower() == filter_lower]
        if not rows:
            log.error(
                "No facilities found for city %r in %s", city_filter, path
            )
            raise SystemExit(1)
        log.info("City filter applied: %r → %d row(s)", city_filter, len(rows))

    # Deduplicate by city (keep first occurrence per city)
    seen: set[str] = set()
    deduped = []
    for row in rows:
        city_key = row["city"].strip().lower()
        if city_key not in seen:
            seen.add(city_key)
            deduped.append(row)

    if len(deduped) < len(rows):
        log.info(
            "Deduplicated %d facilities → %d unique cities.",
            len(rows),
            len(deduped),
        )

    return deduped


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "WP4: Build a GDELT-sourced news corpus of data center "
            "contestation events per facility city."
        )
    )
    parser.add_argument(
        "--facility-index",
        default="data/facility_index/facilities.csv",
        metavar="PATH",
        help="Path to facility index CSV (default: data/facility_index/facilities.csv).",
    )
    parser.add_argument(
        "--output",
        default="data/processed/wp4_contestation_corpus",
        metavar="DIR",
        help="Output directory (default: data/processed/wp4_contestation_corpus).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        metavar="SECONDS",
        help=f"Pause between API requests (default: {DEFAULT_DELAY}s).",
    )
    parser.add_argument(
        "--city",
        default=None,
        metavar="CITY",
        help="Run for a single city only (case-insensitive match against city column).",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=DEFAULT_START_YEAR,
        metavar="YEAR",
        help=f"First year of analysis window (default: {DEFAULT_START_YEAR}).",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=DEFAULT_END_YEAR,
        metavar="YEAR",
        help=f"Last year of analysis window (default: {DEFAULT_END_YEAR}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned requests without calling the API.",
    )
    args = parser.parse_args()

    facility_index_path = Path(args.facility_index)
    output_dir = Path(args.output)

    if not facility_index_path.exists():
        log.error("Facility index not found: %s", facility_index_path)
        raise SystemExit(1)

    if args.start_year > args.end_year:
        log.error(
            "--start-year (%d) must not exceed --end-year (%d)",
            args.start_year,
            args.end_year,
        )
        raise SystemExit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    log.info("Output directory: %s", output_dir.resolve())

    facilities = load_facilities(facility_index_path, args.city)
    log.info(
        "Processing %d city/cities over %d–%d.",
        len(facilities),
        args.start_year,
        args.end_year,
    )

    all_summaries: list[dict] = []

    for facility in facilities:
        summary = process_city(
            facility=facility,
            output_dir=output_dir,
            delay=args.delay,
            start_year=args.start_year,
            end_year=args.end_year,
            dry_run=args.dry_run,
        )
        all_summaries.append(summary)

    # Write cross-city summary
    summary_path = output_dir / "wp4_signal_summary.csv"
    if args.dry_run:
        log.info("[dry-run] Would write signal summary → %s", summary_path)
    else:
        write_signal_summary_csv(
            all_summaries,
            summary_path,
            args.start_year,
            args.end_year,
        )

    log.info(
        "Done. Processed %d city/cities. Summary: %s",
        len(all_summaries),
        summary_path,
    )


if __name__ == "__main__":
    main()
