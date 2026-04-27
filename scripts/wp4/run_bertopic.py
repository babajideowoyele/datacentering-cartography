"""
BERTopic on DCD corpus headlines + intros.
Run from repo root: python scripts/wp4/run_bertopic.py

Outputs:
  data/processed/wp4_dcd/bertopic_topics.csv
  data/processed/wp4_dcd/embeddings.npy          (sentence-transformer embeddings)
  data/processed/wp4_dcd/reduced_embeddings.npy  (2-D UMAP)
  data/processed/wp4_dcd/bertopic_map.html        (intertopic distance)
  data/processed/wp4_dcd/bertopic_hierarchy.html  (topic dendrogram)
  data/processed/wp4_dcd/bertopic_documents.html  (Plotly doc scatter)
  data/processed/wp4_dcd/bertopic_datamap.html    (DataMapPlot doc scatter)
  manuscript/figures/bertopic_barchart.pdf
"""
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TSV  = "datacentering_crawl_datacenterdynamics.tsv"
OUT  = Path("data/processed/wp4_dcd")
FIGS = Path("manuscript/figures")
OUT.mkdir(parents=True, exist_ok=True)

rows = list(csv.DictReader(open(TSV, encoding="utf-8"), delimiter="\t"))
docs = [
    (str(r.get("block-link", "")) + ". " + str(r.get("card__intro", ""))).strip()
    for r in rows
    if r.get("block-link", "").strip()
]
print(f"Documents: {len(docs):,}")

# ── Embeddings (cache to disk so reruns are fast) ───────────────
EMB_PATH = OUT / "embeddings.npy"
if EMB_PATH.exists():
    print("Loading cached embeddings...")
    embeddings = np.load(EMB_PATH)
else:
    print("Encoding with sentence-transformers all-MiniLM-L6-v2...")
    from sentence_transformers import SentenceTransformer
    emb_model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = emb_model.encode(docs, show_progress_bar=True, batch_size=64)
    np.save(EMB_PATH, embeddings)
    print(f"Saved embeddings {embeddings.shape}")

# ── BERTopic ────────────────────────────────────────────────────
from bertopic import BERTopic
from sklearn.feature_extraction.text import CountVectorizer

vectorizer = CountVectorizer(stop_words="english", ngram_range=(1, 2), min_df=5)

model = BERTopic(
    language="english",
    min_topic_size=15,
    nr_topics="auto",
    calculate_probabilities=False,
    vectorizer_model=vectorizer,
    verbose=True,
)

topics, _ = model.fit_transform(docs, embeddings)

info = model.get_topic_info()
info.to_csv(OUT / "bertopic_topics.csv", index=False)
print(f"\nFound {len(info)-1} topics")
print("\nTop 25 topics:")
for _, row in info[info["Topic"] != -1].head(25).iterrows():
    print(f"  Topic {row['Topic']:3d} (n={row['Count']:4d}): {row['Name']}")

# ── Save 2-D reduced embeddings (UMAP already run inside model) ─
try:
    reduced = model.umap_model.embedding_
    np.save(OUT / "reduced_embeddings.npy", reduced)
    print(f"Saved reduced_embeddings {reduced.shape}")
except Exception as e:
    print(f"Could not extract UMAP embeddings: {e}")
    reduced = None

# ── Bar chart (exclude outlier -1 and generic topic 0) ──────────
TOPIC_COLORS = {
    "cooling": "#4a7c9e", "liquid": "#4a7c9e", "immersion": "#4a7c9e",
    "equinix": "#2e4057", "colt": "#2e4057", "rackspace": "#2e4057",
    "softlayer": "#2e4057", "fabros": "#2e4057",
    "carbon": "#6b8f71", "renewable": "#6b8f71", "pue": "#6b8f71",
    "ceo": "#8c7b6b", "appoint": "#8c7b6b", "awards": "#8c7b6b",
    "jobs": "#c0504d", "union": "#c0504d", "workforce": "#c0504d",
    "tiktok": "#B85C00", "fcc": "#B85C00", "planning": "#B85C00",
}

def topic_color(name):
    nm = name.lower()
    for kw, col in TOPIC_COLORS.items():
        if kw in nm:
            return col
    return "#6e6e6e"

top20 = info[(info["Topic"] != -1) & (info["Topic"] != 0)].head(20)
fig, ax = plt.subplots(figsize=(10, 7))
labels = [n.split("_",1)[1].replace("_"," ")[:40] for n in top20["Name"].values]
bar_colors = [topic_color(n) for n in top20["Name"].values]
ax.barh(labels[::-1], top20["Count"].values[::-1], color=bar_colors[::-1])
ax.set_xlabel("Documents", fontsize=11)
ax.set_title("DCD corpus: top 20 BERTopic clusters", fontsize=13, fontweight="bold")
ax.grid(axis="x", color="#eeeeee", zorder=0)
fig.text(0.98, 0.01,
         f"n={len(docs):,} articles (2006-2026); BERTopic, min_topic_size=15; topics 0 & -1 excluded.",
         ha="right", fontsize=7, color="#6e6e6e")
fig.tight_layout()
fig.savefig(FIGS / "bertopic_barchart.pdf", bbox_inches="tight")
plt.close()
print("Saved bertopic_barchart.pdf")

# ── Intertopic distance map ──────────────────────────────────────
try:
    model.visualize_topics().write_html(str(OUT / "bertopic_map.html"))
    print("Saved bertopic_map.html")
except Exception as e:
    print(f"Intertopic map skipped: {e}")

# ── Hierarchy dendrogram (no raw docs needed) ────────────────────
try:
    model.visualize_hierarchy().write_html(str(OUT / "bertopic_hierarchy.html"))
    print("Saved bertopic_hierarchy.html")
except Exception as e:
    print(f"Hierarchy skipped: {e}")

# ── Document scatter (Plotly) ────────────────────────────────────
try:
    kw = {}
    if reduced is not None:
        kw["reduced_embeddings"] = reduced
    else:
        kw["embeddings"] = embeddings
    model.visualize_documents(
        docs, hide_annotations=True, custom_labels=True, **kw
    ).write_html(str(OUT / "bertopic_documents.html"))
    print("Saved bertopic_documents.html")
except Exception as e:
    print(f"Document scatter skipped: {e}")

# ── Topic similarity heatmap ────────────────────────────────────
try:
    model.visualize_heatmap().write_html(str(OUT / "bertopic_heatmap.html"))
    print("Saved bertopic_heatmap.html")
except Exception as e:
    print(f"Heatmap skipped: {e}")

# ── DataMapPlot ──────────────────────────────────────────────────
try:
    kw = {}
    if reduced is not None:
        kw["reduced_embeddings"] = reduced
    else:
        kw["embeddings"] = embeddings
    fig_dmp = model.visualize_document_datamap(docs, **kw)
    fig_dmp.savefig(str(OUT / "bertopic_datamap.png"), dpi=150, bbox_inches="tight")
    print("Saved bertopic_datamap.png")
except Exception as e:
    print(f"DataMapPlot skipped: {e}")
