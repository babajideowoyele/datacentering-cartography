# Facility Index Schema

This document defines the schema for the community-maintained facility index. The index is the shared empirical backbone of the Datacentering Cartography project — a structured, citable record of data center facilities worldwide.

**Template file:** [`facility_index_template.csv`](facility_index_template.csv)
**Index location:** `data/facility_index/facilities.csv`

Before contributing records, please read the full [contributing guide](../../CONTRIBUTING.md).

---

## Schema version

`1.0` — last revised April 2026

---

## Fields

### `facility_id`

| Property | Value |
|---|---|
| Type | String |
| Required | Yes |
| Format | `{ISO2_country_code}-{city_slug}-{four_digit_sequence}` |
| Example | `US-noVA-0001` |

A unique, stable identifier assigned to each facility record. Use the two-letter ISO 3166-1 alpha-2 country code, a lowercase ASCII slug for the city or metropolitan area, and a zero-padded four-digit sequence number. Once assigned, identifiers should not be reused even if a facility closes. Contact maintainers if you are unsure which ID to assign.

---

### `operator_name`

| Property | Value |
|---|---|
| Type | String |
| Required | Yes |
| Example | `Equinix` |

The name of the entity that operates the facility — i.e., the organisation responsible for day-to-day management. This may differ from the legal owner. Use the operator's most widely used trading name. If unknown, enter `Unknown`.

---

### `parent_company`

| Property | Value |
|---|---|
| Type | String |
| Required | No |
| Example | `Equinix Inc.` |

The ultimate parent company or controlling entity, if the operator is a subsidiary. Leave blank if the operator is itself the top-level entity or if the ownership structure is not publicly known.

---

### `ownership_type`

| Property | Value |
|---|---|
| Type | Controlled vocabulary |
| Required | Yes |
| Allowed values | `operator-owned`, `REIT`, `private-equity`, `sovereign-wealth`, `joint-venture`, `other`, `unknown` |
| Example | `REIT` |

The primary ownership structure of the facility's underlying real estate or operating entity. Definitions:

- `operator-owned` — the operating company directly owns the physical asset
- `REIT` — owned by a Real Estate Investment Trust (e.g., Digital Realty, Iron Mountain)
- `private-equity` — owned or majority-controlled by a private equity fund
- `sovereign-wealth` — owned or majority-controlled by a sovereign wealth fund or state entity
- `joint-venture` — owned through a formal joint venture between two or more distinct entities
- `other` — publicly documented structure that does not fit the above
- `unknown` — ownership structure is not publicly known

If the structure is transitional (e.g., recently acquired), use the current known structure and note the history in `contributor_notes`.

---

### `country`

| Property | Value |
|---|---|
| Type | String |
| Required | Yes |
| Format | Full English country name |
| Example | `United States` |

Full English country name. Use the UN M.49 standard name where applicable.

---

### `region`

| Property | Value |
|---|---|
| Type | String |
| Required | No |
| Example | `Virginia` |

State, province, or equivalent administrative region. For US facilities, use the full state name (not the two-letter abbreviation).

---

### `city`

| Property | Value |
|---|---|
| Type | String |
| Required | Yes |
| Example | `Ashburn` |

City or municipality. For facilities outside city boundaries, use the nearest named settlement or the county/municipality name.

---

### `latitude`

| Property | Value |
|---|---|
| Type | Float |
| Required | No |
| Format | Decimal degrees, WGS84, four decimal places |
| Example | `39.0437` |

Latitude of the facility or campus centroid. Four decimal places (approximately 10 m precision) is sufficient. Do not use more precision than planning documents already make public. Leave blank if only an approximate city-level location is known.

---

### `longitude`

| Property | Value |
|---|---|
| Type | Float |
| Required | No |
| Format | Decimal degrees, WGS84, four decimal places |
| Example | `-77.4875` |

Longitude of the facility or campus centroid. See `latitude` for precision guidance.

---

### `capacity_mw`

| Property | Value |
|---|---|
| Type | Float |
| Required | No |
| Example | `120.0` |

Total IT load capacity in megawatts (MW), as disclosed or reported. This is IT load, not gross power draw. If only a range is reported, use the midpoint and note the range in `contributor_notes`. Leave blank if not publicly known.

---

### `energy_source`

| Property | Value |
|---|---|
| Type | String (semi-colon separated if multiple) |
| Required | No |
| Example | `grid; PPA-wind` |

Primary energy source(s) serving the facility, as documented. Use plain descriptors: `grid`, `on-site-solar`, `PPA-wind`, `PPA-solar`, `nuclear`, `diesel-backup`, `gas-CHP`, etc. This field records what is known or claimed, not an assessment of actual carbon intensity. Note the basis (e.g., operator claim vs. grid mix) in `contributor_notes` if relevant.

---

### `water_source`

| Property | Value |
|---|---|
| Type | String |
| Required | No |
| Example | `municipal` |

Primary water source used for cooling, if known. Suggested values: `municipal`, `on-site-well`, `recycled`, `river`, `none` (for air-cooled facilities), `unknown`.

---

### `planning_status`

| Property | Value |
|---|---|
| Type | Controlled vocabulary |
| Required | Yes |
| Allowed values | `operational`, `under-construction`, `planning-approved`, `planning-pending`, `planning-refused`, `decommissioned`, `unknown` |
| Example | `operational` |

Current planning/operational status of the facility:

- `operational` — facility is in active operation
- `under-construction` — construction has begun
- `planning-approved` — planning permission granted but construction not yet begun
- `planning-pending` — application submitted, decision pending
- `planning-refused` — application refused (may be under appeal)
- `decommissioned` — facility has closed
- `unknown` — status cannot be determined from public sources

---

### `moratorium`

| Property | Value |
|---|---|
| Type | Boolean |
| Required | Yes |
| Example | `false` |

Whether the facility is located in, or subject to, an active or recently lifted moratorium or formal planning pause on new data center development. Values: `true`, `false`. If `true`, describe the moratorium in `moratorium_notes`.

---

### `moratorium_notes`

| Property | Value |
|---|---|
| Type | String |
| Required | No (required if `moratorium` is `true`) |
| Example | `Amsterdam municipality moratorium in effect 2019–2022; lifted subject to sustainability conditions` |

Free-text description of the moratorium: which authority imposed it, when, its scope, and current status. Include source URL if possible.

---

### `community_resistance`

| Property | Value |
|---|---|
| Type | Boolean |
| Required | Yes |
| Example | `false` |

Whether there is documented community opposition, organised resistance, or significant public controversy related to this facility or its planning process. Values: `true`, `false`. If `true`, describe in `community_resistance_notes`.

---

### `community_resistance_notes`

| Property | Value |
|---|---|
| Type | String |
| Required | No (required if `community_resistance` is `true`) |
| Example | `Local residents' group Weerstand Datacenters filed objections in 2023; covered by NRC and De Volkskrant` |

Free-text description of the nature, actors, and current status of community opposition. Cite sources. Do not include personal information about individuals.

---

### `disclosure_level`

| Property | Value |
|---|---|
| Type | Controlled vocabulary |
| Required | Yes |
| Allowed values | `high`, `medium`, `low`, `none` |
| Example | `medium` |

An overall assessment of how much the operator or owner publicly discloses about this facility:

- `high` — detailed public reporting on location, capacity, energy, water, and sustainability metrics
- `medium` — some public disclosure (e.g., location and approximate capacity confirmed, but energy/water not reported)
- `low` — existence is publicly documented but little operational detail is disclosed
- `none` — facility is identified from third-party sources (planning documents, satellite imagery, press reports) with no operator disclosure

---

### `primary_sources`

| Property | Value |
|---|---|
| Type | String (semi-colon separated list of URLs or formal citations) |
| Required | Yes |
| Example | `https://planning.loudoun.gov/case/12345; Hogan, B. (2015). The Hermit Crab: The Infrastructure of Social Media. doi:10.1177/1461444815577493` |

One or more primary sources supporting the record. Every record must have at least one verifiable source. URLs should be as specific as possible (direct link to document, not homepage). For sources behind paywalls, include a formal citation. See [data standards](../../CONTRIBUTING.md#5-data-standards) in the contributing guide.

---

### `last_updated`

| Property | Value |
|---|---|
| Type | Date string |
| Required | Yes |
| Format | `YYYY-MM-DD` |
| Example | `2026-03-15` |

The date on which this record was most recently verified or updated. When editing an existing record, always update this field.

---

### `contributor`

| Property | Value |
|---|---|
| Type | String |
| Required | Yes |
| Example | `github:jsmith` |

The GitHub username or name of the person who created or most recently substantively updated this record, prefixed with `github:` for GitHub usernames. For anonymous contributions, use `anon`. Multiple contributors can be listed separated by semi-colons.

---

### `contributor_notes`

| Property | Value |
|---|---|
| Type | String |
| Required | No |
| Example | `Capacity figure from planning application; operator has not confirmed publicly. Ownership chain inferred from Companies House filings.` |

Optional free-text field for methodological notes, caveats, outstanding uncertainties, or anything else a future contributor should know when updating this record.

---

## Controlled vocabulary summary

| Field | Allowed values |
|---|---|
| `ownership_type` | `operator-owned`, `REIT`, `private-equity`, `sovereign-wealth`, `joint-venture`, `other`, `unknown` |
| `planning_status` | `operational`, `under-construction`, `planning-approved`, `planning-pending`, `planning-refused`, `decommissioned`, `unknown` |
| `moratorium` | `true`, `false` |
| `community_resistance` | `true`, `false` |
| `disclosure_level` | `high`, `medium`, `low`, `none` |

---

## Required vs. optional fields at a glance

| Field | Required |
|---|---|
| `facility_id` | Yes |
| `operator_name` | Yes |
| `parent_company` | No |
| `ownership_type` | Yes |
| `country` | Yes |
| `region` | No |
| `city` | Yes |
| `latitude` | No |
| `longitude` | No |
| `capacity_mw` | No |
| `energy_source` | No |
| `water_source` | No |
| `planning_status` | Yes |
| `moratorium` | Yes |
| `moratorium_notes` | Conditional |
| `community_resistance` | Yes |
| `community_resistance_notes` | Conditional |
| `disclosure_level` | Yes |
| `primary_sources` | Yes |
| `last_updated` | Yes |
| `contributor` | Yes |
| `contributor_notes` | No |
