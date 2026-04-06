"""
WP1 — Divergence Analysis: Operator Websites vs. Wikipedia City Pages
=======================================================================
Research purpose: Compute metrics that operationalise the divergence between
how data center operators describe themselves (corporate self-presentation)
and how host territories describe themselves (Wikipedia city pages).

The divergence is theoretically significant: it reflects governance gaps,
opacity strategies, and uneven power relations in the sociotechnical
production of "the cloud".

Metrics computed:
  1. Keyword presence and density — environmental / location terms per source
  2. Sentiment polarity per source (positive/negative framing)
  3. Data center mention frequency in Wikipedia (territorial acknowledgement)
  4. Vocabulary exclusivity — terms appearing in corporate text but not Wikipedia
  5. Environmental claim index — weighted score of green/sustainability language

Input:
  data/raw/corporate-websites/{operator_name}/{slug}.txt
  data/raw/corporate-websites/{operator_name}/{slug}_meta.json
  data/raw/wikipedia/{city_name}/page.txt
  data/raw/wikipedia/{city_name}/page_meta.json

Output:
  data/processed/wp1_divergence_summary.csv
  data/processed/wp1_keyword_matrix.csv

Usage:
    python -m scripts.wp1.analyse_divergence \
        --corp-dir data/raw/corporate-websites \
        --wiki-dir data/raw/wikipedia \
        --config scripts/wp1/config_template.csv \
        --output-dir data/processed
"""

import argparse
import csv
import json
import logging
import math
import re
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional NLP dependencies — graceful fallback to regex-based processing
# ---------------------------------------------------------------------------
try:
    import nltk  # type: ignore
    from nltk.corpus import stopwords  # type: ignore
    from nltk.sentiment import SentimentIntensityAnalyzer  # type: ignore
    from nltk.tokenize import word_tokenize  # type: ignore

    # Download required NLTK data if missing (quiet, no-op if already present)
    for _resource in ("vader_lexicon", "stopwords", "punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{_resource}")
        except LookupError:
            try:
                nltk.download(_resource, quiet=True)
            except Exception:
                pass

    HAVE_NLTK = True
    _STOPWORDS = set(stopwords.words("english"))
    _SIA = SentimentIntensityAnalyzer()
    log_msg = "NLTK available — using VADER sentiment and tokenisation."
except ImportError:
    HAVE_NLTK = False
    _STOPWORDS: set[str] = set()
    _SIA = None
    log_msg = "NLTK not installed — using regex tokenisation and rule-based sentiment fallback."

try:
    import spacy  # type: ignore
    _NLP = spacy.load("en_core_web_sm")
    HAVE_SPACY = True
except (ImportError, OSError):
    HAVE_SPACY = False
    _NLP = None

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
log.info(log_msg)
if HAVE_SPACY:
    log.info("spaCy available (en_core_web_sm).")
else:
    log.info("spaCy not installed — entity extraction disabled.")

# ---------------------------------------------------------------------------
# Keyword sets (research-driven)
# ---------------------------------------------------------------------------

# Category → list of terms (all lowercase, matched as whole words)
KEYWORD_CATEGORIES: dict[str, list[str]] = {
    "energy": [
        "energy", "power", "electricity", "renewable", "solar", "wind",
        "ppa", "grid", "megawatt", "mw", "gigawatt", "gw",
    ],
    "water": [
        "water", "cooling", "evaporation", "consumption", "litre", "liter",
        "gallon", "wue", "water usage effectiveness",
    ],
    "carbon": [
        "carbon", "co2", "emissions", "greenhouse", "ghg", "net zero",
        "carbon neutral", "decarbonisation", "decarbonization", "offset",
    ],
    "location": [
        "location", "region", "campus", "facility", "site", "zone",
        "district", "municipality", "local", "community", "neighbourhood",
        "neighborhood", "planning", "permit", "zoning",
    ],
    "sustainability": [
        "sustainability", "sustainable", "green", "esg", "responsible",
        "environment", "environmental", "circular", "resilience",
    ],
    "financial": [
        "investment", "reit", "revenue", "profit", "market", "valuation",
        "acquisition", "equity", "fund", "investor",
    ],
    "community": [
        "community", "resident", "protest", "opposition", "local authority",
        "council", "planning objection", "impact", "noise", "landscape",
    ],
}

# Positive / negative framing terms for rule-based sentiment
POSITIVE_TERMS = {
    "sustainable", "green", "clean", "efficient", "responsible",
    "commitment", "progress", "innovation", "leading", "partnership",
    "transparent", "accountability", "benefit", "positive", "improve",
}
NEGATIVE_TERMS = {
    "impact", "pollution", "concern", "opposition", "protest", "risk",
    "threat", "controversy", "objection", "problem", "harm", "damage",
    "criticism", "complaints", "congestion",
}


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def tokenise(text: str) -> list[str]:
    """Return lowercase word tokens, stripping punctuation."""
    if HAVE_NLTK:
        try:
            tokens = word_tokenize(text.lower())
            return [t for t in tokens if re.match(r"[a-z]", t)]
        except Exception:
            pass
    # Fallback: simple regex tokenisation
    return re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower())


def keyword_counts(tokens: list[str], categories: dict[str, list[str]]) -> dict[str, int]:
    """
    Count occurrences of each keyword category in a token list.

    Multi-word terms (e.g. "net zero") are checked against the original text
    separately below; single-word terms are matched against the token list.
    """
    token_set = Counter(tokens)
    counts: dict[str, int] = {}
    for cat, terms in categories.items():
        total = 0
        for term in terms:
            if " " in term:
                # handled separately via full-text regex
                continue
            total += token_set.get(term, 0)
        counts[cat] = total
    return counts


def multiword_counts(text: str, categories: dict[str, list[str]]) -> dict[str, int]:
    """Count multi-word phrase occurrences (case-insensitive) per category."""
    counts: dict[str, int] = {}
    lowered = text.lower()
    for cat, terms in categories.items():
        total = 0
        for term in terms:
            if " " in term:
                total += len(re.findall(re.escape(term), lowered))
        counts[cat] = total
    return counts


def sentiment_score(text: str) -> dict[str, float]:
    """
    Return sentiment scores for a text block.

    Uses NLTK VADER if available, otherwise a simple term-ratio heuristic.
    Score keys: compound (−1 to +1), positive, negative, neutral.
    """
    if HAVE_NLTK and _SIA is not None:
        # VADER works best on shorter chunks; average over paragraphs
        paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]
        if not paras:
            paras = [text[:2000]]
        scores = [_SIA.polarity_scores(p) for p in paras[:50]]  # cap at 50 paras
        avg = {
            k: sum(s[k] for s in scores) / len(scores)
            for k in ("compound", "pos", "neg", "neu")
        }
        return {
            "compound": round(avg["compound"], 4),
            "positive": round(avg["pos"], 4),
            "negative": round(avg["neg"], 4),
            "neutral": round(avg["neu"], 4),
            "method": "vader",
        }

    # Rule-based fallback
    tokens = tokenise(text)
    if not tokens:
        return {"compound": 0.0, "positive": 0.0, "negative": 0.0, "neutral": 1.0, "method": "rule-based"}
    pos_count = sum(1 for t in tokens if t in POSITIVE_TERMS)
    neg_count = sum(1 for t in tokens if t in NEGATIVE_TERMS)
    total = pos_count + neg_count or 1
    compound = (pos_count - neg_count) / math.sqrt(len(tokens))
    return {
        "compound": round(max(-1.0, min(1.0, compound)), 4),
        "positive": round(pos_count / total, 4),
        "negative": round(neg_count / total, 4),
        "neutral": round(1.0 - (pos_count + neg_count) / max(len(tokens), 1), 4),
        "method": "rule-based",
    }


def ttr(tokens: list[str]) -> float:
    """Type-token ratio — a basic lexical diversity measure."""
    if not tokens:
        return 0.0
    content_tokens = [t for t in tokens if t not in _STOPWORDS and len(t) > 2]
    if not content_tokens:
        return 0.0
    return round(len(set(content_tokens)) / len(content_tokens), 4)


def environmental_claim_index(kw_counts: dict[str, int], total_tokens: int) -> float:
    """
    Weighted composite score: how prominently does a source foreground
    environmental claims? Higher weight to carbon/energy/sustainability.

    Returns density per 1,000 tokens.
    """
    if total_tokens == 0:
        return 0.0
    weighted = (
        kw_counts.get("carbon", 0) * 2.0
        + kw_counts.get("energy", 0) * 1.5
        + kw_counts.get("sustainability", 0) * 2.0
        + kw_counts.get("water", 0) * 1.0
    )
    return round(weighted / total_tokens * 1000, 4)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_corporate_texts(corp_dir: Path, operator_name: str) -> dict[str, str]:
    """
    Load all .txt files for an operator (sustainability, data_centers, about).
    Returns {slug: text_content}.
    """
    op_dir = corp_dir / operator_name
    texts: dict[str, str] = {}
    if not op_dir.is_dir():
        log.warning("Corporate website dir not found: %s", op_dir)
        return texts
    for txt_file in op_dir.glob("*.txt"):
        slug = txt_file.stem
        texts[slug] = txt_file.read_text(encoding="utf-8", errors="replace")
    return texts


def load_wikipedia_text(wiki_dir: Path, city_name: str) -> str | None:
    """Load the full Wikipedia page text for a city."""
    city_slug = city_name.strip().lower().replace(" ", "_")
    page_path = wiki_dir / city_slug / "page.txt"
    if not page_path.exists():
        log.warning("Wikipedia page not found: %s", page_path)
        return None
    return page_path.read_text(encoding="utf-8", errors="replace")


def load_meta_json(path: Path) -> dict:
    """Load a JSON metadata file, returning empty dict on failure."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Could not parse JSON %s: %s", path, exc)
        return {}


# ---------------------------------------------------------------------------
# Per-operator/city analysis
# ---------------------------------------------------------------------------

def analyse_text(text: str, source_label: str) -> dict:
    """Compute all metrics for a single text block."""
    tokens = tokenise(text)
    kw = keyword_counts(tokens, KEYWORD_CATEGORIES)
    mw = multiword_counts(text, KEYWORD_CATEGORIES)
    # Merge multi-word into single-word counts
    for cat in kw:
        kw[cat] += mw.get(cat, 0)

    sent = sentiment_score(text)
    eci = environmental_claim_index(kw, len(tokens))
    dc_count = len(re.findall(r"\bdata\s+cent(?:er|re)s?\b", text, re.IGNORECASE))

    return {
        "source": source_label,
        "total_tokens": len(tokens),
        "type_token_ratio": ttr(tokens),
        "datacenter_mentions": dc_count,
        "sentiment_compound": sent["compound"],
        "sentiment_positive": sent["positive"],
        "sentiment_negative": sent["negative"],
        "sentiment_method": sent["method"],
        "environmental_claim_index": eci,
        **{f"kw_{cat}": count for cat, count in kw.items()},
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="WP1: Analyse divergence between operator websites and Wikipedia city pages."
    )
    parser.add_argument("--corp-dir", default="data/raw/corporate-websites")
    parser.add_argument("--wiki-dir", default="data/raw/wikipedia")
    parser.add_argument("--config", default="scripts/wp1/config_template.csv")
    parser.add_argument("--output-dir", default="data/processed")
    args = parser.parse_args()

    corp_dir = Path(args.corp_dir)
    wiki_dir = Path(args.wiki_dir)
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not config_path.exists():
        log.error("Config CSV not found: %s", config_path)
        raise SystemExit(1)

    with config_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    log.info("Loaded %d rows from %s", len(rows), config_path)

    # -----------------------------------------------------------------------
    # Collect per-row analysis records
    # -----------------------------------------------------------------------
    records: list[dict] = []
    keyword_matrix_rows: list[dict] = []

    for row in rows:
        operator_name = row.get("operator_name", "").strip().replace(" ", "_").lower()
        city_name = row.get("city_name", "").strip()
        country = row.get("country", "").strip()

        log.info("--- Analysing: %s / %s ---", operator_name, city_name)

        # Load corporate texts (concatenate all page slugs)
        corp_texts = load_corporate_texts(corp_dir, operator_name)
        if not corp_texts:
            log.warning("No corporate text found for %s — skipping corporate analysis.", operator_name)
            corp_combined = ""
        else:
            corp_combined = "\n\n".join(corp_texts.values())

        # Load Wikipedia text
        wiki_text = load_wikipedia_text(wiki_dir, city_name)
        if wiki_text is None:
            log.warning("No Wikipedia text found for %s — skipping Wikipedia analysis.", city_name)
            wiki_text = ""

        # Analyse both sources
        corp_metrics = analyse_text(corp_combined, f"corporate:{operator_name}") if corp_combined else {}
        wiki_metrics = analyse_text(wiki_text, f"wikipedia:{city_name}") if wiki_text else {}

        # -----------------------------------------------------------------------
        # Divergence metrics
        # -----------------------------------------------------------------------
        # Environmental claim index divergence: corporate − wikipedia
        corp_eci = corp_metrics.get("environmental_claim_index", None)
        wiki_eci = wiki_metrics.get("environmental_claim_index", None)
        eci_divergence = (
            round(corp_eci - wiki_eci, 4)
            if corp_eci is not None and wiki_eci is not None
            else None
        )

        # Sentiment divergence: corporate − wikipedia (positive framing gap)
        corp_sent = corp_metrics.get("sentiment_compound", None)
        wiki_sent = wiki_metrics.get("sentiment_compound", None)
        sentiment_divergence = (
            round(corp_sent - wiki_sent, 4)
            if corp_sent is not None and wiki_sent is not None
            else None
        )

        # DC mention asymmetry: is the operator silent about location in corp
        # text vs. how prominently the city notes data centers?
        corp_dc = corp_metrics.get("datacenter_mentions", 0)
        wiki_dc = wiki_metrics.get("datacenter_mentions", 0)
        dc_mention_gap = wiki_dc - corp_dc  # positive = city more forthcoming

        # Build divergence summary record
        summary = {
            "operator_name": operator_name,
            "city_name": city_name,
            "country": country,
            # Corporate
            "corp_total_tokens": corp_metrics.get("total_tokens", 0),
            "corp_ttr": corp_metrics.get("type_token_ratio", None),
            "corp_datacenter_mentions": corp_dc,
            "corp_sentiment_compound": corp_sent,
            "corp_sentiment_positive": corp_metrics.get("sentiment_positive", None),
            "corp_sentiment_negative": corp_metrics.get("sentiment_negative", None),
            "corp_eci": corp_eci,
            # Wikipedia
            "wiki_total_tokens": wiki_metrics.get("total_tokens", 0),
            "wiki_ttr": wiki_metrics.get("type_token_ratio", None),
            "wiki_datacenter_mentions": wiki_dc,
            "wiki_sentiment_compound": wiki_sent,
            "wiki_sentiment_positive": wiki_metrics.get("sentiment_positive", None),
            "wiki_sentiment_negative": wiki_metrics.get("sentiment_negative", None),
            "wiki_eci": wiki_eci,
            # Divergence
            "eci_divergence_corp_minus_wiki": eci_divergence,
            "sentiment_divergence_corp_minus_wiki": sentiment_divergence,
            "dc_mention_gap_wiki_minus_corp": dc_mention_gap,
        }
        records.append(summary)

        # Keyword matrix (flat, for heatmap / comparison plot)
        for cat in KEYWORD_CATEGORIES:
            keyword_matrix_rows.append(
                {
                    "operator_name": operator_name,
                    "city_name": city_name,
                    "country": country,
                    "keyword_category": cat,
                    "corp_count": corp_metrics.get(f"kw_{cat}", 0),
                    "wiki_count": wiki_metrics.get(f"kw_{cat}", 0),
                    "corp_density_per_1k": (
                        round(
                            corp_metrics.get(f"kw_{cat}", 0)
                            / max(corp_metrics.get("total_tokens", 1), 1)
                            * 1000,
                            4,
                        )
                        if corp_metrics
                        else 0
                    ),
                    "wiki_density_per_1k": (
                        round(
                            wiki_metrics.get(f"kw_{cat}", 0)
                            / max(wiki_metrics.get("total_tokens", 1), 1)
                            * 1000,
                            4,
                        )
                        if wiki_metrics
                        else 0
                    ),
                }
            )

    # -----------------------------------------------------------------------
    # Write CSV outputs
    # -----------------------------------------------------------------------
    def write_csv(rows: list[dict], path: Path):
        if not rows:
            log.warning("No rows to write for %s", path)
            return
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        log.info("Wrote %d rows to %s", len(rows), path)

    write_csv(records, output_dir / "wp1_divergence_summary.csv")
    write_csv(keyword_matrix_rows, output_dir / "wp1_keyword_matrix.csv")

    log.info("Analysis complete.")


if __name__ == "__main__":
    main()
