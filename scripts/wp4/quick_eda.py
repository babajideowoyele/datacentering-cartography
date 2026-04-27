"""Quick EDA on the real 37,811-row DCD CSV. Run from repo root."""
import csv, re, collections
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

CSV   = "datacentering_crawl_datacenterdynamics.tsv"
FIGS  = Path("manuscript/figures")
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.family":"serif","axes.spines.top":False,"axes.spines.right":False})
C_DARK="#141414"; C_MID="#6e6e6e"; C_ACC="#B85C00"; BG="#ffffff"

rows = list(csv.DictReader(open(CSV, encoding="utf-8"), delimiter="	"))
print(f"Rows loaded: {len(rows)}")

def parse_date(s):
    for fmt in ["%d %b %Y","%d %B %Y"]:
        try: return datetime.strptime(s.strip(), fmt)
        except: pass
    return None

dated = [(parse_date(r["card__overlay"]), r) for r in rows]
dated = [(d,r) for d,r in dated if d is not None]
print(f"Dated: {len(dated)}, range: {min(d for d,_ in dated).date()} – {max(d for d,_ in dated).date()}")

STRONG = [r"moratorium", r"\bban\b", r"\bhalt\b", r"\bblock\b",
          r"reject|refus|deni", r"oppos|protest|campaign",
          r"court|lawsuit|sue\b", r"withdraw|cancel", r"moratori"]
WEAK   = ["community","residents","planning","council","mayor",
          "county","concern","water","noise","grid","zoning","environ"]

def is_contest(h, intro=""):
    t = (str(h)+" "+str(intro)).lower()
    if any(re.search(p, t) for p in STRONG): return True
    return sum(1 for p in WEAK if p in t) >= 2

contest = [(d,r) for d,r in dated if is_contest(r.get("block-link",""), r.get("card__intro",""))]
print(f"Contestation: {len(contest)} ({len(contest)/len(dated)*100:.1f}%)")

print("\nTop 15 contestation headlines (recent):")
for d,r in sorted(contest, key=lambda x: x[0], reverse=True)[:15]:
    print(f"  {d.strftime('%b %Y')}  {r['block-link'][:75]}")

# ── Figure 1: Annual volume ────────────────────────────────────────
yr_all = collections.Counter(d.year for d,_ in dated)
yr_con = collections.Counter(d.year for d,_ in contest)
years = sorted(y for y in yr_all if 2007 <= y <= 2026)

fig, ax = plt.subplots(figsize=(10,5))
ax.bar(years, [yr_all.get(y,0) for y in years], color="#4a7c9e", label="All articles", zorder=2, alpha=0.85)
ax.bar(years, [yr_con.get(y,0) for y in years], color="#B85C00", label="Contestation events", zorder=3)
ax.set_title("DCD news archive: annual volume (2007–2026)", fontsize=13, fontweight="bold")
ax.set_ylabel("Articles"); ax.legend(frameon=False)
ax.set_xticks(years); ax.set_xticklabels(years, rotation=45, ha="right", fontsize=8)
ax.grid(axis="y", color="#eeeeee", zorder=1)
fig.text(0.98,0.01,f"Source: DCD scraped April 2026. n={len(dated):,} articles, {len(contest):,} contestation events.", ha="right",fontsize=7,color=C_MID)
fig.tight_layout(); fig.savefig(FIGS/"dcd_eda_timeline.pdf", bbox_inches="tight"); plt.close()
print("Saved dcd_eda_timeline.pdf")

# ── Figure 2: Geography ────────────────────────────────────────────
LOC = {
    "Ashburn / N.Virginia": r"ashburn|loudoun|northern virginia|data center alley|prince william",
    "Amsterdam": r"amsterdam|netherlands",
    "Dublin / Ireland": r"dublin|ireland",
    "UK": r"\buk\b|united kingdom|england|wales|scotland|london",
    "Germany": r"germany|frankfurt|berlin|munich",
    "France": r"france|paris",
    "Nordics": r"sweden|norway|denmark|finland|nordic|stockholm|oslo",
    "Singapore": r"singapore",
    "Texas": r"\btexas\b|\bdallas\b|\bhouston\b|\baustin\b",
    "Ohio": r"\bohio\b|columbus|cleveland|mansfield",
    "Maryland": r"\bmaryland\b|harford",
    "California": r"california|san jose|san francisco",
    "Indiana": r"\bindiana\b|\bla porte\b",
    "Virginia (other)": r"\bvirginia\b",
    "Maine": r"\bmaine\b",
    "Australia": r"australia|sydney|melbourne",
    "Japan": r"\bjapan\b|\btokyo\b",
    "India": r"\bindia\b|hyderabad|mumbai",
}
CASE_CITIES = {"Ashburn / N.Virginia","Amsterdam","Dublin / Ireland","Maine"}

def detect_loc(h, intro=""):
    t = (str(h)+" "+str(intro)).lower()
    for loc, pat in LOC.items():
        if re.search(pat, t, re.IGNORECASE): return loc
    return None

loc_counts = collections.Counter()
for d,r in contest:
    l = detect_loc(r.get("block-link",""), r.get("card__intro",""))
    if l: loc_counts[l] += 1

top = sorted(loc_counts.items(), key=lambda x:-x[1])[:14]
labels, vals = zip(*top) if top else ([],[])
colors = [C_ACC if l in CASE_CITIES else C_DARK for l in labels]

fig, ax = plt.subplots(figsize=(9,5))
ax.barh(list(labels)[::-1], list(vals)[::-1], color=list(colors)[::-1])
ax.set_xlabel("Contestation events"); ax.set_title("Where is contestation? DCD corpus 2007–2026", fontsize=13, fontweight="bold")
ax.grid(axis="x", color="#eeeeee", zorder=0)
red_p = mpatches.Patch(color=C_ACC, label="Case study cities")
gray_p= mpatches.Patch(color=C_DARK,label="Other locations")
ax.legend(handles=[red_p,gray_p], frameon=False)
fig.text(0.98,0.01,f"n={len(contest):,} contestation articles; locations from headlines+intros.",ha="right",fontsize=7,color=C_MID)
fig.tight_layout(); fig.savefig(FIGS/"dcd_eda_geography.pdf", bbox_inches="tight"); plt.close()
print("Saved dcd_eda_geography.pdf")

# ── Figure 3: Event types ──────────────────────────────────────────
ETYPES = {
    "Moratorium / ban":    r"moratorium|ban\b|\bhalt\b|freeze|pause",
    "Planning refusal":    r"refus|reject|deni|no longer pursue|cancel|withdraw",
    "Planning approval":   r"approv|permit|green.light|go.ahead|ok for",
    "Community opposition":r"community|residents|oppos|protest|campaign|objection",
    "Energy / grid":       r"grid|power|energy|electricity|megawatt|\bMW\b|transmission",
    "Water / environment": r"water|drought|environment|pollution|climate",
    "Noise":               r"\bnoise\b|sound|acoustic",
    "Legal / court":       r"court|lawsuit|legal|tribunal|appeal|sue\b",
}
et_counts = collections.Counter()
for d,r in contest:
    t = (str(r.get("block-link",""))+" "+str(r.get("card__intro",""))).lower()
    for label, pat in ETYPES.items():
        if re.search(pat, t): et_counts[label] += 1

top_et = sorted(et_counts.items(), key=lambda x:-x[1])
labels_et, vals_et = zip(*top_et) if top_et else ([],[])
colors_et = [C_ACC if "Moratorium" in l or "refusal" in l or "opposition" in l else C_DARK for l in labels_et]

fig, ax = plt.subplots(figsize=(9,5))
ax.barh(list(labels_et)[::-1], list(vals_et)[::-1], color=list(colors_et)[::-1])
ax.set_xlabel("Events (overlapping categories)"); ax.set_title("What triggers contestation? DCD 2007–2026", fontsize=13, fontweight="bold")
ax.grid(axis="x", color="#eeeeee", zorder=0)
fig.text(0.98,0.01,f"n={len(contest):,} contestation articles; event types from headline+intro.",ha="right",fontsize=7,color=C_MID)
fig.tight_layout(); fig.savefig(FIGS/"dcd_eda_event_types.pdf", bbox_inches="tight"); plt.close()
print("Saved dcd_eda_event_types.pdf")

# ── Figure 4: Contestation rate over time ─────────────────────────
rates = {y: yr_con.get(y,0)/yr_all.get(y,1)*100 for y in years}
fig, ax = plt.subplots(figsize=(10,4))
ax.plot(years, [rates[y] for y in years], color="#B85C00", linewidth=2.5, marker="o", markersize=5)
ax.fill_between(years, [rates[y] for y in years], alpha=0.15, color="#B85C00")
ax.set_ylabel("Contestation articles (%)"); ax.set_title("Contestation as share of DCD coverage over time", fontsize=13, fontweight="bold")
ax.set_xticks(years); ax.set_xticklabels(years, rotation=45, ha="right", fontsize=8)
ax.grid(axis="y", color="#eeeeee")
fig.tight_layout(); fig.savefig(FIGS/"dcd_eda_contestation_rate.pdf", bbox_inches="tight"); plt.close()
print("Saved dcd_eda_contestation_rate.pdf")

# ── Summary stats ──────────────────────────────────────────────────
print(f"\n=== SUMMARY ===")
print(f"Total articles: {len(dated):,}")
print(f"Contestation events: {len(contest):,}")
print(f"Date range: {min(d for d,_ in dated).strftime('%b %Y')} – {max(d for d,_ in dated).strftime('%b %Y')}")
print(f"Top locations: {dict(list(loc_counts.most_common(5)))}")
print(f"Top event types: {dict(list(et_counts.most_common(4)))}")
peak_year = max(yr_con, key=yr_con.get)
print(f"Peak contestation year: {peak_year} ({yr_con[peak_year]} events)")
print("\nAll figures saved to manuscript/figures/")
