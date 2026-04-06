"""
WP1 — Wikipedia City Page Scraper
===================================
Research purpose: Extract territorial self-descriptions for cities hosting
major data centers. Wikipedia pages serve as the counter-narrative to
operator corporate self-presentation — they reflect community and civic
framings rather than corporate ones.

Sections of particular interest: Infrastructure, Economy, Environment,
Transport. Any mention of "data center" / "data centre" is flagged as a
direct territorial acknowledgement of the infrastructure's presence.

Input:  scripts/wp1/config_template.csv  (or a populated copy)
Output: data/raw/wikipedia/{city_name}/
        - page.txt             full plain text of the Wikipedia article
        - sections.json        parsed section content
        - datacenter_mentions.json  all sentences containing data center refs
        - page_meta.json       title, page_id, url, summary, categories

Usage:
    python -m scripts.wp1.scrape_wikipedia \
        --config scripts/wp1/config_template.csv \
        --output data/raw/wikipedia \
        [--lang en] [--delay 1.0] [--dry-run]
"""

import argparse
import csv
import json
import logging
import re
import time
from pathlib import Path

# wikipedia-api is the preferred library (pip install wikipedia-api)
# Graceful fallback to raw MediaWiki API if unavailable.
try:
    import wikipediaapi  # type: ignore
    HAVE_WIKIPEDIAAPI = True
except ImportError:
    HAVE_WIKIPEDIAAPI = False
    import requests  # standard library fallback via MediaWiki REST API

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
DEFAULT_DELAY = 1.0       # seconds between API calls
WIKI_USER_AGENT = (
    "DatacenteringCartographyBot/1.0 "
    "(research project; +https://github.com/datacentering-cartography)"
)

# Sections of particular interest for the territorial counter-narrative
SECTIONS_OF_INTEREST = [
    "infrastructure",
    "economy",
    "environment",
    "transport",
    "energy",
    "industry",
    "geography",
    "history",
]

# Regex pattern matching data center references (both spellings, plural)
DATACENTER_PATTERN = re.compile(
    r"\bdata\s+cent(?:er|re)s?\b", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Wikipedia API helpers
# ---------------------------------------------------------------------------


def build_wiki(lang: str):
    """Return a wikipediaapi.Wikipedia instance (or None if not installed)."""
    if not HAVE_WIKIPEDIAAPI:
        return None
    return wikipediaapi.Wikipedia(
        language=lang,
        extract_format=wikipediaapi.ExtractFormat.WIKI,
        user_agent=WIKI_USER_AGENT,
    )


def fetch_page_wikipediaapi(wiki, title: str) -> dict | None:
    """
    Fetch a Wikipedia page using the wikipedia-api library.

    Returns a structured dict or None if the page does not exist.
    """
    page = wiki.page(title)
    if not page.exists():
        log.warning("Page does not exist (wikipedia-api): '%s'", title)
        return None

    # Recursively flatten sections to a list of {title, level, text}
    def flatten_sections(sections, level=1):
        result = []
        for s in sections:
            result.append(
                {
                    "title": s.title,
                    "level": level,
                    "text": s.text,
                }
            )
            result.extend(flatten_sections(s.sections, level + 1))
        return result

    flat_sections = flatten_sections(page.sections)

    return {
        "title": page.title,
        "page_id": page.pageid,
        "url": page.fullurl,
        "summary": page.summary,
        "full_text": page.text,
        "sections": flat_sections,
        "categories": list(page.categories.keys()),
    }


def fetch_page_mediawiki_api(title: str, lang: str) -> dict | None:
    """
    Fallback: fetch page content via the MediaWiki REST API (no extra deps).

    Returns a structured dict or None on failure.
    """
    endpoint = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts|info|categories",
        "explaintext": True,
        "exsectionformat": "plain",
        "inprop": "url",
        "cllimit": "50",
        "format": "json",
        "redirects": 1,
    }
    headers = {"User-Agent": WIKI_USER_AGENT}
    try:
        resp = requests.get(endpoint, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        log.error("MediaWiki API request failed for '%s': %s", title, exc)
        return None

    data = resp.json()
    pages = data.get("query", {}).get("pages", {})
    page_data = next(iter(pages.values()))

    if "missing" in page_data:
        log.warning("Page does not exist (MediaWiki API): '%s'", title)
        return None

    full_text = page_data.get("extract", "")
    categories = [
        c["title"].replace("Category:", "")
        for c in page_data.get("categories", [])
    ]

    # Parse sections naively from plain text (== Section == markers)
    sections = _parse_sections_from_plaintext(full_text)

    # Build a summary from the first paragraph
    first_para = full_text.split("\n\n")[0] if full_text else ""

    return {
        "title": page_data.get("title", title),
        "page_id": page_data.get("pageid"),
        "url": page_data.get("fullurl", ""),
        "summary": first_para,
        "full_text": full_text,
        "sections": sections,
        "categories": categories,
    }


def _parse_sections_from_plaintext(text: str) -> list[dict]:
    """
    Parse Wikipedia plain-text extract into sections.

    The MediaWiki API returns plain text where section headers appear as
    lines of the form "== Section ==" or "=== Sub ==="
    """
    lines = text.splitlines()
    sections = []
    current_title = "__preamble__"
    current_level = 0
    current_lines: list[str] = []

    header_re = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$")

    for line in lines:
        m = header_re.match(line)
        if m:
            # Save the previous section
            sections.append(
                {
                    "title": current_title,
                    "level": current_level,
                    "text": "\n".join(current_lines).strip(),
                }
            )
            current_title = m.group(2).strip()
            current_level = len(m.group(1)) - 1  # == = level 1, === = level 2
            current_lines = []
        else:
            current_lines.append(line)

    # Final section
    sections.append(
        {
            "title": current_title,
            "level": current_level,
            "text": "\n".join(current_lines).strip(),
        }
    )
    return sections


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------


def extract_sections_of_interest(sections: list[dict]) -> dict[str, str]:
    """
    Return a filtered dict of {section_title: text} for sections matching
    SECTIONS_OF_INTEREST (case-insensitive prefix match).
    """
    result = {}
    for sec in sections:
        if any(
            sec["title"].lower().startswith(kw)
            for kw in SECTIONS_OF_INTEREST
        ):
            result[sec["title"]] = sec["text"]
    return result


def extract_datacenter_mentions(full_text: str) -> list[dict]:
    """
    Find every sentence (heuristic: split on '. ') that contains a data
    center reference. Returns list of {sentence, char_offset}.
    """
    # Split on sentence boundaries (simple heuristic — good enough for WP1)
    sentence_re = re.compile(r"(?<=[.!?])\s+")
    sentences = sentence_re.split(full_text)
    mentions = []
    offset = 0
    for sent in sentences:
        if DATACENTER_PATTERN.search(sent):
            mentions.append({"sentence": sent.strip(), "char_offset": offset})
        offset += len(sent) + 1  # +1 for the space consumed by split
    return mentions


# ---------------------------------------------------------------------------
# Per-city processing
# ---------------------------------------------------------------------------


def process_city(
    row: dict,
    output_root: Path,
    wiki,           # wikipediaapi instance or None
    lang: str,
    delay: float,
    dry_run: bool,
) -> dict:
    """
    Fetch and save Wikipedia data for one city row.
    """
    city_slug = (
        row.get("city_name", "").strip().lower().replace(" ", "_")
    )
    wiki_title = row.get("wikipedia_page_title", "").strip() or row.get("city_name", "").strip()

    if not city_slug:
        log.warning("Skipping row with empty city_name: %s", row)
        return {"city": city_slug, "status": "skipped"}

    log.info("=== Processing city: %s (Wikipedia: '%s') ===", city_slug, wiki_title)

    if dry_run:
        log.info("[dry-run] Would fetch Wikipedia page: '%s'", wiki_title)
        return {"city": city_slug, "status": "dry-run"}

    # Fetch page data
    page_data = None
    if wiki is not None:
        page_data = fetch_page_wikipediaapi(wiki, wiki_title)
    if page_data is None:
        log.info("Falling back to MediaWiki REST API for '%s'", wiki_title)
        page_data = fetch_page_mediawiki_api(wiki_title, lang)

    time.sleep(delay)

    if page_data is None:
        log.error("Failed to retrieve Wikipedia page for '%s'", wiki_title)
        return {"city": city_slug, "status": "failed"}

    # Compute derived outputs
    sections_of_interest = extract_sections_of_interest(page_data["sections"])
    dc_mentions = extract_datacenter_mentions(page_data["full_text"])

    # Build metadata summary (without the bulk text)
    page_meta = {
        "title": page_data["title"],
        "page_id": page_data["page_id"],
        "url": page_data["url"],
        "summary": page_data["summary"],
        "categories": page_data["categories"],
        "total_chars": len(page_data["full_text"]),
        "section_count": len(page_data["sections"]),
        "sections_of_interest": list(sections_of_interest.keys()),
        "datacenter_mention_count": len(dc_mentions),
        "config_row": {k: v for k, v in row.items()},
    }

    # Write outputs
    city_dir = output_root / city_slug
    city_dir.mkdir(parents=True, exist_ok=True)

    (city_dir / "page.txt").write_text(
        page_data["full_text"], encoding="utf-8"
    )
    (city_dir / "sections.json").write_text(
        json.dumps(page_data["sections"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (city_dir / "sections_of_interest.json").write_text(
        json.dumps(sections_of_interest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (city_dir / "datacenter_mentions.json").write_text(
        json.dumps(dc_mentions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (city_dir / "page_meta.json").write_text(
        json.dumps(page_meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    log.info(
        "[%s] Saved. %d chars, %d data center mentions, %d sections of interest.",
        city_slug,
        len(page_data["full_text"]),
        len(dc_mentions),
        len(sections_of_interest),
    )

    return {
        "city": city_slug,
        "status": "ok",
        "chars": len(page_data["full_text"]),
        "datacenter_mentions": len(dc_mentions),
        "sections_of_interest": len(sections_of_interest),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="WP1: Scrape Wikipedia city pages for Datacentering Cartography."
    )
    parser.add_argument(
        "--config",
        default="scripts/wp1/config_template.csv",
        help="Path to operator/city config CSV.",
    )
    parser.add_argument(
        "--output",
        default="data/raw/wikipedia",
        help="Root output directory (default: data/raw/wikipedia).",
    )
    parser.add_argument(
        "--lang",
        default="en",
        help="Wikipedia language code (default: en).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Seconds between API calls (default: {DEFAULT_DELAY}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be fetched without making any API calls.",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    output_root = Path(args.output)

    if not config_path.exists():
        log.error("Config CSV not found: %s", config_path)
        raise SystemExit(1)

    with config_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    log.info("Loaded %d rows from %s", len(rows), config_path)

    if HAVE_WIKIPEDIAAPI:
        log.info("Using wikipedia-api library.")
        wiki = build_wiki(args.lang)
    else:
        log.info("wikipedia-api not installed; using MediaWiki REST API fallback.")
        wiki = None

    output_root.mkdir(parents=True, exist_ok=True)
    all_summaries = []

    for row in rows:
        result = process_city(
            row=row,
            output_root=output_root,
            wiki=wiki,
            lang=args.lang,
            delay=args.delay,
            dry_run=args.dry_run,
        )
        all_summaries.append(result)

    if not args.dry_run:
        summary_path = output_root / "scrape_summary.json"
        summary_path.write_text(
            json.dumps(all_summaries, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log.info("Scrape summary written to %s", summary_path)

    log.info("Done. Processed %d cities.", len(all_summaries))


if __name__ == "__main__":
    main()
