"""
BERTopic on DCD corpus headlines + intros.
Run from repo root: python scripts/wp4/run_bertopic.py

Outputs:
  data/processed/wp4_dcd/bertopic_topics.csv
  data/processed/wp4_dcd/bertopic_map.html
  manuscript/figures/bertopic_barchart.pdf   (top 20 topics)
"""
import csv
from pathlib import Path
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

from bertopic import BERTopic

model = BERTopic(
    language="english",
    min_topic_size=15,
    nr_topics="auto",
    calculate_probabilities=False,
    verbose=True,
)

topics, _ = model.fit_transform(docs)

info = model.get_topic_info()
info.to_csv(OUT / "bertopic_topics.csv", index=False)
print(f"\nFound {len(info)-1} topics")
print("\nTop 25 topics:")
for _, row in info[info["Topic"] != -1].head(25).iterrows():
    print(f"  Topic {row['Topic']:3d} (n={row['Count']:4d}): {row['Name']}")

# Bar chart of top 20 topics
top20 = info[info["Topic"] != -1].head(20)
fig, ax = plt.subplots(figsize=(10, 7))
ax.barh(top20["Name"].values[::-1], top20["Count"].values[::-1], color="#141414")
ax.set_xlabel("Documents", fontsize=11)
ax.set_title("DCD corpus: top 20 BERTopic clusters", fontsize=13, fontweight="bold")
ax.grid(axis="x", color="#eeeeee", zorder=0)
fig.text(0.98, 0.01,
         f"n={len(docs):,} articles (2006-2026); BERTopic, min_topic_size=15.",
         ha="right", fontsize=7, color="#6e6e6e")
fig.tight_layout()
fig.savefig(FIGS / "bertopic_barchart.pdf", bbox_inches="tight")
plt.close()
print("Saved bertopic_barchart.pdf")

try:
    fig_html = model.visualize_topics()
    fig_html.write_html(str(OUT / "bertopic_map.html"))
    print("Saved bertopic_map.html")
except Exception as e:
    print(f"HTML map skipped: {e}")
