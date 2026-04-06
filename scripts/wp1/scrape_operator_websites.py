"""
WP1 — Operator Corporate Website Scraper
=========================================
Research purpose: Capture how data center operators construct and maintain the
"cloud" imaginary through digital self-presentation. Targeted pages are
sustainability pages, facility/data-center listing pages, and about pages.

Input:  scripts/wp1/config_template.csv  (or a populated copy)
Output: data/raw/corporate-websites/{operator_name}/
        - {slug}.html        raw HTML
        - {slug}.txt         extracted plain text
        - {slug}_meta.json   title, meta description, image alt tags, links

Usage:
    python -m scripts.wp1.scrape_operator_websites \
        --config scripts/wp1/config_template.csv \
        --output data/raw/corporate-websites \
        [--delay 2.0] [--dry-run]
"""

import argparse
import csv
import json
import logging
import re
import time
import urllib.parse
import urllib.robotparser
from pathlib import Path

import requests
from bs4 import BeautifulSoup

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
DEFAULT_DELAY = 2.0          # seconds between requests (polite scraping)
DEFAULT_TIMEOUT = 20         # HTTP request timeout in seconds
USER_AGENT = (
    "DatacenteringCartographyBot/1.0 "
    "(research project; +https://github.com/datacentering-cartography; "
    "polite bot, respects robots.txt)"
)

# Page slugs to attempt for each operator (relative paths tried in order)
# These are appended to the base website_url when no explicit URL is given.
FALLBACK_PAGE_PATHS = {
    "sustainability": [
        "/sustainability",
        "/sustainability/",
        "/about/sustainability",
        "/company/sustainability",
        "/en/sustainability",
        "/corporate/sustainability",
    ],
    "data_centers": [
        "/data-centers",
        "/data-centers/",
        "/global-data-centers",
        "/locations",
        "/infrastructure",
        "/products/data-centers",
    ],
    "about": [
        "/about",
        "/about-us",
        "/company",
        "/company/about",
        "/en/about",
    ],
}

# Environmental / location keywords of research interest
KEYWORDS_OF_INTEREST = [
    "energy", "renewable", "carbon", "emissions", "water", "cooling",
    "pue", "power", "efficiency", "green", "climate", "net zero",
    "location", "region", "community", "local", "facility", "campus",
    "hyperscale", "colocation", "edge", "cloud",
]


# ---------------------------------------------------------------------------
# Robots.txt helper
# ---------------------------------------------------------------------------

class RobotsCache:
    """Cache robots.txt parsers keyed by scheme+netloc."""

    def __init__(self, user_agent: str):
        self._cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._ua = user_agent

    def allowed(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._cache:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = f"{base}/robots.txt"
            try:
                # Fetch robots.txt with a browser UA — CDNs/WAFs may return
                # different content to bot UAs, causing false disallows.
                import requests as _req
                resp = _req.get(
                    robots_url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=10,
                )
                rp.parse(resp.text.splitlines())
                log.debug("Fetched robots.txt from %s", robots_url)
            except Exception as exc:
                log.warning("Could not read robots.txt for %s: %s", base, exc)
            self._cache[base] = rp
        # Check our bot UA; fall back to wildcard '*' rules
        allowed_bot = self._cache[base].can_fetch(self._ua, url)
        allowed_star = self._cache[base].can_fetch("*", url)
        return allowed_bot or allowed_star


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------

def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return session


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def extract_metadata(soup: BeautifulSoup, url: str) -> dict:
    """Extract structured metadata from a parsed HTML page."""
    title = soup.title.get_text(strip=True) if soup.title else ""

    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta_tag:
        meta_desc = meta_tag.get("content", "")

    # Image alt tags — indicative of visual messaging choices
    image_alts = [
        img.get("alt", "").strip()
        for img in soup.find_all("img")
        if img.get("alt", "").strip()
    ]

    # Internal links that look like facility / location pages
    parsed_base = urllib.parse.urlparse(url)
    facility_keywords = re.compile(
        r"(data.?cent|facilit|campus|location|region|site)", re.I
    )
    internal_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        abs_href = urllib.parse.urljoin(url, href)
        parsed_href = urllib.parse.urlparse(abs_href)
        if parsed_href.netloc == parsed_base.netloc and facility_keywords.search(href):
            internal_links.append(
                {"text": a.get_text(strip=True)[:120], "href": abs_href}
            )

    # Deduplicate links by href
    seen: set[str] = set()
    deduped_links = []
    for lnk in internal_links:
        if lnk["href"] not in seen:
            seen.add(lnk["href"])
            deduped_links.append(lnk)

    # Keyword presence count (research signal)
    full_text = soup.get_text(" ", strip=True).lower()
    keyword_counts = {
        kw: len(re.findall(r"\b" + re.escape(kw) + r"\b", full_text))
        for kw in KEYWORDS_OF_INTEREST
    }

    return {
        "url": url,
        "title": title,
        "meta_description": meta_desc,
        "image_alts": image_alts,
        "facility_links": deduped_links,
        "keyword_counts": keyword_counts,
    }


def extract_text(soup: BeautifulSoup) -> str:
    """Return clean plain text, removing script/style noise."""
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text("\n").splitlines()]
    non_empty = [l for l in lines if l]
    return "\n".join(non_empty)


# ---------------------------------------------------------------------------
# Core scraping logic
# ---------------------------------------------------------------------------

def fetch_page(
    session: requests.Session,
    robots: RobotsCache,
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[str | None, str | None]:
    """
    Fetch a URL, respecting robots.txt.

    Returns (html_content, final_url) or (None, None) on failure.
    """
    if not robots.allowed(url):
        log.warning("robots.txt disallows: %s", url)
        return None, None
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp.text, resp.url
    except requests.exceptions.HTTPError as exc:
        log.warning("HTTP %s for %s", exc.response.status_code, url)
    except requests.exceptions.RequestException as exc:
        log.warning("Request failed for %s: %s", url, exc)
    return None, None


def resolve_url(base_url: str, explicit_url: str, fallback_paths: list[str]) -> str | None:
    """
    Return explicit_url if provided and non-empty, otherwise probe fallbacks.
    Returns the first non-empty URL string to attempt (probing happens later).
    """
    if explicit_url and explicit_url.strip():
        return explicit_url.strip()
    # Return first fallback composed from base
    if fallback_paths:
        base = base_url.rstrip("/")
        return base + fallback_paths[0]
    return None


def scrape_operator(
    row: dict,
    output_root: Path,
    session: requests.Session,
    robots: RobotsCache,
    delay: float,
    dry_run: bool,
) -> dict:
    """
    Scrape all relevant pages for one operator.

    Returns a summary dict recording what was collected.
    """
    operator_name = row["operator_name"].strip().replace(" ", "_").lower()
    base_url = row["website_url"].strip().rstrip("/")
    sustainability_url = row.get("sustainability_page_url", "").strip()

    operator_dir = output_root / operator_name
    if not dry_run:
        operator_dir.mkdir(parents=True, exist_ok=True)

    summary = {"operator": operator_name, "pages_collected": []}

    # Explicit per-page URLs from config (optional columns)
    explicit_dc_url = row.get("data_centers_page_url", "").strip()
    explicit_about_url = row.get("about_page_url", "").strip()

    # Build target list: (slug, url_candidates)
    # Explicit URL goes first; fallback paths appended after
    targets: list[tuple[str, list[str]]] = [
        ("sustainability", [sustainability_url] if sustainability_url else []),
        ("data_centers", [explicit_dc_url] if explicit_dc_url else []),
        ("about", [explicit_about_url] if explicit_about_url else []),
    ]
    # Append fallback paths for all targets
    for i, (slug, candidates) in enumerate(targets):
        for path in FALLBACK_PAGE_PATHS.get(slug, []):
            candidate = base_url + path
            if candidate not in candidates:
                candidates.append(candidate)
        targets[i] = (slug, candidates)

    for slug, url_candidates in targets:
        if not url_candidates:
            log.info("[%s] No candidates for slug '%s', skipping.", operator_name, slug)
            continue

        html, final_url = None, None
        for candidate in url_candidates:
            log.info("[%s] Trying %s → %s", operator_name, slug, candidate)
            if dry_run:
                log.info("[dry-run] Would fetch: %s", candidate)
                summary["pages_collected"].append(
                    {"slug": slug, "url": candidate, "status": "dry-run"}
                )
                break

            html, final_url = fetch_page(session, robots, candidate)
            time.sleep(delay)
            if html:
                break

        if dry_run:
            continue

        if not html:
            log.warning("[%s] Could not retrieve page for slug '%s'", operator_name, slug)
            summary["pages_collected"].append(
                {"slug": slug, "url": url_candidates[0], "status": "failed"}
            )
            continue

        soup = BeautifulSoup(html, "html.parser")
        text = extract_text(soup)
        meta = extract_metadata(soup, final_url)

        # Write outputs
        (operator_dir / f"{slug}.html").write_text(html, encoding="utf-8")
        (operator_dir / f"{slug}.txt").write_text(text, encoding="utf-8")
        (operator_dir / f"{slug}_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        log.info(
            "[%s] Saved %s (%d chars, %d facility links)",
            operator_name,
            slug,
            len(text),
            len(meta["facility_links"]),
        )
        summary["pages_collected"].append(
            {
                "slug": slug,
                "url": final_url,
                "status": "ok",
                "text_chars": len(text),
                "facility_links": len(meta["facility_links"]),
            }
        )

    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="WP1: Scrape operator corporate websites for Datacentering Cartography."
    )
    parser.add_argument(
        "--config",
        default="scripts/wp1/config_template.csv",
        help="Path to operator config CSV (default: scripts/wp1/config_template.csv)",
    )
    parser.add_argument(
        "--output",
        default="data/raw/corporate-websites",
        help="Root output directory (default: data/raw/corporate-websites)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Seconds between HTTP requests (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be fetched without making any HTTP requests.",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    output_root = Path(args.output)

    if not config_path.exists():
        log.error("Config CSV not found: %s", config_path)
        raise SystemExit(1)

    with config_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    log.info("Loaded %d operator rows from %s", len(rows), config_path)

    session = build_session()
    robots = RobotsCache(USER_AGENT)
    all_summaries = []

    for row in rows:
        operator_name = row.get("operator_name", "").strip()
        if not operator_name:
            log.warning("Skipping row with missing operator_name: %s", row)
            continue
        log.info("=== Processing operator: %s ===", operator_name)
        summary = scrape_operator(
            row=row,
            output_root=output_root,
            session=session,
            robots=robots,
            delay=args.delay,
            dry_run=args.dry_run,
        )
        all_summaries.append(summary)

    if not args.dry_run:
        summary_path = output_root / "scrape_summary.json"
        output_root.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(all_summaries, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log.info("Scrape summary written to %s", summary_path)

    log.info("Done. Processed %d operators.", len(all_summaries))


if __name__ == "__main__":
    main()
