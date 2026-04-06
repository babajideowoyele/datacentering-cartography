"""
WP2 — fetch_auxiliary_imagery.py

Downloads two auxiliary GEE datasets per facility:

  1. Land Surface Temperature (LST) — Landsat 8/9 Collection 2 Level-2 thermal
     band (ST_B10), summer composite (June–August), converted to °C.
     Buffer: 3 km (large enough to show cooling-tower heat plumes).

  2. VIIRS Nighttime Lights — NOAA VIIRS DNB monthly composites, averaged into
     annual mosaics (2013–2024), showing electricity-intensity growth over time.
     Buffer: 10 km (VIIRS pixel = ~750 m; need context to see cluster growth).

Outputs
-------
  data/raw/visual/lst/
    {facility_id}/
      lst_summer_{year}.tif        — LST GeoTIFF in °C (scaled ×100 → int16)
      metadata.json

  data/raw/visual/nightlights/
    {facility_id}/
      viirs_{year}.tif             — average radiance (nanoWatts/cm²/sr)
      metadata.json

  manuscript/figures/
    wp2_lst_map.pdf/.png           — 3-panel LST figure (one panel per city)
    wp2_nightlights_timeseries.pdf/.png — annual radiance growth chart

Usage
-----
    python scripts/wp2/fetch_auxiliary_imagery.py
    python scripts/wp2/fetch_auxiliary_imagery.py --lst-only
    python scripts/wp2/fetch_auxiliary_imagery.py --viirs-only
    python scripts/wp2/fetch_auxiliary_imagery.py --figures-only
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import urllib.request
from pathlib import Path

import ee

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

GEE_PROJECT = "rpcartography"

# Facilities: (facility_id, label, lat, lon)
FACILITIES: list[tuple[str, str, float, float]] = [
    ("noVA_aws_001",        "Ashburn, VA",  38.9517, -77.4481),
    ("ams_equinix_001",     "Amsterdam",    52.3676,   4.9041),
    ("dub_digitalrealty_001","Dublin",      53.3498,  -6.2603),
]

LST_OUTDIR       = Path("data/raw/visual/lst")
VIIRS_OUTDIR     = Path("data/raw/visual/nightlights")
FIGURES_DIR      = Path("manuscript/figures")
LST_BUFFER_M     = 3_000   # 3 km — captures heat plume
VIIRS_BUFFER_M   = 10_000  # 10 km — VIIRS 750m pixels need context
VIIRS_YEARS      = list(range(2013, 2025))
LST_YEAR         = 2024
LST_SUMMER_START = f"{LST_YEAR}-06-01"
LST_SUMMER_END   = f"{LST_YEAR}-09-01"


# ---------------------------------------------------------------------------
# Geometry helper
# ---------------------------------------------------------------------------

def bbox_rect(lat: float, lon: float, buffer_m: int) -> ee.Geometry:
    d_lat = buffer_m / 111_000
    d_lon = buffer_m / (111_000 * math.cos(math.radians(lat)))
    return ee.Geometry.Rectangle(
        [lon - d_lon, lat - d_lat, lon + d_lon, lat + d_lat]
    )


# ---------------------------------------------------------------------------
# LST download
# ---------------------------------------------------------------------------

def fetch_lst(facility_id: str, lat: float, lon: float) -> None:
    outdir = LST_OUTDIR / facility_id
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / f"lst_summer_{LST_YEAR}.tif"
    if out_path.exists():
        logger.info("[%s] LST already exists, skipping.", facility_id)
        return

    aoi = bbox_rect(lat, lon, LST_BUFFER_M)

    # Landsat 8 + 9 Collection 2 Level-2 surface temperature
    col = (
        ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
        .merge(ee.ImageCollection("LANDSAT/LC08/C02/T1_L2"))
        .filterBounds(aoi)
        .filterDate(LST_SUMMER_START, LST_SUMMER_END)
        .filter(ee.Filter.lt("CLOUD_COVER", 20))
        .select("ST_B10")
    )

    count = col.size().getInfo()
    if count == 0:
        logger.warning("[%s] No Landsat scenes for LST.", facility_id)
        return

    # Median composite → convert DN to Kelvin → to Celsius
    # ST_B10 scale: 0.00341802, offset: 149.0 K
    lst_k = col.median().multiply(0.00341802).add(149.0)
    lst_c = lst_k.subtract(273.15).rename("LST_C")

    url = lst_c.getDownloadURL({
        "region": aoi,
        "scale": 30,
        "format": "GEO_TIFF",
        "crs": "EPSG:4326",
    })

    logger.info("[%s] Downloading LST → %s", facility_id, out_path)
    urllib.request.urlretrieve(url, out_path)

    meta = {
        "facility_id": facility_id, "lat": lat, "lon": lon,
        "buffer_m": LST_BUFFER_M, "year": LST_YEAR,
        "season": "summer (Jun–Aug)", "scenes": count,
        "collection": "LANDSAT/LC08+09/C02/T1_L2",
        "band": "ST_B10 → LST_C (°C)", "scale_m": 30,
    }
    (outdir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("[%s] LST saved.", facility_id)


# ---------------------------------------------------------------------------
# VIIRS nighttime lights download
# ---------------------------------------------------------------------------

def fetch_viirs_year(facility_id: str, lat: float, lon: float, year: int) -> float | None:
    """Download annual VIIRS composite for one year. Returns mean radiance or None."""
    out_path = VIIRS_OUTDIR / facility_id / f"viirs_{year}.tif"
    if out_path.exists():
        # Just compute mean for the time series chart without re-downloading
        pass
    else:
        aoi = bbox_rect(lat, lon, VIIRS_BUFFER_M)
        col = (
            ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
            .filterBounds(aoi)
            .filterDate(f"{year}-01-01", f"{year+1}-01-01")
            .select("avg_rad")
        )
        count = col.size().getInfo()
        if count == 0:
            return None

        annual = col.mean()
        url = annual.getDownloadURL({
            "region": aoi,
            "scale": 500,
            "format": "GEO_TIFF",
            "crs": "EPSG:4326",
        })
        out_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("[%s] VIIRS %d → %s", facility_id, year, out_path)
        urllib.request.urlretrieve(url, out_path)

    # Compute mean radiance for time series
    aoi = bbox_rect(lat, lon, VIIRS_BUFFER_M)
    col = (
        ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
        .filterBounds(aoi)
        .filterDate(f"{year}-01-01", f"{year+1}-01-01")
        .select("avg_rad")
    )
    if col.size().getInfo() == 0:
        return None
    mean_val = col.mean().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=500,
        maxPixels=1e8,
    ).getInfo().get("avg_rad")
    return mean_val


def fetch_viirs(facility_id: str, lat: float, lon: float) -> dict[int, float]:
    """Download VIIRS for all years. Returns {year: mean_radiance}."""
    series: dict[int, float] = {}
    for year in VIIRS_YEARS:
        val = fetch_viirs_year(facility_id, lat, lon, year)
        if val is not None:
            series[year] = round(val, 4)
    meta = {
        "facility_id": facility_id, "lat": lat, "lon": lon,
        "buffer_m": VIIRS_BUFFER_M, "years": VIIRS_YEARS,
        "collection": "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG",
        "band": "avg_rad (nW/cm²/sr)", "scale_m": 500,
        "annual_mean_radiance": series,
    }
    (VIIRS_OUTDIR / facility_id / "metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return series


# ---------------------------------------------------------------------------
# Figure generation
# ---------------------------------------------------------------------------

def make_lst_figure() -> None:
    """3-panel LST map using rasterio + matplotlib."""
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        import rasterio
    except ImportError:
        logger.warning("rasterio or matplotlib not installed; skipping LST figure.")
        return

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5),
                             facecolor="#0d1b2a", constrained_layout=True)

    for ax, (fid, label, lat, lon) in zip(axes, FACILITIES):
        tif = LST_OUTDIR / fid / f"lst_summer_{LST_YEAR}.tif"
        ax.set_facecolor("#0d1b2a")
        ax.set_title(label, color="white", fontsize=11, pad=6)
        ax.set_xticks([]); ax.set_yticks([])

        if not tif.exists():
            ax.text(0.5, 0.5, "No data", color="gray",
                    ha="center", va="center", transform=ax.transAxes)
            continue

        with rasterio.open(tif) as src:
            data = src.read(1).astype(float)
            data[data == src.nodata] = np.nan if src.nodata else data[data < -100]

        # Clip to sensible range for display
        vmin, vmax = np.nanpercentile(data, [2, 98])
        im = ax.imshow(data, cmap="inferno", vmin=vmin, vmax=vmax, interpolation="bilinear")
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("°C", color="white", fontsize=8)
        cbar.ax.yaxis.set_tick_params(color="white")
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white", fontsize=7)

        # Mark facility centre
        h, w = data.shape
        ax.plot(w // 2, h // 2, "r+", markersize=12, markeredgewidth=2)

    fig.suptitle(
        f"Land Surface Temperature — Summer {LST_YEAR} (Landsat 8/9, 30 m)",
        color="white", fontsize=13, y=1.01,
    )

    for fmt in ("pdf", "png"):
        out = FIGURES_DIR / f"wp2_lst_map.{fmt}"
        fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        logger.info("Saved %s", out)
    plt.close(fig)


def make_viirs_figure() -> None:
    """Nighttime lights annual radiance time series."""
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    # Load series from metadata files
    series_data: dict[str, dict[int, float]] = {}
    for fid, label, *_ in FACILITIES:
        meta_path = VIIRS_OUTDIR / fid / "metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            series_data[label] = {int(k): v for k, v in
                                   meta.get("annual_mean_radiance", {}).items()}

    if not series_data:
        logger.warning("No VIIRS metadata found; skipping nightlights figure.")
        return

    colors = {"Ashburn, VA": "#c0504d", "Amsterdam": "#4bacc6", "Dublin": "#9bbb59"}

    fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0d1b2a")
    ax.set_facecolor("#0d1b2a")

    for label, series in series_data.items():
        years = sorted(series.keys())
        vals  = [series[y] for y in years]
        color = colors.get(label, "white")
        ax.plot(years, vals, marker="o", linewidth=2, markersize=5,
                color=color, label=label)
        # Annotate last value
        if years:
            ax.annotate(f"{vals[-1]:.1f}",
                        xy=(years[-1], vals[-1]),
                        xytext=(4, 2), textcoords="offset points",
                        color=color, fontsize=8)

    ax.set_xlabel("Year", color="white", fontsize=11)
    ax.set_ylabel("Mean radiance (nW/cm²/sr)", color="white", fontsize=11)
    ax.set_title(
        "VIIRS Nighttime Lights: Annual Mean Radiance (10 km radius)\n"
        "NOAA VIIRS DNB Monthly V1",
        color="white", fontsize=12,
    )
    ax.tick_params(colors="white")
    ax.xaxis.set_major_locator(mticker.MultipleLocator(2))
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    ax.legend(framealpha=0.2, labelcolor="white", fontsize=10)
    ax.grid(color="#333", linewidth=0.5)

    fig.tight_layout()
    for fmt in ("pdf", "png"):
        out = FIGURES_DIR / f"wp2_nightlights_timeseries.{fmt}"
        fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        logger.info("Saved %s", out)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch LST and VIIRS nighttime lights via GEE (WP2)."
    )
    parser.add_argument("--lst-only",     action="store_true")
    parser.add_argument("--viirs-only",   action="store_true")
    parser.add_argument("--figures-only", action="store_true")
    args = parser.parse_args()

    do_lst   = not args.viirs_only   and not args.figures_only
    do_viirs = not args.lst_only     and not args.figures_only
    do_figs  = not args.lst_only     and not args.viirs_only

    if not args.figures_only:
        ee.Initialize(project=GEE_PROJECT)
        logger.info("GEE initialized (project: %s)", GEE_PROJECT)

    if do_lst:
        logger.info("=== Land Surface Temperature ===")
        for fid, label, lat, lon in FACILITIES:
            logger.info("LST: %s (%s)", fid, label)
            fetch_lst(fid, lat, lon)

    if do_viirs:
        logger.info("=== VIIRS Nighttime Lights ===")
        for fid, label, lat, lon in FACILITIES:
            logger.info("VIIRS: %s (%s)", fid, label)
            fetch_viirs(fid, lat, lon)

    if do_figs:
        logger.info("=== Generating figures ===")
        FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        make_lst_figure()
        make_viirs_figure()

    logger.info("Done.")


if __name__ == "__main__":
    main()
