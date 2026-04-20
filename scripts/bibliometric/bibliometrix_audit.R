## Bibliometric audit — data center literature, 2010-2025
## Uses openalexR + bibliometrix to build concept co-occurrence network
##
## Run from repo root:
##   Rscript scripts/bibliometric/bibliometrix_audit.R
##
## Outputs:
##   data/processed/bibliometric/concept_network.pdf
##   data/processed/bibliometric/concept_network_bw.pdf  (slide-ready)
##   data/processed/bibliometric/keyword_cooccurrence.pdf
##   data/processed/bibliometric/works_raw.rds           (cached fetch)
##   data/processed/bibliometric/M.rds                   (bibliometrix df)

library(openalexR)
library(bibliometrix)
library(tidyverse)
library(igraph)

OUT_DIR <- "data/processed/bibliometric"
dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)

## ---------------------------------------------------------------------------
## 1. Fetch corpus from OpenAlex
##    "data centre" in title, 2010-2025 (European spelling — ~4,800 works)
##    Cache to RDS so re-runs are fast
## ---------------------------------------------------------------------------
rds_raw <- file.path(OUT_DIR, "works_raw.rds")

if (file.exists(rds_raw)) {
  message("Loading cached fetch from ", rds_raw)
  works <- readRDS(rds_raw)
} else {
  message("Fetching from OpenAlex (this takes a few minutes)...")
  works <- oa_fetch(
    entity        = "works",
    title.search  = "data centre",
    publication_year = c(2010, 2025),
    mailto        = "babajide.owoyele@gmail.com",
    verbose       = TRUE
  )
  saveRDS(works, rds_raw)
  message("Saved ", nrow(works), " works to ", rds_raw)
}

message("Corpus size: ", nrow(works), " works")

## ---------------------------------------------------------------------------
## 2. Convert to bibliometrix data frame
## ---------------------------------------------------------------------------
rds_M <- file.path(OUT_DIR, "M.rds")

if (file.exists(rds_M)) {
  M <- readRDS(rds_M)
} else {
  M <- convert2df(works, dbsource = "openalex", format = "api")
  saveRDS(M, rds_M)
}

message("bibliometrix df: ", nrow(M), " rows, ", ncol(M), " cols")

## Basic descriptives
results <- biblioAnalysis(M, sep = ";")
cat("\n--- Summary ---\n")
summary(results, k = 10, pause = FALSE)

## ---------------------------------------------------------------------------
## 3. Concept / keyword co-occurrence network
##    DE = Author Keywords; ID = OpenAlex concepts (more complete)
## ---------------------------------------------------------------------------

## Use OpenAlex concepts (ID field) — richer than author keywords
NetMatrix_concept <- biblioNetwork(
  M,
  analysis   = "co-occurrences",
  network    = "keywords",   # uses ID field (concepts)
  sep        = ";",
  short      = TRUE
)

## Remove very rare nodes (< 5 co-occurrences) for clarity
NetMatrix_concept <- NetMatrix_concept[
  rowSums(NetMatrix_concept) >= 5,
  colSums(NetMatrix_concept) >= 5
]

message("Concept network: ", nrow(NetMatrix_concept), " nodes")

## ---------------------------------------------------------------------------
## 4. Plot — colour palette matching the paper
## ---------------------------------------------------------------------------
DC_BLUE  <- "#1f497d"
DC_RED   <- "#c0504d"
DC_GRAY  <- "#888888"

## Full-colour version
pdf(file.path(OUT_DIR, "concept_network.pdf"), width = 14, height = 10)
net_out <- networkPlot(
  NetMatrix_concept,
  n             = 80,          # top 80 nodes by degree
  Title         = "Data centre literature: concept co-occurrence network (OpenAlex, 2010-2025)",
  type          = "fruchterman",
  size          = 5,
  size.cex      = TRUE,
  labelsize     = 0.7,
  halo          = FALSE,
  cluster       = "walktrap",
  community.repulsion = 0.1,
  normalize     = FALSE,
  weighted      = TRUE,
  edgesize      = 2,
  edges.min     = 2,
  label.cex     = TRUE,
  verbose       = FALSE
)
dev.off()
message("Saved concept_network.pdf")

## ---------------------------------------------------------------------------
## 5. Black-and-white version for slides
## ---------------------------------------------------------------------------
pdf(file.path(OUT_DIR, "concept_network_bw.pdf"), width = 12, height = 9)
net_bw <- networkPlot(
  NetMatrix_concept,
  n             = 60,
  Title         = "",
  type          = "fruchterman",
  size          = 4,
  size.cex      = TRUE,
  labelsize     = 0.65,
  halo          = FALSE,
  cluster       = "walktrap",
  community.repulsion = 0.1,
  normalize     = FALSE,
  weighted      = TRUE,
  edgesize      = 1.5,
  edges.min     = 3,
  label.cex     = TRUE,
  verbose       = FALSE
)
dev.off()
message("Saved concept_network_bw.pdf")

## ---------------------------------------------------------------------------
## 6. Keyword co-occurrence (author keywords — DE field)
##    Sparser but shows exact terms authors use
## ---------------------------------------------------------------------------
has_DE <- sum(!is.na(M$DE) & M$DE != "") > 100

if (has_DE) {
  NetMatrix_kw <- biblioNetwork(
    M,
    analysis = "co-occurrences",
    network  = "author_keywords",
    sep      = ";",
    short    = TRUE
  )
  NetMatrix_kw <- NetMatrix_kw[
    rowSums(NetMatrix_kw) >= 3,
    colSums(NetMatrix_kw) >= 3
  ]

  pdf(file.path(OUT_DIR, "keyword_cooccurrence.pdf"), width = 14, height = 10)
  networkPlot(
    NetMatrix_kw,
    n             = 60,
    Title         = "Data centre literature: author keyword co-occurrence (OpenAlex, 2010-2025)",
    type          = "fruchterman",
    size          = 5,
    size.cex      = TRUE,
    labelsize     = 0.7,
    halo          = FALSE,
    cluster       = "walktrap",
    community.repulsion = 0.1,
    normalize     = FALSE,
    weighted      = TRUE,
    edgesize      = 2,
    edges.min     = 2,
    label.cex     = TRUE,
    verbose       = FALSE
  )
  dev.off()
  message("Saved keyword_cooccurrence.pdf")
} else {
  message("Skipping author keyword network — insufficient DE data from OpenAlex")
}

## ---------------------------------------------------------------------------
## 7. Annual production plot
## ---------------------------------------------------------------------------
pdf(file.path(OUT_DIR, "annual_production.pdf"), width = 8, height = 5)
annual <- M %>%
  filter(!is.na(PY), PY >= 2010, PY <= 2025) %>%
  count(PY) %>%
  rename(year = PY, papers = n)

ggplot(annual, aes(year, papers)) +
  geom_col(fill = DC_BLUE, width = 0.7) +
  geom_smooth(method = "loess", se = FALSE, colour = DC_RED, linewidth = 0.8) +
  scale_x_continuous(breaks = seq(2010, 2025, 2)) +
  labs(
    title    = "Data centre literature: annual output (OpenAlex, 2010-2025)",
    subtitle = sprintf("n = %s works; 'data centre' in title", format(nrow(M), big.mark = ",")),
    x        = NULL,
    y        = "Publications"
  ) +
  theme_minimal(base_size = 12) +
  theme(panel.grid.minor = element_blank())
dev.off()
message("Saved annual_production.pdf")

## ---------------------------------------------------------------------------
## 8. Thematic map (keyword clusters by centrality vs density)
## ---------------------------------------------------------------------------
pdf(file.path(OUT_DIR, "thematic_map.pdf"), width = 10, height = 8)
tryCatch({
  thematicMap(
    net_out,
    NetMatrix_concept,
    minfreq   = 5,
    stemming  = FALSE,
    size      = 0.7,
    n         = 1000,
    repel     = TRUE
  )
}, error = function(e) message("Thematic map failed: ", e$message))
dev.off()
message("Saved thematic_map.pdf")

message("\nAll outputs written to ", OUT_DIR)
message("Key files for the paper:")
message("  concept_network_bw.pdf  -> manuscript/figures/ (slide-ready)")
message("  concept_network.pdf     -> full colour version")
message("  keyword_cooccurrence.pdf -> author keyword clusters")
message("  annual_production.pdf   -> growth trajectory figure")
