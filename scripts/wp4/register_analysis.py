"""
Registerial cartography of datacentering discourse.

Following Matthiessen (2015) 'Register in the round: registerial cartography'.
Functional Linguistics 2:9. DOI 10.1186/s40554-015-0015-8

Pipeline:
  1. POS-tag headlines + intros with spaCy
  2. Extract verb lemmas
  3. Classify by Hallidayan process type
     (material, mental, relational, verbal, enabling, behavioral, existential)
  4. Map onto Matthiessen's 8 fields of activity
     (reporting, doing, enabling, recommending, expounding, exploring, sharing, recreating)
  5. Build registerial profile per city/region
  6. Output:
       data/processed/wp4_dcd/register_verbs.csv     -- verb inventory
       data/processed/wp4_dcd/register_profiles.csv  -- per-city profiles
       manuscript/figures/register_process_types.pdf  -- process type bar chart
       manuscript/figures/register_city_profiles.pdf  -- city heatmap
       manuscript/figures/register_temporal.pdf       -- verb register over time

Run from repo root:
    pip install spacy pandas matplotlib seaborn
    python -m spacy download en_core_web_sm
    python scripts/wp4/register_analysis.py
"""

from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import seaborn as sns

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CONTEST_CSV = Path("data/processed/wp4_dcd/dcd_all.csv")
OUT_DIR     = Path("data/processed/wp4_dcd")
FIG_DIR     = Path("manuscript/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Hallidayan process type lexicon (verb lemmas)
# Based on Halliday & Matthiessen (2004) Introduction to Functional Grammar
# ---------------------------------------------------------------------------
PROCESS_TYPES = {

    # Material — doing and happening: physical actions, construction, transactions
    "material": {
        "build", "construct", "break", "ground", "impose", "withdraw", "approve",
        "deny", "reject", "secure", "fund", "invest", "sign", "launch", "open",
        "close", "expand", "install", "deploy", "complete", "develop", "create",
        "establish", "acquire", "purchase", "buy", "sell", "demolish", "remove",
        "halt", "stop", "block", "pause", "freeze", "cancel", "delay", "defer",
        "extend", "upgrade", "power", "cool", "consume", "draw", "generate",
        "connect", "link", "wire", "supply", "deliver", "operate", "run",
        "move", "relocate", "lease", "rent", "own", "hold", "manage",
        "announce", "open", "close", "file", "submit", "apply", "seek",
        "win", "lose", "grant", "refuse", "impose", "lift", "issue",
        "break", "violate", "comply", "meet", "exceed", "reduce", "cut",
        "increase", "raise", "lower", "limit", "cap", "set", "fix",
    },

    # Mental — sensing, thinking, feeling, perceiving
    "mental": {
        "concern", "worry", "fear", "think", "believe", "consider", "feel",
        "oppose", "support", "want", "need", "plan", "expect", "hope",
        "doubt", "question", "challenge", "criticise", "criticize", "object",
        "resist", "protest", "complain", "welcome", "endorse", "back",
        "know", "understand", "realise", "realize", "recognise", "recognize",
        "see", "watch", "notice", "find", "discover", "learn", "argue",
        "agree", "disagree", "prefer", "choose", "decide", "intend",
        "demand", "insist", "urge", "push", "call",
    },

    # Verbal — saying, claiming, communicating
    "verbal": {
        "say", "tell", "report", "state", "claim", "warn", "argue",
        "urge", "demand", "pledge", "confirm", "reveal", "note", "add",
        "describe", "explain", "announce", "declare", "assert", "contend",
        "suggest", "propose", "recommend", "advise", "inform", "notify",
        "respond", "reply", "comment", "cite", "quote", "mention",
        "highlight", "stress", "emphasise", "emphasize", "point",
        "acknowledge", "admit", "deny", "dispute", "reject",
        "express", "voice", "raise", "outline", "detail",
    },

    # Relational — being, becoming, having, attributing
    "relational": {
        "be", "become", "remain", "stay", "seem", "appear", "look",
        "have", "include", "contain", "comprise", "consist", "involve",
        "represent", "constitute", "form", "make",
        "equal", "total", "amount", "reach", "hit", "mark",
        "serve", "act", "function", "work",
        "face", "experience", "suffer", "benefit", "gain",
    },

    # Enabling/regulatory — permitting, regulating, governing (domain-specific)
    "enabling": {
        "permit", "allow", "enable", "authorise", "authorize", "approve",
        "regulate", "require", "mandate", "enforce", "govern", "oversee",
        "legislate", "ban", "prohibit", "restrict", "limit", "cap",
        "license", "certify", "accredit", "designate", "zone", "rezone",
        "plan", "review", "inspect", "audit", "assess", "evaluate",
        "consult", "negotiate", "agree", "commit", "oblige", "force",
        "impose", "lift", "repeal", "amend", "update", "revise",
        "implement", "enforce", "monitor", "track", "report",
    },

    # Behavioral — physiological/social behavior (protest, campaign)
    "behavioral": {
        "protest", "campaign", "demonstrate", "march", "petition",
        "lobby", "organise", "organize", "mobilise", "mobilize",
        "contest", "litigate", "sue", "appeal", "challenge",
        "attend", "participate", "join", "meet", "gather",
    },

    # Existential — existing, occurring
    "existential": {
        "exist", "occur", "happen", "arise", "emerge", "appear",
        "there", "stand", "lie",
    },
}

# Matthiessen's 8 fields of activity → dominant process types
FIELD_MAPPING = {
    "reporting":      ["verbal", "material", "relational"],
    "doing":          ["material", "behavioral"],
    "enabling":       ["enabling", "verbal", "relational"],
    "recommending":   ["verbal", "enabling", "mental"],
    "expounding":     ["relational", "existential", "mental"],
    "exploring":      ["mental", "verbal", "behavioral"],
    "sharing":        ["mental", "relational", "verbal"],
    "recreating":     ["material", "mental", "behavioral"],
}

# DCD-specific location patterns (reuse from eda script)
LOCATION_PATTERNS = {
    "Ashburn / N.Virginia": r"ashburn|loudoun|northern virginia|data center alley|prince william",
    "Amsterdam": r"amsterdam|netherlands",
    "Dublin / Ireland": r"dublin|ireland",
    "UK": r"\buk\b|united kingdom|england|wales|scotland|london",
    "Germany": r"germany|frankfurt|berlin|munich",
    "France": r"france|paris",
    "Nordics": r"sweden|norway|denmark|finland|nordic|stockholm|oslo|copenhagen",
    "Singapore": r"singapore",
    "Texas": r"\btexas\b|\bdallas\b|\bhouston\b|\baustin\b",
    "Ohio": r"\bohio\b|columbus|cleveland|mansfield",
    "Maryland": r"\bmaryland\b|harford",
    "Virginia (other)": r"\bvirginia\b",
    "California": r"california|\bla\b|los angeles|san jose|san francisco",
    "Oregon": r"\boregon\b|\bportland\b",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
C_DARK    = "#141414"
C_MID     = "#6e6e6e"
C_LIGHT   = "#dadada"
C_ACCENT  = "#c0504d"
BG        = "#ffffff"

plt.rcParams.update({
    "font.family":      "serif",
    "axes.spines.top":  False,
    "axes.spines.right": False,
    "figure.facecolor": BG,
    "axes.facecolor":   BG,
})

PROCESS_COLORS = {
    "material":    "#2e4057",
    "verbal":      "#6b8f71",
    "mental":      "#c0504d",
    "relational":  "#8c7b6b",
    "enabling":    "#4a7c9e",
    "behavioral":  "#b08850",
    "existential": "#aaaaaa",
}


def classify_verb(lemma: str) -> str:
    lemma = lemma.lower()
    for ptype, verbs in PROCESS_TYPES.items():
        if lemma in verbs:
            return ptype
    return "other"


def extract_verbs_spacy(texts: list[str]) -> list[dict]:
    import spacy
    nlp = spacy.load("en_core_web_sm")

    records = []
    for text in texts:
        doc = nlp(str(text))
        for token in doc:
            if token.pos_ in ("VERB", "AUX") and not token.is_stop:
                lemma = token.lemma_.lower()
                ptype = classify_verb(lemma)
                records.append({
                    "lemma":        lemma,
                    "process_type": ptype,
                    "pos":          token.pos_,
                    "dep":          token.dep_,
                    "text_snippet": token.sent.text[:80],
                })
    return records


def detect_location(text: str) -> str:
    import re
    t = str(text).lower()
    for loc, pat in LOCATION_PATTERNS.items():
        if re.search(pat, t, re.IGNORECASE):
            return loc
    return "Other / Unknown"


def field_of_activity(profile: dict) -> str:
    """
    Assign dominant field of activity from process type profile.
    Returns the Matthiessen field whose expected process types best match.
    """
    total = sum(profile.values()) or 1
    norm  = {k: v / total for k, v in profile.items()}

    scores = {}
    for field, expected in FIELD_MAPPING.items():
        scores[field] = sum(norm.get(pt, 0) for pt in expected)
    return max(scores, key=scores.get)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not CONTEST_CSV.exists():
        print(f"ERROR: {CONTEST_CSV} not found — run scrape_dcd_listings.py first")
        return

    df = pd.read_csv(CONTEST_CSV, parse_dates=["date_parsed"])
    df = df.drop_duplicates(subset="url")
    print(f"Loaded {len(df):,} articles")

    # Combine headline + intro for analysis
    df["text"] = df["headline"].fillna("") + ". " + df.get("intro", pd.Series([""] * len(df))).fillna("")

    # ---------------------------------------------------------------------------
    # 1. Extract verbs
    # ---------------------------------------------------------------------------
    print("Extracting verbs with spaCy...")
    try:
        all_records = []
        for i, row in df.iterrows():
            records = extract_verbs_spacy([row["text"]])
            for r in records:
                r["url"]      = row.get("url", "")
                r["date"]     = str(row.get("date_parsed", ""))[:10]
                r["location"] = detect_location(row["text"])
                r["contested"]= bool(row.get("contestation", False))
            all_records.extend(records)
    except OSError:
        print("spaCy model not found — install with: python -m spacy download en_core_web_sm")
        return

    verbs_df = pd.DataFrame(all_records)
    verbs_df.to_csv(OUT_DIR / "register_verbs.csv", index=False)
    print(f"Extracted {len(verbs_df):,} verb tokens -> {OUT_DIR}/register_verbs.csv")

    # ---------------------------------------------------------------------------
    # 2. Process type frequency
    # ---------------------------------------------------------------------------
    type_counts = verbs_df[verbs_df["process_type"] != "other"]["process_type"].value_counts()

    fig, ax = plt.subplots(figsize=(9, 5))
    colors  = [PROCESS_COLORS.get(t, C_MID) for t in type_counts.index]
    ax.barh(type_counts.index[::-1], type_counts.values[::-1], color=colors[::-1])
    ax.set_xlabel("Verb tokens", fontsize=11)
    ax.set_title("DCD corpus: Hallidayan process types in verb inventory",
                 fontsize=13, fontweight="bold")
    ax.grid(axis="x", color="#eeeeee", zorder=0)
    note = ("Source: DCD corpus, spaCy POS + Hallidayan process type lexicon. "
            "Following Matthiessen (2015) registerial cartography.")
    fig.text(0.98, 0.01, note, ha="right", fontsize=7, color=C_MID)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "register_process_types.pdf", bbox_inches="tight")
    plt.close()
    print(f"Saved register_process_types.pdf")

    # ---------------------------------------------------------------------------
    # 3. Contested vs non-contested register comparison
    # ---------------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, (label, subset) in zip(axes, [
        ("Non-contestation", verbs_df[~verbs_df["contested"]]),
        ("Contestation events", verbs_df[verbs_df["contested"]]),
    ]):
        tc = subset[subset["process_type"] != "other"]["process_type"].value_counts(normalize=True) * 100
        colors = [PROCESS_COLORS.get(t, C_MID) for t in tc.index]
        ax.barh(tc.index[::-1], tc.values[::-1], color=colors[::-1])
        ax.set_title(label, fontsize=12, fontweight="bold")
        ax.set_xlabel("% of verb tokens", fontsize=10)
        ax.grid(axis="x", color="#eeeeee", zorder=0)

    fig.suptitle("Register contrast: contestation vs non-contestation DCD articles",
                 fontsize=13, fontweight="bold")
    note = "Matthiessen (2015): field of activity realized by process type profile."
    fig.text(0.98, 0.01, note, ha="right", fontsize=7, color=C_MID)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "register_contrast.pdf", bbox_inches="tight")
    plt.close()
    print(f"Saved register_contrast.pdf")

    # ---------------------------------------------------------------------------
    # 4. Per-city registerial profile (heatmap)
    # ---------------------------------------------------------------------------
    ptypes   = [p for p in PROCESS_COLORS if p != "existential"]
    locations = [l for l in LOCATION_PATTERNS if l != "Other / Unknown"]

    profile_rows = []
    for loc in locations:
        sub = verbs_df[verbs_df["location"] == loc]
        total = len(sub[sub["process_type"] != "other"]) or 1
        row   = {pt: sub[sub["process_type"] == pt].shape[0] / total * 100
                 for pt in ptypes}
        row["location"] = loc
        row["field"]    = field_of_activity({pt: row[pt] for pt in ptypes})
        row["n"]        = len(sub)
        profile_rows.append(row)

    profile_df = pd.DataFrame(profile_rows).set_index("location")
    profile_df.to_csv(OUT_DIR / "register_profiles.csv")

    heat_data = profile_df[ptypes].T

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.heatmap(
        heat_data,
        ax=ax,
        cmap="Greys",
        linewidths=0.5,
        linecolor="#eeeeee",
        annot=True,
        fmt=".0f",
        annot_kws={"size": 8},
        cbar_kws={"label": "% of verb tokens"},
    )
    ax.set_title("Registerial profiles by city/region — Hallidayan process types (%)",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("Process type", fontsize=10)

    # Add field of activity as column annotation
    fields = profile_df["field"].reindex(heat_data.columns)
    for i, (col, field) in enumerate(fields.items()):
        ax.text(i + 0.5, -0.6, field, ha="center", va="top",
                fontsize=7, color=C_ACCENT, rotation=30)

    note = "Matthiessen (2015): field of activity = dominant process type profile."
    fig.text(0.98, 0.01, note, ha="right", fontsize=7, color=C_MID)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "register_city_profiles.pdf", bbox_inches="tight")
    plt.close()
    print(f"Saved register_city_profiles.pdf")

    # ---------------------------------------------------------------------------
    # 5. Top verbs by process type (for slides / speaker notes)
    # ---------------------------------------------------------------------------
    print("\n--- Top 10 verbs by process type ---")
    for ptype in ptypes:
        top = (verbs_df[verbs_df["process_type"] == ptype]["lemma"]
               .value_counts().head(10).to_dict())
        print(f"  {ptype:12s}: {', '.join(top.keys())}")

    # ---------------------------------------------------------------------------
    # 6. Temporal verb register shift
    # ---------------------------------------------------------------------------
    if "date" in verbs_df.columns:
        verbs_df["year"] = pd.to_datetime(verbs_df["date"], errors="coerce").dt.year
        yearly = (verbs_df[verbs_df["process_type"].isin(ptypes)]
                  .groupby(["year", "process_type"])
                  .size()
                  .unstack(fill_value=0))
        yearly_pct = yearly.div(yearly.sum(axis=1), axis=0) * 100
        yearly_pct = yearly_pct.dropna()

        if len(yearly_pct) > 1:
            fig, ax = plt.subplots(figsize=(11, 5))
            for pt in ptypes:
                if pt in yearly_pct.columns:
                    ax.plot(yearly_pct.index, yearly_pct[pt],
                            label=pt, color=PROCESS_COLORS[pt], linewidth=1.8,
                            marker="o", markersize=3)
            ax.set_xlabel("Year", fontsize=11)
            ax.set_ylabel("% of verb tokens", fontsize=11)
            ax.set_title("Temporal shift in registerial profile — DCD corpus",
                         fontsize=13, fontweight="bold")
            ax.legend(frameon=False, fontsize=9, ncol=3)
            ax.grid(axis="y", color="#eeeeee")
            note = "Matthiessen (2015): shifts in process type distribution signal register change over time."
            fig.text(0.98, 0.01, note, ha="right", fontsize=7, color=C_MID)
            fig.tight_layout()
            fig.savefig(FIG_DIR / "register_temporal.pdf", bbox_inches="tight")
            plt.close()
            print("Saved register_temporal.pdf")

    print(f"\nAll register figures saved to {FIG_DIR}/")
    print("\nCity registerial profiles:")
    print(profile_df[["field", "n"]].to_string())


# ---------------------------------------------------------------------------
# Actor extraction (spaCy NER + domain actor types)
# ---------------------------------------------------------------------------
ACTOR_TYPES = {
    "hyperscaler":  r"amazon|aws|microsoft|google|meta|oracle|apple",
    "colo":         r"equinix|digital realty|iron mountain|cyrusone|coresite|ntt|vantage",
    "reit":         r"reit|real estate investment trust|brookfield|blackstone|kkr",
    "planning":     r"planning commission|planning board|council|county|municipality|borough|authority",
    "utility":      r"national grid|ercot|miso|pjm|eir?grid|elia|tennet|vattenfall",
    "community":    r"resident|community|neighbour|neighbor|campaign|coalition|group",
    "regulator":    r"fcc|epa|ofgem|ferc|puc|commission|minister|department",
    "court":        r"court|tribunal|judge|ruling|lawsuit|litigation",
}


def extract_actors(texts: list[str]) -> list[dict]:
    """
    Extract named actors using spaCy NER + domain pattern matching.
    Returns records: {text, entity, label, actor_type, source_text}
    """
    import re, spacy
    nlp = spacy.load("en_core_web_sm")
    records = []
    for text in texts:
        doc = nlp(str(text))
        for ent in doc.ents:
            if ent.label_ in ("ORG", "PERSON", "GPE", "LAW"):
                actor_type = "unknown"
                for atype, pat in ACTOR_TYPES.items():
                    if re.search(pat, ent.text, re.IGNORECASE):
                        actor_type = atype
                        break
                records.append({
                    "entity":      ent.text,
                    "ner_label":   ent.label_,
                    "actor_type":  actor_type,
                    "context":     ent.sent.text[:100],
                })
    return records


def run_actors(df: pd.DataFrame):
    print("Extracting actors with spaCy NER...")
    all_actors = []
    for _, row in df.iterrows():
        actors = extract_actors([str(row.get("text", ""))])
        for a in actors:
            a["url"]       = row.get("url", "")
            a["date"]      = str(row.get("date_parsed", ""))[:10]
            a["location"]  = detect_location(str(row.get("text", "")))
            a["contested"] = bool(row.get("contestation", False))
        all_actors.extend(actors)

    actors_df = pd.DataFrame(all_actors)
    actors_df.to_csv(OUT_DIR / "register_actors.csv", index=False)
    print(f"Extracted {len(actors_df):,} actor mentions -> register_actors.csv")

    # Top actors by type
    print("\n--- Top actors by type ---")
    for atype in ACTOR_TYPES:
        top = (actors_df[actors_df["actor_type"] == atype]["entity"]
               .value_counts().head(5).to_dict())
        if top:
            print(f"  {atype:12s}: {', '.join(top.keys())}")

    # Actor co-occurrence network prep
    actor_counts = actors_df.groupby(["entity", "actor_type"])["url"].count().reset_index()
    actor_counts.columns = ["entity", "actor_type", "frequency"]
    actor_counts.to_csv(OUT_DIR / "actor_frequency.csv", index=False)

    # Figure: actor types in contestation vs non-contestation
    fig, ax = plt.subplots(figsize=(9, 5))
    contest_actors  = actors_df[actors_df["contested"]]["actor_type"].value_counts()
    regular_actors  = actors_df[~actors_df["contested"]]["actor_type"].value_counts()

    x = range(len(ACTOR_TYPES))
    labels = list(ACTOR_TYPES.keys())
    w = 0.38
    ax.bar([i - w/2 for i in x],
           [regular_actors.get(l, 0) for l in labels],
           width=w, color=C_MID, label="All articles")
    ax.bar([i + w/2 for i in x],
           [contest_actors.get(l, 0) for l in labels],
           width=w, color=C_DARK, label="Contestation events")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Actor mentions", fontsize=11)
    ax.set_title("Actor types: contestation vs all DCD articles", fontsize=13, fontweight="bold")
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#eeeeee", zorder=0)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "register_actors.pdf", bbox_inches="tight")
    plt.close()
    print("Saved register_actors.pdf")

    return actors_df


# ---------------------------------------------------------------------------
# BERTopic topic modelling (headlines + intros)
# ---------------------------------------------------------------------------
def run_bertopic(df: pd.DataFrame):
    try:
        from bertopic import BERTopic
    except ImportError:
        print("BERTopic not installed — skipping. pip install bertopic")
        return None

    texts = df["text"].dropna().tolist()
    print(f"Running BERTopic on {len(texts):,} documents...")

    topic_model = BERTopic(
        language="english",
        calculate_probabilities=False,
        verbose=True,
        min_topic_size=5,
        nr_topics="auto",
    )
    topics, _ = topic_model.fit_transform(texts)
    df = df.copy()
    df["topic"] = topics

    # Save topic info
    topic_info = topic_model.get_topic_info()
    topic_info.to_csv(OUT_DIR / "bertopic_topics.csv", index=False)
    print(f"Found {len(topic_info)-1} topics -> bertopic_topics.csv")

    # Print top topics
    print("\n--- Top 15 topics ---")
    for _, row in topic_info.head(16).iterrows():
        if row["Topic"] == -1:
            continue
        print(f"  Topic {row['Topic']:3d} (n={row['Count']:4d}): {row['Name']}")

    # Save visualisation
    try:
        fig = topic_model.visualize_topics()
        fig.write_html(str(OUT_DIR / "bertopic_map.html"))
        print("Saved bertopic_map.html")
    except Exception:
        pass

    return topic_model, df


# ---------------------------------------------------------------------------
# Spatial map: city registerial profiles as geoJSON (for cartalog)
# ---------------------------------------------------------------------------
def run_spatial_map(profile_df: pd.DataFrame):
    """
    Output city registerial profiles as GeoJSON with lat/lon for each location.
    Fields: city, dominant_field, process_type_profile, contestation_n.
    """
    import json

    CITY_COORDS = {
        "Ashburn / N.Virginia": (39.0438, -77.4874),
        "Amsterdam":            (52.3676, 4.9041),
        "Dublin / Ireland":     (53.3498, -6.2603),
        "UK":                   (51.5074, -0.1278),
        "Germany":              (52.5200, 13.4050),
        "France":               (48.8566, 2.3522),
        "Nordics":              (59.3293, 18.0686),
        "Singapore":            (1.3521, 103.8198),
        "Texas":                (30.2672, -97.7431),
        "Ohio":                 (39.9612, -82.9988),
        "Maryland":             (39.0458, -76.6413),
        "Virginia (other)":     (37.4316, -78.6569),
        "California":           (37.7749, -122.4194),
        "Oregon":               (45.5231, -122.6765),
    }

    ptypes = [p for p in PROCESS_COLORS if p != "existential"]

    features = []
    for loc, coords in CITY_COORDS.items():
        if loc not in profile_df.index:
            continue
        row = profile_df.loc[loc]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [coords[1], coords[0]]},
            "properties": {
                "city":         loc,
                "dominant_field": str(row.get("field", "unknown")),
                "n_articles":   int(row.get("n", 0)),
                **{pt: round(float(row.get(pt, 0)), 1) for pt in ptypes},
            }
        })

    geojson = {"type": "FeatureCollection", "features": features}
    out = OUT_DIR / "register_spatial.geojson"
    out.write_text(json.dumps(geojson, indent=2))
    print(f"Saved {out} ({len(features)} city features for cartalog map)")


# ---------------------------------------------------------------------------
# Extended main
# ---------------------------------------------------------------------------
def main():
    if not CONTEST_CSV.exists():
        print(f"ERROR: {CONTEST_CSV} not found — run scrape_dcd_listings.py first")
        return

    df = pd.read_csv(CONTEST_CSV, parse_dates=["date_parsed"])
    df = df.drop_duplicates(subset="url")
    print(f"Loaded {len(df):,} articles")

    df["text"] = df["headline"].fillna("") + ". " + df.get("intro", pd.Series([""] * len(df))).fillna("")

    # 1. Verb extraction + register analysis
    print("\n=== REGISTER ANALYSIS ===")
    try:
        all_records = []
        for _, row in df.iterrows():
            records = extract_verbs_spacy([row["text"]])
            for r in records:
                r["url"]       = row.get("url", "")
                r["date"]      = str(row.get("date_parsed", ""))[:10]
                r["location"]  = detect_location(row["text"])
                r["contested"] = bool(row.get("contestation", False))
            all_records.extend(records)
    except OSError:
        print("Install spaCy model: python -m spacy download en_core_web_sm")
        return

    verbs_df = pd.DataFrame(all_records)
    verbs_df.to_csv(OUT_DIR / "register_verbs.csv", index=False)
    print(f"Extracted {len(verbs_df):,} verb tokens")

    type_counts = verbs_df[verbs_df["process_type"] != "other"]["process_type"].value_counts()

    # Process type bar chart
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = [PROCESS_COLORS.get(t, C_MID) for t in type_counts.index]
    ax.barh(type_counts.index[::-1], type_counts.values[::-1], color=colors[::-1])
    ax.set_xlabel("Verb tokens", fontsize=11)
    ax.set_title("DCD corpus: Hallidayan process types in verb inventory", fontsize=13, fontweight="bold")
    ax.grid(axis="x", color="#eeeeee", zorder=0)
    fig.text(0.98, 0.01, "Matthiessen (2015) registerial cartography framework.", ha="right", fontsize=7, color=C_MID)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "register_process_types.pdf", bbox_inches="tight")
    plt.close()

    # Register contrast
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, (label, subset) in zip(axes, [
        ("Non-contestation", verbs_df[~verbs_df["contested"]]),
        ("Contestation events", verbs_df[verbs_df["contested"]]),
    ]):
        tc = subset[subset["process_type"] != "other"]["process_type"].value_counts(normalize=True) * 100
        colors = [PROCESS_COLORS.get(t, C_MID) for t in tc.index]
        ax.barh(tc.index[::-1], tc.values[::-1], color=colors[::-1])
        ax.set_title(label, fontsize=12, fontweight="bold")
        ax.set_xlabel("% of verb tokens", fontsize=10)
        ax.grid(axis="x", color="#eeeeee", zorder=0)
    fig.suptitle("Register contrast: contestation vs non-contestation", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "register_contrast.pdf", bbox_inches="tight")
    plt.close()
    print("Saved register_process_types.pdf + register_contrast.pdf")

    # Top verbs
    print("\n--- Top verbs by process type ---")
    for ptype in [p for p in PROCESS_COLORS if p != "existential"]:
        top = verbs_df[verbs_df["process_type"] == ptype]["lemma"].value_counts().head(8).to_dict()
        if top:
            print(f"  {ptype:12s}: {', '.join(top.keys())}")

    # Per-city profiles
    ptypes = [p for p in PROCESS_COLORS if p != "existential"]
    locations = list(LOCATION_PATTERNS.keys())
    profile_rows = []
    for loc in locations:
        sub   = verbs_df[verbs_df["location"] == loc]
        total = len(sub[sub["process_type"] != "other"]) or 1
        row   = {pt: sub[sub["process_type"] == pt].shape[0] / total * 100 for pt in ptypes}
        row["location"] = loc
        row["field"]    = field_of_activity({pt: row[pt] for pt in ptypes})
        row["n"]        = len(sub)
        profile_rows.append(row)

    profile_df = pd.DataFrame(profile_rows).set_index("location")
    profile_df.to_csv(OUT_DIR / "register_profiles.csv")

    heat_data = profile_df[ptypes].T
    fig, ax = plt.subplots(figsize=(13, 6))
    sns.heatmap(heat_data, ax=ax, cmap="Greys", linewidths=0.5, linecolor="#eeeeee",
                annot=True, fmt=".0f", annot_kws={"size": 8},
                cbar_kws={"label": "% of verb tokens"})
    ax.set_title("Registerial profiles by city — Hallidayan process types (%)", fontsize=13, fontweight="bold", pad=12)
    fields = profile_df["field"].reindex(heat_data.columns)
    for i, (col, field) in enumerate(fields.items()):
        ax.text(i + 0.5, -0.6, field, ha="center", va="top", fontsize=7, color=C_ACCENT, rotation=30)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "register_city_profiles.pdf", bbox_inches="tight")
    plt.close()
    print("Saved register_city_profiles.pdf")

    # Spatial map
    run_spatial_map(profile_df)

    # 2. Actor extraction
    print("\n=== ACTOR EXTRACTION ===")
    actors_df = run_actors(df)

    # 3. BERTopic (optional — needs bertopic installed)
    print("\n=== TOPIC MODELLING (BERTopic) ===")
    run_bertopic(df)

    print("\nDone. Figures ready for slides_monday.tex")
    print("City registerial profiles:")
    print(profile_df[["field", "n"]].to_string())


if __name__ == "__main__":
    main()
