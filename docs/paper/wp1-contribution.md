# WP1 Contribution: Corporate and Territorial Text

## Data Sources, Method, and Analytical Logic

Work Package 1 constructs a comparative textual corpus drawn from two distinct
registers of self-presentation: the corporate websites of major data center
operators, and the Wikipedia articles for the cities and counties in which those
operators are materially embedded. The corpus is structured around operator–city
pairings — currently anchored by Amazon Web Services paired with Ashburn
(Loudoun County, Virginia), Equinix paired with Amsterdam, and Digital Realty
paired with Dallas — but the scaffolding is designed to accommodate the full
comparative spine of the project.

For the corporate side, `scrape_operator_websites.py` targets three page types
per operator: sustainability pages, facility or data-center listing pages, and
about pages. The scraper extracts plain text, structured metadata (title, meta
description, image alt tags), and internal links whose URLs suggest a
facility-geography relationship. A predefined keyword vocabulary — spanning
energy, water, carbon, location, sustainability, financial, and community terms
— is applied at collection time, producing normalised frequency counts per page
that carry through to analysis. The scraper operates within a robots.txt
compliance wrapper and self-identifies via a research user-agent string, making
the data collection methodologically transparent.

For the territorial side, `scrape_wikipedia.py` retrieves the full Wikipedia
article for each city, parsing it into sections and flagging every sentence that
contains a direct reference to data centers or data centres. The sections
targeted as analytically significant — Economy, Infrastructure, Environment,
Transport, Industry — are those where data center presence might surface as
civic or geographic fact rather than as brand narrative. Wikipedia is not
treated here as ground truth; it is treated as a counter-register, reflecting
encyclopaedic and community-assembled territorial description rather than
operator-controlled communication.

The `analyse_divergence.py` script then computes several metrics across each
operator–city pair: an Environmental Claim Index (a weighted density score
combining carbon, energy, sustainability, and water vocabulary); VADER-based
sentiment polarity averaged across paragraphs; a data-center mention asymmetry
score (how many times each source references data centers, normalised); and a
keyword-by-category matrix flattened for heatmap visualisation. The key output
metrics are *divergence* figures — corporate ECI minus Wikipedia ECI, corporate
sentiment minus Wikipedia sentiment, and the absolute gap in data-center mention
frequency. These divergence scores operationalise, in a deliberately modest
computational register, the imaginary-gap that is the theoretical object of WP1.

## The Conceptual Dimension: Imaginaries, Territorial Claims, and the Cloud Rhetoric Gap

WP1 speaks directly to Phillips and Ritala's conceptual dimension of
socio-material assemblages: the boundaries actors draw, the perspectives they
project, and the imaginaries they maintain. What the corporate website corpus
reveals is not simply promotional language but a structured act of
*placelessness production*. Operators consistently foreground the abstracted
properties of infrastructure — efficiency, renewable energy commitments,
global network reach, carbon neutrality targets — while largely evacuating the
spatial and political content of what it means to build at scale in a specific
locality. The language of "the cloud" functions here as an imaginary that
decouples computation from territory, positioning data center campuses as nodes
in a universal technical commons rather than as large-scale industrial land uses
embedded in particular water sheds, power grids, and communities.

The notebook frames this explicitly: corporate website text constructs data
center operators as "responsible stewards of infrastructure" while obscuring
"local land use, water consumption, community impact." The analytical
diagnostic is keyword asymmetry. A high sustainability-to-community ratio in
the keyword matrix signals what the notebook labels a greenwashing pattern —
environmental claims detached from local territorial accountability. A high
energy-to-location ratio signals an efficiency framing that abstracts spatial
politics into technical performance. Conversely, high carbon and high water
vocabulary together suggest more holistic environmental disclosure, including
the kinds of claims that invite territorial scrutiny. The absence of terms like
"planning," "objection," "noise," or "neighbourhood" in corporate text is
treated as analytically significant: their disappearance from the page
constructs the infrastructure as placeless.

## The USA–Europe Comparison

The comparative spine makes the conceptual gap legible across two different
governance regimes. In the American case, Equinix and AWS describe Ashburn and
the broader Northern Virginia cluster in terms of network density, carrier
diversity, hyperscale capacity, and sustainability commitments that foreground
energy sourcing. The territory — Loudoun County, now routinely described in
trade press as "Data Center Alley" — appears in corporate text as a topology
of opportunity: low-latency proximity to federal and financial users, a
favourable regulatory climate, an energy-rich region. What is largely absent is
the material friction that has begun to surface in planning hearings, water
studies, and local electoral politics. The Wikipedia article for Ashburn, by
contrast, has begun to accumulate the territorial acknowledgement of this
infrastructure: data center references appear in economic and infrastructure
sections, though the encyclopaedic register still lags the pace of land-use
contestation on the ground.

In the European case, the contrast is structurally different. Equinix's
Amsterdam materials operate within a context shaped by the Amsterdam data
center moratorium (2019–2020), the Dutch national spatial strategy on data
center siting, and growing municipal anxiety about energy and water consumption.
The company's sustainability page therefore cannot simply produce the cloud
imaginary without acknowledging its territorial footprint, because the
regulatory and public discourse environment demands some form of territorial
accountability. The vocabulary of "sustainability" is accordingly denser in the
Amsterdam-linked materials, but the question WP1 asks is whether that density
reflects genuine territorial embeddedness or a more sophisticated form of the
same placelessness production — one that speaks the language of green
infrastructure while still resisting the spatial specificity that community and
planning actors demand. Amsterdam's Wikipedia article carries a comparatively
richer data-center-mention count, reflecting years of public debate that have
made the infrastructure visible in civic description in ways that remain
unusual for American counterparts.

The divergence scores thus function differently across the two cases. In the
Northern Virginia pairing, a high ECI divergence (high corporate, low
Wikipedia) would indicate the classic cloud imaginary gap: operators claiming
green credentials that have not yet penetrated territorial self-description. In
Amsterdam, a lower ECI divergence might indicate either genuine convergence or
a more sophisticated rhetorical absorption of territorial critique — a
distinction that requires the close reading the keyword matrix enables but
cannot resolve on its own.

## Analytical Outputs and What Remains to Be Built

The pipeline as built produces two structured outputs: `wp1_divergence_summary.csv`,
a per-operator-city record of divergence metrics and sentiment scores, and
`wp1_keyword_matrix.csv`, a long-format table of keyword category counts and
token-normalised densities for both corporate and Wikipedia sources. The
notebook `01_explore_operator_websites.ipynb` provides the exploratory layer:
word frequency analysis, keyword heatmaps, and a preliminary divergence
overview once `analyse_divergence.py` has been run. The infrastructure for
structured comparison is therefore in place.

What remains to be built is the populated corpus. The config template currently
holds three operator–city pairings; the full comparative argument requires
expanding this to cover additional Northern Virginia operators (including
hyperscalers beyond AWS, and colocation players such as CyrusOne and Iron
Mountain), the broader Amsterdam cluster, and ideally one or two
further-European comparison points (Frankfurt, Dublin) to test whether the
Dutch regulatory environment produces measurable imaginary differences relative
to lighter-touch European regimes. A second notebook for divergence analysis
proper — flagged as `02_divergence_analysis.ipynb` in the existing code — is
designed but not yet written, and the image alt-tag analysis begun in the
scraper but not yet foregrounded in the notebook could yield a complementary
visual-rhetorical layer: how operators represent their infrastructure
photographically is itself a site of imaginary production that the keyword
analysis of body text does not capture.
