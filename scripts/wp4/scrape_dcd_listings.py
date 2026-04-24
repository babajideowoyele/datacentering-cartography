"""
Scrape Data Center Dynamics news listing pages to build a contestation corpus.

Pipeline step 1: listing pages only (article pages return 403).
Extracts headline, date, URL, tags from each listing page.
Filters for contestation-relevant headlines.
Outputs two CSVs:
  data/processed/wp4_dcd/dcd_all.csv         -- full archive
  data/processed/wp4_dcd/dcd_contestation.csv -- filtered events

Checkpoint: saves progress page-by-page so it can resume after interruption.

Usage:
    pip install requests beautifulsoup4 pandas
    python scripts/wp4/scrape_dcd_listings.py [--max-pages N] [--resume]

Robots.txt: Allow: / for all agents. Research use, not AI training.
Rate: 2s between requests (polite crawl).
"""

import argparse
import csv
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL   = "https://www.datacenterdynamics.com"
NEWS_URL   = f"{BASE_URL}/en/news/"
OUT_DIR    = Path("data/processed/wp4_dcd")
CHECKPOINT = OUT_DIR / "checkpoint.csv"
ALL_CSV    = OUT_DIR / "dcd_all.csv"
CONTEST_CSV = OUT_DIR / "dcd_contestation.csv"

HEADERS = {
    "User-Agent": (
        "datacentering-cartography-research/1.0 "
        "(academic research; babajide.owoyele@gmail.com; "
        "github.com/babayyy/datacentering-cartography)"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9",
}

DELAY = 2.0  # seconds between requests

# ---------------------------------------------------------------------------
# Contestation keyword filter
# Headline must contain at least one STRONG term, OR two WEAK terms
# ---------------------------------------------------------------------------
STRONG_TERMS = [
    "moratorium", "ban", "halt", "block", "blocked",
    "reject", "rejected", "denied", "denial", "refuses", "refused",
    "opposition", "protest", "campaign against",
    "planning refusal", "planning appeal", "planning dispute",
    "community concern", "residents oppose", "residents fight",
    "noise complaint", "water concern", "water usage",
    "grid concern", "power concern", "energy concern",
    "environmental concern", "environmental impact",
    "court", "lawsuit", "legal challenge", "injunction",
    "withdraw", "withdrawn", "cancelled", "cancel",
]

WEAK_TERMS = [
    "community", "residents", "local", "planning", "council",
    "mayor", "county", "city", "town", "municipality",
    "concern", "worry", "oppose", "fight", "push back",
    "water", "noise", "grid", "power", "energy",
    "approve", "approval", "permit", "permission",
    "zoning", "land use", "environmental",
]

FIELDNAMES = ["page", "date_raw", "date_parsed", "headline", "url", "tags", "contestation"]


def is_contestation(headline: str) -> bool:
    h = headline.lower()
    if any(t in h for t in STRONG_TERMS):
        return True
    weak_hits = sum(1 for t in WEAK_TERMS if t in h)
    return weak_hits >= 2


def parse_date(raw: str) -> str:
    """Try to normalise DCD date strings to ISO format."""
    raw = raw.strip()
    for fmt in ("%d %b %Y", "%B %d, %Y", "%d %B %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return raw  # return as-is if parsing fails


def fetch_page(session: requests.Session, page: int) -> BeautifulSoup | None:
    url = NEWS_URL if page == 1 else f"{NEWS_URL}?page={page}"
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except requests.RequestException as e:
        print(f"  ERROR page {page}: {e}")
        return None


def extract_articles(soup: BeautifulSoup, page: int) -> list[dict]:
    articles = []

    # DCD uses article cards — try multiple selectors
    cards = (
        soup.select("article.article-card") or
        soup.select("div.article-card") or
        soup.select("li.article-card") or
        soup.select("[class*='article-card']") or
        soup.select("article") or
        soup.select(".news-listing__item")
    )

    for card in cards:
        # Headline — DCD uses h1.card__title inside article cards
        h_tag = card.select_one("h1.card__title, h2.card__title, .card__title, h2, h3, h4")
        headline = h_tag.get_text(strip=True) if h_tag else ""
        if not headline:
            continue

        # URL — use the .headline-link anchor, fall back to first a[href]
        a_tag = card.select_one("a.headline-link, a.block-link, a[href*='/en/news/']")
        if not a_tag:
            a_tag = card.select_one("a[href]")
        href = a_tag["href"] if a_tag else ""
        if not href or "/en/news/" not in href:
            continue  # skip promo/event cards
        url = BASE_URL + href if href.startswith("/") else href

        # Date — DCD puts date in card__overlay > time
        date_tag = card.select_one("time")
        if date_tag:
            date_raw = date_tag.get("datetime") or date_tag.get_text(strip=True)
        else:
            date_raw = ""
        date_parsed = parse_date(date_raw) if date_raw else ""

        # Intro text (card__intro) — extra signal for contestation filter
        intro_tag = card.select_one(".card__intro, .card__body p")
        intro = intro_tag.get_text(strip=True) if intro_tag else ""

        # Tags / categories
        tag_els = card.select(".tag, .category, [class*='tag'], [class*='category']")
        tags = "; ".join(t.get_text(strip=True) for t in tag_els if t.get_text(strip=True))

        articles.append({
            "page":         page,
            "date_raw":     date_raw,
            "date_parsed":  date_parsed,
            "headline":     headline,
            "url":          url,
            "tags":         tags,
            "contestation": is_contestation(f"{headline} {intro}"),
        })

    return articles


def get_max_pages(soup: BeautifulSoup) -> int:
    """Extract total page count from pagination."""
    # Look for "Page X of Y" or last page link
    text = soup.get_text()
    m = re.search(r"[Pp]age\s+\d+\s+of\s+(\d+)", text)
    if m:
        return int(m.group(1))
    # Fallback: find highest page number in pagination links
    page_links = soup.select("a[href*='page=']")
    nums = []
    for a in page_links:
        m2 = re.search(r"page=(\d+)", a["href"])
        if m2:
            nums.append(int(m2.group(1)))
    return max(nums) if nums else 1723  # known total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Stop after N pages (default: all)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint (skip already-scraped pages)")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load checkpoint
    done_pages: set[int] = set()
    if args.resume and CHECKPOINT.exists():
        existing = pd.read_csv(CHECKPOINT)
        done_pages = set(existing["page"].tolist())
        print(f"Resuming — {len(done_pages)} pages already done")

    session = requests.Session()

    # Get page 1 to determine total
    print("Fetching page 1...")
    soup1 = fetch_page(session, 1)
    if soup1 is None:
        print("Failed to fetch page 1. Exiting.")
        return

    total_pages = get_max_pages(soup1)
    max_pages = min(args.max_pages or total_pages, total_pages)
    print(f"Total pages: {total_pages} | Scraping up to: {max_pages}")

    # Open output files
    mode = "a" if args.resume else "w"
    all_f = open(ALL_CSV, mode, newline="", encoding="utf-8")
    all_writer = csv.DictWriter(all_f, fieldnames=FIELDNAMES)
    if not args.resume:
        all_writer.writeheader()

    contest_f = open(CONTEST_CSV, mode, newline="", encoding="utf-8")
    contest_writer = csv.DictWriter(contest_f, fieldnames=FIELDNAMES)
    if not args.resume:
        contest_writer.writeheader()

    chk_f = open(CHECKPOINT, mode, newline="", encoding="utf-8")
    chk_writer = csv.DictWriter(chk_f, fieldnames=FIELDNAMES)
    if not args.resume:
        chk_writer.writeheader()

    total_articles = 0
    total_contestation = 0

    for page in range(1, max_pages + 1):
        if page in done_pages:
            continue

        if page == 1:
            soup = soup1
        else:
            time.sleep(DELAY)
            soup = fetch_page(session, page)
            if soup is None:
                print(f"  Skipping page {page}")
                continue

        articles = extract_articles(soup, page)

        if not articles:
            print(f"  Page {page}: no articles parsed (selector may need updating)")
        else:
            for row in articles:
                all_writer.writerow(row)
                chk_writer.writerow(row)
                if row["contestation"]:
                    contest_writer.writerow(row)

            n_contest = sum(1 for a in articles if a["contestation"])
            total_articles += len(articles)
            total_contestation += n_contest
            print(
                f"  Page {page:4d}/{max_pages} | "
                f"{len(articles):2d} articles | "
                f"{n_contest:2d} contestation | "
                f"running total: {total_articles} / {total_contestation}"
            )

        # Flush periodically
        if page % 10 == 0:
            all_f.flush()
            contest_f.flush()
            chk_f.flush()

    all_f.close()
    contest_f.close()
    chk_f.close()

    print(f"\nDone.")
    print(f"  All articles : {ALL_CSV}  ({total_articles} rows)")
    print(f"  Contestation : {CONTEST_CSV}  ({total_contestation} rows)")
    print(f"\nNext step: run scripts/wp4/screenshot_articles.py to capture")
    print(f"individual article pages for OCR.")


if __name__ == "__main__":
    main()
