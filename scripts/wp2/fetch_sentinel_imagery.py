"""
WP2 — fetch_sentinel_imagery.py

Fetches Sentinel-2 satellite imagery for data center facilities using either:
  1. Google Earth Engine (earthengine-api) — preferred
  2. Copernicus Open Access Hub (sentinelsat) — fallback
  3. Static instructions only — if neither API is configured

Usage
-----
    python scripts/wp2/fetch_sentinel_imagery.py \
        --config scripts/wp2/config_template.csv \
        --outdir data/raw/visual/satellite \
        [--buffer 500] \
        [--start-date 2024-01-01] \
        [--end-date 2024-12-31] \
        [--cloud-pct 20]

API Setup Instructions
----------------------

**Option A: Google Earth Engine (recommended)**
1. Sign up for a free GEE account: https://earthengine.google.com/signup/
2. Install the Python client:
       pip install earthengine-api
3. Authenticate once:
       earthengine authenticate
   This opens a browser; follow the prompts to save credentials locally.
4. Initialise in code (handled automatically by this script).

**Option B: Copernicus Open Access Hub**
1. Register for free: https://scihub.copernicus.eu/dhus/#/self-registration
2. Install sentinelsat:
       pip install sentinelsat
3. Set environment variables before running:
       export COPERNICUS_USER=your_username
       export COPERNICUS_PASSWORD=your_password
   On Windows (PowerShell):
       $env:COPERNICUS_USER="your_username"
       $env:COPERNICUS_PASSWORD="your_password"

Note: Copernicus Hub has moved to the new Copernicus Data Space Ecosystem
(https://dataspace.copernicus.eu/) for newer archives. The sentinelsat
library supports both; adjust the API URL accordingly.

If neither API is configured, this script prints these instructions and exits
without error, so it can be included in automated pipelines safely.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_BUFFER_METRES: int = 500       # half-width of bounding box around facility
DEFAULT_START_DATE: str = "2024-01-01"
DEFAULT_END_DATE: str = "2024-12-31"
DEFAULT_CLOUD_PCT: int = 20            # maximum cloud cover percentage
GEE_COLLECTION: str = "COPERNICUS/S2_SR_HARMONIZED"
S2_BANDS: list[str] = ["B4", "B3", "B2"]  # RGB (10m resolution)


# ---------------------------------------------------------------------------
# Geometry helper
# ---------------------------------------------------------------------------

def bounding_box(lat: float, lon: float, buffer_m: int) -> dict[str, float]:
    """
    Compute a square bounding box of side 2*buffer_m around (lat, lon).
    Uses a simple degree approximation (accurate enough at facility scale).

    Returns dict with keys: min_lon, min_lat, max_lon, max_lat.
    """
    # 1 degree latitude ~111 km
    delta_lat = buffer_m / 111_000
    # 1 degree longitude ~ 111 km * cos(lat)
    import math
    delta_lon = buffer_m / (111_000 * math.cos(math.radians(lat)))
    return {
        "min_lat": lat - delta_lat,
        "max_lat": lat + delta_lat,
        "min_lon": lon - delta_lon,
        "max_lon": lon + delta_lon,
    }


# ---------------------------------------------------------------------------
# Backend: Google Earth Engine
# ---------------------------------------------------------------------------

def _try_gee(
    facility: dict[str, str],
    outdir: Path,
    buffer_m: int,
    start_date: str,
    end_date: str,
    cloud_pct: int,
) -> bool:
    """
    Attempt to fetch imagery via GEE. Returns True on success, False if
    GEE is unavailable or credentials are not configured.
    """
    try:
        import ee  # type: ignore
    except ImportError:
        logger.debug("earthengine-api not installed; skipping GEE backend.")
        return False

    try:
        ee.Initialize()
    except Exception as exc:
        logger.debug("GEE initialisation failed (%s); skipping GEE backend.", exc)
        return False

    facility_id = facility["facility_id"]
    lat = float(facility["lat"])
    lon = float(facility["lon"])
    bbox = bounding_box(lat, lon, buffer_m)

    aoi = ee.Geometry.Rectangle(
        [bbox["min_lon"], bbox["min_lat"], bbox["max_lon"], bbox["max_lat"]]
    )

    collection = (
        ee.ImageCollection(GEE_COLLECTION)
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_pct))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )

    count = collection.size().getInfo()
    if count == 0:
        logger.warning(
            "[%s] No Sentinel-2 scenes found for date range %s–%s, cloud<%d%%.",
            facility_id, start_date, end_date, cloud_pct,
        )
        return True  # GEE worked, just no scenes

    # Take the least cloudy image
    image = collection.first().select(S2_BANDS)

    # Scale to 0–255 (Sentinel-2 SR values are 0–10000)
    image_vis = image.visualize(
        bands=S2_BANDS,
        min=0,
        max=3000,
        gamma=1.4,
    )

    # Export as GeoTIFF via getDownloadURL (small tiles only; for large
    # areas use ee.batch.Export.image.toDrive instead)
    url = image_vis.getDownloadURL(
        {
            "region": aoi,
            "scale": 10,
            "format": "GEO_TIFF",
            "crs": "EPSG:4326",
        }
    )

    import urllib.request

    fac_outdir = outdir / facility_id
    fac_outdir.mkdir(parents=True, exist_ok=True)
    out_path = fac_outdir / "sentinel2_rgb.tif"

    logger.info("[%s] Downloading GEE tile → %s", facility_id, out_path)
    urllib.request.urlretrieve(url, out_path)

    # Save metadata sidecar
    meta = {
        "facility_id": facility_id,
        "lat": lat,
        "lon": lon,
        "buffer_m": buffer_m,
        "start_date": start_date,
        "end_date": end_date,
        "cloud_pct_max": cloud_pct,
        "collection": GEE_COLLECTION,
        "bands": S2_BANDS,
        "scenes_available": count,
        "backend": "GEE",
    }
    (fac_outdir / "metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    logger.info("[%s] GEE imagery saved.", facility_id)
    return True


# ---------------------------------------------------------------------------
# Backend: Copernicus Open Access Hub (sentinelsat)
# ---------------------------------------------------------------------------

def _try_copernicus(
    facility: dict[str, str],
    outdir: Path,
    buffer_m: int,
    start_date: str,
    end_date: str,
    cloud_pct: int,
) -> bool:
    """
    Attempt to fetch imagery via Copernicus Hub using sentinelsat.
    Returns True on success, False if not configured.
    """
    user = os.environ.get("COPERNICUS_USER")
    password = os.environ.get("COPERNICUS_PASSWORD")
    if not user or not password:
        logger.debug(
            "COPERNICUS_USER / COPERNICUS_PASSWORD not set; skipping Copernicus backend."
        )
        return False

    try:
        from sentinelsat import SentinelAPI, geojson_to_wkt, read_geojson  # type: ignore
        from shapely.geometry import box  # type: ignore
    except ImportError:
        logger.debug("sentinelsat / shapely not installed; skipping Copernicus backend.")
        return False

    facility_id = facility["facility_id"]
    lat = float(facility["lat"])
    lon = float(facility["lon"])
    bbox = bounding_box(lat, lon, buffer_m)

    footprint_geom = box(
        bbox["min_lon"], bbox["min_lat"], bbox["max_lon"], bbox["max_lat"]
    )
    footprint_wkt = footprint_geom.wkt

    # New Copernicus Data Space Ecosystem endpoint (replaces scihub.copernicus.eu)
    api_url = "https://catalogue.dataspace.copernicus.eu/resto/api/collections/Sentinel2/search.json"
    api = SentinelAPI(user, password, api_url=api_url)

    from datetime import datetime
    products = api.query(
        area=footprint_wkt,
        date=(
            datetime.strptime(start_date, "%Y-%m-%d"),
            datetime.strptime(end_date, "%Y-%m-%d"),
        ),
        platformname="Sentinel-2",
        producttype="S2MSI2A",
        cloudcoverpercentage=(0, cloud_pct),
    )

    if not products:
        logger.warning(
            "[%s] No Copernicus products found for %s–%s, cloud<%d%%.",
            facility_id, start_date, end_date, cloud_pct,
        )
        return True

    # Download the first (least cloudy) product
    product_id = min(
        products,
        key=lambda pid: products[pid].get("cloudcoverpercentage", 100),
    )

    fac_outdir = outdir / facility_id
    fac_outdir.mkdir(parents=True, exist_ok=True)

    logger.info("[%s] Downloading Copernicus product %s", facility_id, product_id)
    api.download(product_id, directory_path=str(fac_outdir))

    meta = {
        "facility_id": facility_id,
        "lat": lat,
        "lon": lon,
        "buffer_m": buffer_m,
        "start_date": start_date,
        "end_date": end_date,
        "cloud_pct_max": cloud_pct,
        "product_id": product_id,
        "backend": "Copernicus",
    }
    (fac_outdir / "metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    logger.info("[%s] Copernicus imagery saved.", facility_id)
    return True


# ---------------------------------------------------------------------------
# Setup instructions (printed when no backend is available)
# ---------------------------------------------------------------------------

SETUP_INSTRUCTIONS = """
============================================================
 Sentinel-2 imagery fetch: NO API CONFIGURED
============================================================

To fetch satellite imagery, configure at least one backend:

OPTION A — Google Earth Engine (recommended, free for research)
---------------------------------------------------------------
1. Sign up: https://earthengine.google.com/signup/
2. pip install earthengine-api
3. earthengine authenticate
   (opens browser; saves credentials to ~/.config/earthengine/)

OPTION B — Copernicus Data Space Ecosystem (free, no quota)
-----------------------------------------------------------
1. Register: https://dataspace.copernicus.eu/
2. pip install sentinelsat shapely
3. Set environment variables:
     export COPERNICUS_USER=your_username
     export COPERNICUS_PASSWORD=your_password

Then re-run this script.

For large-scale downloads, consider:
  - GEE Batch Export to Google Drive (ee.batch.Export.image.toDrive)
  - Copernicus S3/STAC access via odc-stac or pystac-client
============================================================
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_facilities(config_path: Path) -> list[dict[str, str]]:
    with config_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Sentinel-2 satellite imagery for facilities (WP2)."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("scripts/wp2/config_template.csv"),
        help="Path to facility coordinates CSV.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("data/raw/visual/satellite"),
        help="Output directory for satellite imagery.",
    )
    parser.add_argument(
        "--buffer",
        type=int,
        default=DEFAULT_BUFFER_METRES,
        help=f"Bounding box half-width in metres (default: {DEFAULT_BUFFER_METRES}).",
    )
    parser.add_argument(
        "--start-date",
        default=DEFAULT_START_DATE,
        help=f"Start of imagery date range (default: {DEFAULT_START_DATE}).",
    )
    parser.add_argument(
        "--end-date",
        default=DEFAULT_END_DATE,
        help=f"End of imagery date range (default: {DEFAULT_END_DATE}).",
    )
    parser.add_argument(
        "--cloud-pct",
        type=int,
        default=DEFAULT_CLOUD_PCT,
        help=f"Max cloud cover percentage (default: {DEFAULT_CLOUD_PCT}).",
    )
    args = parser.parse_args()

    if not args.config.exists():
        parser.error(f"Config file not found: {args.config}")

    facilities = load_facilities(args.config)
    logger.info("Loaded %d facilities from %s", len(facilities), args.config)
    args.outdir.mkdir(parents=True, exist_ok=True)

    any_success = False
    for facility in facilities:
        fid = facility.get("facility_id", "unknown")
        logger.info("Processing facility: %s", fid)

        # Try GEE first
        if _try_gee(
            facility, args.outdir, args.buffer,
            args.start_date, args.end_date, args.cloud_pct
        ):
            any_success = True
            continue

        # Fallback to Copernicus
        if _try_copernicus(
            facility, args.outdir, args.buffer,
            args.start_date, args.end_date, args.cloud_pct
        ):
            any_success = True
            continue

        # Neither backend available — print instructions once and exit
        if not any_success:
            print(SETUP_INSTRUCTIONS)
            sys.exit(0)

        logger.warning(
            "[%s] No imagery backend available; skipping.", fid
        )

    logger.info("Done. Imagery saved to %s", args.outdir)


if __name__ == "__main__":
    main()
