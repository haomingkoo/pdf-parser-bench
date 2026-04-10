# PDF Parsing Sandbox

Ablation test harness for evaluating open-source PDF parsing tools on customer complaint forms.  
All parsers run **on-prem, no API keys required** for core tools.

---

## What's inside

```
sandbox/
├── src/
│   ├── parsers/          # 8 parser implementations (pypdf, pymupdf, pdfplumber,
│   │                     #   docling, paddleocr, tesseract, trocr, claude*)
│   ├── preprocessing/    # Deskew → Denoise → CLAHE → Sauvola binarization
│   ├── metrics/          # CER, WER, FER, Field F1, Table Cell Accuracy, calibration
│   └── ablation/         # Systematic parser × doc_type × preprocessing runner
├── scripts/
│   └── download_datasets.py   # FUNSD, DocLayNet, synthetic form generator
├── rubric/
│   └── evaluation_rubric.md   # 10-criterion weighted scoring guide
├── playwright/
│   └── verify_blog.spec.ts    # Browser rendering tests for the blog post
├── data/                      # Test PDFs (gitignored; downloaded via scripts/)
├── results/                   # Evaluation outputs (gitignored)
├── evaluate.py                # Main CLI
├── Dockerfile                 # Tesseract + Poppler + Python 3.11
├── docker-compose.yml
├── requirements.txt
└── KNOWN_ISSUES.md            # Post-critique bug tracker
```

---

## Parsers compared

| Parser | License | Scanned | Tables | Handwriting | On-prem |
|---|---|---|---|---|---|
| pypdf | BSD-3 | ✗ | ✗ | ✗ | ✓ |
| pdfplumber | MIT | ✗ | ✓ (rule) | ✗ | ✓ |
| PyMuPDF | AGPL-3.0¹ | ✗ | Basic | ✗ | ✓ |
| Docling (IBM) | MIT | ✓ | ✓ (ML) | Limited | ✓ |
| PaddleOCR | Apache-2.0 | ✓ | ✓ (ML) | Limited | ✓ |
| Tesseract | Apache-2.0 | ✓ | ✗ | ✗ | ✓ |
| TrOCR (MS) | MIT | ✓ | ✗ | ✓ | ✓ |
| Claude API* | Proprietary | ✓ | ✓ | ✓ | ✗ |

¹ PyMuPDF AGPL-3.0: free for internal/open-source use. Commercial redistribution requires a paid Artifex license.  
\* Claude API: NOT on-prem. Sends data to Anthropic. Requires `ANTHROPIC_API_KEY`. Not recommended for real complaint PII. Uncomment in `requirements.txt` to include.

---

## Quick start

### Docker (recommended — handles all system dependencies)

```bash
# Build image (downloads Tesseract, Poppler, Python deps)
docker compose build

# Download test datasets
docker compose run --rm parser python scripts/download_datasets.py

# Run full ablation
docker compose run --rm parser python evaluate.py --all

# Quick smoke test (3 docs max per type)
docker compose run --rm parser python evaluate.py --all --max-docs 3

# Single file test
docker compose run --rm parser python evaluate.py \
  --file data/raw/digital_text_layer/my_form.pdf \
  --parser docling
```

### Local Python (requires system Tesseract + Poppler)

```bash
# macOS
brew install tesseract poppler ghostscript

# Ubuntu/Debian
sudo apt-get install tesseract-ocr poppler-utils ghostscript

pip install -r requirements.txt
python evaluate.py --list-parsers
python evaluate.py --all --max-docs 5
```

---

## Datasets

Downloaded via `scripts/download_datasets.py`:

| Dataset | Source | Forms | Type | License |
|---|---|---|---|---|
| FUNSD | EPFL (Jaume et al. 2019) | 199 | Noisy scanned business forms | Public / Research |
| DocLayNet samples | IBM (Pfitzmann et al. 2022) | 50 | Mixed enterprise documents | CC-BY 4.0 |
| Synthetic complaint forms | Generated (Faker + ReportLab) | 20 | Digital AcroForms, no real PII | N/A |

**Important:** No benchmark for actual customer complaint forms exists publicly. FUNSD is the closest proxy. You must build a proprietary annotated corpus from your real complaint forms (anonymized) for production evaluation. See `rubric/evaluation_rubric.md` §5.2.

**IAM Handwriting Database** (required for handwriting evaluation): Free registration at [fki.tic.heia-fr.ch](https://fki.tic.heia-fr.ch/databases/iam-handwriting-database). Download manually and place in `data/raw/handwritten_majority/`.

---

## Running the ablation

```bash
# All parsers, all document types
python evaluate.py --all

# Specific parsers only
python evaluate.py --parsers docling pymupdf paddleocr_en tesseract_eng

# Specific document type
python evaluate.py --all --doc-type scanned_clean_300dpi

# Results land in results/ablation_YYYYMMDD_HHMMSS.jsonl
# and results/summary_YYYYMMDD_HHMMSS.csv
```

Output includes a terminal summary table and a CSV for notebook analysis.

---

## Ground truth format

Each test PDF in `data/raw/` has a corresponding `data/ground_truth/<name>.json`:

```json
{
  "full_text": "full document text in reading order",
  "fields": [
    {"name": "complainant_name", "value": "John Smith", "type": "text"},
    {"name": "complaint_date",   "value": "01/15/2024", "type": "date"},
    {"name": "is_handwritten",   "value": "checked",    "type": "checkbox"}
  ],
  "tables": [
    {"rows": [["Header 1", "Header 2"], ["val1", "val2"]]}
  ],
  "page_count": 3,
  "source": "funsd | synthetic | manual"
}
```

---

## Measured results (2026-04-10, Apple Silicon CPU)

### Digital AcroForms — 20 synthetic complaint forms

| Parser | CER ↓ | WER ↓ | Field F1 ↑ | Speed (p/s) ↑ | AcroForm fields |
|---|---|---|---|---|---|
| pypdf | 0.490† | 0.524† | **1.000** | **415** | ✓ |
| pymupdf | 0.470† | 0.437† | **1.000** | 32‡ | ✓ |
| pdfplumber | 0.490† | 0.524† | 0.000 | 151 | ✗ |
| Tesseract | 0.534 | 0.611 | 0.000 | 0.68 | ✗ |

† CER/WER artifact: AcroForm GT interleaves label+value; parsers read them in separate passes. Field F1 is the correct metric for AcroForms.  
‡ pymupdf slower because it also runs `find_tables()` + `page.widgets()` per page.

### Scanned forms — FUNSD N=10 (real annotated business forms, EPFL 2019)

| Parser | CER ↓ | WER ↓ | Speed (p/s) ↑ | Reads scanned? |
|---|---|---|---|---|
| **Tesseract (raw)** | **0.484** | **0.749** | 1.05 | ✓ |
| Tesseract +preproc | 0.560 | 0.866 | 0.25 | ✓ |
| pypdf / pymupdf / pdfplumber | 1.000 | 1.000 | instant | ✗ (no text layer) |

> **Key finding:** Preprocessing (deskew + denoise + CLAHE + Sauvola) **hurts** already-adequate 300 DPI scans in this slice: CER rose from 0.484 to 0.560 (+0.076 absolute, +15.7% relative). It only helps genuinely degraded inputs (fax, heavily skewed, low-contrast). Gate preprocessing on `check_dpi()` and measured skew, not a global flag.

Tesseract CER=0.484 is consistent with published benchmarks (0.40–0.55 range on noisy scanned business forms). Docling and PaddleOCR results pending model download.

---

## Known issues

See `KNOWN_ISSUES.md` for the full post-critique bug list. Fixes applied this session:
- Rubric weights corrected (were summing to 1.20, now 1.00)
- Deskew angle sign corrected (was doubling skew, now corrects it)
- Docling using `export_to_text()` not `export_to_markdown()` for fair CER
- CER/WER normalized before comparison (unicode, whitespace)
- WER updated for jiwer 4.0 API (manual normalization before `jiwer.wer()`)
- WER clamped to 1.0
- `doc_type` added to `EvaluationResult` and CSV output
- Field matching now uses fuzzy name matching (rapidfuzz token_sort_ratio ≥ 80)
- Checkbox fields use exact match, not CER threshold
- Claude parser default DPI raised 150 → 300 for fair comparison
- PII warning moved from `result.errors` to `logging.warning()`
- Parser registry uses conditional imports (sandbox runs with partial deps)
- Tesseract parser `name` property now includes `+preproc` suffix when active
- Synthetic form generator produces real AcroForm widgets (not plain text)
- Ground truth `full_text` matches PDF visual content including field values

---

## License

All parser wrapper code in this sandbox: MIT.  
Underlying tools have their own licenses — see the table above and each parser's docstring.  
Do not use real customer complaint forms (containing PII) in this sandbox without appropriate data governance controls.
