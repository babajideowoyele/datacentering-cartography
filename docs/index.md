---
layout: default
title: Datacentering Cartography
description: Open research infrastructure for mapping the sociotechnical dynamics of data center development
---

# Datacentering Cartography

**Open research infrastructure for mapping the sociotechnical dynamics of data center development.**

---

## The problem

Data centers now consume an estimated **400 TWh of electricity per year** — roughly 1.5% of global electricity demand, and rising. They underpin the cloud services, AI inference workloads, and digital communication that innovation scholars increasingly study. Yet the physical infrastructure behind "the cloud" remains almost entirely invisible to sustainability transitions research, science and technology studies, and innovation policy.

This invisibility is not accidental. Operators strategically conceal facility locations, energy sources, water consumption, and emissions. No public database exists. Planning disputes flare and pass with little systematic documentation. Ownership chains run through REITs, sovereign wealth funds, and shell companies across multiple jurisdictions.

Three structural gaps in the literature make this worse:

- **No sociotechnical framing:** a bibliometric analysis of 4,757 publications (OpenAlex, 2010–2025) found zero papers engaging Multi-Level Perspective, Technological Innovation Systems, or sociotechnical regime concepts
- **Three non-communicating silos:** technical efficiency, environmental impact, and socio-political research do not speak to each other
- **Ethnographic isolation:** rich qualitative work on single sites is invisible to the broader innovation scholarship community

---

## What this project does

Datacentering Cartography develops a **multimodal cartographic methodology** for studying data centers as **Complex Adaptive Systems** constituted by human actors and socio-material things. Rather than treating a data center as a fixed object, we study *datacentering* — the continuous socio-material processes through which this infrastructure is made and remade.

The methodology triangulates across four work packages:

| Work Package | Data Sources | Research Focus |
|---|---|---|
| **WP1** Corporate & territorial | Operator websites, city Wikipedia pages | Cloud imaginary vs. governance reality |
| **WP2** Visual | Satellite imagery, news and corporate photos | Strategic visibility and concealment |
| **WP3** Financial & ownership | Company registries, REITs, Crunchbase | Financialisation of digital infrastructure |
| **WP4** Contestation signals | News archives, social media | Early indicators of transition pressure |

Each work package feeds into a **community-maintained facility index** — a structured, citable, openly licensed database of data center facilities, their ownership structures, planning histories, and contestation signals.

---

## How to contribute

This project is a research commons. Contributions of every kind are welcome:

- **Data:** add records to the facility index, correct errors, add sources
- **Code:** build or improve WP pipeline scripts
- **Local knowledge:** flag new cases, planning disputes, or jurisdictions
- **Analysis:** open a Discussion about methodology or findings

See the full [Contributing Guide](../CONTRIBUTING.md) for detailed instructions on each pathway.

The facility index schema and CSV template are in [`data/schema/`](../data/schema/).

You do not need to be a programmer or an academic to contribute. If you know of a planning dispute, a moratorium, a community resistance campaign, or simply a facility that is not in the index, that knowledge is valuable here.

---

## How to use the data

The facility index is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). You are free to use, adapt, and redistribute it for any purpose, including commercial research, provided you attribute the source.

If you use data from this project in published research, please cite the project and the individual record's `contributor` and `primary_sources` fields. Attribution sustains the community that maintains the data.

**Data location:** `data/facility_index/facilities.csv`
**Schema:** [`data/schema/facility_index_schema.md`](../data/schema/facility_index_schema.md)
**Template:** [`data/schema/facility_index_template.csv`](../data/schema/facility_index_template.csv)

Code in the repository is licensed under the [MIT License](../LICENSE).

---

## The paper

This infrastructure is developed alongside a research paper:

> *Towards a Cartography of Datacentering: A Multimodal Research Agenda*
> Research Policy 11th Online ECR Conference, April 2026

The paper lays out the theoretical framing (Complex Adaptive Systems, datacentering as active process, multimodal triangulation), documents the bibliometric gaps, and describes the methodology in detail.

---

## Community and contact

Conversations about the project happen in [GitHub Discussions](../../discussions). Open a thread to:

- Propose a new case or jurisdiction
- Ask questions about the methodology or data
- Share relevant reports or findings
- Introduce yourself

For direct contact, open a Discussion or an issue on GitHub.

---

*Datacentering Cartography is open research infrastructure. Code: MIT. Data: CC BY 4.0.*
