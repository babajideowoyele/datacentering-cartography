# Datacentering Cartography

A multimodal research project mapping the sociotechnical dynamics of data center infrastructure — and an open research infrastructure for doing it together.

> **Paper:** *Towards a Cartography of Datacentering: A Multimodal Research Agenda*
> Research Policy 11th Online ECR Conference, April 2026

---

## Open research infrastructure vision

Data centers are intentionally opaque. No single researcher or team can map them alone. This repository is designed as a **research commons**: community-maintained data, shared analytical pipelines, and open exchange — not just a private codebase for one project.

The core artifact is a **community-maintained facility index**: a structured, openly licensed database of data center facilities worldwide, covering ownership structures, planning histories, energy and water sources, and community contestation. Anyone can contribute a record, correct an error, or flag a new case.

If you have local expertise, documents, code, or analytical skills to offer, there is a place for you here. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

---

## Overview

This project develops a **multimodal cartographic methodology** to study data centers as socio-material phenomena — bringing sustainability transitions (ST), science and technology studies (STS), and innovation policy frameworks to bear on an infrastructure that has, until now, remained outside these fields.

The central challenge is **opacity**: operators rarely disclose facility locations, energy sources, water consumption, or emissions. No single method can cut through this strategically constructed invisibility. This project triangulates across four data modalities:

| Modality | Data Sources | Research Focus |
|---|---|---|
| Corporate & territorial | Operator websites, city Wikipedia pages | Cloud imaginary vs. governance reality |
| Visual | Satellite imagery, news/corporate photos | Strategic visibility and concealment |
| Financial & ownership | Crunchbase, company registries, REITs | Financialisation of digital infrastructure |
| Contestation signals | News archives, social media | Early indicators of transition pressure |

---

## How to contribute

Contributions of every kind are welcome: data, code, local knowledge, analysis, and conversation.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — full guide covering all contribution pathways
- **[Facility index schema](data/schema/facility_index_schema.md)** — field definitions and data standards
- **[Facility index template](data/schema/facility_index_template.csv)** — CSV template with example rows
- **[GitHub Discussions](../../discussions)** — open conversation about methodology, cases, and findings

You do not need to be a programmer or an academic to contribute. If you know of a planning dispute, a moratorium, or a facility that is missing from the index, that knowledge is valuable.

---

## Data

### What is available

| Resource | Location | License |
|---|---|---|
| Facility index | `data/facility_index/facilities.csv` | CC BY 4.0 |
| Facility index schema | `data/schema/facility_index_schema.md` | CC BY 4.0 |
| WP pipeline scripts | `scripts/` | MIT |
| Analysis notebooks | `notebooks/` | MIT |

### What is needed

The facility index is the foundation everything else depends on. Priority gaps include:

- Southeast Asian markets (Singapore, Malaysia, Indonesia)
- Latin American markets (Brazil, Chile, Mexico)
- African markets (South Africa, Nigeria, Kenya)
- Secondary European markets beyond the AMS-LON-FRA corridor
- Detailed ownership chain documentation for APAC operators
- Planning dispute records for any jurisdiction with active moratoriums or community resistance

If you can fill any of these gaps — even partially — please see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Repository structure

```
datacentering-cartography/
├── data/
│   ├── facility_index/          # Community-maintained facility records
│   │   └── facilities.csv
│   ├── schema/                  # Schema documentation and template
│   │   ├── facility_index_schema.md
│   │   └── facility_index_template.csv
│   ├── raw/
│   │   ├── corporate-websites/  # WP1
│   │   ├── wikipedia/           # WP1
│   │   ├── visual/              # WP2
│   │   ├── financial/           # WP3
│   │   └── news-social/         # WP4
│   └── processed/
├── notebooks/
├── scripts/
│   ├── wp1/
│   ├── wp2/
│   ├── wp3/
│   └── wp4/
├── outputs/
│   ├── figures/
│   └── tables/
├── docs/
│   └── index.md                 # GitHub Pages landing page
├── CONTRIBUTING.md
└── README.md
```

---

## Background

A bibliometric analysis of 4,757 publications (OpenAlex, 2010–2025) revealed three structural gaps in the literature:

- **Gap 1:** Zero papers engage Multi-Level Perspective, Technological Innovation Systems, Strategic Niche Management, or sociotechnical regimes
- **Gap 2:** Three non-communicating silos — technical efficiency (n≈279), environmental impact (n≈114), socio-political (n≈15)
- **Gap 3:** Rich ethnographic work exists but is invisible to innovation scholars and limited to single sites

Data centers now consume an estimated **400 TWh of electricity per year**. That scale of infrastructure — constituted by human actors and socio-material things, subject to financialisation, planning contestation, and community resistance — demands the conceptual tools that sustainability transitions and STS research have developed. This project builds the empirical foundation to apply them.

---

## Key concepts

- **Datacentering** — the active, socio-material processes through which digital infrastructure is continuously made and remade (siting decisions, planning negotiations, corporate narratives, community contestations)
- **Multimodal cartography** — systematic triangulation across data sources to spatially and relationally reconstruct infrastructure dynamics
- **Financialisation** — the shift in data center ownership from operators to external investors (private equity, pension funds, sovereign wealth funds)
- **Complex Adaptive Systems (CAS)** — the theoretical framing that treats data centers not as fixed objects but as emergent, adaptive assemblages of human and non-human actors

---

## Community

The primary space for open conversation about the project is [GitHub Discussions](../../discussions). You are welcome to:

- Propose new analytical angles or theoretical framings
- Share relevant reports, papers, or news
- Ask questions about methodology or data
- Introduce yourself and your research interests
- Flag a new case or jurisdiction

Discussion is low-barrier by design. Local knowledge, journalism, activism, and policy experience are as valuable here as technical or scholarly expertise.

---

## Requirements

```bash
pip install -r requirements.txt
```

---

## License

Code in this repository is licensed under the [MIT License](LICENSE).
Research outputs (papers, figures, datasets) are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
