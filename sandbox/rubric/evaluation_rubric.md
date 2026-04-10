# PDF Parser Evaluation Rubric
## Customer Complaint Form Processing — Scoring Guide

**Version:** 1.0  
**Purpose:** Standardised scoring matrix for evaluating PDF parsing tools against complaint form requirements.  
**How to use:** Score each tool 1–5 per criterion using the rubric descriptions below. Multiply by weight to get weighted score. Sum weighted scores for final rank.

---

## Scoring Scale

| Score | Label | Meaning |
|---|---|---|
| 5 | Excellent | Meets or exceeds the requirement consistently across all document subtypes tested |
| 4 | Good | Meets the requirement for most documents; minor failures on edge cases |
| 3 | Adequate | Partial support; acceptable only with additional workarounds or fine-tuning |
| 2 | Weak | Significant gaps; requires substantial additional engineering to be usable |
| 1 | Failing | Does not meet the requirement; not viable for this use case |
| N/A | Not Applicable | The tool is not designed for this category; do not score |

**Absence of data:** Do not assign a score if you have not measured it on your actual corpus. Leave blank and note "untested." Do not infer scores from vendor documentation.

---

## Criterion Definitions and Weights

### A. Text Extraction Accuracy (Weight: 0.12)

Measures the fidelity of extracted text for the *printed* portions of complaint forms.

| Score | Description |
|---|---|
| 5 | CER ≤ 2% on printed text at ≥300 DPI. All text blocks in correct reading order. |
| 4 | CER 2–5%. Minor reading order issues on multi-column layouts. |
| 3 | CER 5–10%. Some garbled text on complex layouts or embedded fonts. |
| 2 | CER 10–20%. Significant text loss or corruption. |
| 1 | CER >20% or frequent total page failures. |

**Key test cases:** Multi-column forms, headers/footers, embedded special characters, date fields.

---

### B. Handwritten Field Extraction (Weight: 0.22)

The most critical failure mode for physical complaint forms. Measures HTR accuracy on handwritten value fields.

| Score | Description |
|---|---|
| 5 | CER ≤ 5% on real-world handwritten fields from your complaint corpus. Field values intelligible. |
| 4 | CER 5–15%. Most words correct; occasional character-level errors in names/numbers. |
| 3 | CER 15–30%. Many field values partially correct; dates and numbers frequently wrong. |
| 2 | CER 30–50%. Handwritten content largely unreadable. Requires full HITL review. |
| 1 | No handwriting capability. CER >50% or complete failure. |

**Key test cases:** Handwritten name, handwritten date (DD/MM format), handwritten account number, free-text complaint narrative.  
**Note:** Score this ONLY after testing on your actual complaint form handwriting, not on the IAM benchmark. IAM is cleaner than real complaint forms.

---

### C. Table Structure Extraction (Weight: 0.08)

Measures ability to recover table structure (rows, columns, cells) from complaint forms.

| Score | Description |
|---|---|
| 5 | Table cell accuracy ≥95%. Row and column counts correct. Multi-header tables handled. |
| 4 | Table cell accuracy 85–95%. Occasional merged cell errors. |
| 3 | Table cell accuracy 70–85%. Borderless tables fail; bordered tables mostly correct. |
| 2 | Table cell accuracy 50–70%. Tables frequently merged into flat text. |
| 1 | No table extraction. All table content returned as unstructured text. |

**Key test cases:** Simple bordered table (billing history), complex multi-column table (incident log), borderless alignment-based table.

---

### D. Form Field / KVP Extraction (Weight: 0.18)

Measures ability to extract key-value pairs (field label → field value) from structured forms.

| Score | Description |
|---|---|
| 5 | Field F1 ≥0.95. Correct label-value pairing for all field types including nested fields. |
| 4 | Field F1 0.85–0.95. Most fields correctly paired; some label confusion on densely packed forms. |
| 3 | Field F1 0.70–0.85. Key fields extracted; secondary fields missed or incorrectly paired. |
| 2 | Field F1 0.50–0.70. Only obvious fields (first column of form) reliably extracted. |
| 1 | Field F1 <0.50. No meaningful KVP extraction. Raw text only. |

**Key test cases:** AcroForm digital fields, printed label + typed value, printed label + handwritten value, checkbox fields, nested/conditional fields.

---

### E. Diagram and Figure Handling (Weight: 0.05)

Measures how the tool handles embedded images, signatures, diagrams, or charts in complaint forms.

| Score | Description |
|---|---|
| 5 | Correctly identifies figure regions; extracts/labels them; does not hallucinate text from images. |
| 4 | Figure regions identified; text extraction skips them cleanly (no bleed-through). |
| 3 | Figures partially contaminate extracted text; some hallucinated characters near figure edges. |
| 2 | Figure regions cause significant text corruption in surrounding fields. |
| 1 | No figure awareness; hallucinated characters throughout image-heavy pages. |

**Key test cases:** Embedded signature field (should be skipped), attached photo/screenshot, embedded chart from prior correspondence.  
**Critical:** Hallucinated text from non-text regions (images, signatures) is the worst failure — score 1 if observed.

---

### F. Degraded Scan Handling (Weight: 0.10)

Measures robustness to fax-quality and low-DPI scans that are common in complaint intake.

| Score | Description |
|---|---|
| 5 | CER <10% on 200 DPI fax-quality bitonal scans after preprocessing. Skew correction automatic. |
| 4 | CER 10–20% on degraded scans. Requires preprocessing; explicit 300 DPI scans work well. |
| 3 | CER 20–35% on degraded scans. Preprocessing helps significantly but still error-prone. |
| 2 | CER 35–50% on degraded scans. Essentially unusable on fax-quality input. |
| 1 | No degraded scan support. Fails on anything below 300 DPI. |

**Key test cases:** 200 DPI fax scan, skewed 3–5°, coffee-stained form, mobile phone photo of form (shadows, perspective).

---

### G. Processing Speed (Weight: 0.05)

Measures throughput for batch processing. Scored relative to a 5-page complaint form.

| Score | Description |
|---|---|
| 5 | ≥5 pages/second on CPU. Full 5-page form in <1 second. |
| 4 | 1–5 pages/second on CPU. Full form in 1–5 seconds. |
| 3 | 0.2–1 page/second on CPU. Full form in 5–25 seconds. |
| 2 | 0.05–0.2 page/second on CPU. Full form in 25–100 seconds. |
| 1 | <0.05 pages/second. Full form takes >100 seconds. Unusable for batch processing. |

**Note:** GPU scores should be reported separately. Score with CPU-only unless GPU is available in your deployment.

---

### H. Compliance and Data Residency (Weight: 0.10)

Measures whether the tool supports on-prem deployment, audit trails, and compliance requirements.

| Score | Description |
|---|---|
| 5 | Fully local (zero egress), deterministic output, version-pinnable, MIT/Apache-2.0 license. |
| 4 | Local deployment available with minor setup. Version-pinnable. Permissive license. |
| 3 | Self-hosted option exists but requires cloud licensing or activation. Some egress risk. |
| 2 | Cloud API only; DPA available; data residency configurable. GDPR-compliant with setup. |
| 1 | Cloud API only; no DPA by default; data leaves infrastructure with no residency controls. |

**Critical:** Tools scoring 1 or 2 here require legal review before handling complaint PII.

---

### I. License and Cost (Weight: 0.05)

Measures whether the tool is truly free for commercial on-prem use.

| Score | Description |
|---|---|
| 5 | MIT, Apache-2.0, or BSD: free for any use including commercial production. |
| 4 | AGPL-3.0: free for internal on-prem use; commercial redistribution requires paid license. |
| 3 | GPL-3.0 (code): code is open source; not compatible with proprietary products without dual-license. Model weights may have additional restrictions. |
| 2 | Mixed: open-source client library but proprietary model weights (e.g. Open Rail-M NC variants). |
| 1 | Proprietary API: no open-source option; pay-per-use only. |

---

### J. Maintenance and Community Health (Weight: 0.05) — *[Qualitative]*

Measures long-term viability: active maintenance, issue response, documentation quality.

| Score | Description |
|---|---|
| 5 | Active releases in last 6 months; issues responded to within 1 week; comprehensive docs; large community. |
| 4 | Active releases in last 12 months; good documentation; responsive maintainers. |
| 3 | Releases within 18 months; adequate documentation; occasional issues going unaddressed. |
| 2 | Last release 18–36 months ago; sparse documentation; limited maintainer response. |
| 1 | Last release >3 years ago or effectively abandoned. Security vulnerabilities may be unpatched. |

---

## Scoring Matrix Template

Copy this table and fill in scores after running the ablation tests.

| Tool | A: Text (0.15) | B: HW (0.25) | C: Table (0.10) | D: KVP (0.20) | E: Figures (0.05) | F: Degraded (0.10) | G: Speed (0.05) | H: Compliance (0.15) | I: License (0.05) | J: Maint (0.10) | **Weighted Total** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| docling | — | — | — | — | — | — | — | — | — | — | — |
| pymupdf | — | — | — | — | — | — | — | — | — | — | — |
| pdfplumber | — | — | — | — | — | — | — | — | — | — | — |
| paddleocr_en | — | — | — | — | — | — | — | — | — | — | — |
| tesseract_eng | — | — | — | — | — | — | — | — | — | — | — |
| trocr_large | — | — | — | — | — | — | — | — | — | — | — |
| pypdf | — | — | — | — | — | — | — | — | — | — | — |
| claude_sonnet* | — | — | — | — | — | — | — | — | — | — | — |

*claude_sonnet: NOT on-prem. Score H = 1 (cloud API). Include only if approved by legal/compliance.

---

## Interpreting Results

**Composite score thresholds:**
- **≥4.0**: Recommended for production complaint form processing
- **3.0–3.9**: Viable with supplemental engineering (preprocessing pipeline, HITL threshold tuning)
- **2.0–2.9**: Viable only for one specific document subtype; not suitable as a general parser
- **<2.0**: Not recommended; research/experimental use only

**Mandatory criteria (non-negotiable, regardless of composite score):**
- Criterion H (Compliance) must be ≥3 before any tool can process real customer complaint PII
- Criterion B (Handwriting) must be ≥2 if any complaint forms include handwritten fields
- A tool that scores 1 on Criterion E (hallucinated text from figures) is disqualified if figures are present

---

## Notes on Measurement

1. **Measure on YOUR corpus.** All numbers in this rubric are thresholds derived from published research baselines. Your specific complaint form vocabulary, scan quality, and layout will produce different absolute numbers.

2. **Report confidence intervals.** With 200 test forms, compute 95% bootstrap confidence intervals for all accuracy metrics. A difference of ±2% CER may not be statistically significant.

3. **Stratify by document type.** Report separate scores for: digital, scanned clean, scanned degraded, handwritten. A tool that scores 5 on digital but 1 on handwritten should not receive the average of those scores — they serve different document populations.

4. **Do not average across incompatible field types.** A 99% accuracy on printed text + 72% accuracy on handwritten text does not average to 85.5% "overall accuracy" if 40% of your complaint forms have significant handwriting.

5. **Vendor confidence scores are not calibrated.** Before using confidence scores to set HITL thresholds, run the calibration protocol in `src/metrics/compute.py`. Do not assume a confidence score of 0.90 means 90% accuracy.
