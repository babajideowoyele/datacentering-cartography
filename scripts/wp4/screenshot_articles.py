"""
Pipeline step 2: screenshot contestation article pages using Playwright,
then OCR with pytesseract or easyocr.

Reads dcd_contestation.csv (from scrape_dcd_listings.py).
For each article URL:
  1. Opens in headless Chromium (full page screenshot)
  2. OCR extracts text
  3. Saves text + screenshot to data/processed/wp4_dcd/articles/

Then step 3 (city extraction) reads the OCR text and feeds into city2graph.

Requirements:
    pip install playwright pytesseract Pillow easyocr
    playwright install chromium

Usage:
    python scripts/wp4/screenshot_articles.py [--limit N] [--ocr-engine tesseract|easyocr]
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from PIL import Image

CONTEST_CSV  = Path("data/processed/wp4_dcd/dcd_contestation.csv")
ARTICLES_DIR = Path("data/processed/wp4_dcd/articles")
CITIES_OUT   = Path("data/processed/wp4_dcd/cities_extracted.jsonl")

DELAY = 3.0  # seconds between page loads


def slug(url: str) -> str:
    """Turn a URL into a safe filename."""
    return url.rstrip("/").split("/")[-1][:80]


def screenshot_and_ocr(urls: list[str], ocr_engine: str, limit: int | None):
    from playwright.sync_api import sync_playwright

    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        processed = 0
        for url in urls:
            if limit and processed >= limit:
                break

            s = slug(url)
            txt_path = ARTICLES_DIR / f"{s}.txt"
            img_path = ARTICLES_DIR / f"{s}.png"

            if txt_path.exists():
                print(f"  Skip (cached): {s}")
                processed += 1
                continue

            print(f"  Loading: {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(1.5)  # let lazy content settle

                # Full-page screenshot
                page.screenshot(path=str(img_path), full_page=True)

                # OCR
                text = ocr_image(img_path, ocr_engine)
                txt_path.write_text(text, encoding="utf-8")

                print(f"    -> {len(text)} chars extracted")
                processed += 1
                time.sleep(DELAY)

            except Exception as e:
                print(f"    ERROR: {e}")
                continue

        browser.close()

    print(f"\nProcessed {processed} articles -> {ARTICLES_DIR}")


def ocr_image(img_path: Path, engine: str) -> str:
    if engine == "easyocr":
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False)
        results = reader.readtext(str(img_path), detail=0)
        return "\n".join(results)
    else:
        # pytesseract (default)
        import pytesseract
        img = Image.open(img_path)
        return pytesseract.image_to_string(img)


def extract_cities_from_text(text: str, headline: str, url: str, date: str) -> list[dict]:
    """
    Simple heuristic city/location extractor.
    Returns list of {city, country, context, url, date, headline}.
    A more robust version should use spaCy NER.
    """
    import re

    # Known data center markets — expand as needed
    LOCATIONS = {
        # Cities
        "Amsterdam": "Netherlands", "Dublin": "Ireland", "London": "UK",
        "Frankfurt": "Germany", "Paris": "France", "Madrid": "Spain",
        "Stockholm": "Sweden", "Copenhagen": "Denmark", "Helsinki": "Finland",
        "Singapore": "Singapore", "Sydney": "Australia", "Tokyo": "Japan",
        "Hong Kong": "China", "Mumbai": "India", "Johannesburg": "South Africa",
        "Ashburn": "US", "Northern Virginia": "US", "Loudoun County": "US",
        "Dallas": "US", "Chicago": "US", "Phoenix": "US", "Atlanta": "US",
        "Seattle": "US", "San Jose": "US", "New York": "US", "Los Angeles": "US",
        "Portland": "US", "Denver": "US", "Columbus": "US",
        "Toronto": "Canada", "Montreal": "Canada",
        "São Paulo": "Brazil", "Mexico City": "Mexico",
        "Warsaw": "Poland", "Bucharest": "Romania",
        # Regions
        "Virginia": "US", "Texas": "US", "Oregon": "US", "Nevada": "US",
        "Iowa": "US", "Ohio": "US", "Georgia": "US", "Indiana": "US",
        "Netherlands": "Netherlands", "Ireland": "Ireland",
        "Nordics": "Nordic", "Scandinavia": "Nordic",
    }

    hits = []
    combined = f"{headline} {text[:2000]}"  # headline + first 2000 chars of article

    for location, country in LOCATIONS.items():
        if location.lower() in combined.lower():
            # Extract a sentence of context
            pattern = rf".{{0,100}}{re.escape(location)}.{{0,100}}"
            m = re.search(pattern, combined, re.IGNORECASE)
            context = m.group(0).strip() if m else ""
            hits.append({
                "city":     location,
                "country":  country,
                "context":  context,
                "url":      url,
                "date":     date,
                "headline": headline,
            })

    return hits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",      type=int, default=None,
                        help="Max articles to screenshot (default: all)")
    parser.add_argument("--ocr-engine", choices=["tesseract", "easyocr"],
                        default="tesseract")
    parser.add_argument("--skip-screenshot", action="store_true",
                        help="Skip screenshots, only run city extraction on existing .txt files")
    args = parser.parse_args()

    if not CONTEST_CSV.exists():
        print(f"ERROR: {CONTEST_CSV} not found. Run scrape_dcd_listings.py first.")
        return

    df = pd.read_csv(CONTEST_CSV)
    print(f"Loaded {len(df)} contestation articles from {CONTEST_CSV}")

    urls = df["url"].dropna().tolist()

    # Step 1: screenshot + OCR
    if not args.skip_screenshot:
        screenshot_and_ocr(urls, args.ocr_engine, args.limit)

    # Step 2: city extraction from OCR text
    print("\nExtracting cities from OCR text...")
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    all_cities = []

    url_to_meta = {
        row["url"]: {"headline": row["headline"], "date": row.get("date_parsed", "")}
        for _, row in df.iterrows()
    }

    for txt_file in sorted(ARTICLES_DIR.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8", errors="ignore")
        # Find matching URL by slug
        file_slug = txt_file.stem
        matching_url = next(
            (u for u in urls if slug(u) == file_slug), ""
        )
        meta = url_to_meta.get(matching_url, {"headline": file_slug, "date": ""})

        cities = extract_cities_from_text(
            text, meta["headline"], matching_url, meta["date"]
        )
        all_cities.extend(cities)

    # Write cities JSONL
    CITIES_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(CITIES_OUT, "w", encoding="utf-8") as f:
        for c in all_cities:
            f.write(json.dumps(c) + "\n")

    print(f"Extracted {len(all_cities)} city mentions -> {CITIES_OUT}")
    print("\nCity frequency:")
    city_counts = {}
    for c in all_cities:
        city_counts[c["city"]] = city_counts.get(c["city"], 0) + 1
    for city, count in sorted(city_counts.items(), key=lambda x: -x[1])[:20]:
        print(f"  {city:<25} {count:>4} mentions")

    print(f"\nNext step: feed {CITIES_OUT} into scripts/wp3/build_urban_graph.py")
    print("  -> city2graph will pull Overture Maps for each detected city")
