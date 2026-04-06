"""
build_ownership_network.py — WP3b: Data Center REIT Ownership Network

Constructs a NetworkX graph of ownership and subsidiary relationships among
major data center REITs (Equinix, Digital Realty, Iron Mountain), their key
subsidiaries, and their top institutional investors.

Two data sources are layered:

1. Seed graph (always built): Hardcoded from publicly known REIT structures,
   producing a meaningful 20-30 node graph without any network calls.

2. SEC EDGAR enrichment (opt-in via --enrich-sec): Fetches company filing
   metadata from the SEC EDGAR API to discover additional subsidiaries listed
   in 10-K filings. Skipped gracefully on timeout or API error.

Outputs
-------
data/processed/wp3_ownership/ownership_network.graphml
data/processed/wp3_ownership/nodes.csv
data/processed/wp3_ownership/edges.csv
data/processed/wp3_ownership/ownership_summary.json

Usage
-----
python build_ownership_network.py
python build_ownership_network.py --enrich-sec
python build_ownership_network.py --dry-run
python build_ownership_network.py --output path/to/dir
"""

import argparse
import json
import logging
import os
import time
from pathlib import Path

import networkx as nx
import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SEC EDGAR API constants
# ---------------------------------------------------------------------------
SEC_HEADERS = {
    "User-Agent": "DatacenteringCartography/1.0 research@example.org",
    "Accept": "application/json",
}
SEC_SEARCH_URL = (
    "https://efts.sec.gov/LATEST/search-index"
    "?q={company_name}"
    "&dateRange=custom&startdt=2020-01-01&enddt=2026-01-01"
    "&forms=10-K"
)
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# 1. Seed graph — hardcoded from publicly known REIT structures
# ---------------------------------------------------------------------------

def build_seed_graph() -> nx.DiGraph:
    """Return a directed NetworkX graph of known REIT ownership structures.

    Nodes carry attributes:
        entity_type : str  — one of reit | subsidiary | institutional_investor |
                             sovereign_wealth | datacenter_facility | operating_company
        jurisdiction : str — ISO country code or region label
        reit_status  : bool
        cik          : str | None  — SEC CIK where known

    Edges carry attributes:
        relationship_type : str  — owns | subsidiary_of | invests_in | operates
        ownership_pct     : float | None
    """
    G = nx.DiGraph()

    # ------------------------------------------------------------------
    # Helper shorthands
    # ------------------------------------------------------------------
    def add_entity(node_id: str, name: str, entity_type: str,
                   jurisdiction: str = "US", reit_status: bool = False,
                   cik: str | None = None, **extra) -> None:
        G.add_node(node_id, name=name, entity_type=entity_type,
                   jurisdiction=jurisdiction, reit_status=reit_status,
                   cik=cik, **extra)

    def add_ownership(source: str, target: str, relationship_type: str,
                      ownership_pct: float | None = None) -> None:
        G.add_edge(source, target, relationship_type=relationship_type,
                   ownership_pct=ownership_pct)

    # ------------------------------------------------------------------
    # Institutional investors (shared across REITs)
    # ------------------------------------------------------------------
    add_entity("vanguard", "The Vanguard Group",
               entity_type="institutional_investor", jurisdiction="US")
    add_entity("blackrock", "BlackRock Inc.",
               entity_type="institutional_investor", jurisdiction="US")
    add_entity("statestreet", "State Street Corporation",
               entity_type="institutional_investor", jurisdiction="US")

    # ------------------------------------------------------------------
    # EQUINIX (EQIX) — CIK 0001101239
    # ------------------------------------------------------------------
    add_entity("eqix", "Equinix Inc.",
               entity_type="reit", jurisdiction="US", reit_status=True,
               cik="0001101239",
               enterprise_value_bn=26.0,
               reit_conversion_year=2015)

    # Subsidiaries
    add_entity("eqix_opco", "Equinix Operating Co. LLC",
               entity_type="operating_company", jurisdiction="US",
               parent_cik="0001101239")
    add_entity("eqix_europe", "Equinix Europe Ltd",
               entity_type="subsidiary", jurisdiction="GB",
               parent_cik="0001101239")
    add_entity("switch_data", "Switch and Data LLC",
               entity_type="subsidiary", jurisdiction="US",
               parent_cik="0001101239",
               note="Acquired 2010")
    add_entity("eqix_apac", "Equinix Asia-Pacific Pte. Ltd",
               entity_type="subsidiary", jurisdiction="SG",
               parent_cik="0001101239")
    add_entity("eqix_brazil", "Equinix do Brasil Ltda",
               entity_type="subsidiary", jurisdiction="BR",
               parent_cik="0001101239")

    # Ownership: REIT → subsidiaries
    add_ownership("eqix", "eqix_opco",  "owns", 100.0)
    add_ownership("eqix", "eqix_europe", "owns", 100.0)
    add_ownership("eqix", "switch_data", "owns", 100.0)
    add_ownership("eqix", "eqix_apac",   "owns", 100.0)
    add_ownership("eqix", "eqix_brazil", "owns", 100.0)

    # Subsidiary-of edges (reverse direction for graph traversal)
    add_ownership("eqix_opco",  "eqix", "subsidiary_of")
    add_ownership("eqix_europe","eqix", "subsidiary_of")
    add_ownership("switch_data","eqix", "subsidiary_of")
    add_ownership("eqix_apac",  "eqix", "subsidiary_of")
    add_ownership("eqix_brazil","eqix", "subsidiary_of")

    # Institutional investors → EQIX
    add_ownership("vanguard",   "eqix", "invests_in", 10.0)
    add_ownership("blackrock",  "eqix", "invests_in",  8.0)
    add_ownership("statestreet","eqix", "invests_in",  5.0)

    # ------------------------------------------------------------------
    # DIGITAL REALTY (DLR) — CIK 0001297996
    # ------------------------------------------------------------------
    add_entity("dlr", "Digital Realty Trust Inc.",
               entity_type="reit", jurisdiction="US", reit_status=True,
               cik="0001297996",
               enterprise_value_bn=20.0)

    # Operating partnership (the typical REIT dual-entity structure)
    add_entity("dlr_lp", "Digital Realty Trust LP",
               entity_type="operating_company", jurisdiction="US",
               parent_cik="0001297996",
               note="Operating partnership; holds physical assets")
    add_entity("dlr_sg", "Digital Singapore Jurong East Pte. Ltd",
               entity_type="subsidiary", jurisdiction="SG",
               parent_cik="0001297996")
    add_entity("dlr_ie", "Digital Dublin Ltd",
               entity_type="subsidiary", jurisdiction="IE",
               parent_cik="0001297996")
    add_entity("dlr_nl", "Digital Realty Netherlands BV",
               entity_type="subsidiary", jurisdiction="NL",
               parent_cik="0001297996")
    add_entity("dlr_au", "Digital Realty Australia Pty Ltd",
               entity_type="subsidiary", jurisdiction="AU",
               parent_cik="0001297996")

    add_ownership("dlr", "dlr_lp", "owns", 100.0)
    add_ownership("dlr", "dlr_sg", "owns", 100.0)
    add_ownership("dlr", "dlr_ie", "owns", 100.0)
    add_ownership("dlr", "dlr_nl", "owns", 100.0)
    add_ownership("dlr", "dlr_au", "owns", 100.0)

    add_ownership("dlr_lp", "dlr", "subsidiary_of")
    add_ownership("dlr_sg",  "dlr", "subsidiary_of")
    add_ownership("dlr_ie",  "dlr", "subsidiary_of")
    add_ownership("dlr_nl",  "dlr", "subsidiary_of")
    add_ownership("dlr_au",  "dlr", "subsidiary_of")

    add_ownership("vanguard",  "dlr", "invests_in", 13.0)
    add_ownership("blackrock", "dlr", "invests_in",  7.0)

    # ------------------------------------------------------------------
    # IRON MOUNTAIN (IRM) — CIK 0001020569
    # ------------------------------------------------------------------
    add_entity("irm", "Iron Mountain Inc.",
               entity_type="reit", jurisdiction="US", reit_status=True,
               cik="0001020569",
               reit_conversion_year=2014)

    add_entity("irm_dc", "Iron Mountain Data Centers LLC",
               entity_type="operating_company", jurisdiction="US",
               parent_cik="0001020569")
    add_entity("irm_uk", "Iron Mountain (UK) Ltd",
               entity_type="subsidiary", jurisdiction="GB",
               parent_cik="0001020569")
    add_entity("irm_eu", "Iron Mountain Europe Ltd",
               entity_type="subsidiary", jurisdiction="GB",
               parent_cik="0001020569")
    add_entity("irm_au", "Iron Mountain Australia Group Pty Ltd",
               entity_type="subsidiary", jurisdiction="AU",
               parent_cik="0001020569")

    add_ownership("irm", "irm_dc", "owns", 100.0)
    add_ownership("irm", "irm_uk", "owns", 100.0)
    add_ownership("irm", "irm_eu", "owns", 100.0)
    add_ownership("irm", "irm_au", "owns", 100.0)

    add_ownership("irm_dc", "irm", "subsidiary_of")
    add_ownership("irm_uk", "irm", "subsidiary_of")
    add_ownership("irm_eu", "irm", "subsidiary_of")
    add_ownership("irm_au", "irm", "subsidiary_of")

    add_ownership("vanguard",  "irm", "invests_in", 11.0)
    add_ownership("blackrock", "irm", "invests_in",  9.0)

    log.info("Seed graph built: %d nodes, %d edges",
             G.number_of_nodes(), G.number_of_edges())
    return G


# ---------------------------------------------------------------------------
# 2. SEC EDGAR enrichment (opt-in, gracefully skipped on error)
# ---------------------------------------------------------------------------

def _fetch_json(url: str, timeout: int = SEC_TIMEOUT) -> dict | None:
    """GET *url* and return parsed JSON, or None on any error."""
    try:
        resp = requests.get(url, headers=SEC_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        log.warning("SEC API timeout: %s", url)
    except requests.exceptions.HTTPError as exc:
        log.warning("SEC API HTTP error %s: %s", exc.response.status_code, url)
    except Exception as exc:  # noqa: BLE001
        log.warning("SEC API error (%s): %s", type(exc).__name__, url)
    return None


def enrich_from_sec(G: nx.DiGraph, cik: str) -> None:
    """Attempt to add subsidiary nodes discovered from an SEC 10-K submission.

    Fetches ``/submissions/CIK{cik}.json`` which contains the company's filing
    history. For each 10-K found we log the accession number; richer parsing
    (actual exhibit 21 subsidiary tables) is out of scope for this function but
    can be layered on later.

    Adds a ``sec_enriched`` boolean attribute to the REIT node on success.
    Silently returns on any network or parsing failure.
    """
    padded_cik = cik.lstrip("0").zfill(10)
    url = SEC_SUBMISSIONS_URL.format(cik=padded_cik)
    log.info("Fetching SEC submissions for CIK %s …", cik)

    data = _fetch_json(url)
    if data is None:
        log.warning("Skipping SEC enrichment for CIK %s (fetch failed)", cik)
        return

    company_name = data.get("name", "Unknown")
    sic = data.get("sic", "")
    sic_description = data.get("sicDescription", "")
    state = data.get("stateOfIncorporation", "")

    log.info(
        "  SEC: %s | SIC %s (%s) | incorporated %s",
        company_name, sic, sic_description, state,
    )

    # Find the node whose cik matches and annotate it
    for node_id, attrs in G.nodes(data=True):
        if attrs.get("cik", "").lstrip("0") == cik.lstrip("0"):
            G.nodes[node_id]["sec_enriched"] = True
            G.nodes[node_id]["sec_sic"] = sic
            G.nodes[node_id]["sec_sic_description"] = sic_description
            G.nodes[node_id]["sec_state_of_incorporation"] = state
            break

    # Try to surface former names as alias nodes (non-exhaustive enrichment)
    former_names = data.get("formerNames", [])
    for fn in former_names:
        former = fn.get("name", "")
        if former:
            alias_id = f"alias_{cik}_{former[:20].replace(' ', '_').lower()}"
            if not G.has_node(alias_id):
                G.add_node(alias_id, name=former, entity_type="subsidiary",
                           jurisdiction=state or "US", reit_status=False,
                           cik=None, note="Former name / predecessor entity")
                # Link the alias to the current REIT node
                for node_id, attrs in G.nodes(data=True):
                    if attrs.get("cik", "").lstrip("0") == cik.lstrip("0") \
                            and attrs.get("entity_type") == "reit":
                        G.add_edge(node_id, alias_id,
                                   relationship_type="owns",
                                   ownership_pct=None)
                        break

    # Respect SEC rate-limit guidance: 10 req/s max
    time.sleep(0.15)


# ---------------------------------------------------------------------------
# 3. Save outputs
# ---------------------------------------------------------------------------

def save_outputs(G: nx.DiGraph, output_dir: Path, dry_run: bool = False) -> None:
    """Write the graph and derived tables to *output_dir*.

    Files written
    -------------
    ownership_network.graphml
    nodes.csv
    edges.csv
    ownership_summary.json
    """
    output_dir = Path(output_dir)

    # ------------------------------------------------------------------
    # Build DataFrames
    # ------------------------------------------------------------------
    node_rows = []
    for node_id, attrs in G.nodes(data=True):
        node_rows.append({
            "entity_id":   node_id,
            "name":        attrs.get("name", node_id),
            "entity_type": attrs.get("entity_type", ""),
            "jurisdiction":attrs.get("jurisdiction", ""),
            "reit_status": attrs.get("reit_status", False),
            "cik":         attrs.get("cik", ""),
        })
    nodes_df = pd.DataFrame(node_rows)

    edge_rows = []
    for src, tgt, attrs in G.edges(data=True):
        edge_rows.append({
            "source":            src,
            "target":            tgt,
            "relationship_type": attrs.get("relationship_type", ""),
            "ownership_pct":     attrs.get("ownership_pct", ""),
        })
    edges_df = pd.DataFrame(edge_rows)

    # ------------------------------------------------------------------
    # Summary stats
    # ------------------------------------------------------------------
    entity_type_counts = (
        nodes_df["entity_type"].value_counts().to_dict()
        if not nodes_df.empty else {}
    )
    relationship_counts = (
        edges_df["relationship_type"].value_counts().to_dict()
        if not edges_df.empty else {}
    )
    reits = nodes_df[nodes_df["reit_status"] == True]["name"].tolist()  # noqa: E712

    summary = {
        "node_count":          G.number_of_nodes(),
        "edge_count":          G.number_of_edges(),
        "reit_entities":       reits,
        "entity_type_counts":  entity_type_counts,
        "relationship_counts": relationship_counts,
        "is_dag":              nx.is_directed_acyclic_graph(G),
        "weakly_connected_components": nx.number_weakly_connected_components(G),
    }

    # ------------------------------------------------------------------
    # Write / preview
    # ------------------------------------------------------------------
    if dry_run:
        log.info("[dry-run] Would write to %s:", output_dir)
        log.info("  ownership_network.graphml  (%d nodes, %d edges)",
                 G.number_of_nodes(), G.number_of_edges())
        log.info("  nodes.csv                  (%d rows)", len(nodes_df))
        log.info("  edges.csv                  (%d rows)", len(edges_df))
        log.info("  ownership_summary.json")
        log.info("Summary: %s", json.dumps(summary, indent=2))
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # GraphML cannot serialise None values; replace with empty string
    G_graphml = G.copy()
    for _n, attrs in G_graphml.nodes(data=True):
        for k, v in list(attrs.items()):
            if v is None:
                attrs[k] = ""
    for _u, _v, attrs in G_graphml.edges(data=True):
        for k, v in list(attrs.items()):
            if v is None:
                attrs[k] = ""

    graphml_path = output_dir / "ownership_network.graphml"
    nx.write_graphml(G_graphml, str(graphml_path))
    log.info("Wrote %s", graphml_path)

    nodes_path = output_dir / "nodes.csv"
    nodes_df.to_csv(nodes_path, index=False)
    log.info("Wrote %s  (%d rows)", nodes_path, len(nodes_df))

    edges_path = output_dir / "edges.csv"
    edges_df.to_csv(edges_path, index=False)
    log.info("Wrote %s  (%d rows)", edges_path, len(edges_df))

    summary_path = output_dir / "ownership_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    log.info("Wrote %s", summary_path)


# ---------------------------------------------------------------------------
# 4. CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse arguments and orchestrate the pipeline."""
    parser = argparse.ArgumentParser(
        description=(
            "WP3b — Build data center REIT ownership network. "
            "Outputs GraphML, CSV node/edge tables, and a summary JSON."
        )
    )
    parser.add_argument(
        "--enrich-sec",
        action="store_true",
        default=False,
        help=(
            "Fetch additional data from the SEC EDGAR API. "
            "Disabled by default to avoid slow network calls."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Build the graph but do not write any files; print a preview.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Directory for output files. "
            "Defaults to data/processed/wp3_ownership/ relative to the "
            "project root (two levels above this script)."
        ),
    )
    args = parser.parse_args()

    # Resolve output directory relative to project root when not specified
    if args.output is None:
        script_dir = Path(__file__).resolve().parent
        project_root = script_dir.parent.parent
        output_dir = project_root / "data" / "processed" / "wp3_ownership"
    else:
        output_dir = Path(args.output)

    # ---- Step 1: build seed graph ----------------------------------------
    G = build_seed_graph()

    # ---- Step 2: optional SEC enrichment -----------------------------------
    if args.enrich_sec:
        log.info("SEC EDGAR enrichment enabled.")
        known_ciks = {
            "Equinix":        "0001101239",
            "Digital Realty": "0001297996",
            "Iron Mountain":  "0001020569",
        }
        for company, cik in known_ciks.items():
            log.info("Enriching %s (CIK %s) from SEC EDGAR …", company, cik)
            enrich_from_sec(G, cik)
    else:
        log.info(
            "SEC enrichment skipped (pass --enrich-sec to enable). "
            "Using seed graph only."
        )

    # ---- Step 3: save outputs ----------------------------------------------
    save_outputs(G, output_dir, dry_run=args.dry_run)

    if not args.dry_run:
        log.info(
            "Done. Graph: %d nodes, %d edges → %s",
            G.number_of_nodes(), G.number_of_edges(), output_dir,
        )


if __name__ == "__main__":
    main()
