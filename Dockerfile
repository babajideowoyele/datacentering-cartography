# Datacentering Cartography — full pipeline container
# Includes all WP1-WP4 dependencies + Hyphe for browser-rendered scraping
#
# Usage:
#   docker build -t datacentering-cartography .
#   docker run -v $(pwd)/data:/app/data \
#              -v $(pwd)/scripts:/app/scripts \
#              -e COPERNICUS_USER=... \
#              -e COPERNICUS_PASSWORD=... \
#              datacentering-cartography \
#              python -m scripts.wp1.scrape_operator_websites \
#                     --config scripts/wp1/config_template.csv \
#                     --output data/raw/corporate-websites

FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    ca-certificates \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy project
COPY . .

# Create data directories
RUN mkdir -p \
    data/raw/corporate-websites \
    data/raw/wikipedia \
    data/raw/visual/satellite \
    data/raw/visual/corporate \
    data/raw/financial \
    data/raw/news-social \
    data/processed \
    outputs/figures \
    outputs/tables

# Default: run WP1 website scraper dry-run to confirm setup
CMD ["python", "-m", "scripts.wp1.scrape_operator_websites", \
     "--config", "scripts/wp1/config_template.csv", \
     "--output", "data/raw/corporate-websites", \
     "--dry-run"]
