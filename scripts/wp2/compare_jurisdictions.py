"""
WP2 — compare_jurisdictions.py

Tests whether visual abstraction scores vary systematically across jurisdictions
with different disclosure requirements.

Pipeline
--------
1. Load data/processed/wp2_visual_summary.csv
2. Merge with facility index (scripts/wp2/config_template.csv) on operator_name
   to attach jurisdiction_disclosure_level
3. Run a Kruskal-Wallis H-test (non-parametric) across disclosure-level groups
4. Print a summary table to stdout
5. Save a bar chart (mean abstraction score by disclosure level) to
   outputs/figures/wp2_abstraction_by_jurisdiction.png

Usage
-----
    python scripts/wp2/compare_jurisdictions.py \
        [--summary  data/processed/wp2_visual_summary.csv] \
        [--config   scripts/wp2/config_template.csv] \
        [--outfig   outputs/figures/wp2_abstraction_by_jurisdiction.png]

Notes
-----
- Kruskal-Wallis is preferred over ANOVA because abstraction scores are
  bounded [0,1] and operator sample sizes are small.
- scipy is required for the Kruskal-Wallis test; the script degrades
  gracefully to a group-mean table if scipy is unavailable.
- matplotlib is required for the figure; the script skips figure generation
  if matplotlib is unavailable.
"""

from __future__ import annotations

import argparse
import csv
import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def merge_on_operator(
    summary_rows: list[dict[str, str]],
    config_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """
    Left-join summary onto config by operator_name.
    Adds jurisdiction_disclosure_level and country fields.
    """
    config_lookup: dict[str, dict[str, str]] = {
        row["operator_name"]: row for row in config_rows
    }
    merged: list[dict[str, str]] = []
    for row in summary_rows:
        op = row["operator_name"]
        config_match = config_lookup.get(op, {})
        merged_row = {**row}
        merged_row["jurisdiction_disclosure_level"] = config_match.get(
            "jurisdiction_disclosure_level", "unknown"
        )
        merged_row["country"] = config_match.get("country", "unknown")
        merged.append(merged_row)
    return merged


# ---------------------------------------------------------------------------
# Statistical test
# ---------------------------------------------------------------------------

def group_scores(
    rows: list[dict[str, str]],
) -> dict[str, list[float]]:
    """Group abstraction scores by disclosure level. Skip missing values."""
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        level = row.get("jurisdiction_disclosure_level", "unknown")
        score_str = row.get("abstraction_score", "")
        if score_str == "" or score_str is None:
            continue
        try:
            groups[level].append(float(score_str))
        except ValueError:
            pass
    return dict(groups)


def run_kruskal_wallis(groups: dict[str, list[float]]) -> Optional[dict]:
    """
    Run Kruskal-Wallis H-test across groups (requires scipy).
    Returns dict with H statistic and p-value, or None if unavailable/insufficient data.
    """
    try:
        from scipy import stats  # type: ignore
    except ImportError:
        logger.info("scipy not installed; skipping Kruskal-Wallis test. pip install scipy")
        return None

    # Need at least 2 groups with >=2 observations
    valid_groups = {k: v for k, v in groups.items() if len(v) >= 2}
    if len(valid_groups) < 2:
        logger.info(
            "Insufficient data for Kruskal-Wallis test "
            "(need >= 2 groups with >= 2 observations each)."
        )
        return None

    h_stat, p_value = stats.kruskal(*valid_groups.values())
    return {
        "H_statistic": round(h_stat, 4),
        "p_value": round(p_value, 6),
        "groups_tested": list(valid_groups.keys()),
    }


# ---------------------------------------------------------------------------
# Summary table (stdout)
# ---------------------------------------------------------------------------

def print_summary(
    groups: dict[str, list[float]],
    kruskal_result: Optional[dict],
) -> None:
    print("\n" + "=" * 60)
    print("WP2: Visual Abstraction Score by Jurisdiction Disclosure Level")
    print("=" * 60)
    print(f"{'Disclosure Level':<25} {'N':>4} {'Mean':>8} {'Min':>8} {'Max':>8}")
    print("-" * 60)
    for level, scores in sorted(groups.items()):
        n = len(scores)
        mean = sum(scores) / n if n else float("nan")
        print(
            f"{level:<25} {n:>4} {mean:>8.3f} "
            f"{min(scores):>8.3f} {max(scores):>8.3f}"
        )
    print("-" * 60)

    if kruskal_result:
        print(
            f"\nKruskal-Wallis H = {kruskal_result['H_statistic']}, "
            f"p = {kruskal_result['p_value']}"
        )
        p = kruskal_result["p_value"]
        if p < 0.001:
            interp = "Strong evidence that abstraction score differs by disclosure level (p < 0.001)."
        elif p < 0.05:
            interp = "Moderate evidence that abstraction score differs by disclosure level (p < 0.05)."
        else:
            interp = "No statistically significant difference detected (p >= 0.05)."
        print(f"Interpretation: {interp}")
    else:
        print(
            "\nStatistical test not run "
            "(scipy unavailable or insufficient data)."
        )
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Bar chart
# ---------------------------------------------------------------------------

def save_bar_chart(
    groups: dict[str, list[float]],
    outfig: Path,
    kruskal_result: Optional[dict],
) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
        import matplotlib.ticker as ticker  # type: ignore
    except ImportError:
        logger.warning(
            "matplotlib not installed; skipping figure. pip install matplotlib"
        )
        return

    labels = sorted(groups.keys())
    means = [sum(groups[l]) / len(groups[l]) for l in labels]
    errors = []
    for l in labels:
        scores = groups[l]
        if len(scores) > 1:
            import math
            std = math.sqrt(sum((x - sum(scores) / len(scores)) ** 2 for x in scores) / (len(scores) - 1))
            errors.append(std)
        else:
            errors.append(0)
    counts = [len(groups[l]) for l in labels]

    fig, ax = plt.subplots(figsize=(8, 5))

    bars = ax.bar(
        labels,
        means,
        yerr=errors,
        capsize=5,
        color=["#4a90d9", "#e07b39", "#5cb85c"],
        edgecolor="white",
        alpha=0.85,
    )

    # Annotate with n
    for bar, n in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height() + max(errors) * 0.1 + 0.01,
            f"n={n}",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#333333",
        )

    ax.set_xlabel("Jurisdiction Disclosure Level", fontsize=11)
    ax.set_ylabel("Mean Visual Abstraction Score", fontsize=11)
    ax.set_ylim(0, 1.15)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))

    title = "Visual Abstraction Score by Jurisdiction Disclosure Level"
    if kruskal_result:
        title += f"\nKruskal-Wallis H={kruskal_result['H_statistic']}, p={kruskal_result['p_value']}"
    ax.set_title(title, fontsize=12, pad=14)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    outfig.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfig, dpi=150)
    plt.close(fig)
    logger.info("Figure saved to %s", outfig)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare visual abstraction scores across jurisdictions (WP2)."
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/processed/wp2_visual_summary.csv"),
        help="Path to wp2_visual_summary.csv.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("scripts/wp2/config_template.csv"),
        help="Path to facility index CSV (provides disclosure levels).",
    )
    parser.add_argument(
        "--outfig",
        type=Path,
        default=Path("outputs/figures/wp2_abstraction_by_jurisdiction.png"),
        help="Output path for bar chart.",
    )
    args = parser.parse_args()

    for p, name in [(args.summary, "summary"), (args.config, "config")]:
        if not p.exists():
            logger.error("%s file not found: %s", name, p)
            return

    summary_rows = load_csv(args.summary)
    config_rows = load_csv(args.config)

    merged = merge_on_operator(summary_rows, config_rows)
    logger.info("Merged %d operator records.", len(merged))

    groups = group_scores(merged)
    if not groups:
        logger.error(
            "No abstraction scores found in %s. "
            "Run analyse_visual_content.py first.",
            args.summary,
        )
        return

    kruskal_result = run_kruskal_wallis(groups)
    print_summary(groups, kruskal_result)
    save_bar_chart(groups, args.outfig, kruskal_result)


if __name__ == "__main__":
    main()
