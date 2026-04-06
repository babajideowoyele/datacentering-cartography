"""
WP2 — analyse_visual_content.py

Analyses corporate imagery to compute a visual "abstraction score" per operator:
the ratio of abstract/interior images vs. exterior/location-specific images.

Pipeline
--------
1. Load all manifest.csv files from data/raw/visual/corporate/
2. For each image in the manifest:
   a. Basic metrics via Pillow: dimensions, aspect ratio, dominant colours
   b. Optional content tagging via a pre-trained image classifier
      (torchvision ResNet or HuggingFace transformers CLIP — with graceful
       fallback if neither is installed)
3. Heuristic abstraction scoring based on classifier labels + alt text keywords
4. Aggregate per operator → output to data/processed/wp2_visual_summary.csv

Usage
-----
    python scripts/wp2/analyse_visual_content.py \
        --imgroot data/raw/visual/corporate \
        --outfile data/processed/wp2_visual_summary.csv \
        [--model {resnet,clip,none}]
"""

from __future__ import annotations

import argparse
import csv
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstraction heuristics
# ---------------------------------------------------------------------------

# Keywords in alt text / classifier labels that suggest an abstract image
# (server rooms, logos, diagrams, render, sustainability icons, etc.)
ABSTRACT_KEYWORDS: frozenset[str] = frozenset(
    [
        "server", "rack", "data center interior", "interior", "logo", "icon",
        "diagram", "chart", "render", "abstract", "circuit", "cable",
        "network", "cloud", "sustainability", "leaf", "green", "energy",
        "badge", "award", "illustration",
    ]
)

# Keywords that suggest exterior / location-specific imagery
EXTERIOR_KEYWORDS: frozenset[str] = frozenset(
    [
        "building", "exterior", "facade", "campus", "aerial", "rooftop",
        "parking", "entrance", "facility", "warehouse", "construction",
        "satellite", "map", "location", "city", "landscape", "sky",
        "cooling tower", "substation",
    ]
)


def heuristic_label(alt_text: str, classifier_labels: list[str]) -> str:
    """
    Return 'abstract', 'exterior', or 'unknown' based on keyword matching
    across alt text and classifier labels.
    """
    combined = (alt_text + " " + " ".join(classifier_labels)).lower()
    abstract_hits = sum(1 for kw in ABSTRACT_KEYWORDS if kw in combined)
    exterior_hits = sum(1 for kw in EXTERIOR_KEYWORDS if kw in combined)

    if abstract_hits > exterior_hits:
        return "abstract"
    if exterior_hits > abstract_hits:
        return "exterior"
    return "unknown"


# ---------------------------------------------------------------------------
# Basic image analysis (Pillow)
# ---------------------------------------------------------------------------

def analyse_with_pillow(image_path: Path) -> Optional[dict]:
    """
    Return basic image metrics using Pillow.
    Returns None if the image cannot be opened.
    """
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        logger.warning("Pillow not installed. Run: pip install Pillow")
        return None

    try:
        with Image.open(image_path) as img:
            width, height = img.size
            aspect_ratio = round(width / height, 3) if height else None
            mode = img.mode

            # Dominant colour: reduce to palette and take most common
            dominant_colour = _dominant_colour(img)

            return {
                "width_px": width,
                "height_px": height,
                "aspect_ratio": aspect_ratio,
                "colour_mode": mode,
                "dominant_colour_hex": dominant_colour,
            }
    except Exception as exc:
        logger.debug("Pillow failed on %s: %s", image_path, exc)
        return None


def _dominant_colour(img) -> str:
    """Return the most common colour in the image as a hex string."""
    try:
        from PIL import Image  # type: ignore

        # Convert to RGB (handles RGBA, P, etc.)
        rgb = img.convert("RGB")
        # Resize to speed up; 50x50 is plenty for dominant colour
        rgb = rgb.resize((50, 50), Image.LANCZOS)
        pixels = list(rgb.getdata())
        # Quantise to avoid near-duplicate colours
        quantised = [
            (r // 32 * 32, g // 32 * 32, b // 32 * 32) for r, g, b in pixels
        ]
        most_common = Counter(quantised).most_common(1)[0][0]
        return "#{:02x}{:02x}{:02x}".format(*most_common)
    except Exception:
        return "#unknown"


# ---------------------------------------------------------------------------
# Optional: content classification
# ---------------------------------------------------------------------------

def classify_with_resnet(image_path: Path, top_k: int = 3) -> list[str]:
    """
    Tag image using torchvision ResNet50 (ImageNet classes).
    Returns list of label strings, or empty list if unavailable.
    """
    try:
        import torch  # type: ignore
        from torchvision import models, transforms  # type: ignore
        from torchvision.models import ResNet50_Weights  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        return []

    try:
        weights = ResNet50_Weights.DEFAULT
        model = models.resnet50(weights=weights)
        model.eval()
        preprocess = weights.transforms()

        with Image.open(image_path) as img:
            img_rgb = img.convert("RGB")
            tensor = preprocess(img_rgb).unsqueeze(0)

        with torch.no_grad():
            out = model(tensor)

        probabilities = torch.nn.functional.softmax(out[0], dim=0)
        top_indices = probabilities.topk(top_k).indices.tolist()
        labels = [weights.meta["categories"][i].lower() for i in top_indices]
        return labels
    except Exception as exc:
        logger.debug("ResNet classification failed for %s: %s", image_path, exc)
        return []


def classify_with_clip(image_path: Path) -> list[str]:
    """
    Tag image using HuggingFace CLIP zero-shot classification against
    a set of data-center-relevant candidate labels.
    Returns list of matched label strings, or empty list if unavailable.
    """
    try:
        from transformers import pipeline  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        return []

    candidate_labels = [
        "server room interior",
        "data center exterior",
        "building facade",
        "cooling tower",
        "renewable energy",
        "corporate logo",
        "aerial view",
        "warehouse",
        "abstract diagram",
    ]

    try:
        classifier = pipeline(
            "zero-shot-image-classification",
            model="openai/clip-vit-base-patch32",
        )
        with Image.open(image_path) as img:
            img_rgb = img.convert("RGB")
        result = classifier(img_rgb, candidate_labels=candidate_labels)
        # Return labels above a threshold
        return [r["label"] for r in result if r["score"] > 0.15]
    except Exception as exc:
        logger.debug("CLIP classification failed for %s: %s", image_path, exc)
        return []


def classify_image(image_path: Path, model: str) -> list[str]:
    """Dispatch to the requested classifier, or return empty list."""
    if model == "resnet":
        return classify_with_resnet(image_path)
    if model == "clip":
        return classify_with_clip(image_path)
    return []


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------

def load_manifest(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Per-operator analysis
# ---------------------------------------------------------------------------

def analyse_operator(
    operator_name: str,
    op_dir: Path,
    model: str,
) -> dict:
    """
    Process all images for one operator and return a summary dict.
    """
    manifest_path = op_dir / "manifest.csv"
    if not manifest_path.exists():
        logger.warning("No manifest for %s; skipping.", operator_name)
        return {}

    records = load_manifest(manifest_path)
    if not records:
        return {}

    label_counts: Counter = Counter()
    total_width = 0
    total_height = 0
    valid_images = 0

    for rec in records:
        filename = rec.get("filename", "")
        if not filename:
            continue

        image_path = op_dir / filename
        if not image_path.exists():
            continue

        # Pillow metrics
        pillow_meta = analyse_with_pillow(image_path)
        if pillow_meta:
            total_width += pillow_meta["width_px"]
            total_height += pillow_meta["height_px"]
            valid_images += 1

        # Classifier labels
        classifier_labels = classify_image(image_path, model)

        # Heuristic label
        label = heuristic_label(rec.get("alt_text", ""), classifier_labels)
        label_counts[label] += 1

    total_labelled = sum(label_counts.values())
    abstract_count = label_counts.get("abstract", 0)
    exterior_count = label_counts.get("exterior", 0)
    unknown_count = label_counts.get("unknown", 0)

    abstraction_score = (
        abstract_count / total_labelled if total_labelled > 0 else None
    )

    return {
        "operator_name": operator_name,
        "total_images": len(records),
        "analysed_images": valid_images,
        "abstract_count": abstract_count,
        "exterior_count": exterior_count,
        "unknown_count": unknown_count,
        "abstraction_score": round(abstraction_score, 4) if abstraction_score is not None else "",
        "avg_width_px": round(total_width / valid_images) if valid_images else "",
        "avg_height_px": round(total_height / valid_images) if valid_images else "",
        "classifier_model": model,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse corporate imagery and compute abstraction scores (WP2)."
    )
    parser.add_argument(
        "--imgroot",
        type=Path,
        default=Path("data/raw/visual/corporate"),
        help="Root directory containing per-operator image folders.",
    )
    parser.add_argument(
        "--outfile",
        type=Path,
        default=Path("data/processed/wp2_visual_summary.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--model",
        choices=["resnet", "clip", "none"],
        default="none",
        help=(
            "Image classifier to use for content tagging. "
            "'resnet' requires torchvision; 'clip' requires transformers. "
            "Defaults to 'none' (heuristic alt-text only)."
        ),
    )
    args = parser.parse_args()

    if not args.imgroot.exists():
        logger.error("Image root directory not found: %s", args.imgroot)
        return

    summaries: list[dict] = []
    for op_dir in sorted(args.imgroot.iterdir()):
        if not op_dir.is_dir():
            continue
        operator_name = op_dir.name
        logger.info("Analysing operator: %s", operator_name)
        summary = analyse_operator(operator_name, op_dir, args.model)
        if summary:
            summaries.append(summary)

    if not summaries:
        logger.warning("No operator data found. Run collect_corporate_imagery.py first.")
        return

    args.outfile.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "operator_name", "total_images", "analysed_images",
        "abstract_count", "exterior_count", "unknown_count",
        "abstraction_score", "avg_width_px", "avg_height_px",
        "classifier_model",
    ]
    with args.outfile.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)

    logger.info("Visual summary written to %s (%d operators)", args.outfile, len(summaries))


if __name__ == "__main__":
    main()
