"""
Fast register analysis — no spaCy, regex verb extraction.
Runs on the full 37,811-row DCD CSV in < 30 seconds.
Outputs figures for the ECR presentation.

Following Matthiessen (2015) Hallidayan process types.
"""
import csv, re, collections
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

CSV  = "datacentering_crawl_datacenterdynamics.tsv"
FIGS = Path("manuscript/figures")
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.family":"serif","axes.spines.top":False,"axes.spines.right":False})
C_DARK="#141414"; C_MID="#6e6e6e"; C_ACC="#B85C00"; BG="#ffffff"

PROCESS_PATTERNS = {
    "material":   r"\b(secures?|builds?|breaks?|launches?|opens?|closes?|expands?|installs?|deploys?|develops?|constructs?|acquires?|purchases?|buys?|sells?|demolish|withdraws?|approves?|denies?|rejects?|grants?|imposes?|lifts?|funds?|invests?|signs?|completes?|powers?|supplies?|operates?)\b",
    "verbal":     r"\b(says?|announces?|reports?|states?|claims?|warns?|argues?|urges?|demands?|pledges?|confirms?|reveals?|notes?|describes?|explains?|declares?|asserts?|suggests?|proposes?|recommends?|highlights?|stresses?|acknowledges?|admits?|disputes?|voices?)\b",
    "mental":     r"\b(concerns?|worries?|fears?|thinks?|believes?|considers?|opposes?|supports?|wants?|plans?|expects?|hopes?|doubts?|questions?|challenges?|objects?|resists?|protests?|complains?|welcomes?|endorses?|backs?|finds?|discovers?)\b",
    "relational": r"\b(is|are|was|were|becomes?|remains?|stays?|seems?|appears?|has|have|had|includes?|contains?|represents?|constitutes?|forms?|totals?|amounts?|reaches?)\b",
    "enabling":   r"\b(permits?|allows?|enables?|authorises?|authorizes?|regulates?|requires?|mandates?|enforces?|governs?|bans?|prohibits?|restricts?|limits?|licenses?|certifies?|zones?|rezones?|reviews?|inspects?|assesses?|consults?|negotiates?|commits?|obliges?|forces?|implements?|monitors?)\b",
    "behavioral": r"\b(protests?|campaigns?|demonstrates?|marches?|petitions?|lobbies?|organises?|organizes?|contests?|litigates?|sues?|appeals?|challenges?)\b",
}

ACTOR_PATTERNS = {
    "hyperscaler": r"\b(Amazon|AWS|Microsoft|Google|Meta|Oracle|Apple|Alphabet)\b",
    "colo":        r"\b(Equinix|Digital Realty|Iron Mountain|CyrusOne|CoreSite|NTT|Vantage|Colt)\b",
    "planning":    r"\b(planning commission|planning board|council|county|municipality|borough|authority|committee)\b",
    "utility":     r"\b(National Grid|ERCOT|MISO|PJM|EirGrid|Elia|TenneT|grid operator|electricity company)\b",
    "community":   r"\b(residents?|community|neighbours?|neighbors?|campaign|coalition|local group)\b",
    "regulator":   r"\b(FCC|EPA|OFGEM|FERC|minister|department|regulator|commission)\b",
    "court":       r"\b(court|tribunal|judge|ruling|lawsuit|litigation|sue\b|sued)\b",
}

LOC = {
    "Ashburn / N.Virginia": r"ashburn|loudoun|northern virginia",
    "Amsterdam":            r"amsterdam|netherlands",
    "Dublin / Ireland":     r"dublin|ireland",
    "UK":                   r"\buk\b|united kingdom|england|wales|scotland|london",
    "Germany":              r"germany|frankfurt",
    "Nordics":              r"sweden|norway|denmark|finland|nordic|stockholm",
    "Texas":                r"\btexas\b|\bdallas\b|\bhouston\b",
    "Ohio":                 r"\bohio\b|columbus|cleveland|mansfield",
    "Maryland":             r"\bmaryland\b|harford",
    "Maine":                r"\bmaine\b",
}
CASE_CITIES = {"Ashburn / N.Virginia","Amsterdam","Dublin / Ireland","Maine"}

from datetime import datetime
def parse_date(s):
    for fmt in ["%d %b %Y","%d %B %Y"]:
        try: return datetime.strptime(s.strip(), fmt)
        except: pass
    return None

rows = list(csv.DictReader(open(CSV, encoding="utf-8"), delimiter="	"))
dated = [(parse_date(r["card__overlay"]), r) for r in rows]
dated = [(d,r) for d,r in dated if d]
print(f"Loaded {len(dated):,} dated articles")

STRONG = [r"moratorium",r"\bban\b",r"\bhalt\b",r"\bblock\b",r"reject|refus|deni",
          r"oppos|protest|campaign",r"court|lawsuit",r"withdraw|cancel"]
WEAK   = ["community","residents","planning","council","mayor","county",
          "concern","water","noise","grid","zoning","environ"]
def is_contest(h, intro=""):
    t=(str(h)+" "+str(intro)).lower()
    if any(re.search(p,t) for p in STRONG): return True
    return sum(1 for p in WEAK if p in t)>=2

contest = [(d,r) for d,r in dated if is_contest(r.get("block-link",""),r.get("card__intro",""))]
nocontest = [(d,r) for d,r in dated if not is_contest(r.get("block-link",""),r.get("card__intro",""))]
print(f"Contestation: {len(contest):,} | Non-contestation: {len(nocontest):,}")

def count_processes(articles):
    counts = collections.Counter()
    for _,r in articles:
        t = str(r.get("block-link",""))+" "+str(r.get("card__intro",""))
        for ptype, pat in PROCESS_PATTERNS.items():
            counts[ptype] += len(re.findall(pat, t, re.IGNORECASE))
    return counts

def top_verbs(articles, ptype, n=12):
    verbs = collections.Counter()
    pat = PROCESS_PATTERNS[ptype]
    for _,r in articles:
        t = str(r.get("block-link",""))+" "+str(r.get("card__intro",""))
        for m in re.findall(pat, t, re.IGNORECASE):
            verbs[m.lower().rstrip("s")] += 1
    return verbs.most_common(n)

# ── Figure 1: Process types — contest vs non-contest ──────────────
PCOLORS = {"material":"#2e4057","verbal":"#6b8f71","mental":"#c0504d",
           "relational":"#8c7b6b","enabling":"#4a7c9e","behavioral":"#b08850"}

c_cnt  = count_processes(contest)
nc_cnt = count_processes(nocontest)
ptypes = list(PCOLORS.keys())

c_tot  = sum(c_cnt.values())  or 1
nc_tot = sum(nc_cnt.values()) or 1
c_pct  = [c_cnt[p]/c_tot*100 for p in ptypes]
nc_pct = [nc_cnt[p]/nc_tot*100 for p in ptypes]

fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
for ax, vals, label in [(axes[0], nc_pct, "Non-contestation"), (axes[1], c_pct, "Contestation events")]:
    colors = [PCOLORS[p] for p in ptypes]
    ax.barh(ptypes[::-1], [vals[i] for i in range(len(ptypes)-1,-1,-1)],
            color=[colors[i] for i in range(len(ptypes)-1,-1,-1)])
    ax.set_title(label, fontsize=12, fontweight="bold")
    ax.set_xlabel("% of verb matches", fontsize=10)
    ax.grid(axis="x", color="#eeeeee", zorder=0)
fig.suptitle("Registerial contrast: Hallidayan process types in DCD corpus", fontsize=13, fontweight="bold")
fig.text(0.98,0.01,"Matthiessen (2015); regex process type classifier on 37,552 articles.",ha="right",fontsize=7,color=C_MID)
fig.tight_layout()
fig.savefig(FIGS/"register_contrast.pdf", bbox_inches="tight"); plt.close()
print("Saved register_contrast.pdf")

# ── Figure 2: Top verbs per process type ──────────────────────────
fig, axes = plt.subplots(2, 3, figsize=(14, 8))
axes = axes.flatten()
for ax, ptype in zip(axes, ptypes):
    top = top_verbs(contest, ptype, 10)
    if not top:
        ax.axis("off"); continue
    labels_v, vals_v = zip(*top)
    ax.barh(list(labels_v)[::-1], list(vals_v)[::-1], color=PCOLORS[ptype])
    ax.set_title(f"{ptype.capitalize()} processes", fontweight="bold", fontsize=10)
    ax.grid(axis="x", color="#eeeeee")
    ax.tick_params(labelsize=8)
fig.suptitle("Top verbs by process type — contestation events (DCD 2008–2026)", fontsize=13, fontweight="bold")
fig.tight_layout()
fig.savefig(FIGS/"register_top_verbs.pdf", bbox_inches="tight"); plt.close()
print("Saved register_top_verbs.pdf")

# ── Figure 3: Actor types in contestation corpus ──────────────────
actor_counts = collections.Counter()
for _,r in contest:
    t = str(r.get("block-link",""))+" "+str(r.get("card__intro",""))
    for atype, pat in ACTOR_PATTERNS.items():
        if re.search(pat, t, re.IGNORECASE):
            actor_counts[atype] += 1

fig, ax = plt.subplots(figsize=(8, 4))
actor_labels = list(actor_counts.keys())
actor_vals   = [actor_counts[a] for a in actor_labels]
ACTOR_COLORS = {"Hyperscaler":"#2e4057","Colo/REIT":"#4a7c9e","Regulator":"#B85C00",
                "Planning body":"#6b8f71","Community":"#c0504d","Court/Legal":"#8c7b6b",
                "Utility/Grid":"#5a7a5a","Financial":"#7b68a8","Labour":"#b08850","Media/Press":"#aaaaaa"}
actor_bar_colors = [ACTOR_COLORS.get(l, C_DARK) for l in actor_labels]
ax.barh(actor_labels[::-1], actor_vals[::-1], color=actor_bar_colors[::-1])
ax.set_xlabel("Contestation articles mentioning actor type")
ax.set_title("Actor types in DCD contestation corpus", fontsize=13, fontweight="bold")
ax.grid(axis="x", color="#eeeeee", zorder=0)
fig.tight_layout()
fig.savefig(FIGS/"register_actors.pdf", bbox_inches="tight"); plt.close()
print("Saved register_actors.pdf")

# ── Figure 4: Per-city register profile ───────────────────────────
profile_data = {}
for loc, pat in LOC.items():
    loc_articles = [(d,r) for d,r in contest
                   if re.search(pat, str(r.get("block-link",""))+" "+str(r.get("card__intro","")), re.IGNORECASE)]
    if len(loc_articles) < 3:
        continue
    cnt = count_processes(loc_articles)
    tot = sum(cnt.values()) or 1
    profile_data[loc] = {p: cnt[p]/tot*100 for p in ptypes}
    profile_data[loc]["n"] = len(loc_articles)

import pandas as pd
import seaborn as sns
if profile_data:
    df = pd.DataFrame(profile_data).T[ptypes]
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.heatmap(df.T, ax=ax, cmap="Greys", linewidths=0.5,
                annot=True, fmt=".0f", annot_kws={"size": 9},
                cbar_kws={"label":"% verb matches"})
    ax.set_title("Registerial profiles by city — DCD contestation corpus", fontsize=13, fontweight="bold")
    ax.set_xlabel("City/region", fontsize=10)
    ax.set_ylabel("Process type", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGS/"register_city_profiles.pdf", bbox_inches="tight"); plt.close()
    print("Saved register_city_profiles.pdf")

# ── Print top register verbs for speaker notes ────────────────────
print("\n=== TOP VERBS BY PROCESS TYPE (contestation corpus) ===")
for ptype in ptypes:
    top = top_verbs(contest, ptype, 8)
    print(f"  {ptype:12s}: {', '.join(v for v,_ in top)}")

print("\n=== ACTOR PRESENCE ===")
for a, c in sorted(actor_counts.items(), key=lambda x:-x[1]):
    print(f"  {a:15s}: {c:4d} articles ({c/len(contest)*100:.1f}%)")

print(f"\n=== KEY REGISTER FINDING ===")
# What differs between contestation and non-contestation?
for p in ptypes:
    c_rate  = c_cnt[p]/c_tot*100
    nc_rate = nc_cnt[p]/nc_tot*100
    diff    = c_rate - nc_rate
    marker  = "++" if diff > 3 else ("+" if diff > 1 else ("-" if diff < -1 else "="))
    print(f"  {p:12s}: contestation={c_rate:.1f}%  non-contest={nc_rate:.1f}%  diff={diff:+.1f}% {marker}")
