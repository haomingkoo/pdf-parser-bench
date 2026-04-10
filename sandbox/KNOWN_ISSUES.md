# Known Issues — Post-Critique Review

Identified by internal code critique agent. Ordered by severity. Fixes marked.

| # | Severity | Issue | Status |
|---|---|---|---|
| 1 | 🔴 Critical | Rubric weights sum to 1.20 not 1.00 — all composite scores inflated | ✅ Fixed → updated rubric/evaluation_rubric.md |
| 2 | 🔴 Critical | `__init__.py` missing in src/ subdirs — imports fail | ✅ Fixed |
| 3 | 🔴 Critical | Docling `export_to_markdown()` inflates CER vs plain-text GT | ✅ Fixed → `export_to_text()` |
| 4 | 🔴 Critical | CER/WER computed without text normalization — whitespace artifacts dominate | ✅ Fixed → normalize before metric |
| 5 | 🔴 Critical | WER not clamped to 1.0 — distorts mean statistics | ✅ Fixed + updated for jiwer 4.0 API |
| 6 | 🟠 High | Field F1 exact name match — all OCR parsers score ~0 on scanned forms | ✅ Fixed → rapidfuzz token_sort_ratio ≥ 80 fuzzy matching |
| 7 | 🟠 High | FUNSD downloads PNGs but runner only globs `*.pdf` | ✅ Fixed → PIL PNG→PDF conversion in evaluate session |
| 8 | 🟠 High | CSV export drops `doc_type` column from EvaluationResult | ✅ Fixed → `doc_type` field added to dataclass and `to_dict()` |
| 9 | 🔴 Critical | Deskew rotation angle sign wrong — doubles skew instead of correcting | ✅ Fixed → negate angle |
| 10 | 🟠 High | Table matching uses positional index — wrong when parser detects extra tables | TODO: use best-overlap IoU matching |
| 11 | 🟡 Medium | Checkbox fields use CER threshold instead of exact match | ✅ Fixed → exact normalized match for field_type="checkbox" |
| 12 | 🟡 Medium | Missing `paddleocr_en+preproc` and `trocr_large+preproc` in PARSER_REGISTRY | ✅ Fixed → conditional imports + all preproc variants registered |
| 13 | 🟡 Medium | N=50 per type insufficient for statistical comparison of 10 parsers | TODO: increase to N≥100; add bootstrap CIs |
| 14 | 🟡 Medium | Claude parser uses 150 DPI (unfair comparison); PII warning in errors not logs | ✅ Fixed → default dpi=300; warning via `logging.warning()` |
| 15 | 🟡 Medium | GT schema missing `bbox` and `reading_order` — figures/hallucination untestable | TODO: extend GT schema; preserve FUNSD bboxes in converter |
| 16 | 🟡 Medium | Tesseract parser name identical with/without preprocessing — summary merges rows | ✅ Fixed → name includes `+preproc` suffix when active |
| 17 | 🟠 High | Synthetic form GT `full_text` didn't match PDF visual content (snake_case keys, truncation mismatch) | ✅ Fixed → GT uses human labels + same MAX_VALUE_CHARS as PDF render |
| 18 | 🟠 High | Synthetic forms used plain `drawString` not AcroForm widgets — field extraction untestable | ✅ Fixed → `canvas.acroForm.textfield()` for real AcroForm widgets |
| 19 | 🟡 Medium | WER used old jiwer API (Compose transforms) incompatible with jiwer 4.0 | ✅ Fixed → manual normalization then plain `jiwer.wer()` call |
| 20 | 🟡 Medium | Preprocessing hurts already-good 300 DPI scans (FUNSD: CER 0.484→0.560) | TODO: gate preprocessing on `check_dpi()` + skew measurement, not a boolean flag |

## Rubric Weight Fix

The original weights summed to 1.20. Corrected weights (sum = 1.00):

| Criterion | Original | Corrected |
|---|---|---|
| A: Text Extraction | 0.15 | 0.12 |
| B: Handwriting | 0.25 | 0.22 |
| C: Table Structure | 0.10 | 0.08 |
| D: KVP / Form Fields | 0.20 | 0.18 |
| E: Diagrams/Figures | 0.05 | 0.05 |
| F: Degraded Scans | 0.10 | 0.10 |
| G: Speed | 0.05 | 0.05 |
| H: Compliance | 0.15 | 0.10 |
| I: License | 0.05 | 0.05 |
| J: Maintenance | 0.10 | 0.05 |
| **Total** | **1.20** | **1.00** |
