"""
Actor co-occurrence network from DCD corpus.
For each article, detect which actor types appear.
Build edge: actor_A co-occurs with actor_B in same article.
Output:
  data/processed/wp4_dcd/actor_nodes.csv
  data/processed/wp4_dcd/actor_edges.csv
  data/processed/wp4_dcd/actor_network.gexf
  manuscript/figures/actor_cooccurrence.pdf
  docs/cartalog/actor_network_data.json  (for UI)
"""
import csv, re, json, collections
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

TSV  = "datacentering_crawl_datacenterdynamics.tsv"
OUT  = Path("data/processed/wp4_dcd")
FIGS = Path("manuscript/figures")
UI   = Path("docs/cartalog")
OUT.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)
UI.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.family":"serif"})

ACTORS = {
    "Hyperscaler":  r"\b(Amazon|AWS|Microsoft|Google|Meta|Oracle|Alphabet|Apple)\b",
    "Colo/REIT":    r"\b(Equinix|Digital Realty|Iron Mountain|CyrusOne|CoreSite|NTT|Vantage|Colt|DataBank)\b",
    "Regulator":    r"\b(FCC|EPA|OFGEM|FERC|minister|department|regulator|commission|government)\b",
    "Planning body":r"\b(planning commission|planning board|county board|council|municipality|borough|authority)\b",
    "Community":    r"\b(residents?|community|neighbours?|neighbors?|campaign|coalition|protest)\b",
    "Court/Legal":  r"\b(court|tribunal|judge|ruling|lawsuit|litigation|sue\b|appeal)\b",
    "Utility/Grid": r"\b(National Grid|ERCOT|MISO|PJM|EirGrid|Elia|TenneT|Dominion|grid operator)\b",
    "Financial":    r"\b(REIT|pension fund|BlackRock|Vanguard|KKR|Brookfield|SWF|sovereign wealth)\b",
    "Labour":       r"\b(workers?|union|strike|workforce|employees?|staff)\b",
    "Media/Press":  r"\b(report|journalist|coverage|DCD|Bloomberg|FT|Guardian)\b",
}

COLORS = {
    "Hyperscaler":   "#2e4057",
    "Colo/REIT":     "#4a7c9e",
    "Regulator":     "#B85C00",
    "Planning body": "#6b8f71",
    "Community":     "#c0504d",
    "Court/Legal":   "#8c7b6b",
    "Utility/Grid":  "#5a7a5a",
    "Financial":     "#7b68a8",
    "Labour":        "#b08850",
    "Media/Press":   "#aaaaaa",
}

rows = list(csv.DictReader(open(TSV, encoding="utf-8"), delimiter="\t"))
print(f"Loaded {len(rows):,} rows")

# Count actor mentions and co-occurrences
node_counts = collections.Counter()
edge_counts = collections.Counter()

for r in rows:
    text = str(r.get("block-link","")) + " " + str(r.get("card__intro",""))
    present = []
    for actor, pat in ACTORS.items():
        if re.search(pat, text, re.IGNORECASE):
            present.append(actor)
            node_counts[actor] += 1
    # All pairs
    for i in range(len(present)):
        for j in range(i+1, len(present)):
            pair = tuple(sorted([present[i], present[j]]))
            edge_counts[pair] += 1

print(f"\nActor frequencies:")
for a, n in sorted(node_counts.items(), key=lambda x:-x[1]):
    print(f"  {a:20s} {n:6,}")

print(f"\nTop 15 co-occurrences:")
for (a, b), n in sorted(edge_counts.items(), key=lambda x:-x[1])[:15]:
    print(f"  {a:20s} -- {b:20s} : {n:,}")

# Save CSVs
pd_rows = [{"actor": a, "count": n, "color": COLORS.get(a,"#888")}
           for a, n in node_counts.items()]
with open(OUT/"actor_nodes.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=["actor","count","color"])
    w.writeheader(); w.writerows(pd_rows)

edge_rows = [{"source": a, "target": b, "weight": n}
             for (a,b), n in edge_counts.items()]
with open(OUT/"actor_edges.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=["source","target","weight"])
    w.writeheader(); w.writerows(edge_rows)

# Save JSON for UI
ui_data = {
    "nodes": [{"id": a, "count": n, "color": COLORS.get(a,"#888")}
              for a, n in node_counts.items()],
    "links": [{"source": a, "target": b, "weight": n}
              for (a,b), n in sorted(edge_counts.items(), key=lambda x:-x[1])[:30]]
}
(UI/"actor_network_data.json").write_text(json.dumps(ui_data, indent=2))

# ── GEXF for Gephi ─────────────────────────────────────────────────
try:
    import networkx as nx
    G = nx.Graph()
    for a, n in node_counts.items():
        G.add_node(a, weight=n, color=COLORS.get(a,"#888"))
    for (a,b), n in edge_counts.items():
        G.add_edge(a, b, weight=n)
    nx.write_gexf(G, str(OUT/"actor_network.gexf"))
    print("Saved actor_network.gexf")
except ImportError:
    print("networkx not installed — skipping GEXF")

# ── Figure: co-occurrence heatmap ──────────────────────────────────
actors = sorted(node_counts, key=lambda x:-node_counts[x])
n = len(actors)
matrix = [[edge_counts.get(tuple(sorted([actors[i],actors[j]])),0)
           for j in range(n)] for i in range(n)]

fig, ax = plt.subplots(figsize=(10,8))
mat_arr = np.array(matrix, dtype=float)
mat_arr[mat_arr == 0] = np.nan
im = ax.imshow(mat_arr, cmap="Greys", aspect="auto")
ax.set_xticks(range(n)); ax.set_xticklabels(actors, rotation=45, ha="right", fontsize=9)
ax.set_yticks(range(n)); ax.set_yticklabels(actors, fontsize=9)
# Annotate cells
for i in range(n):
    for j in range(n):
        if matrix[i][j] > 0:
            ax.text(j,i,str(matrix[i][j]),ha="center",va="center",fontsize=7,
                    color="white" if matrix[i][j]>500 else "black")
ax.set_title("Actor co-occurrence in DCD corpus (40,565 articles)", fontsize=13, fontweight="bold")
plt.colorbar(im, ax=ax, label="Co-occurrences")
fig.tight_layout()
fig.savefig(FIGS/"actor_cooccurrence.pdf", bbox_inches="tight")
plt.close()
print("Saved actor_cooccurrence.pdf")
