"""
WP3 — build_urban_graph.py
===========================
Research purpose: Construct a heterogeneous urban graph for each data center
facility in the facility index, embedding each facility within its surrounding
socio-material actor constellation: power infrastructure, water infrastructure,
residential zones, street network, and municipal boundaries.

This operationalises the CAS structural dimension: the spatial-relational
architecture through which data center assemblages are embedded in and
constituted by their urban context. The graph makes legible which actors
(infrastructure, communities, municipalities) are proximate to each facility,
and enables systematic comparison across jurisdictions (e.g. Loudoun County
vs Amsterdam).

Node types:
    - datacenter       : facility locations from the facility index
    - substation       : power grid substations (Overture infrastructure)
    - water_facility   : water treatment / pumping infrastructure
    - residential      : residential land use zones
    - commercial       : commercial / office land use zones
    - municipal        : administrative boundary centroid

Edge types:
    - (datacenter, near_power, substation)       : KNN, k=3
    - (datacenter, near_water, water_facility)   : KNN, k=3
    - (datacenter, adjacent_residential, residential) : fixed radius 1km
    - (datacenter, within_municipality, municipal)    : spatial containment
    - (residential, adjacent, residential)            : queen contiguity

Input:
    data/facility_index/facilities.csv

Output:
    data/processed/wp3_urban_graphs/{facility_id}/
        - graph.graphml        NetworkX heterogeneous graph (GraphML)
        - nodes.geojson        All nodes as GeoDataFrame (GeoJSON)
        - edges.geojson        All edges as GeoDataFrame (GeoJSON)
        - summary.json         Node/edge counts, layer coverage
    data/processed/wp3_urban_graph_summary.csv   Cross-facility summary

Usage:
    python -m scripts.wp3.build_urban_graph \\
        --facilities data/facility_index/facilities.csv \\
        --output data/processed/wp3_urban_graphs \\
        [--buffer-km 2.0] \\
        [--overture-cache data/raw/urban] \\
        [--dry-run]

Data source:
    Overture Maps (https://overturemaps.org/) — downloaded once per facility
    bounding box, cached locally. Requires internet on first run only.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import warnings
from pathlib import Path

# Ensure user-local Python Scripts directory is in PATH so the overturemaps CLI
# (installed via pip install --user) is discoverable by city2graph subprocess calls.
_user_scripts = Path.home() / "AppData" / "Roaming" / "Python" / "Python313" / "Scripts"
if _user_scripts.exists() and str(_user_scripts) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_user_scripts) + os.pathsep + os.environ.get("PATH", "")

# Force UTF-8 I/O for the overturemaps subprocess on Windows (avoids cp1252 UnicodeEncodeError)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import geopandas as gpd
import networkx as nx
import numpy as np
from shapely.geometry import Point, box

warnings.filterwarnings("ignore", category=FutureWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BUFFER_KM = 2.0       # bounding box radius around each facility
KNN_POWER = 3                 # k nearest substations
KNN_WATER = 3                 # k nearest water facilities
RESIDENTIAL_RADIUS_M = 1000   # residential zone adjacency radius (metres)
CRS_GEOGRAPHIC = "EPSG:4326"
CRS_PROJECTED = "EPSG:3857"   # Web Mercator for distance calculations

# Overture Maps layer types we want
OVERTURE_TYPES = ["infrastructure", "land_use", "segment"]

# Overture infrastructure subtypes mapping to our node types
POWER_SUBTYPES = {
    "power_substation", "substation", "power_plant", "power_line",
    "transformer", "electricity", "utility",
}
WATER_SUBTYPES = {
    "water_treatment", "pumping_station", "reservoir", "water_tower",
    "water_works", "waterworks",
}

# Land use classes mapping to our node types
RESIDENTIAL_CLASSES = {"residential", "housing", "apartments", "multifamily"}
COMMERCIAL_CLASSES  = {"commercial", "retail", "office", "mixed_use"}


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def facility_bbox(lat: float, lon: float, buffer_km: float) -> tuple[float, float, float, float]:
    """
    Return (min_lon, min_lat, max_lon, max_lat) bounding box around a point.
    Approximation: 1 degree lat ≈ 111 km; 1 degree lon ≈ 111*cos(lat) km.
    """
    delta_lat = buffer_km / 111.0
    delta_lon = buffer_km / (111.0 * abs(np.cos(np.radians(lat))) + 1e-9)
    return (lon - delta_lon, lat - delta_lat, lon + delta_lon, lat + delta_lat)


def bbox_to_polygon(bbox: tuple) -> "shapely.geometry.Polygon":
    return box(*bbox)


# ---------------------------------------------------------------------------
# Overture Maps data loader (with local cache)
# ---------------------------------------------------------------------------

def load_overture_layer(
    bbox: tuple,
    layer_type: str,
    cache_dir: Path,
    facility_id: str,
) -> gpd.GeoDataFrame | None:
    """
    Load an Overture Maps layer for a bounding box.

    Checks the local cache first; downloads if not present.
    Returns a GeoDataFrame or None if download fails.
    """
    cache_path = cache_dir / facility_id / f"{layer_type}.geojson"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        log.info("[%s] Loading cached %s layer from %s", facility_id, layer_type, cache_path)
        try:
            gdf = gpd.read_file(cache_path)
            return gdf if not gdf.empty else None
        except Exception as exc:
            log.warning("[%s] Cache read failed for %s: %s", facility_id, layer_type, exc)

    log.info("[%s] Downloading Overture Maps %s layer (bbox: %s)", facility_id, layer_type, bbox)
    try:
        import city2graph as c2g
        # save_to_file=True: city2graph writes directly to disk (avoids piping large
        # data through Python on Windows, which triggers cp1252/memory issues).
        # output_dir set to cache_path.parent so the file lands at cache_path.
        result = c2g.load_overture_data(
            area=list(bbox),               # [min_lon, min_lat, max_lon, max_lat]
            types=[layer_type],
            save_to_file=True,
            output_dir=str(cache_path.parent),
        )
        # result is dict[str, GeoDataFrame]; key is the layer type
        gdf = result.get(layer_type)
        if gdf is None or gdf.empty:
            log.warning("[%s] No %s data returned for bbox.", facility_id, layer_type)
            return None
        log.info("[%s] Downloaded %s layer (%d features), cached to %s", facility_id, layer_type, len(gdf), cache_path)
        return gdf
    except Exception as exc:
        log.error("[%s] Failed to download %s layer: %s", facility_id, layer_type, exc)
        return None


# ---------------------------------------------------------------------------
# Node extraction
# ---------------------------------------------------------------------------

def extract_infrastructure_nodes(
    infra_gdf: gpd.GeoDataFrame,
    facility_id: str,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Split infrastructure GDF into power and water node GDFs.
    Returns (power_gdf, water_gdf) as point GDFs.
    """
    if infra_gdf is None or infra_gdf.empty:
        empty = gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs=CRS_GEOGRAPHIC))
        return empty, empty

    # Normalise subtype field — Overture uses 'subtype' or 'class'
    subtype_col = None
    for col in ("subtype", "class", "category", "type"):
        if col in infra_gdf.columns:
            subtype_col = col
            break

    def matches(row, subtypes: set) -> bool:
        if subtype_col is None:
            return False
        val = str(row.get(subtype_col, "") or "").lower()
        return any(s in val for s in subtypes)

    power_mask = infra_gdf.apply(lambda r: matches(r, POWER_SUBTYPES), axis=1)
    water_mask = infra_gdf.apply(lambda r: matches(r, WATER_SUBTYPES), axis=1)

    def to_points(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Convert any geometry to centroid points (project to metric CRS for accuracy)."""
        if gdf.empty:
            return gdf
        gdf = gdf.copy()
        gdf["geometry"] = gdf.to_crs(CRS_PROJECTED).geometry.centroid.to_crs(CRS_GEOGRAPHIC)
        return gdf[gdf.geometry.notna()]

    power_gdf = to_points(infra_gdf[power_mask].copy())
    water_gdf = to_points(infra_gdf[water_mask].copy())

    log.info(
        "[%s] Infrastructure: %d power nodes, %d water nodes",
        facility_id, len(power_gdf), len(water_gdf),
    )
    return power_gdf, water_gdf


def extract_landuse_nodes(
    landuse_gdf: gpd.GeoDataFrame,
    facility_id: str,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Split land use GDF into residential and commercial zone GDFs.
    Returns (residential_gdf, commercial_gdf).
    """
    if landuse_gdf is None or landuse_gdf.empty:
        empty = gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs=CRS_GEOGRAPHIC))
        return empty, empty

    class_col = None
    for col in ("class", "subtype", "category", "land_use", "landuse"):
        if col in landuse_gdf.columns:
            class_col = col
            break

    def matches(row, classes: set) -> bool:
        if class_col is None:
            return False
        val = str(row.get(class_col, "") or "").lower()
        return any(c in val for c in classes)

    res_mask  = landuse_gdf.apply(lambda r: matches(r, RESIDENTIAL_CLASSES), axis=1)
    com_mask  = landuse_gdf.apply(lambda r: matches(r, COMMERCIAL_CLASSES), axis=1)

    residential_gdf = landuse_gdf[res_mask].copy()
    commercial_gdf  = landuse_gdf[com_mask].copy()

    log.info(
        "[%s] Land use: %d residential zones, %d commercial zones",
        facility_id, len(residential_gdf), len(commercial_gdf),
    )
    return residential_gdf, commercial_gdf


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_facility_graph(
    facility: dict,
    buffer_km: float,
    cache_dir: Path,
    dry_run: bool,
) -> tuple[nx.MultiDiGraph | None, dict]:
    """
    Build the heterogeneous urban graph for a single facility.

    Returns (graph, summary_dict).
    """
    import city2graph as c2g

    facility_id = facility["facility_id"]
    lat = float(facility["lat"])
    lon = float(facility["lon"])
    city = facility.get("city", "")
    country = facility.get("country", "")

    log.info("=== Building urban graph: %s (%s, %s) ===", facility_id, city, country)

    bbox = facility_bbox(lat, lon, buffer_km)
    summary = {
        "facility_id": facility_id,
        "city": city,
        "country": country,
        "bbox": bbox,
        "nodes_datacenter": 1,
        "nodes_substation": 0,
        "nodes_water": 0,
        "nodes_residential": 0,
        "nodes_commercial": 0,
        "edges_near_power": 0,
        "edges_near_water": 0,
        "edges_adj_residential": 0,
        "status": "ok",
    }

    if dry_run:
        log.info("[%s] [dry-run] Would download Overture layers for bbox %s", facility_id, bbox)
        summary["status"] = "dry-run"
        return None, summary

    # ------------------------------------------------------------------
    # 1. Load Overture layers
    # ------------------------------------------------------------------
    infra_gdf   = load_overture_layer(bbox, "infrastructure", cache_dir, facility_id)
    landuse_gdf = load_overture_layer(bbox, "land_use", cache_dir, facility_id)

    # ------------------------------------------------------------------
    # 2. Extract node GDFs
    # ------------------------------------------------------------------
    power_gdf, water_gdf = extract_infrastructure_nodes(infra_gdf, facility_id)
    residential_gdf, commercial_gdf = extract_landuse_nodes(landuse_gdf, facility_id)

    # Facility as a single-row GDF
    dc_gdf = gpd.GeoDataFrame(
        [{
            "facility_id": facility_id,
            "operator_name": facility.get("operator_name", ""),
            "operator_type": facility.get("operator_type", ""),
            "city": city,
            "country": country,
        }],
        geometry=[Point(lon, lat)],
        crs=CRS_GEOGRAPHIC,
    )

    # ------------------------------------------------------------------
    # 3. Build heterogeneous graph via NetworkX
    #    city2graph proximity functions return (nodes_gdf, edges_gdf)
    # ------------------------------------------------------------------
    G = nx.MultiDiGraph()

    # Add data center node
    G.add_node(
        facility_id,
        node_type="datacenter",
        lat=lat,
        lon=lon,
        city=city,
        country=country,
        operator=facility.get("operator_name", ""),
    )

    def _graphml_safe(v):
        """Convert a value to a GraphML-compatible scalar (str/int/float/bool)."""
        if v is None:
            return ""
        if isinstance(v, (list, dict)):
            return str(v)
        if hasattr(v, "item"):          # numpy scalar → Python scalar
            return v.item()
        return v

    def add_nodes_from_gdf(gdf: gpd.GeoDataFrame, node_type: str, prefix: str) -> list[str]:
        """Add nodes from GDF, return list of node IDs."""
        if gdf is None or gdf.empty:
            return []
        gdf_geo = gdf.to_crs(CRS_GEOGRAPHIC) if gdf.crs and gdf.crs != CRS_GEOGRAPHIC else gdf
        ids = []
        for i, row in gdf_geo.iterrows():
            nid = f"{prefix}_{i}"
            attrs = {k: _graphml_safe(v) for k, v in row.items() if k != "geometry"}
            attrs["node_type"] = node_type
            geom = row.geometry
            if geom is not None and not geom.is_empty:
                # Project to Web Mercator for accurate centroid, then back to lon/lat
                from shapely.ops import transform
                import pyproj
                proj = pyproj.Transformer.from_crs(CRS_GEOGRAPHIC, CRS_PROJECTED, always_xy=True)
                proj_back = pyproj.Transformer.from_crs(CRS_PROJECTED, CRS_GEOGRAPHIC, always_xy=True)
                geom_m = transform(proj.transform, geom)
                c = geom_m.centroid
                lon, lat = proj_back.transform(c.x, c.y)
                attrs["lat"] = round(lat, 7)
                attrs["lon"] = round(lon, 7)
            G.add_node(nid, **attrs)
            ids.append(nid)
        return ids

    power_ids      = add_nodes_from_gdf(power_gdf, "substation", "pwr")
    water_ids      = add_nodes_from_gdf(water_gdf, "water_facility", "wat")
    res_ids        = add_nodes_from_gdf(residential_gdf, "residential", "res")
    com_ids        = add_nodes_from_gdf(commercial_gdf, "commercial", "com")

    summary["nodes_substation"]  = len(power_ids)
    summary["nodes_water"]       = len(water_ids)
    summary["nodes_residential"] = len(res_ids)
    summary["nodes_commercial"]  = len(com_ids)

    # ------------------------------------------------------------------
    # 4. Add edges using city2graph proximity functions
    # ------------------------------------------------------------------

    def haversine_km(lat1, lon1, lat2, lon2) -> float:
        """Approximate great-circle distance in km."""
        R = 6371.0
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlam = np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
        return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    def add_knn_edges(source_ids: list, target_ids: list, k: int, edge_type: str):
        """Add k nearest neighbour edges from each source to targets."""
        if not source_ids or not target_ids:
            return 0
        count = 0
        for src in source_ids:
            src_data = G.nodes[src]
            src_lat, src_lon = src_data.get("lat", 0), src_data.get("lon", 0)
            distances = []
            for tgt in target_ids:
                tgt_data = G.nodes[tgt]
                tgt_lat, tgt_lon = tgt_data.get("lat", 0), tgt_data.get("lon", 0)
                d = haversine_km(src_lat, src_lon, tgt_lat, tgt_lon)
                distances.append((d, tgt))
            distances.sort()
            for d, tgt in distances[:k]:
                G.add_edge(src, tgt, edge_type=edge_type, distance_km=round(d, 4))
                count += 1
        return count

    def add_radius_edges(source_ids: list, target_ids: list, radius_km: float, edge_type: str):
        """Add edges where distance is within radius."""
        if not source_ids or not target_ids:
            return 0
        count = 0
        for src in source_ids:
            src_data = G.nodes[src]
            src_lat, src_lon = src_data.get("lat", 0), src_data.get("lon", 0)
            for tgt in target_ids:
                tgt_data = G.nodes[tgt]
                tgt_lat, tgt_lon = tgt_data.get("lat", 0), tgt_data.get("lon", 0)
                d = haversine_km(src_lat, src_lon, tgt_lat, tgt_lon)
                if d <= radius_km:
                    G.add_edge(src, tgt, edge_type=edge_type, distance_km=round(d, 4))
                    count += 1
        return count

    # DC → power substations (KNN)
    n = add_knn_edges([facility_id], power_ids, KNN_POWER, "near_power")
    summary["edges_near_power"] = n

    # DC → water facilities (KNN)
    n = add_knn_edges([facility_id], water_ids, KNN_WATER, "near_water")
    summary["edges_near_water"] = n

    # DC → residential zones within 1km
    n = add_radius_edges([facility_id], res_ids, RESIDENTIAL_RADIUS_M / 1000, "adjacent_residential")
    summary["edges_adj_residential"] = n

    log.info(
        "[%s] Graph: %d nodes, %d edges",
        facility_id, G.number_of_nodes(), G.number_of_edges(),
    )

    return G, summary


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def save_graph(G: nx.MultiDiGraph, output_dir: Path, facility_id: str):
    """Save graph as GraphML and node/edge GeoJSONs."""
    out = output_dir / facility_id
    out.mkdir(parents=True, exist_ok=True)

    # GraphML
    graphml_path = out / "graph.graphml"
    nx.write_graphml(G, str(graphml_path))
    log.info("[%s] Saved GraphML to %s", facility_id, graphml_path)

    # Nodes as GeoJSON
    node_records = []
    for nid, attrs in G.nodes(data=True):
        lat = attrs.get("lat")
        lon = attrs.get("lon")
        if lat is not None and lon is not None:
            node_records.append({
                "id": nid,
                **{k: v for k, v in attrs.items() if k not in ("lat", "lon")},
                "geometry": Point(lon, lat),
            })
    if node_records:
        nodes_gdf = gpd.GeoDataFrame(node_records, crs=CRS_GEOGRAPHIC)
        nodes_gdf.to_file(out / "nodes.geojson", driver="GeoJSON")
        log.info("[%s] Saved %d nodes to nodes.geojson", facility_id, len(nodes_gdf))

    # Edges as GeoJSON (straight lines between nodes)
    from shapely.geometry import LineString
    edge_records = []
    for src, tgt, attrs in G.edges(data=True):
        src_data = G.nodes[src]
        tgt_data = G.nodes[tgt]
        if src_data.get("lat") and tgt_data.get("lat"):
            edge_records.append({
                "source": src,
                "target": tgt,
                **attrs,
                "geometry": LineString([
                    (src_data["lon"], src_data["lat"]),
                    (tgt_data["lon"], tgt_data["lat"]),
                ]),
            })
    if edge_records:
        edges_gdf = gpd.GeoDataFrame(edge_records, crs=CRS_GEOGRAPHIC)
        edges_gdf.to_file(out / "edges.geojson", driver="GeoJSON")
        log.info("[%s] Saved %d edges to edges.geojson", facility_id, len(edges_gdf))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="WP3: Build heterogeneous urban graphs for data center facilities."
    )
    parser.add_argument(
        "--facilities",
        default="data/facility_index/facilities.csv",
        help="Facility index CSV.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/wp3_urban_graphs",
        help="Output directory for per-facility graphs.",
    )
    parser.add_argument(
        "--overture-cache",
        default="data/raw/urban",
        help="Local cache directory for Overture Maps downloads.",
    )
    parser.add_argument(
        "--buffer-km",
        type=float,
        default=DEFAULT_BUFFER_KM,
        help=f"Bounding box radius around each facility in km (default: {DEFAULT_BUFFER_KM}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be built without downloading data.",
    )
    parser.add_argument(
        "--facility-id",
        default=None,
        help="Run for a single facility ID only (for testing).",
    )
    args = parser.parse_args()

    facilities_path = Path(args.facilities)
    output_dir = Path(args.output)
    cache_dir = Path(args.overture_cache)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not facilities_path.exists():
        log.error("Facility index not found: %s", facilities_path)
        raise SystemExit(1)

    with facilities_path.open(newline="", encoding="utf-8") as f:
        facilities = list(csv.DictReader(f))

    if args.facility_id:
        facilities = [f for f in facilities if f["facility_id"] == args.facility_id]
        if not facilities:
            log.error("Facility ID not found: %s", args.facility_id)
            raise SystemExit(1)

    log.info("Building urban graphs for %d facilities (buffer: %.1f km)", len(facilities), args.buffer_km)

    all_summaries = []

    for facility in facilities:
        try:
            G, summary = build_facility_graph(
                facility=facility,
                buffer_km=args.buffer_km,
                cache_dir=cache_dir,
                dry_run=args.dry_run,
            )
            if G is not None:
                save_graph(G, output_dir, facility["facility_id"])
            all_summaries.append(summary)
        except Exception as exc:
            log.error("[%s] Failed: %s", facility.get("facility_id", "?"), exc, exc_info=True)
            all_summaries.append({
                "facility_id": facility.get("facility_id", "?"),
                "status": f"error: {exc}",
            })

    # Write cross-facility summary CSV
    if all_summaries:
        summary_path = output_dir / "wp3_urban_graph_summary.csv"
        fieldnames = list(all_summaries[0].keys())
        with summary_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_summaries)
        log.info("Summary written to %s", summary_path)

    log.info("Done. Processed %d facilities.", len(all_summaries))


if __name__ == "__main__":
    main()
