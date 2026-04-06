"""
WP2 — collect_corporate_imagery.py

Downloads images from operator websites (sustainability, facilities, about pages)
and saves them alongside a manifest CSV capturing metadata.

Usage
-----
    python scripts/wp2/collect_corporate_imagery.py \
        --config data/raw/corporate-websites/operators.csv \
        --outdir data/raw/visual/corporate \
        [--delay 2.0]

The config CSV is the WP1 config_template.csv format:
    operator_name, website_url, sustainability_page_url, city_name, country, ...

Additional pages scraped per operator (hardcoded slug heuristics, see EXTRA_SLUGS).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import os
import re
import time
import urllib.parse
import urllib.robotparser
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Additional page slugs to attempt per operator (appended to base URL)
EXTRA_SLUGS: list[str] = [
    "/about",
    "/about-us",
    "/facilities",
    "/data-centers",
    "/datacenters",
    "/infrastructure",
    "/sustainability",
    "/esg",
    "/environment",
]

# Only download these MIME types
ALLOWED_CONTENT_TYPES: set[str] = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/svg+xml",
}

# Minimum image file size to bother saving (bytes)
MIN_IMAGE_BYTES: int = 2_048

DEFAULT_DELAY: float = 2.0  # seconds between requests
REQUEST_TIMEOUT: int = 20   # seconds

HEADERS: dict[str, str] = {
    "User-Agent": (
        "DatacenteringCartographyBot/1.0 "
        "(academic research; contact: research@example.org)"
    )
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# robots.txt helper
# ---------------------------------------------------------------------------

class RobotsCache:
    """Cache and query robots.txt per domain."""

    def __init__(self) -> None:
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _get_parser(self, base_url: str) -> urllib.robotparser.RobotFileParser:
        parsed = urllib.parse.urlparse(base_url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        if domain not in self._parsers:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = f"{domain}/robots.txt"
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception as exc:
                logger.warning("Could not read robots.txt at %s: %s", robots_url, exc)
            self._parsers[domain] = rp
        return self._parsers[domain]

    def is_allowed(self, url: str, user_agent: str = "*") -> bool:
        # Skip data: and blob: URIs — not HTTP resources
        if url.startswith(("data:", "blob:")):
            return False
        try:
            rp = self._get_parser(url)
            return rp.can_fetch(user_agent, url)
        except Exception:
            return True  # fail open


# ---------------------------------------------------------------------------
# Core scraping functions
# ---------------------------------------------------------------------------

def resolve_pages(operator: dict[str, str]) -> list[str]:
    """Return list of page URLs to scrape for this operator."""
    base = operator["website_url"].rstrip("/")
    pages: list[str] = []

    # Always include the sustainability page if present
    if operator.get("sustainability_page_url"):
        pages.append(operator["sustainability_page_url"])

    # Attempt extra slugs
    for slug in EXTRA_SLUGS:
        pages.append(base + slug)

    return pages


def fetch_html(url: str, session: requests.Session, delay: float) -> Optional[str]:
    """GET a page, respecting delay. Returns HTML text or None on failure."""
    time.sleep(delay)
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        logger.debug("Failed to fetch %s: %s", url, exc)
        return None


def extract_images(html: str, page_url: str) -> list[dict[str, str]]:
    """
    Parse HTML and return a list of image records with:
        img_url, alt_text, context_text, page_url
    """
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []

    for img_tag in soup.find_all("img"):
        src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
        if not src:
            continue

        img_url = urllib.parse.urljoin(page_url, src)
        alt_text = img_tag.get("alt", "").strip()

        # Gather surrounding text (parent element text, trimmed)
        parent = img_tag.parent
        context_text = ""
        if parent:
            context_text = parent.get_text(separator=" ", strip=True)[:300]

        records.append(
            {
                "img_url": img_url,
                "alt_text": alt_text,
                "context_text": context_text,
                "page_url": page_url,
            }
        )

    return records


def url_to_filename(url: str) -> str:
    """Derive a safe local filename from a URL."""
    parsed = urllib.parse.urlparse(url)
    path_part = parsed.path.rstrip("/")
    basename = path_part.split("/")[-1] if path_part else "image"
    # Append a short hash to handle collisions
    short_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    # Sanitise
    basename = re.sub(r"[^\w.\-]", "_", basename)
    return f"{short_hash}_{basename}" if basename else f"{short_hash}.jpg"


def download_image(
    record: dict[str, str],
    outdir: Path,
    session: requests.Session,
    delay: float,
) -> Optional[str]:
    """
    Download a single image. Returns the local filename on success, else None.
    Skips if content-type is not an image or file is too small.
    """
    time.sleep(delay)
    url = record["img_url"]

    # Skip data URIs
    if url.startswith("data:"):
        return None

    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS, stream=True)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.debug("Image download failed %s: %s", url, exc)
        return None

    content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        return None

    data = resp.content
    if len(data) < MIN_IMAGE_BYTES:
        return None

    filename = url_to_filename(url)
    outpath = outdir / filename
    outpath.write_bytes(data)
    return filename


def write_manifest(records: list[dict[str, str]], outdir: Path) -> None:
    """Write (or append to) manifest.csv in outdir."""
    manifest_path = outdir / "manifest.csv"
    fieldnames = ["filename", "img_url", "alt_text", "context_text", "page_url"]
    mode = "w"
    write_header = True

    if manifest_path.exists():
        mode = "a"
        write_header = False

    with manifest_path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for rec in records:
            writer.writerow(rec)

    logger.info("Manifest written to %s (%d records)", manifest_path, len(records))


# ---------------------------------------------------------------------------
# Per-operator pipeline
# ---------------------------------------------------------------------------

def process_operator(
    operator: dict[str, str],
    outdir: Path,
    robots: RobotsCache,
    session: requests.Session,
    delay: float,
) -> None:
    name = operator["operator_name"]
    op_outdir = outdir / name
    op_outdir.mkdir(parents=True, exist_ok=True)

    pages = resolve_pages(operator)
    all_records: list[dict[str, str]] = []

    for page_url in pages:
        if not robots.is_allowed(page_url, HEADERS["User-Agent"]):
            logger.info("robots.txt disallows: %s", page_url)
            continue

        logger.info("[%s] Fetching page: %s", name, page_url)
        html = fetch_html(page_url, session, delay)
        if html is None:
            continue

        image_records = extract_images(html, page_url)
        logger.info("[%s] Found %d image tags on %s", name, len(image_records), page_url)

        for rec in image_records:
            if not robots.is_allowed(rec["img_url"], HEADERS["User-Agent"]):
                logger.debug("robots.txt disallows image: %s", rec["img_url"])
                continue

            filename = download_image(rec, op_outdir, session, delay)
            if filename:
                rec["filename"] = filename
                all_records.append(rec)

    if all_records:
        write_manifest(all_records, op_outdir)
    else:
        logger.warning("[%s] No images collected.", name)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def load_operators(config_path: Path) -> list[dict[str, str]]:
    with config_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect corporate imagery from operator websites (WP2)."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("scripts/wp1/config_template.csv"),
        help="Path to operators config CSV (WP1 format).",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("data/raw/visual/corporate"),
        help="Root output directory for downloaded images.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help="Seconds to wait between HTTP requests (default: 2.0).",
    )
    args = parser.parse_args()

    if not args.config.exists():
        parser.error(f"Config file not found: {args.config}")

    operators = load_operators(args.config)
    logger.info("Loaded %d operators from %s", len(operators), args.config)

    args.outdir.mkdir(parents=True, exist_ok=True)
    robots = RobotsCache()

    with requests.Session() as session:
        for operator in operators:
            process_operator(operator, args.outdir, robots, session, args.delay)

    logger.info("Done. Images saved to %s", args.outdir)


if __name__ == "__main__":
    main()
