"""
EDA of DCD contestation corpus.

Reads data/processed/wp4_dcd/dcd_all.csv and dcd_contestation.csv.
Generates figures for the Monday 27 April 2026 slide deck:

  figures/dcd_eda_timeline.pdf        -- annual event volume (all + contestation)
  figures/dcd_eda_geography.pdf       -- top cities by contestation event count
  figures/dcd_eda_event_types.pdf     -- event type breakdown (from headline NLP)
  figures/dcd_eda_contestation_map.pdf -- world map with event hotspots (optional)

Run from repo root after scrape_dcd_listings.py:
    python scripts/wp4/eda_dcd_corpus.py
"""

import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ALL_CSV      = Path("data/processed/wp4_dcd/dcd_all.csv")
CONTEST_CSV  = Path("data/processed/wp4_dcd/dcd_contestation.csv")
FIG_DIR      = Path("manuscript/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Colour palette — matches paper/slides (B&W safe)
# ---------------------------------------------------------------------------
C_DARK  = "#141414"
C_MID   = "#6e6e6e"
C_LIGHT = "#dadada"
C_ACCENT = "#c0504d"
BG      = "#ffffff"

plt.rcParams.update({
    "font.family":     "serif",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": BG,
    "axes.facecolor":   BG,
})

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
if not ALL_CSV.exists():
    raise FileNotFoundError(f"{ALL_CSV} not found — run scrape_dcd_listings.py first")

all_df  = pd.read_csv(ALL_CSV, parse_dates=["date_parsed"])
cont_df = pd.read_csv(CONTEST_CSV, parse_dates=["date_parsed"])

# Deduplicate by URL (same article may appear on multiple listing pages)
all_df  = all_df.drop_duplicates(subset="url")
cont_df = cont_df.drop_duplicates(subset="url")

print(f"Corpus: {len(all_df):,} articles total | {len(cont_df):,} contestation")
print(f"Date range: {all_df['date_parsed'].min().date()} to {all_df['date_parsed'].max().date()}")

# ---------------------------------------------------------------------------
# Helper: extract location from headline
# ---------------------------------------------------------------------------
LOCATION_PATTERNS = {
    # US jurisdictions
    "Loudoun Co. / Ashburn": r"ashburn|loudoun|northern virginia|data center alley",
    "Northern Virginia": r"northern virginia|prince william|fairfax",
    "Amsterdam": r"amsterdam|netherlands",
    "Dublin / Ireland": r"dublin|ireland",
    "London / UK": r"london|united kingdom|\buk\b|england|wales|scotland",
    "Germany": r"germany|frankfurt|berlin|munich|hamburg",
    "France": r"france|paris|lyon",
    "Spain": r"spain|madrid|barcelona",
    "Nordics": r"sweden|norway|denmark|finland|nordic|stockholm|oslo|copenhagen|helsinki",
    "Singapore": r"singapore",
    "Australia": r"australia|sydney|melbourne",
    "Japan": r"japan|tokyo",
    "India": r"india|mumbai|bangalore|hyderabad",
    "Texas": r"\btexas\b|\bdallas\b|\bhouston\b|\baustin\b",
    "Ohio": r"\bohio\b|columbus|cleveland",
    "Virginia (other)": r"\bvirginia\b",
    "Maryland": r"\bmaryland\b",
    "Georgia": r"\bgeorgia\b|\batlanta\b",
    "Illinois / Chicago": r"chicago|illinois",
    "Oregon": r"\boregon\b|\bportland\b",
    "Arizona": r"arizona|phoenix",
    "Nevada": r"\bnevada\b|\blas vegas\b|\breno\b",
    "Iowa": r"\biowa\b|\bdes moines\b",
    "Indiana": r"\bindiana\b",
    "South Africa": r"south africa|johannesburg|cape town",
    "Poland": r"\bpoland\b|\bwarsaw\b",
    "Romania": r"romania|bucharest",
}

EVENT_TYPE_PATTERNS = {
    "Moratorium / ban": r"moratorium|ban\b|halt\b|pause\b|freeze\b",
    "Planning refusal": r"refus|reject|denied|denial|no longer pursue|cancel",
    "Planning approval": r"approv|permit|green.light|allow|go ahead",
    "Community opposition": r"community|residents|oppose|protest|campaign|objection|pushback|push back",
    "Energy / grid": r"grid|power|energy|electricity|megawatt|MW\b|transmission|generation",
    "Water concern": r"water|drought|consump|usage|withdrawal",
    "Noise / environment": r"noise|sound|environment|pollution|impact",
    "Legal / court": r"court|lawsuit|legal|injunction|tribunal|appeal",
    "Tax / financial": r"tax|incentive|subsid|relief|break\b|rebate",
    "Acquisition / investment": r"acqui|invest|fund|capital|credit|financ",
}


def classify_headline(headline: str, patterns: dict) -> list[str]:
    h = headline.lower()
    return [label for label, pat in patterns.items() if re.search(pat, h)]


def top_locations(df: pd.DataFrame, n: int = 15) -> pd.Series:
    counts = Counter()
    for h in df["headline"].dropna():
        for loc, pat in LOCATION_PATTERNS.items():
            if re.search(pat, h, re.IGNORECASE):
                counts[loc] += 1
    return pd.Series(counts).sort_values(ascending=False).head(n)


# ---------------------------------------------------------------------------
# Figure 1 — Timeline: annual volume (all vs contestation)
# ---------------------------------------------------------------------------
def fig_timeline():
    all_yr  = all_df["date_parsed"].dt.year.value_counts().sort_index()
    cont_yr = cont_df["date_parsed"].dt.year.value_counts().sort_index()

    years = sorted(set(all_yr.index) | set(cont_yr.index))
    years = [y for y in years if 2010 <= y <= 2026]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(years, [all_yr.get(y, 0) for y in years],
           color=C_LIGHT, label="All articles", zorder=2)
    ax.bar(years, [cont_yr.get(y, 0) for y in years],
           color=C_DARK, label="Contestation events", zorder=3)

    ax.set_xlabel("Year", fontsize=11)
    ax.set_ylabel("Articles", fontsize=11)
    ax.set_title("DCD news archive: annual volume", fontsize=13, fontweight="bold")
    ax.legend(frameon=False, fontsize=10)
    ax.set_xticks(years)
    ax.set_xticklabels(years, rotation=45, ha="right", fontsize=9)
    ax.grid(axis="y", color="#eeeeee", zorder=1)

    note = f"Source: Data Center Dynamics, scraped April 2026. n={len(all_df):,} articles, {len(cont_df):,} contestation events."
    fig.text(0.98, 0.01, note, ha="right", fontsize=7, color=C_MID)

    fig.tight_layout()
    out = FIG_DIR / "dcd_eda_timeline.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close()
    print(f"Saved {out}")


# ---------------------------------------------------------------------------
# Figure 2 — Geography: top locations in contestation headlines
# ---------------------------------------------------------------------------
def fig_geography():
    locs = top_locations(cont_df, n=12)
    if locs.empty:
        print("No location data — skipping geography figure")
        return

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(locs.index[::-1], locs.values[::-1], color=C_DARK)

    # Highlight key case study cities
    highlights = {"Amsterdam", "Dublin / Ireland", "Loudoun Co. / Ashburn", "Northern Virginia"}
    for bar, label in zip(bars, locs.index[::-1]):
        if label in highlights:
            bar.set_color(C_ACCENT)

    ax.set_xlabel("Contestation events in corpus", fontsize=11)
    ax.set_title("Where is contestation? Top locations in DCD corpus", fontsize=13, fontweight="bold")

    red_patch  = mpatches.Patch(color=C_ACCENT, label="Case study cities")
    gray_patch = mpatches.Patch(color=C_DARK,   label="Other locations")
    ax.legend(handles=[red_patch, gray_patch], frameon=False, fontsize=10)
    ax.grid(axis="x", color="#eeeeee", zorder=0)

    note = f"Source: DCD, April 2026. n={len(cont_df):,} contestation articles; locations extracted from headlines."
    fig.text(0.98, 0.01, note, ha="right", fontsize=7, color=C_MID)

    fig.tight_layout()
    out = FIG_DIR / "dcd_eda_geography.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close()
    print(f"Saved {out}")


# ---------------------------------------------------------------------------
# Figure 3 — Event type breakdown
# ---------------------------------------------------------------------------
def fig_event_types():
    type_counts = Counter()
    for h in cont_df["headline"].dropna():
        types = classify_headline(h, EVENT_TYPE_PATTERNS)
        for t in types:
            type_counts[t] += 1

    if not type_counts:
        print("No event type data — skipping")
        return

    labels = list(type_counts.keys())
    values = list(type_counts.values())
    # Sort descending
    paired = sorted(zip(values, labels), reverse=True)
    values, labels = zip(*paired)

    fig, ax = plt.subplots(figsize=(9, 5))
    colors = [C_ACCENT if "Moratorium" in l or "refusal" in l or "opposition" in l
              else C_DARK for l in labels]
    ax.barh(list(labels)[::-1], list(values)[::-1], color=list(colors)[::-1])

    ax.set_xlabel("Events in corpus", fontsize=11)
    ax.set_title("What triggers contestation? Event types in DCD corpus", fontsize=13, fontweight="bold")
    ax.grid(axis="x", color="#eeeeee", zorder=0)

    note = f"Source: DCD, April 2026. n={len(cont_df):,} articles; types extracted from headlines (may overlap)."
    fig.text(0.98, 0.01, note, ha="right", fontsize=7, color=C_MID)

    fig.tight_layout()
    out = FIG_DIR / "dcd_eda_event_types.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close()
    print(f"Saved {out}")


# ---------------------------------------------------------------------------
# Figure 4 — Contestation share over time (contestation / all articles)
# ---------------------------------------------------------------------------
def fig_contestation_rate():
    all_yr  = all_df["date_parsed"].dt.year.value_counts().sort_index()
    cont_yr = cont_df["date_parsed"].dt.year.value_counts().sort_index()

    years = sorted(set(all_yr.index) | set(cont_yr.index))
    years = [y for y in years if 2010 <= y <= 2026]
    rates = [cont_yr.get(y, 0) / all_yr.get(y, 1) * 100 for y in years]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(years, rates, color=C_DARK, linewidth=2, marker="o", markersize=5)
    ax.fill_between(years, rates, alpha=0.12, color=C_DARK)
    ax.set_ylabel("Contestation articles (%)", fontsize=11)
    ax.set_title("Contestation as share of DCD coverage over time", fontsize=13, fontweight="bold")
    ax.set_xticks(years)
    ax.set_xticklabels(years, rotation=45, ha="right", fontsize=9)
    ax.grid(axis="y", color="#eeeeee")

    note = f"Source: DCD, April 2026. Contestation share = contestation articles / all articles per year."
    fig.text(0.98, 0.01, note, ha="right", fontsize=7, color=C_MID)

    fig.tight_layout()
    out = FIG_DIR / "dcd_eda_contestation_rate.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close()
    print(f"Saved {out}")


# ---------------------------------------------------------------------------
# Print top contestation headlines for speaker notes
# ---------------------------------------------------------------------------
def print_top_headlines():
    print("\n--- Top contestation headlines (most recent) ---")
    sample = cont_df.sort_values("date_parsed", ascending=False).head(20)
    for _, row in sample.iterrows():
        print(f"  {str(row['date_parsed'])[:10]}  {row['headline'][:90]}")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    fig_timeline()
    fig_geography()
    fig_event_types()
    fig_contestation_rate()
    print_top_headlines()
    print(f"\nAll figures saved to {FIG_DIR}/")
    print("Figures ready for slides_monday.tex")
