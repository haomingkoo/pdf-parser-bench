#!/usr/bin/env python3
"""
Download public PDF test datasets for the parsing evaluation sandbox.

All datasets are publicly available and free to use for research.
No registration or API key required.

Datasets downloaded:
1. FUNSD — 199 annotated noisy scanned forms (EPFL 2019)
   - Best proxy for complaint forms (scanned, noisy, KVP annotation)
   - URL: https://guillaumejaume.github.io/FUNSD/

2. SROIE — Scanned receipts (ICDAR 2019)
   - 1,000 annotated receipts; useful for KVP + table extraction baseline

3. DocLayNet samples — Layout-annotated enterprise documents (IBM 2022)
   - Available via HuggingFace datasets
   - Covers financial reports, patents, scientific docs, government docs

4. IAM Handwriting Database (subset) — Handwritten text lines
   - WARNING: requires free registration at https://fki.tic.heia-fr.ch/databases/iam-handwriting-database
   - Download manually and place in data/raw/handwritten_majority/

5. PubLayNet samples — Scientific paper layout (IBM 2019)
   - Available via HuggingFace datasets

IMPORTANT:
- These datasets are for research/evaluation only
- Do NOT use real customer complaint forms with PII for benchmarking
- Synthesize complaint-form-like PDFs using tools like Faker + ReportLab for domain-specific testing

Usage:
    python scripts/download_datasets.py
    python scripts/download_datasets.py --dataset funsd
    python scripts/download_datasets.py --dataset sroie
    python scripts/download_datasets.py --list
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

DATA_DIR = Path("data/raw")
GT_DIR = Path("data/ground_truth")


def download_file(url: str, dest: Path, desc: str = "") -> None:
    """Download a file with progress bar."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    with open(dest, "wb") as f, tqdm(
        total=total, unit="B", unit_scale=True, desc=desc or dest.name
    ) as bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))


def download_funsd() -> None:
    """
    Download FUNSD: Form Understanding in Noisy Scanned Documents.

    Contents: 199 annotated scanned business forms
    - Training set: 149 forms
    - Testing set: 50 forms
    - Annotations: bounding boxes, text, entity labels (header, question, answer, other)
    - Ground truth: JSON with words, bounding boxes, label, linking

    Citation: Jaume et al., ICDAR-OST 2019 (arXiv:1905.13538)

    Note: These are business/administrative forms, not complaint forms specifically.
    They are the closest publicly available proxy. FUNSD does NOT contain
    customer complaint form layouts or complaint-specific vocabulary.
    """
    print("\n=== Downloading FUNSD ===")
    url = "https://guillaumejaume.github.io/FUNSD/dataset.zip"
    zip_path = DATA_DIR / "funsd.zip"

    try:
        download_file(url, zip_path, desc="FUNSD")

        funsd_dir = DATA_DIR / "scanned_clean_300dpi"
        funsd_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(DATA_DIR / "_funsd_raw")

        # Convert FUNSD annotations to our ground truth format
        funsd_raw = DATA_DIR / "_funsd_raw" / "dataset" / "testing_data"
        if funsd_raw.exists():
            _convert_funsd_annotations(funsd_raw)
            print(f"FUNSD test set converted: {funsd_dir}")
        else:
            print(f"WARNING: Expected {funsd_raw} not found. Check zip structure.")

        zip_path.unlink(missing_ok=True)

    except requests.RequestException as e:
        print(f"ERROR downloading FUNSD: {e}")
        print("Manual download: https://guillaumejaume.github.io/FUNSD/dataset.zip")


def _convert_funsd_annotations(funsd_raw: Path) -> None:
    """
    Convert FUNSD annotation format to our ground truth JSON format.

    FUNSD format: {"form": [{"id": int, "text": str, "box": [...], "linking": [...], "label": str, "words": [...]}]}
    Our format:   {"full_text": str, "fields": [{"name": str, "value": str, "type": str}], "tables": []}
    """
    GT_DIR.mkdir(parents=True, exist_ok=True)
    images_dir = funsd_raw / "images"
    annotations_dir = funsd_raw / "annotations"

    if not annotations_dir.exists():
        return

    out_dir_pdf = DATA_DIR / "scanned_clean_300dpi"
    out_dir_pdf.mkdir(parents=True, exist_ok=True)

    for ann_file in annotations_dir.glob("*.json"):
        with open(ann_file) as f:
            funsd_ann = json.load(f)

        form_items = funsd_ann.get("form", [])

        # Extract questions (field names) and answers (field values)
        questions: dict[int, str] = {}
        answers: dict[int, str] = {}

        for item in form_items:
            label = item.get("label", "")
            text = item.get("text", "")
            item_id = item.get("id")
            if label == "question":
                questions[item_id] = text
            elif label == "answer":
                answers[item_id] = text

        # Build KV pairs using linking
        fields = []
        full_text_parts = []

        for item in form_items:
            full_text_parts.append(item.get("text", ""))

            if item.get("label") == "question":
                q_text = item.get("text", "")
                # Find linked answers
                linked_answers = []
                for link in item.get("linking", []):
                    linked_id = link[1] if len(link) > 1 else None
                    if linked_id and linked_id in answers:
                        linked_answers.append(answers[linked_id])

                fields.append({
                    "name": q_text,
                    "value": " ".join(linked_answers),
                    "type": "text",
                })

        gt = {
            "full_text": " ".join(full_text_parts),
            "fields": fields,
            "tables": [],
            "source": "funsd",
        }

        gt_out = GT_DIR / f"{ann_file.stem}.json"
        with open(gt_out, "w") as f:
            json.dump(gt, f, indent=2)

        # Copy image (PNG) to our scanned_clean_300dpi directory
        img_src = images_dir / f"{ann_file.stem}.png"
        if img_src.exists():
            shutil.copy(img_src, out_dir_pdf / f"{ann_file.stem}.png")


def download_hf_dataset_samples(dataset_name: str, subset: str, dest_subdir: str, n_samples: int = 50) -> None:
    """
    Download sample PDFs/images from a HuggingFace dataset.
    Requires: pip install datasets
    """
    try:
        from datasets import load_dataset
        print(f"\n=== Downloading {dataset_name} (first {n_samples} samples) ===")
        ds = load_dataset(dataset_name, subset, split="test", streaming=True, trust_remote_code=True)
        dest = DATA_DIR / dest_subdir
        dest.mkdir(parents=True, exist_ok=True)

        count = 0
        for sample in ds:
            if count >= n_samples:
                break
            img = sample.get("image")
            if img:
                img.save(dest / f"{dataset_name.replace('/', '_')}_{count:04d}.png")
            count += 1
        print(f"Downloaded {count} samples to {dest}")
    except ImportError:
        print("ERROR: 'datasets' package not installed. Run: pip install datasets")
    except Exception as e:
        print(f"ERROR downloading {dataset_name}: {e}")


def generate_synthetic_complaint_forms(n: int = 20) -> None:
    """
    Generate synthetic complaint form PDFs for testing.
    Uses Faker for realistic data and ReportLab for PDF generation.

    IMPORTANT: These are synthetic — do not use real customer data.
    The generated forms mimic typical financial/insurance complaint layouts.
    """
    try:
        from faker import Faker
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        print("ERROR: faker and reportlab required. Run: pip install faker reportlab")
        return

    fake = Faker()
    dest = DATA_DIR / "digital_acroform"
    dest.mkdir(parents=True, exist_ok=True)
    gt_dest = GT_DIR
    gt_dest.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Generating {n} synthetic complaint forms ===")

    for i in range(n):
        form_id = f"synthetic_complaint_{i:04d}"
        pdf_path = dest / f"{form_id}.pdf"

        # Synthetic data (no real PII)
        fields_data = {
            "complainant_name": fake.name(),
            "complaint_date": fake.date_this_decade().strftime("%m/%d/%Y"),
            "account_number": f"ACCT-{fake.numerify('########')}",
            "complaint_type": fake.random_element(["Billing Error", "Service Failure", "Unauthorized Charge", "Other"]),
            "amount_disputed": f"${fake.pydecimal(left_digits=4, right_digits=2, positive=True)}",
            "complaint_description": fake.paragraph(nb_sentences=5),
        }

        # Human-readable labels for each field (what is actually drawn in the PDF).
        human_labels = {
            "complainant_name":      "Complainant Name",
            "complaint_date":        "Complaint Date",
            "account_number":        "Account Number",
            "complaint_type":        "Complaint Type",
            "amount_disputed":       "Amount Disputed",
            "complaint_description": "Complaint Description",
        }

        # Truncated values mirror what actually appears in the PDF.
        # The PDF has a fixed value column width; longer strings are clipped.
        MAX_VALUE_CHARS = 60
        rendered_values = {k: str(v)[:MAX_VALUE_CHARS] for k, v in fields_data.items()}

        # Generate PDF with real AcroForm fields so pypdf/pymupdf field extraction works.
        # Layout: left column = bold label text, right column = AcroForm textfield widget.
        c = rl_canvas.Canvas(str(pdf_path), pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 720, "Customer Complaint Form")
        c.setFont("Helvetica", 11)
        y = 680
        for field_name, rendered_val in rendered_values.items():
            label = human_labels.get(field_name, field_name.replace("_", " ").title()) + ":"
            c.setFont("Helvetica-Bold", 11)
            c.drawString(72, y, label)
            # AcroForm text field — readable by pypdf.get_fields() and page.widgets()
            c.acroForm.textfield(
                name=human_labels.get(field_name, field_name.replace("_", " ").title()),
                tooltip=label,
                value=rendered_val,
                x=245, y=y - 14,
                width=290, height=20,
                fontSize=10,
                borderStyle="inset",
                forceBorder=True,
            )
            y -= 34
            if y < 120:
                c.showPage()
                y = 720
        c.save()

        # Ground truth JSON.
        # full_text = complete document text in reading order (labels then values),
        # matching what PyMuPDF's get_text("text") extracts for AcroForms.
        # Parsers that include form widget text in their output will score CER≈0;
        # parsers that only read the content stream (missing values) will score higher CER.
        full_text_lines = ["Customer Complaint Form"]
        for k, rv in rendered_values.items():
            label = human_labels.get(k, k.replace("_", " ").title())
            full_text_lines.append(f"{label}:")
            full_text_lines.append(rv)

        gt = {
            "full_text": "\n".join(full_text_lines),
            "fields": [
                {"name": human_labels.get(k, k.replace("_", " ").title()), "value": rv, "type": "text"}
                for k, rv in rendered_values.items()
            ],
            "tables": [],
            "source": "synthetic",
        }
        with open(gt_dest / f"{form_id}.json", "w") as f:
            json.dump(gt, f, indent=2)

    print(f"Generated {n} synthetic forms in {dest}")


DATASETS = {
    "funsd": download_funsd,
    "synthetic": lambda: generate_synthetic_complaint_forms(20),
    "doclaynet": lambda: download_hf_dataset_samples(
        "ds4sd/DocLayNet", "default", "mixed_print_handwrite", n_samples=30
    ),
}


def main():
    parser = argparse.ArgumentParser(description="Download PDF parsing test datasets")
    parser.add_argument("--dataset", choices=list(DATASETS.keys()) + ["all"], default="all")
    parser.add_argument("--list", action="store_true", help="List available datasets and exit")
    args = parser.parse_args()

    if args.list:
        print("Available datasets:")
        for name in DATASETS:
            print(f"  {name}")
        return

    if args.dataset == "all":
        for fn in DATASETS.values():
            fn()
    else:
        DATASETS[args.dataset]()

    print("\n=== Download complete ===")
    print(f"PDFs in: {DATA_DIR}")
    print(f"Ground truth in: {GT_DIR}")
    print("\nNote: IAM Handwriting Database requires manual registration.")
    print("Visit: https://fki.tic.heia-fr.ch/databases/iam-handwriting-database")


if __name__ == "__main__":
    main()
