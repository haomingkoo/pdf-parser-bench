# PDF Parser Bench

A reproducible ablation harness for comparing open-source PDF and OCR tools on
structured complaint forms. It measures character and word error, form-field
recovery, table accuracy, calibration, and throughput without requiring cloud
APIs for the core benchmark.

[**Read the visual comparison**][comparison] ·
[Evaluation design](complaint-form-parsing-evaluation-plan.md) ·
[Run the benchmark](sandbox/README.md)

## Parsers covered

- pypdf, pdfplumber, and PyMuPDF for digital PDFs and AcroForms
- Tesseract, PaddleOCR, and TrOCR for scanned or handwritten inputs
- Docling for document structure and layout recovery

## Evidence included

The committed result slice covers 20 synthetic digital AcroForms and 10 FUNSD
scanned forms. It demonstrates why field F1 is more useful than raw CER for
AcroForms, and why preprocessing must be gated: in the recorded 300 DPI slice,
the full preprocessing pipeline made Tesseract CER worse rather than better.

The benchmark does not claim one universal winner. Real production selection
still requires an annotated sample of the actual document distribution.

## Quick start

```bash
cd sandbox
docker compose build
docker compose run --rm parser python evaluate.py --all --max-docs 3
```

See [`sandbox/README.md`](sandbox/README.md) for datasets, metrics, parser setup,
and the full command reference.

[comparison]: https://kooexperience.com/blog/posts/pdf-parsing-comparison.html
