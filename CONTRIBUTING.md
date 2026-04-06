# Contributing to Datacentering Cartography

Welcome — and thank you for your interest in contributing. This project is designed as a **research commons**, not just a codebase. That means contributions of every kind matter: data, code, local knowledge, translation, critique, and conversation.

Data centers are intentionally opaque. No single researcher or team can map them alone. This infrastructure is built on the premise that distributed, community-maintained knowledge — held to shared standards — is more robust than any proprietary dataset. If you have local expertise, documents, or analytical skills to offer, there is a place for you here.

---

## Table of Contents

1. [Adding data to the facility index](#1-adding-data-to-the-facility-index)
2. [Contributing code (WP pipelines)](#2-contributing-code-wp-pipelines)
3. [Opening issues for new cases and jurisdictions](#3-opening-issues-for-new-cases-and-jurisdictions)
4. [Participating in Discussions](#4-participating-in-discussions)
5. [Data standards](#5-data-standards)
6. [Code standards](#6-code-standards)
7. [Code of conduct](#7-code-of-conduct)

---

## 1. Adding data to the facility index

The community-maintained facility index lives in `data/facility_index/`. It is the shared empirical backbone of the project — a structured record of data center facilities, their operators, ownership structures, planning status, and contestation signals.

### Schema and template

Before contributing data, please read:

- [`data/schema/facility_index_schema.md`](data/schema/facility_index_schema.md) — full field definitions, types, and requirements
- [`data/schema/facility_index_template.csv`](data/schema/facility_index_template.csv) — a CSV template with example rows

### How to submit a new facility record

**Option A — Pull request (preferred):**

1. Fork the repository.
2. Copy `data/schema/facility_index_template.csv` as a starting point.
3. Add your row(s) to `data/facility_index/facilities.csv`, following the schema exactly.
4. In your pull request description, briefly describe your sources and how you found the facility.
5. Open the PR against `main`. A maintainer will review for schema compliance and source quality.

**Option B — GitHub Issue:**

If you are not comfortable with Git, open an issue using the **"New facility record"** template. Paste in the data as a table or list. A maintainer will incorporate it and credit you as contributor.

### What makes a good facility record

- At least one verifiable primary source (planning document, company announcement, press report, satellite imagery with coordinates)
- Honest uncertainty: use the `disclosure_level` field and leave fields blank rather than guessing
- No proprietary or paywalled data reproduced verbatim — cite the source, summarise the finding
- Coordinates rounded to four decimal places (roughly 10 m precision) — sufficient for research purposes, avoids enabling surveillance

---

## 2. Contributing code (WP pipelines)

The project is organised around four work packages. Each has a scripts directory and (where appropriate) notebooks:

| Work Package | Focus | Directory |
|---|---|---|
| WP1 | Corporate websites + Wikipedia | `scripts/wp1/` |
| WP2 | Satellite and visual imagery | `scripts/wp2/` |
| WP3 | Financial and ownership data | `scripts/wp3/` |
| WP4 | News archives and social media | `scripts/wp4/` |

### Getting started

```bash
git clone https://github.com/YOUR_USERNAME/datacentering-cartography.git
cd datacentering-cartography
pip install -r requirements.txt
```

### Workflow

1. Open an issue describing what you want to build or fix before writing significant new code. This avoids duplicated effort and lets others comment early.
2. Fork the repo and create a feature branch: `git checkout -b feature/wp1-wikipedia-scraper`
3. Write your code following the [code standards](#6-code-standards) below.
4. Add or update tests where applicable.
5. Open a pull request with a clear description of what the code does, what data it produces, and any known limitations.

### Priority areas

- Scrapers or API clients for planning portals (UK Planning Inspectorate, Dutch DCMR, Irish An Bord Pleanála, US county databases)
- Ownership chain resolution (Companies House, SEC EDGAR, Dutch KvK, OpenCorporates)
- Satellite imagery labelling pipelines (WP2)
- Community resistance / news signal extraction (WP4)
- Data cleaning and deduplication utilities for the facility index

---

## 3. Opening issues for new cases and jurisdictions

One of the most valuable contributions is flagging a data center cluster, planning dispute, or jurisdiction that the project has not yet covered.

Use the **"New case / jurisdiction"** issue template and include:

- Location (country, region, city)
- Why this case is analytically interesting (scale, contestation, ownership structure, policy context)
- Any initial sources you have found

You do not need to have the full data to open an issue. Pointing the community toward a case is itself a contribution.

---

## 4. Participating in Discussions

GitHub Discussions is the primary space for open conversation about the project. You are welcome to:

- Propose new analytical angles or theoretical framings
- Share relevant reports, papers, or news
- Ask questions about methodology or data
- Introduce yourself and your research interests

Discussion is low-barrier by design. You do not need to be a programmer or a scholar to contribute meaningfully — local knowledge, journalism, activism, and policy experience are all valuable here.

---

## 5. Data standards

These standards exist to protect the project's scientific credibility and the communities whose situations are being documented.

### Sources

- **Every field that can be sourced must be sourced.** List URLs or formal citations in the `primary_sources` field.
- Preferred source types (in rough order of reliability): official planning documents, company regulatory filings, peer-reviewed research, established news outlets, satellite imagery analysis, community group documentation.
- Do not reproduce proprietary data (e.g., Datacenter Dynamics subscriber content, JLL market reports) verbatim. You may cite them and summarise non-confidential findings.
- Wikipedia is acceptable as a secondary pointer but should not be the sole primary source for any factual claim.

### Accuracy and uncertainty

- Leave fields blank rather than guessing. The schema marks required vs. optional fields clearly.
- Use `disclosure_level` to signal how much is publicly known about a facility overall.
- If a value is contested or uncertain, note it in the relevant `_notes` field.

### Privacy and harm

- Do not include personal information about individuals (employees, residents, activists) in facility records.
- Coordinates should be facility-level, not precise enough to identify specific structures beyond what planning documents already make public.
- If you are aware that publishing certain information could put community members at risk, raise this in Discussions before submitting.

---

## 6. Code standards

### Language and environment

- Python 3.10+ for all pipeline code.
- Dependencies managed via `requirements.txt` (or a `pyproject.toml` if you prefer). Do not introduce new heavyweight dependencies without discussion.
- Scripts should run from the repository root without modification to system paths.

### Documentation

- Every script and notebook must have a header comment explaining: what it does, what inputs it expects, what outputs it produces, and any rate limits or API keys required.
- Functions should have docstrings.
- Notebooks should be readable as standalone documents — include markdown cells explaining the analytical steps, not just the code.

### Reproducibility

- Do not hard-code absolute file paths. Use relative paths from the repo root or configurable constants.
- If a pipeline requires an API key, read it from an environment variable and document this clearly. Never commit credentials.
- Include a note on data freshness: when was the source last checked, and how often should it be re-run?
- Where randomness is involved, set a seed and document it.

### Data outputs

- Raw data goes in `data/raw/`, processed data in `data/processed/`.
- Outputs should be in open formats: CSV, JSON, GeoJSON, or Parquet. Avoid Excel-only formats.
- Large files (> 50 MB) should not be committed to the repository. Document how to obtain or regenerate them.

---

## 7. Code of conduct

This project follows a simple principle: **treat contributors as you would want to be treated in a research collaboration**. That means:

- Good-faith engagement with different disciplinary perspectives
- Credit given generously and withheld never
- Disagreements about data or methods resolved with evidence and argument, not dismissal
- No harassment, discrimination, or bad-faith behaviour of any kind

If something feels wrong, open a Discussion or contact the maintainers directly.

---

Thank you for being part of this.
