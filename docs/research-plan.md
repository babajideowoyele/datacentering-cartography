# Research Plan: Towards a Cartography of Datacentering

**Researcher:** Babajide Owoyele, Erasmus University Rotterdam
**Document status:** Working plan, April 2026
**Conference talk:** Research Policy 11th Online ECR Conference, 27 April 2026

---

## State of the project, April 2026

Before laying out the phased plan, this section records honestly what exists and what does not. The pipeline infrastructure is substantially further along than the data.

**What is built and working:**

- WP1: `scrape_operator_websites.py`, `scrape_wikipedia.py`, `analyse_divergence.py` — full pipeline from config to divergence output. Produces `wp1_divergence_summary.csv` and `wp1_keyword_matrix.csv`. Config populated with three operator–city pairings (AWS/Ashburn, Equinix/Amsterdam, Digital Realty/Dallas).
- WP2: `fetch_sentinel_imagery.py`, `collect_corporate_imagery.py`, `analyse_visual_content.py`, `compare_jurisdictions.py` — full pipeline from facility coordinates to abstraction scores and Kruskal-Wallis comparison. CLIP zero-shot classification implemented but not yet validated. Config populated with three seed facilities (AWS/Ashburn, Equinix/Amsterdam, Digital Realty/Dublin).
- WP3: `fetch_opencorporates.py` — resolves operator names to canonical legal identities via the OpenCorporates API, writes structured per-company output. Config awaits population. REIT filing extraction, network assembly, and actor typology classifier do not yet exist.
- WP4: Designed. No scripts built. No corpus assembled.
- Facility index: Schema documented (`data/schema/facility_index_schema.md`), template available (`data/schema/facility_index_template.csv`), `data/facility_index/facilities.csv` exists but carries only three seed entries.

**What the paper currently rests on:** The bibliometric audit is the paper's primary empirical foundation. The Virginia/Amsterdam comparison is built from secondary sources — Vonderau (2019), trade press, desk research — not from pipeline output. The four work packages are described as a methodology, not yet reported as a completed analysis.

---

## Immediate priorities — April 2026 (before the conference talk, 27 April)

The talk is in three weeks. The goal for this period is not to generate new findings but to ensure what is presented is accurate, defensible, and grounded in something more than three seed facilities.

### Conference preparation

The slide deck follows the argument structure already documented in `docs/talk-apr2026/slide-outline.md`. No revisions to that structure are needed. The risk is Slide 8 (Virginia vs Amsterdam comparison) and Slide 9 (the research agenda): if challenged, the answer must be precise about what is built versus what is designed.

Prepare short, honest answers for the Q&A to three likely questions: (1) what data the four WPs have actually produced so far, (2) whether the facility index is publicly accessible and how to contribute, (3) whether the "complex adaptive systems" framing adds anything beyond ordinary sociotechnical analysis. Rehearse these answers so they come across as confident, not evasive.

### WP1: Run the pipeline on the three existing entries

Before the talk, run `scrape_operator_websites.py` and `scrape_wikipedia.py` on all three existing config entries (AWS/Ashburn, Equinix/Amsterdam, Digital Realty/Dallas) and then run `analyse_divergence.py`. This will produce the first real divergence scores. The output does not need to be in the talk, but having run it means the claim "the pipeline has been tested on real data" is accurate. Record any failures or rate-limiting issues so they can be addressed in Phase 1.

### WP2: Run satellite acquisition for the three seed facilities

Run `fetch_sentinel_imagery.py` for the three seed coordinates. Confirm Sentinel-2 imagery downloads successfully via Google Earth Engine (or the Copernicus Data Space Ecosystem fallback). Run `collect_corporate_imagery.py` for the same three operators. This validates the end-to-end pipeline before Phase 1 data expansion begins.

### Facility index: Add five to ten entries by hand

The facility index with three entries cannot support a jurisdictional comparison. Before the end of April, add at least five entries manually using the existing schema — one or two more Northern Virginia hyperscaler campuses (Microsoft, Google), two or three more Amsterdam facilities (AMS1, AMS5 from the AMS-IX area), and ideally one Frankfurt entry. These do not require exhaustive documentation; fill what is publicly known. This brings the index to eight to thirteen entries and makes the open infrastructure call-to-action in Slide 10 less embarrassing.

### Nothing else

Do not start WP3 network assembly or WP4 corpus work before the talk. The cost of context-switching now outweighs the benefit.

---

## Phase 1 — May to August 2026

### Goal

Build the Northern Virginia / Amsterdam comparative case with real data from all four work packages. This is the empirical core of the eventual journal paper. By the end of August, the comparison should rest on pipeline output, not just secondary sources.

---

### WP1: Expand the corporate text corpus

**Data targets:**

- Northern Virginia: add Microsoft Azure, Google Cloud, CyrusOne, Iron Mountain, Flexential, and QTS to the config. Target pages: sustainability, data centers/locations, about. Wikipedia target: Loudoun County, Virginia article plus the Sterling and Ashburn articles separately.
- Amsterdam: add AMS-IX member operators (Interxion/Digital Realty AMS sites, Equinix AMS1–AMS11), Amsterdam municipality's own data-center covenant communications. Wikipedia target: Amsterdam article and the Westpoort/Schiphol articles where data center clusters are documented.
- Frankfurt (as a third point): add Equinix FR, Digital Realty FRA, Interxion FRA. Wikipedia: Frankfurt am Main, Hanauer Landstraße area.
- Dublin: Digital Realty DUB, Equinix DB. Wikipedia: Dublin article.

**Code priorities:**

- Write `02_divergence_analysis.ipynb` — the notebook flagged in the WP1 docs as designed but not built. This should produce the heatmap visualisations and divergence scoring summaries that are the WP1 empirical output for the paper.
- Add image alt-tag analysis as a secondary analytical layer in the notebook. The scraper already collects alt text; the analysis is missing.
- Implement a simple temporal comparison flag: if corporate pages can be re-scraped in August, a before/after keyword shift is worth recording.

**By end of August:** divergence scores for at least twelve operator–city pairings, including the full Virginia vs Amsterdam axis. `wp1_keyword_matrix.csv` populated and `02_divergence_analysis.ipynb` producing visualisations.

---

### WP2: Expand the facility index and validate the classifier

The pipeline works end-to-end on three entries. The priority is more data, and then classifier validation.

**Data targets:**

- Expand `facilities.csv` to at least twenty-five entries: ten in Northern Virginia (covering the major Loudoun County campuses), ten in the Amsterdam AMS-IX ecosystem, and five across Frankfurt and Dublin. Coordinates for most of these are publicly available in REIT annual reports and operator investor presentations.
- For each new facility, run `fetch_sentinel_imagery.py` and `collect_corporate_imagery.py`.

**Code priorities:**

- Manually annotate a stratified sample of at least 150 corporate images (fifty per jurisdiction: abstract, exterior, unknown) drawn from the newly collected corpus. This annotation is the prerequisite for CLIP validation. Write annotation results to `data/processed/wp2_annotation_sample.csv`.
- Run CLIP zero-shot classification against the annotated sample. Compute precision and recall per category. If CLIP performance is unsatisfactory (precision below 0.70 on exterior vs abstract distinction), switch to a fine-tuned ResNet50 approach using the annotated sample as training data.
- Once classifier is validated, re-run `analyse_visual_content.py` on the full expanded corpus and `compare_jurisdictions.py` to test whether the Kruskal-Wallis comparison is feasible at the new sample size.

**By end of August:** validated classifier, abstraction scores for at least twenty-five facilities, initial Kruskal-Wallis test result (even if underpowered), and a draft version of `outputs/figures/wp2_abstraction_by_jurisdiction.png`.

---

### WP3: Build the ownership pipeline from OpenCorporates to network graph

WP3 has a working first step (`fetch_opencorporates.py`) and nothing after it.

**Data targets:**

- Populate the WP3 config with all operators and holding companies identified in WP1 and WP2 facility expansion: at minimum AWS (Amazon Data Services), Microsoft Azure (various legal entities), Google LLC, Equinix Inc., Digital Realty Trust Inc., Iron Mountain Inc., CyrusOne LLC, QTS Realty Trust. For each, also add the immediate parent holding entity.
- For the Amsterdam side: Equinix Netherlands B.V., Digital Realty Netherlands B.V., Interxion Nederland B.V.
- Run `fetch_opencorporates.py` for all entities. Expect some matching failures; document them.

**Code priorities to build:**

- `scripts/wp3/parse_sec_reit_filings.py`: A script that queries SEC EDGAR's full-text search API for annual 10-K filings from Equinix, Digital Realty, and Iron Mountain, extracts Schedule of Real Estate Assets (or equivalent schedule), and parses facility names, locations, and square footage into a structured table. EDGAR's XBRL data can be accessed via the `/api/xbrl/frames` endpoint. The alternative is to parse the HTML-formatted 10-K documents directly; start with XBRL and fall back to HTML parsing.
- `scripts/wp3/build_ownership_network.py`: Joins OpenCorporates company records, officer data, and REIT Schedule data into a graph structure using NetworkX. Nodes are legal entities (facilities, operating companies, holding companies, REITs, investment funds). Edges are ownership, directorship, or investment relationships. Write the graph to `data/processed/wp3_ownership_graph.graphml` and a node-attribute table to `data/processed/wp3_node_attributes.csv`.
- `scripts/wp3/classify_actor_types.py`: A rule-based classifier (no ML needed at this stage) that assigns each node in the graph to one of four types: vertically-integrated operator-owner, colocation operator leasing REIT-held assets, financial asset manager with no operational function, public or quasi-public entity. Classification draws on company type field from OpenCorporates and NAICS/SIC codes where available.

**By end of August:** OpenCorporates data retrieved for all major Virginia and Amsterdam entities, `parse_sec_reit_filings.py` working for at least Equinix and Digital Realty, ownership network assembled and visualisable (even if incomplete), actor typology first pass complete.

---

### WP4: Conceptual operationalisation and corpus scoping

WP4 has no code yet. Phase 1 is not the time to build the full pipeline, but it is the time to make the key conceptual decisions and to scope what data collection is feasible, before building infrastructure around the wrong design.

**Conceptual work:**

- Define, in writing (a working methods note, not a publishable section), what counts as the onset of a contestation signal for this project. Candidates: first substantive press article mentioning community opposition or planning concern; first formal planning objection filed; first social media post above a threshold of engagement. The choice has direct implications for what data sources are needed. For the Amsterdam case, Vonderau (2019) provides qualitative guidance; the question is how to operationalise it computationally.
- Define what counts as a regime response: moratorium filing, planning rejection, operator commitment under regulatory pressure, or nothing. This taxonomy must be fixed before event detection can be designed.
- Identify the specific planning records needed for the Amsterdam moratorium episode (2019–2022): Amsterdam municipality planning portal, Gemeenteraad minutes, Dutch spatial strategy documents. Identify equivalent Virginia sources: Loudoun County Board of Supervisors minutes, Virginia State Corporation Commission records.

**Pilot corpus assembly:**

- Pull GDELT event data for "data center" + "Amsterdam" and "data center" + "Loudoun County" / "Northern Virginia" for 2016–2023. GDELT is free and covers English-language press globally. Download via the GDELT 2.0 Event API. Store raw results in `data/raw/news-social/gdelt/`.
- Pull relevant Reddit threads from r/nova (Northern Virginia subreddit) and r/Amsterdam for the same period using the PushShift archive (or PRAW if the pushshift archive remains accessible). Store in `data/raw/news-social/reddit/`.
- Do not build the BERTopic pipeline yet. The goal is to have the raw corpus available for Phase 2 model development.

**By end of August:** Written operationalisation of key constructs (signal onset, regime response); GDELT pilot pulls completed for both cases; Reddit pilot pulls completed; a short memo summarising what WP4 infrastructure needs to be built in Phase 2.

---

### Community and open exchange — Phase 1

**Facility index growth target: 25 entries by end of August.**

The three existing seed entries can grow to twenty-five through a combination of researcher-added entries (as above) and targeted outreach. The most efficient contributors to recruit are:

- Researchers working on Amsterdam's data center politics (Vonderau's work, Dutch digital infrastructure scholars). Contact via academic channels; ask them to contribute planning records and facility identifications they already have.
- Local journalists or activists working on Northern Virginia data center expansion. The groups opposing data center development in Loudoun County (Save Rural Loudoun, local planning blog networks) have documented facility footprints in ways that are publicly available.
- The Open Infrastructure Map community, which partially overlaps with OpenStreetMap contributors and has documented some data center locations.

Publish a GitHub Discussions post by the end of May laying out the facility index clearly and asking for contributions. The post should name specific geographic gaps (Singapore, São Paulo, Frankfurt secondary sites) and be explicit about what level of documentation is sufficient for a partial entry.

---

## Phase 2 — September to December 2026

### Goal

Extend the comparative case beyond Virginia and Amsterdam. Build WP4's analytical pipeline. Expand the facility index to sixty or more entries across all target jurisdictions. Begin integrating findings across work packages.

---

### WP1: Secondary case text corpus

Add Frankfurt, Dublin, Singapore, and São Paulo to the WP1 config.

- Frankfurt: Equinix FR sites, Digital Realty FRA, e-shelter (NTT), Telehouse Frankfurt. Wikipedia: Frankfurt and the Rhine-Main region's digital infrastructure coverage.
- Dublin: Equinix DB sites, Digital Realty DUB, AWS EU-West-1 operator entities. Wikipedia: Dublin, the Clondalkin/Tallaght industrial district articles.
- Singapore: Equinix SG sites, Digital Realty SGP, Keppel Data Centres, ST Telemedia Global Data Centres. Wikipedia: Singapore (the data center section has grown substantially since 2020, reflecting the moratorium debate). Note: some Singapore operator pages are in English but others are not fully indexed; supplement with Monetary Authority of Singapore and Urban Redevelopment Authority policy documents.
- São Paulo: Equinix SP sites, Digital Realty GRU, Ascenty (Digital Realty subsidiary), Scala Data Centers. Wikipedia: São Paulo, Tamboré/Alphaville district. Note: operator websites here may be in Portuguese; VADER sentiment analysis will need a Portuguese-language alternative (use `transformers` with multilingual BERT sentiment model rather than VADER).

Run the scraper and divergence analysis across all new entries. By December, `02_divergence_analysis.ipynb` should be producing a cross-jurisdictional divergence comparison covering six case cities.

---

### WP2: Secondary case imagery

Run the full WP2 pipeline (satellite acquisition and corporate scraping) for Frankfurt, Dublin, Singapore, and São Paulo facilities as they are added to the facility index. The Kruskal-Wallis comparison should now be feasible with a sample of forty or more facilities across at least four disclosure environments (US low-disclosure, Netherlands post-moratorium, Singapore moratorium/regulated, Brazil emerging).

If the CLIP classifier validated in Phase 1 is performing adequately, apply it consistently across the expanded corpus without re-validation. If its performance varied by jurisdiction (which is plausible if architectural styles differ), document the variation and apply separate validation samples for non-Western European contexts.

Produce a finalisable version of `outputs/figures/wp2_abstraction_by_jurisdiction.png` and the supporting `wp2_visual_summary.csv` for all cases.

---

### WP3: Extend ownership mapping to secondary cases; begin network analysis

Extend the OpenCorporates pipeline to Singapore and Irish-registered entities (Digital Realty's European holding structure passes through Ireland). The EDGAR REIT parsing script built in Phase 1 applies directly to Singapore-listed REITs only if they file with equivalent regulators; for Keppel and ST Telemedia, use SGX (Singapore Exchange) annual reports as the equivalent data source. Write a note in the script's README documenting the differences.

Begin network analysis on the Virginia and Amsterdam subgraphs built in Phase 1:

- Compute basic network metrics for both subgraphs: degree distribution, density, clustering coefficient, average path length from facility nodes to beneficial owner nodes.
- Identify the structural differences quantitatively, not just descriptively. The expected finding is that the Virginia subgraph has higher ownership dispersion (measured by Gini coefficient of ownership stakes, or by average path length from facility to ultimate owner) than the Amsterdam subgraph. Confirm or complicate this with the actual data.
- Produce `outputs/figures/wp3_ownership_network_virginia.png` and `outputs/figures/wp3_ownership_network_amsterdam.png` using a force-directed layout with node type as colour.

---

### WP4: Build the analytical pipeline

This is the main WP4 construction phase.

**Corpus assembly:**

- Extend GDELT pulls to Frankfurt, Dublin, Singapore, and São Paulo. For Singapore, use the GDELT Actor2 geo filter; for São Paulo, use Portuguese keyword variants.
- Assemble the Amsterdam planning record corpus: download municipal planning decisions from the Amsterdam Ruimtelijke Ordening portal (or file FOI-equivalent requests for the 2019 moratorium documentation if not publicly accessible online). Store in `data/raw/news-social/planning-records/amsterdam/`.
- Identify and download equivalent Loudoun County planning records from the county's online permitting portal (LandMARC system). Store in `data/raw/news-social/planning-records/loudoun/`.

**Pipeline construction:**

- `scripts/wp4/build_corpus.py`: Joins GDELT event records, Reddit posts, and planning documents into a unified, time-indexed corpus per jurisdiction. Output is a parquet file per jurisdiction in `data/processed/wp4_{jurisdiction}_corpus.parquet`.
- `scripts/wp4/run_bertopic.py`: Applies BERTopic to the joined corpus for each jurisdiction. Saves topic model, per-document topic assignments, and topic-over-time representation. Use sentence-transformers (`all-MiniLM-L6-v2`) as the embedding backbone. For non-English corpora (São Paulo), use `paraphrase-multilingual-MiniLM-L12-v2`.
- `scripts/wp4/detect_events.py`: Rule-based event detector that scans the time-indexed corpus for the signal-onset indicators defined in Phase 1 (first press article mentioning opposition, first formal planning document). Produces a per-jurisdiction event timeline in CSV.
- `scripts/wp4/compute_lag.py`: Computes signal-to-response lag for each jurisdiction where a regime response has been identified. For cases with no response (Northern Virginia), records the lag as open/unclosed.

**By December:** BERTopic models trained for Virginia and Amsterdam; event timelines produced; signal-to-response lag computed for Amsterdam (where the moratorium provides a clear response event); lag left open for Virginia, Frankfurt, and others as appropriate.

---

### Community and open exchange — Phase 2

**Facility index growth target: 60 entries by end of December.**

The gap between 25 (Phase 1 target) and 60 requires external contributions. Specific actions:

- Submit a short data note to a relevant venue (e.g., *Data in Brief* or a relevant RRI/open data venue) describing the facility index schema and methodology. This creates a citable reference for contributors and signals that the infrastructure is real.
- Contact two to three researchers working on data center politics in Singapore (the 2019 Singapore moratorium is less documented than Amsterdam's) and in Brazil (Ascenty's rapid build-out in São Paulo is commercially documented but academically unexamined). Ask for facility entries or planning document pointers.
- Add a GitHub Discussions template specifically for "I know a facility that is missing" — lower barrier than a full CSV contribution.
- Contact the Internet Archive and the Sunlight Foundation about any relevant archived planning records they may hold.

---

## Phase 3 — 2027

### Goal

Complete the full comparative analysis across all six cases, integrate findings across work packages, and prepare the journal submission.

---

### Integration: cross-WP analysis

The four work packages have been built and run in parallel, with separate outputs. Phase 3 is where they are brought together analytically.

The core comparative question — why did Amsterdam produce a moratorium and Virginia did not — is addressed by combining:

- WP1 divergence scores (did the imaginary gap between corporate text and territorial text differ between jurisdictions, and did it close after the moratorium?)
- WP2 abstraction scores (did strategic visual invisibility correlate with governance outcomes?)
- WP3 ownership structure (did ownership dispersal through REITs measurably affect accountability surface area?)
- WP4 signal-to-response lag (what is the quantitative difference in lag across the six cases, and what structural variables predict it?)

Write a cross-WP analysis notebook (`notebooks/integration/01_comparative_analysis.ipynb`) that brings all four output datasets together and tests the core causal hypothesis: that regime structure (operationalised through WP3 ownership metrics) mediates the relationship between contestation signal strength (WP4) and governance response.

The secondary cases (Frankfurt, Dublin, Singapore, São Paulo) serve primarily to complicate and extend the binary Virginia/Amsterdam comparison. Frankfurt and Dublin are expected to sit between Virginia and Amsterdam on the ownership-dispersal dimension (Frankfurt has more public-utility-adjacent ownership; Dublin has significant sovereign wealth exposure through ISIF). Singapore provides a non-Western democratic regulatory context with a documented moratorium episode. São Paulo provides a Global South case where contestation dynamics are driven by different infrastructure-access politics.

---

### WP1: Final corpus and analysis

- Complete the multilingual extension for São Paulo (Portuguese-language sites). If VADER proves inadequate, replace it with a multilingual sentiment model throughout.
- Write `03_cross_case_divergence.ipynb` producing the final divergence comparison figure for the journal paper.
- Finalise and archive the full corporate text corpus in `data/raw/corporate-websites/` with a manifest.

---

### WP2: Final classifier validation and figures

- If the facility index has grown to sixty or more entries through community contributions, assess whether the statistical comparison holds at full scale.
- Produce publication-quality figures: one figure per jurisdictional comparison pair, one summary figure for the full six-case comparison.
- Write a methods appendix documenting the classifier validation process and the decisions made at each stage. This is necessary for peer review.

---

### WP3: Full ownership network analysis

- Complete the ownership network for all six case jurisdictions.
- Produce the actor typology classification for all nodes.
- Write the comparative structural analysis: how does the distribution of actor types differ across jurisdictions, and how does that distribution correlate with the WP4 signal-to-response lag?
- Produce a publication-quality network figure for each jurisdiction, plus a summary table of structural metrics.

---

### WP4: Final temporal analysis

- Finalise the BERTopic models for all six jurisdictions.
- Write `02_comparative_lag_analysis.ipynb` comparing signal-to-response lags across cases and testing for structural predictors.
- Produce the core temporal figure for the paper: a timeline visualisation of contestation intensity and regime response events across all six cases, arranged to make the lag comparison visually legible.

---

### Journal submission preparation

The paper currently exists as a research agenda draft. By the end of 2027, it should be rewritten as an empirical paper that uses the Virginia/Amsterdam comparison as its main evidential case and the secondary cases as extension and robustness tests.

**Target journal:** *Research Policy* (first choice, given the venue of the conference presentation and the bibliometric contribution). Fallback: *Technological Forecasting and Social Change* (Phillips and Ritala's own journal; the CAS framing will receive a more sympathetic reading there). Second fallback: *New Media and Society* or *Big Data and Society* if the methodological contribution is judged too applied for RP.

**Word count target:** 8,000–10,000 words (RP standard article), plus supplementary methods appendix.

**Figures for submission:** Six to eight publication-quality figures. The mandatory ones are: (1) bibliometric gap visualisation from Section 1; (2) WP1 divergence heatmap, Virginia vs Amsterdam; (3) WP2 abstraction score comparison; (4) WP3 ownership network comparison; (5) WP4 signal-to-response timeline. The facility index should be deposited in Zenodo or 4TU.ResearchData with a DOI before submission, so it can be cited as a dataset rather than linked to GitHub.

**Open exchange audit before submission:** Verify that all scripts documented in the paper are fully functional, that the facility index is publicly accessible and documented, and that the CONTRIBUTING.md guide accurately reflects the state of the infrastructure. A reproducibility package (Docker or conda environment, documented run order, sample data) should accompany the submission.

---

## Summary timeline

| Period | Key milestones |
|---|---|
| April 2026 | Conference talk (27 Apr); first pipeline runs on existing seed data; facility index to 8–13 entries |
| May–August 2026 | WP1 Virginia + Amsterdam corpus; WP2 expanded to 25 facilities + classifier validated; WP3 OpenCorporates + EDGAR scripts built; WP4 pilot corpus assembled; facility index to 25 entries |
| Sept–Dec 2026 | Secondary cases added (Frankfurt, Dublin, Singapore, São Paulo) across WP1–WP2; WP3 network analysis; WP4 pipeline built and run; facility index to 60 entries; data note submitted |
| 2027 H1 | Cross-WP integration analysis; full comparative case; all figures production-quality |
| 2027 H2 | Paper rewritten as empirical article; dataset deposited to Zenodo; journal submission |

---

## Standing dependencies and risks

**OpenCorporates API access.** The free tier is limited. If the ownership mapping requires more than free-tier queries, the project needs either an institutional subscription or a workaround using national company registry APIs directly (Companies House for UK, KvK for Netherlands, SEC EDGAR for US). Budget for this or plan the workaround before Phase 1 ends.

**SEC EDGAR REIT filing parsing.** The XBRL-first approach in `parse_sec_reit_filings.py` (to be built) depends on REITs tagging their real estate schedules consistently in XBRL. Equinix's and Digital Realty's filings are large and structurally complex; expect to spend time on parsing edge cases. Allow two to three weeks for this script, not two days.

**Sentinel-2 / Google Earth Engine access.** The GEE API requires institutional authentication. Confirm Erasmus University's GEE access before Phase 1. The Copernicus Data Space Ecosystem fallback is functional but slower; if GEE access is problematic, switch to Copernicus as the primary source and document the change.

**Singapore and São Paulo data.** Singapore planning records are in English but access to historical planning documents may require direct contact with the Urban Redevelopment Authority. São Paulo municipality records are in Portuguese and may require collaboration with a local researcher for document retrieval. Do not assume these will be straightforward desk research.

**WP4 social media data.** Reddit's PushShift archive has had access interruptions. If PushShift is unavailable, replace the Reddit data stream with direct PRAW queries (rate-limited but accessible) or with a Wayback Machine scrape of relevant subreddit pages. GDELT remains reliable but covers English-language press; for São Paulo this is a significant limitation — supplement with Folha de S.Paulo's own search API if accessible.

**Facility index growth.** The target of 60 entries by end of Phase 2 requires external contributions or a significant time investment in manual data entry. If community contributions do not materialise, lower the target and reframe: forty well-documented entries are more useful than sixty incomplete ones. Do not inflate the index with undocumented facilities to hit a target.
