"""
Data centers vs. megaprojects — cumulative capex, inflation-adjusted 2024 USD.

Sources:
  Data center capex : Epoch AI / Platformonomics; company reports
                      (Amazon, Microsoft, Alphabet, Meta, Oracle).
                      DC share of capex scales from ~55% (2020) to ~80% (2026).
  Interstate Hwy    : FHWA; Brookings. $620B over 37 yr (1956–1993).
  F-35 Program      : CRS. ~$400B to date over 25 yr (2001–2026).
  Apollo Program    : NASA. $257B over 14 yr (1961–1975).
  Marshall Plan     : Brookings / ECA. $170B over 4 yr (1948–1952).
  Intl Space Station: NASA / GAO. $150B over 27 yr (1998–2025).
  Manhattan Project : CRS. $36B over 5 yr (1942–1947).
  US Railroads      : Brookings. $550B over 71 yr (1830–1901).

Chart style inspired by Fin Moorhouse (@finmoorhouse), April 2026,
https://x.com/finmoorhouse/status/2044933442236776794
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import FancyArrowPatch

# ---------------------------------------------------------------------------
# Data — (name, label, colour, years_array, cumulative_spend_array_billions)
# ---------------------------------------------------------------------------

# Data center capex: annual DC-attributed capex, 2019–2025, projected 2026
# Derived from Epoch AI / Platformonomics big-5 hyperscaler capex
dc_years_raw  = [0, 1, 2, 3, 4, 5, 6]                    # 2019=0 … 2025=6
dc_annual     = [65, 85, 115, 160, 215, 290, 330]         # ~DC share, $B
# 2019-2024 sum = 930 (≈ Epoch AI / Platformonomics cited figure)
# 2025 = 330 (company guidance); 2026 = +380 projected
dc_cumulative = np.cumsum(dc_annual).tolist()
dc_cumulative = [0] + dc_cumulative                       # len=8, start at 0
dc_years      = [-0.5] + dc_years_raw                     # len=8, solid part
dc_years_ext  = dc_years + [6.8]                          # len=9, with 2026 planned
dc_cum_ext    = dc_cumulative + [dc_cumulative[-1] + 380] # len=9

# Interstate Highway System 1956–1993 (37 yr): $620B total
# Roughly linear build-out with acceleration in 1960s
ihs_yr = np.array([0, 5, 10, 15, 20, 25, 30, 35, 37])
ihs_cu = np.array([0, 50, 130, 240, 360, 470, 555, 610, 620])

# F-35 Program 2001–2026 (25 yr): ~$400B cumulative
f35_yr = np.array([0, 5, 10, 15, 20, 25])
f35_cu = np.array([0, 30, 90, 170, 280, 400])

# Apollo Program 1961–1975 (14 yr): $257B
apo_yr = np.array([0, 3, 7, 10, 14])
apo_cu = np.array([0, 30, 130, 220, 257])

# Marshall Plan 1948–1952 (4 yr): $170B
mar_yr = np.array([0, 1, 2, 3, 4])
mar_cu = np.array([0, 30, 80, 130, 170])

# International Space Station 1998–2025 (27 yr): $150B
iss_yr = np.array([0, 5, 10, 15, 20, 27])
iss_cu = np.array([0, 20, 55, 90, 125, 150])

# Manhattan Project 1942–1947 (5 yr): $36B
man_yr = np.array([0, 1, 2, 3, 4, 5])
man_cu = np.array([0, 2, 7, 18, 30, 36])

# US Railroads 1830–1901 (71 yr): $550B
rail_yr = np.array([0, 10, 20, 30, 40, 50, 60, 71])
rail_cu = np.array([0, 10, 35, 80, 180, 330, 460, 550])

# ---------------------------------------------------------------------------
# Colours (muted, print-safe)
# ---------------------------------------------------------------------------
C_DC    = "#b5534a"   # dusty red
C_IHS   = "#5b8db8"   # steel blue
C_F35   = "#4a8f6f"   # muted green
C_APO   = "#8b7355"   # tan/brown
C_MAR   = "#6b8e6b"   # sage green
C_ISS   = "#7b68a8"   # muted purple
C_MAN   = "#a07840"   # ochre
C_RAIL  = "#5a5a38"   # olive

BG = "#faf8f3"

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 8))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

def trillions(x, pos):
    if x >= 1000:
        return f"${x/1000:.0f}T"
    elif x == 0:
        return "$0"
    else:
        return f"${x:.0f}B"

ax.yaxis.set_major_formatter(mticker.FuncFormatter(trillions))
ax.yaxis.set_major_locator(mticker.MultipleLocator(250))
ax.set_xlim(-1, 78)
ax.set_ylim(-30, 1250)

for spine in ax.spines.values():
    spine.set_visible(False)
ax.tick_params(left=False, bottom=False)
ax.xaxis.set_major_locator(mticker.MultipleLocator(10))
ax.grid(axis="y", color="#d8d4c8", linewidth=0.7, zorder=0)

# --- Draw series ---
def draw(yr, cu, color, lw=2.0, ls="-", zorder=3):
    ax.plot(yr, cu, color=color, linewidth=lw, linestyle=ls,
            solid_capstyle="round", zorder=zorder)
    ax.scatter([yr[-1]], [cu[-1]], color=color, s=28, zorder=zorder+1)

draw(dc_years, dc_cumulative, C_DC, lw=2.8)
# Dashed extension to 2026 planned
ax.plot([dc_years[-1], dc_years_ext[-1]], [dc_cumulative[-1], dc_cum_ext[-1]],
        color=C_DC, linewidth=1.6, linestyle="--", zorder=3)
ax.scatter([dc_years_ext[-1]], [dc_cum_ext[-1]], color=C_DC, s=28,
           facecolors="none", edgecolors=C_DC, zorder=4)

draw(ihs_yr, ihs_cu, C_IHS)
draw(f35_yr, f35_cu, C_F35)
draw(apo_yr, apo_cu, C_APO)
draw(mar_yr, mar_cu, C_MAR)
draw(iss_yr, iss_cu, C_ISS)
draw(man_yr, man_cu, C_MAN)
draw(rail_yr, rail_cu, C_RAIL)

# --- Labels ---
def label(ax, x, y, text, color, ha="left", va="center", fs=9.5):
    ax.text(x, y, text, color=color, fontsize=fs, ha=ha, va=va,
            fontfamily="serif")

label(ax, 1.0, 1060, "2026 (planned)", C_DC, fs=9)
label(ax, 0.3, 870, "2025 •", C_DC, fs=9)
label(ax, 1.5, 790, "Data center capex\n≈$930B in 6 years", C_DC, fs=9.5)

label(ax, 37.5, 632, "Interstate Highway System\n$620B, 37yr", C_IHS)
label(ax, 25.5, 420, "F-35 Program\n$400B, 25yr (to date)", C_F35)
label(ax, 14.5, 265, "Apollo Program\n$257B, 14yr", C_APO)
label(ax, 4.5, 178, "Marshall Plan\n$170B, 4yr", C_MAR, fs=9)
label(ax, 27.5, 136, "International Space Station\n$150B, 27yr", C_ISS, fs=9)
label(ax, 5.5,  50, "Manhattan Project\n$36B, 5yr", C_MAN, fs=9)
label(ax, 72,  538, "US Railroads\n$550B, 71yr", C_RAIL, ha="right", fs=9)

# --- Title ---
ax.text(72, 1180, "Data centers vs. megaprojects", fontsize=14,
        fontfamily="serif", ha="right", color="#2a2a2a", fontweight="bold")
ax.text(72, 1130, "Inflation-adjusted costs, billions USD", fontsize=10,
        fontfamily="serif", ha="right", color="#666666")

# --- Axis labels ---
ax.set_xlabel("Years from start of program", fontsize=10,
              fontfamily="serif", color="#444444")

# --- Source note ---
src = (
    "Sources: Company reports, Epoch AI · FHWA · NASA · CRS · GAO · Brookings · "
    "F. Moorhouse (2026)\n"
    "AI capex = estimated data-centre share of global reported capex at the big-5 "
    "US hyperscalers (Amazon, Microsoft,\n"
    "Alphabet, Meta, Oracle; Epoch AI + Platformonomics). DC share scales from "
    "≈55% in 2020 to ≈80% by 2026.\n"
    "Excludes Chinese hyperscalers. All costs in 2024 dollars."
)
fig.text(0.98, 0.03, src, fontsize=7, ha="right", va="bottom",
         color="#888888", fontfamily="serif")

plt.tight_layout(rect=[0, 0.08, 1, 1])

out = "manuscript/figures/megaprojects_capex.pdf"
plt.savefig(out, dpi=200, bbox_inches="tight", facecolor=BG)
print(f"Saved {out}")
plt.close()
