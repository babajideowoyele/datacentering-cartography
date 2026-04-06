# Datacentering Cartography

A multimodal research project mapping the sociotechnical dynamics of data center infrastructure.

> **Paper:** *Towards a Cartography of Datacentering: A Multimodal Research Agenda*
> Research Policy 11th Online ECR Conference, April 2026

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

## Repository Structure

```
datacentering-cartography/
├── data/
│   ├── raw/
│   │   ├── corporate-websites/
│   │   ├── wikipedia/
│   │   ├── visual/
│   │   ├── financial/
│   │   └── news-social/
│   └── processed/
├── notebooks/
├── scripts/
├── outputs/
│   ├── figures/
│   └── tables/
└── docs/
```

---

## Background

A bibliometric analysis of 4,757 publications (OpenAlex, 2010–2025) revealed three structural gaps in the literature:

- **Gap 1:** Zero papers engage Multi-Level Perspective, Technological Innovation Systems, Strategic Niche Management, or sociotechnical regimes
- **Gap 2:** Three non-communicating silos — technical efficiency (n≈279), environmental impact (n≈114), socio-political (n≈15)
- **Gap 3:** Rich ethnographic work exists but is invisible to innovation scholars and limited to single sites

---

## Key Concepts

- **Datacentering** — the active, socio-material processes through which digital infrastructure is continuously made and remade (siting decisions, planning negotiations, corporate narratives, community contestations)
- **Multimodal cartography** — systematic triangulation across data sources to spatially and relationally reconstruct infrastructure dynamics
- **Financialisation** — the shift in data center ownership from operators to external investors (private equity, pension funds, sovereign wealth funds)

---

## Requirements

```bash
pip install -r requirements.txt
```

---

## License

Code in this repository is licensed under the [MIT License](LICENSE).
Research outputs (papers, figures, datasets) are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
