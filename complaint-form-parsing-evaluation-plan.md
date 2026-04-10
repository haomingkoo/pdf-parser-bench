# PDF Parsing Evaluation Plan for Customer Complaint Forms

**Prepared for:** Engineering Team
**Version:** 1.0
**Date:** 2026-04-10
**Classification:** Internal Technical Reference

---

## 1. Executive Summary

- **No single tool wins universally.** Across 1,355+ benchmark pages (OmniDocBench, CVPR 2025), per-document-type variance exceeds 55 percentage points — corpus composition drives accuracy more than tool selection. Measure on *your* data, not vendor benchmarks.
- **Docling (IBM, MIT) is the recommended open-source baseline.** It achieves 97.9% table accuracy, runs fully local (no data egress), integrates with Microsoft Presidio/GLiNER for PII redaction, and costs ~$0 per page at scale vs. $0.010–$0.065/page for cloud competitors.
- **Handwriting is the critical failure mode.** Printed text hits 99%+ accuracy at 300 DPI; handwritten fields degrade to 70–88%. A preprocessing pipeline (deskew + denoise + contrast enhancement) recovers +22% median accuracy. No existing benchmark adequately covers real complaint form handwriting — you must build your own test corpus.
- **Human-in-the-loop (HITL) is non-negotiable.** Production evidence (Uber Engineering: 90% accuracy improvement) shows routing 5% of low-confidence documents to human review achieves high-efficiency outcomes. Active learning from corrections reduces error rates from 20% to 5% over six months.
- **Compliance must be designed in, not bolted on.** GDPR Art. 28 requires a Data Processing Agreement (DPA) before any complaint PDF reaches a cloud API. CFPB mandates audit trails and record retention (ECOA: 25 months, RESPA: 3 years). The pipeline architecture must support these requirements from day one.

---

## 2. Problem Framing — What Makes Complaint Forms Uniquely Hard

### 2.1 The Compound Difficulty Stack

```
    DIFFICULTY SOURCES FOR COMPLAINT FORM PARSING
    ================================================

    Layer 6: Regulatory          [CFPB, ECOA, RESPA, GDPR, CCPA]
             Compliance          ← Audit trail, retention, DPA
                  ↑
    Layer 5: Field Semantics     [Cross-field validation, date logic,
             Complexity          address consistency, relationship to
                  ↑               claimant records]
    Layer 4: Document            [Multi-page, attachments, mixed
             Heterogeneity       digital+scan, handwritten overlays
                  ↑               on printed forms]
    Layer 3: Scan Quality        [Fax artifacts (200 DPI bitonal),
             Variance            coffee stains, skew, low contrast,
                  ↑               mobile camera captures]
    Layer 2: Layout              [KVP (key-value pairs), tables,
             Diversity           checkboxes, free-text narrative,
                  ↑               multi-column, varied templates]
    Layer 1: Content             [Mixed handwritten + printed text,
             Mixture             PII-dense fields, numeric precision
                                  requirements, multilingual]
```

### 2.2 Why Standard Benchmarks Are Insufficient

- **FUNSD (EPFL 2019):** 199 noisy scanned forms — closest proxy, but covers generic business forms, not financial complaint-specific layouts or handwriting styles
- **DocLayNet (IBM KDD 2022):** 80k annotated pages across 6 document sources — excellent for layout understanding, no complaint-form-specific category
- **OmniDocBench (CVPR 2025):** 9 document types, 3 languages — broadest coverage, but still no complaint form type; the 55+ point variance across types is a direct warning that borrowing accuracy numbers from other domains is invalid
- **Consequence:** You must construct a proprietary 200–500 page annotated test corpus from your actual complaint forms before any tool selection decision can be made with confidence

### 2.3 Field-Level Error Rate Expectations (Baseline)

| Field Type | Expected Accuracy (Printed) | Expected Accuracy (Handwritten) | Primary Failure Mode |
|---|---|---|---|
| Printed text (body) | 99%+ | — | Rare layout errors |
| Checkboxes | 90–96% | — | Adjacent mark contamination |
| Numeric fields | 80–90% | 75–85% | 0↔O, 1↔l confusion |
| Dates | 85–95% | 75–85% | Format ambiguity (MM/DD vs DD/MM) |
| Handwritten free text | — | 70–88% | Variable pen pressure, style |
| Signatures (discard) | N/A | N/A | Not parseable reliably |

---

## 3. Taxonomy of Parsing Methods

### 3.1 Six Categories

```
    PDF PARSING METHOD TAXONOMY
    ============================

    ┌──────────────────────────────────────────────────────┐
    │                 INPUT: Complaint Form PDF             │
    └──────────────────┬───────────────────────────────────┘
                       │
         ┌─────────────┴─────────────────────┐
         ▼                                   ▼
    ┌─────────┐                       ┌──────────────┐
    │Digital  │                       │ Scanned /    │
    │(AcroForm│                       │ Image-based  │
    │/ text   │                       │ PDF          │
    │layer)   │                       └──────┬───────┘
    └────┬────┘                              │
         │                                  │
    ┌────▼────┐  ┌──────────┐  ┌────────────▼──────────────────────────────────────┐
    │CAT-1    │  │CAT-2     │  │ CAT-3          CAT-4       CAT-5       CAT-6       │
    │Text     │  │Rule-based│  │ Traditional    ML Layout   AI/LLM      Hybrid      │
    │Extraction│  │Form      │  │ OCR            Parsers     Native      Pipelines   │
    │Libraries│  │Parsers   │  │                            Parsers                 │
    └─────────┘  └──────────┘  └───────────────────────────────────────────────────┘
```

### 3.2 Full Taxonomy Table

| Category | Representative Tools | Input Type | Strengths | Typical Use Case |
|---|---|---|---|---|
| **CAT-1: Text Extraction** | pypdf, pdfplumber, PyMuPDF, pdfminer.six | Digital PDF (text layer) | Speed, zero cost, 99%+ accuracy on printed text | Clean AcroForms, text-layer PDFs |
| **CAT-2: Rule-Based Form Parsers** | pypdf (AcroForm), PyMuPDF form fields, pdfrw | Digital AcroForm PDF | Exact field extraction, structured output, deterministic | Standardized digital submission portals |
| **CAT-3: Traditional OCR** | Tesseract, EasyOCR, PaddleOCR, Surya | Scanned/image PDF | Broad language support, local, battle-tested | Moderate-quality scans, multilingual |
| **CAT-4: ML Layout Parsers** | Docling, Marker, Unstructured, camelot, TATR | Mixed/complex PDFs | Layout understanding, table recovery, open-source | Complex multi-column forms, tables |
| **CAT-5: AI/LLM-Native Parsers** | LlamaParse, AWS Textract, Azure Document Intelligence, Google Document AI | Any | Highest ceiling for complex docs, managed service | High-value low-volume, regulated cloud OK |
| **CAT-6: Hybrid Custom Pipelines** | Docling + TrOCR + Presidio + Pydantic v2 | Any | Best accuracy, full control, compliance by design | Production at scale, air-gap, PII-sensitive |

---

## 4. Method-by-Method Deep Dive

### 4.1 CAT-1: Text Extraction Libraries

#### PyMuPDF (8.7k★) — Recommended for digital PDFs
- **Fastest** text extraction benchmark winner (arXiv 2410.09871); pypdfium2 co-leader
- Handles AcroForm field extraction natively
- Python bindings with comprehensive coordinate/bounding-box output
- AGPL license in free tier — **verify commercial license requirements**
- No OCR capability; completely useless on scanned forms without pre-processing
- No layout understanding — returns text in PDF stream order, not visual order

#### pdfplumber (7.5k★)
- Best-in-class for table extraction from digital PDFs (uses pdfminer.six under the hood)
- `extract_table()` and `extract_words()` with explicit bounding box control
- Slower than PyMuPDF; memory-intensive on large files
- Ideal for forms with embedded table structures in text layer

#### pypdf (9k★) + pdfminer.six (7k★)
- Pure Python; easiest deployment (no C dependencies)
- AcroForm field extraction via `pypdf.PdfReader.get_fields()`
- Lower accuracy than PyMuPDF on complex text layouts; no table support

**When to use CAT-1:**
- Confirmed digital submission (text layer present, verified via `pdfinfo` or PyMuPDF `page.get_text("blocks")` non-empty check)
- AcroForm standardized submissions from your own portal
- Pre-processing stage to detect digital vs. scanned before routing

---

### 4.2 CAT-2: Rule-Based Form Parsers

- **AcroForm extraction is deterministic and 100% accurate** for fields that were programmatically filled
- Requires form template stability — any layout change breaks field-name mappings
- Not applicable to customer-submitted handwritten/printed-and-scanned forms
- **Critical check:** Many "digital" complaint forms are print-sign-scan; AcroForm fields will be empty even if visually filled

---

### 4.3 CAT-3: Traditional OCR

#### PaddleOCR (70k★, Apache 2.0) — Recommended open-source OCR
- Highest star count; most active development as of 2026
- Supports 80+ languages including multilingual mixed documents
- PP-OCRv4 model achieves strong results on printed text; weaker on handwriting
- GPU-accelerated; runs on CPU in production with acceptable throughput
- Modular: detection, recognition, and layout analysis are separate components

#### Tesseract (62k★, Apache 2.0)
- Industry standard; 40+ year lineage; widest tool integration
- CER ~4–8% on clean printed documents; degrades significantly on noisy scans
- **Requires preprocessing** (deskew, denoise) for complaint form scan quality
- No handwriting recognition capability (use TrOCR instead)
- Best used as a fallback or for language coverage beyond PaddleOCR

#### EasyOCR (28.9k★, Apache 2.0)
- Simpler API than PaddleOCR; 80+ languages
- Slower than PaddleOCR; less accurate on degraded documents
- Good for prototyping; not recommended for production at scale

#### TrOCR (Microsoft, MIT)
- **Best open-source handwritten text recognition (HTR)** — CER ~2.9% on IAM clean dataset
- Transformer-based; fine-tunable on your complaint form handwriting samples
- Degrades heavily on: noisy/low-DPI scans, non-English scripts, mixed print+handwrite
- **Recommended for handwritten field extraction** (name, address, narrative fields)
- Requires separate field segmentation upstream (Docling or Aryn Sycamore to isolate field regions)

#### Surya (13k★, GPL-3.0)
- Strong layout + OCR combined; competes with cloud services on benchmarks
- GPL license: **incompatible with proprietary commercial products unless dual-licensed**
- Evaluate license carefully before adoption

**OCR Preprocessing Pipeline (mandatory for complaint forms):**

```
    MANDATORY SCAN PREPROCESSING PIPELINE
    =======================================

    Raw Scan/Fax Input
          │
          ▼
    ┌─────────────┐    DPI < 300?
    │ DPI Check   │──────────────► Upsample (OpenCV INTER_CUBIC)
    └──────┬──────┘                or REJECT with notification
           │ ≥ 300 DPI
           ▼
    ┌─────────────┐
    │ Deskew      │   (scikit-image Hough transform or OpenCV)
    │ Correction  │   Typical skew: 0–5° in mailed forms
    └──────┬──────┘
           ▼
    ┌─────────────┐
    │ Denoise     │   (OpenCV fastNlMeansDenoising or
    │             │    Gaussian blur + adaptive threshold)
    └──────┬──────┘
           ▼
    ┌─────────────┐
    │ Contrast    │   CLAHE (Contrast Limited Adaptive
    │ Enhancement │   Histogram Equalization) for fax artifacts
    └──────┬──────┘
           ▼
    ┌─────────────┐
    │ Binarization│   Sauvola local thresholding (better than
    │             │   global Otsu for mixed print+handwrite)
    └──────┬──────┘
           ▼
    Preprocessed Image → OCR Engine
    Expected improvement: +22% median accuracy (70% → 92%)
```

---

### 4.4 CAT-4: ML Layout Parsers

#### Docling (IBM, 37k★, MIT) — Primary Recommendation
- **97.9% table accuracy** in independent benchmark (Procycons 2025)
- Handles: PDF text layer, scanned PDFs (via integrated OCR), DOCX, PPTX, images
- Exports to: Markdown, JSON, structured DoclingDocument object
- Integrates natively with: LangChain, LlamaIndex, Hugging Face
- **PII integration:** GLiNER-PII model on Hugging Face; Microsoft Presidio via adapter
- Fully local, no data egress — air-gap compatible
- CPU inference: ~6–8 seconds per form (acceptable for async batch processing)
- GPU inference: significantly faster; recommend for real-time queues
- **MIT license:** production-safe, no commercial restrictions

#### Marker (33k★, GPL-3.0)
- Converts PDFs to high-quality Markdown with layout preservation
- Competitive accuracy with Docling on scientific/academic layouts
- **GPL-3.0 license:** blocks proprietary commercial use — **do not adopt without legal review**
- Lower table accuracy than Docling on financial/form documents (Procycons: Unstructured 75% vs Docling 97.9%)

#### Unstructured (13.8k★, Apache 2.0)
- Broad format support (25+ file types)
- Latency: **51–140 seconds per form** — disqualifying for real-time complaint intake
- 75% table accuracy in benchmark — acceptable only as fallback
- Better suited for document chunking for RAG than structured form extraction

#### Aryn Sycamore (Apache 2.0)
- DETR model trained on DocLayNet — 2–3× better mAP than alternatives on layout segmentation
- Best-in-class for document segmentation into logical regions (header, field groups, tables)
- Use as upstream segmenter feeding per-region OCR, rather than end-to-end extractor
- Lower star count (niche); smaller community; evaluate maintenance trajectory

#### TATR / Table Transformer (3.5k★, MIT)
- Microsoft's table structure recognition model
- Excellent for table detection and cell-level extraction when tables are present
- Complement to Docling, not a replacement

---

### 4.5 CAT-5: AI/LLM-Native Parsers

#### AWS Textract
- **Forms API (KVP extraction):** $0.065/page; improved Dec 2023 for mortgage, insurance, tax forms
- **Handwriting:** 71.2% accuracy on handwritten notes (adequate for many fields)
- HIPAA BAA available; standardized DPA; region pinning for data residency
- AnalyzeDocument API returns confidence scores per field (treat as ordinal, not calibrated probability)
- **Latency:** 2–5 seconds per form — acceptable for real-time

#### Azure Document Intelligence (formerly Form Recognizer)
- **Custom model:** $0.030/page after training on your forms (50+ labeled samples to start)
- **Prebuilt models:** Prebuilt-invoice, prebuilt-receipt — likely not applicable to complaint forms
- EU Data Boundary + container deployment option — strongest data residency story of cloud providers
- Vendor-stated 99%+ accuracy (printed+mixed) — apply significant skepticism; measure on your corpus
- **Best choice if:** EU data residency is mandatory or custom model training budget exists

#### Google Document AI
- **Form Parser:** $0.030/page
- 74.8% accuracy on docs with handwritten notes (R2 data)
- Lowest base OCR pricing ($0.00065/page) but Forms feature pricing is competitive
- Batch API available for cost reduction
- Gemini integration for complex understanding (94% on scanned docs — Koncile 2025 benchmark)

#### LlamaParse (40k★, proprietary)
- Best community adoption; tight LlamaIndex ecosystem integration
- **$0.075/page (premium)** — highest cost in category
- Column misalignment documented in independent benchmarks (Procycons 2025)
- **DPA requires enterprise request** — compliance blocker for regulated pipelines until resolved
- Appropriate for: RAG knowledge base ingestion, not structured field extraction

#### GPT-4 / Claude 3.x / Gemini (direct LLM approach)
- Koncile 2025 benchmarks: Text PDFs — GPT 98% / Claude 97% / Gemini 96%; Scanned — Gemini 94% / GPT 91% / Claude 90%
- Applied AI 2025: Gemini 3 Pro tops 17-parser × 800-doc test at 88% overall
- **Critical warning (Fernández, Medium 2025):** "Don't use LLMs as OCR" — documented number extraction failures on financial data
- **NVIDIA benchmark:** VLM 0.26 pages/sec vs OCR 8.47 pages/sec (32× throughput gap)
- **Alan (Medium 2025):** Few-shot contamination causes hallucination; 70% automation ceiling observed in production
- GDPR Art. 22: automated decision-making on complaint outcomes requires lawful basis + human review rights
- Use for: orchestration, field validation, ambiguity resolution — not as primary extraction engine

---

### 4.6 CAT-6: Hybrid Custom Pipelines

The recommended production architecture. Combines best-in-class components:

```
    RECOMMENDED HYBRID PIPELINE ARCHITECTURE
    ==========================================

    ┌─────────────────────────────────────────────────────────────────┐
    │                    INTAKE (S3 / Object Store)                    │
    └────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │              DOCUMENT CLASSIFIER (LayoutLM page classifier)      │
    │   Outputs: {digital_pdf | scanned_low | scanned_high | mixed}   │
    └───────┬────────────────┬────────────────────┬───────────────────┘
            │                │                    │
            ▼                ▼                    ▼
    ┌──────────────┐  ┌─────────────────┐  ┌────────────────────────┐
    │  Digital     │  │  Scanned PDF    │  │  Mixed / Unknown       │
    │  PDF Path    │  │  Path           │  │  Path                  │
    │              │  │                 │  │                        │
    │  PyMuPDF     │  │  Preprocessing  │  │  Docling (full)        │
    │  AcroForm    │  │  Pipeline       │  │  (handles both layers) │
    │  extraction  │  │  (deskew/       │  │                        │
    │              │  │  denoise/       │  │                        │
    │              │  │  binarize)      │  │                        │
    └──────┬───────┘  │       │         │  └──────────┬─────────────┘
           │          │       ▼         │             │
           │          │  ┌───────────┐  │             │
           │          │  │ Docling + │  │             │
           │          │  │ TrOCR     │  │             │
           │          │  │ (for HW   │  │             │
           │          │  │  fields)  │  │             │
           │          │  └─────┬─────┘  │             │
           │          └────────┘        │             │
           │                  │         │             │
           └──────────────────┴─────────┴─────────────┘
                                        │
                                        ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │              FIELD EXTRACTION & NORMALIZATION                    │
    │      Pydantic v2 models with field validators +                  │
    │      cross-field validators (date order, zip consistency,        │
    │      required fields, numeric range checks)                      │
    └─────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │            CONFIDENCE SCORING & HITL ROUTING                     │
    │                                                                  │
    │  Confidence > 0.90 ──────────────────────────► Auto-process     │
    │  Confidence 0.70–0.90 ──────────────────────► Spot-check queue  │
    │  Confidence < 0.70 ─────────────────────────► HITL full review  │
    │  Any PII anomaly flag ──────────────────────► Security review   │
    └─────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │              PII DETECTION & REDACTION (Presidio)                │
    │   Microsoft Presidio + GLiNER-PII model                         │
    │   Entities: NAME, SSN, ACCOUNT_NO, DOB, ADDRESS, PHONE, EMAIL   │
    │   Action: Redact in stored document; preserve in encrypted field │
    └─────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │              AUDIT LOG & STORAGE                                 │
    │   Immutable log: doc_id, timestamp, method, confidence,          │
    │   reviewer_id (if HITL), fields_extracted, pii_redacted_count   │
    │   Retention: 25 months (ECOA) / 3 years (RESPA)                 │
    └─────────────────────────────────────────────────────────────────┘
```

---

## 5. Evaluation Framework — What to Measure

### 5.1 Metrics Taxonomy

| Metric Category | Specific Metric | Formula / Definition | Target Threshold |
|---|---|---|---|
| **Accuracy — Field Level** | Field Extraction Rate (FER) | Correctly extracted fields / Total fields | ≥ 95% printed; ≥ 85% handwritten |
| **Accuracy — Field Level** | Character Error Rate (CER) | Edit distance / Total chars | ≤ 3% printed; ≤ 10% handwritten |
| **Accuracy — Field Level** | Word Error Rate (WER) | Word-level edit distance | ≤ 5% for narrative fields |
| **Accuracy — Structure** | Table Accuracy | Correctly recovered cells / Total cells | ≥ 95% (Docling 97.9% baseline) |
| **Accuracy — Structure** | Layout Fidelity Score | mAP on bounding box regions | ≥ 0.85 mAP |
| **Accuracy — Semantic** | Cross-Field Consistency Rate | Pydantic validation pass rate | ≥ 99% (catch date/zip errors) |
| **Throughput** | Pages per second (PPS) | Wall-clock pages processed/sec | ≥ 2 PPS for batch; ≥ 0.5 PPS real-time |
| **Throughput** | End-to-end latency (P95) | 95th percentile form completion time | ≤ 10s real-time; ≤ 60s batch |
| **Reliability** | HITL Escalation Rate | Forms routed to human / Total forms | Target: ≤ 10% |
| **Reliability** | Confidence Calibration | Empirical accuracy at each confidence band | Must measure on your corpus |
| **Reliability** | False Negative Rate (missed fields) | Fields not extracted / Total expected fields | ≤ 1% for required fields |
| **Cost** | Cost per form (CPF) | Compute + API cost / Forms processed | Measure at 10K, 100K, 1M scale |
| **Compliance** | PII Detection Recall | PII entities detected / True PII entities | ≥ 99.5% (zero missed SSNs) |
| **Compliance** | Audit Trail Completeness | Logged events / Expected events | 100% (binary requirement) |

### 5.2 Test Corpus Requirements

- **Minimum size:** 200 forms for initial evaluation; 500 forms for production go/no-go decision
- **Required stratification:**
  - Digital AcroForm (clean): 20%
  - Digitally filled + printed + scanned: 20%
  - Handwritten (partial): 30%
  - Handwritten (majority): 15%
  - Fax / very low quality (≤200 DPI): 10%
  - Edge cases (staple marks, torn, rotated pages): 5%
- **Ground truth annotation:** Double-blind human annotation with adjudication; field-level, not form-level
- **PII in test data:** Synthesize or fully anonymize; never use real customer PII for benchmarking
- **Language distribution:** Match production distribution; do not over-index on English-only

### 5.3 Confidence Score Calibration Protocol

```
    CONFIDENCE CALIBRATION PROCEDURE
    ==================================

    For each tool's confidence output:

    1. Extract (confidence_score, ground_truth_correct) pairs
       from your test corpus.

    2. Bin by confidence decile:
       [0.0-0.1] [0.1-0.2] ... [0.9-1.0]

    3. For each bin, compute:
       empirical_accuracy = correct_in_bin / total_in_bin

    4. Plot calibration curve:
       Perfect calibration = diagonal line
       Overconfident tool = curve below diagonal (most cloud APIs)
       Underconfident tool = curve above diagonal

    5. Fit isotonic regression or Platt scaling to correct scores.
       Use CORRECTED scores for HITL threshold setting.

    NOTE: No published calibration study exists for
    Textract, Azure DI, or Google DAI confidence scores.
    You MUST run this procedure before setting thresholds.
```

---

## 6. Phased Evaluation Roadmap

| Phase | Duration | Goal | Key Activities | Success Criteria | Exit Gate |
|---|---|---|---|---|---|
| **Phase 0: Setup** | Week 1–2 | Infrastructure + corpus | Deploy evaluation harness; annotate 200 forms; set up Docling + PyMuPDF + AWS Textract sandbox | Corpus ready; tooling reproducible | All 3 tools returning structured output on 20 sample forms |
| **Phase 1: Baseline** | Week 3–4 | Establish floor | Run Docling, PyMuPDF, AWS Textract on full 200-form corpus; compute all metrics in §5.1 | Quantified FER/CER/latency per tool per form type | ≥1 tool exceeds 85% FER on printed; relative ranking established |
| **Phase 2: Preprocessing** | Week 5 | Scan quality improvement | Apply full preprocessing pipeline (§4.3); re-run OCR; measure delta | +15% FER minimum on scan-heavy subset | Delta achieved; pipeline stable; latency budget confirmed |
| **Phase 3: Handwriting** | Week 6–7 | Address critical failure mode | Evaluate TrOCR (base + fine-tuned on 50 form samples); compare vs Textract/Azure DI for handwritten fields specifically | Identify best-accuracy option for HW fields; CER ≤ 10% | Clear winner identified for handwritten field routing |
| **Phase 4: Integration** | Week 8–9 | Build hybrid pipeline | Implement CAT-6 architecture (§4.6); Pydantic v2 validators; Presidio PII; HITL routing logic | End-to-end pipeline processing forms; audit log populated | Pipeline passes 200-form corpus; all required fields captured |
| **Phase 5: Calibration** | Week 10 | Confidence thresholds | Run calibration protocol (§5.3) on all confidence-outputting tools; set HITL thresholds | Empirical accuracy ≥ 90% in high-confidence bin; HITL rate ≤ 10% | Thresholds set with documented empirical basis |
| **Phase 6: Load Testing** | Week 11 | Production readiness | SQS + ECS deployment; test at 2× expected peak load; P95 latency measurement | P95 latency ≤ 10s; no memory leaks; graceful degradation | Load test report signed off by infra team |
| **Phase 7: Compliance Audit** | Week 12 | Regulatory sign-off | Legal review of DPA status (if any cloud API retained); audit trail review; PII recall measurement | PII detection recall ≥ 99.5%; audit trail 100% complete; DPA in place | Legal/compliance team sign-off |
| **Phase 8: Pilot** | Week 13–16 | Real-world validation | Process 1,000 real forms (fully anonymized for metrics); HITL reviewer feedback loop | ≥ 90% of forms fully auto-processed or HITL-reviewed within SLA | Accuracy and throughput match Phase 1 projections on real data |
| **Phase 9: Active Learning** | Month 5–10 | Continuous improvement | Capture HITL corrections; retrain TrOCR on error cases; track error rate trend | Error rate trend: 20% → ≤ 5% over 6 months (R2 evidence) | Monthly error rate report; ≤5% target achieved |

---

## 7. Decision Tree — Which Method for Which Scenario

```
    PDF PARSING METHOD DECISION TREE
    ==================================

    START: Incoming Complaint Form PDF
    │
    ├─► Is data residency / air-gap required?
    │       │
    │       YES ──────────────────────────────────────────────────────────────►
    │       │    RULE OUT: AWS Textract, Azure DI, Google DAI, LlamaParse     │
    │       │    Must use: CAT-1, CAT-3, CAT-4, or CAT-6 (local only)        │
    │       │                                                                  │
    │       NO (cloud OK with DPA)                                            │
    │       │                                                                  ▼
    ├─► Does PDF have a text layer?                               ┌──────────────────────┐
    │       │                                                     │  LOCAL-ONLY PATH     │
    │       YES ──► Is it an AcroForm with programmatic fields?   │  → Go to ★ below     │
    │       │           │                                         └──────────────────────┘
    │       │           YES ──► Use: pypdf AcroForm extraction
    │       │           │       [FASTEST; 100% accurate for digital forms]
    │       │           │
    │       │           NO (text layer present, not AcroForm)
    │       │           │
    │       │           ├─► Complex layout, tables, or mixed content?
    │       │           │       YES ──► Use: Docling (CAT-4)
    │       │           │               [97.9% table accuracy; handles mixed]
    │       │           │       NO (simple text extraction)
    │       │           │           ──► Use: PyMuPDF (CAT-1)
    │       │           │               [Fastest; best for clean text PDFs]
    │       │
    │       NO (scanned/image PDF)
    │       │
    │       ├─► What is scan quality?
    │       │       │
    │       │       < 200 DPI ──► REJECT or notify submitter
    │       │       │             [Accuracy too low to be actionable; ~56% accuracy]
    │       │       │
    │       │       200–300 DPI ──► Apply FULL preprocessing pipeline
    │       │       │               THEN route to next decision
    │       │       │
    │       │       ≥ 300 DPI ──► Apply standard preprocessing
    │       │                     THEN route to next decision
    │       │
    │       ├─► Are handwritten fields present?
    │               │
    │               YES ──► Is volume > 500K pages/month?
    │               │           YES ──► Self-hosted: Docling + TrOCR (fine-tuned)
    │               │           │       [★ LOCAL-ONLY PATH also applies here]
    │               │           NO ──► Cloud OK?
    │               │                   YES ──► AWS Textract Forms API (71.2% HW acc)
    │               │                           or Azure DI Custom Model ($0.030/pg)
    │               │                   NO  ──► ★ Docling + TrOCR (local)
    │               │
    │               NO (printed/typed only)
    │               │
    │               ├─► Volume > 500K pages/month?
    │               │       YES ──► ★ Docling self-hosted (CAT-4/6)
    │               │               [Cost break-even at ~500K–1M pages/month]
    │               │       NO  ──► AWS Textract or Azure DI
    │                               [Managed, lower ops overhead at low volume]
    │
    └─► Special cases:
            │
            ├─► Table-heavy complaint forms?
            │       ──► Docling primary + TATR for table structure confirmation
            │
            ├─► Need free-text narrative field extraction?
            │       ──► Docling extraction → GPT-4 / Claude for
            │           semantic structuring (NOT primary OCR)
            │
            └─► Multi-language forms?
                    ──► PaddleOCR (80+ language support)
                        Confirm language list matches PaddleOCR coverage
```

---

## 8. Recommended Architecture for Production

### 8.1 Infrastructure Stack

| Component | Recommended Technology | Rationale |
|---|---|---|
| **Message queue** | AWS SQS (or RabbitMQ self-hosted) | Right-sized for <10K forms/day; Kafka is overkill |
| **Compute** | AWS ECS (Fargate) or Kubernetes pods | Auto-scaling; Docling containers are stateless |
| **GPU for OCR** | Single A10G or T4 GPU instance | TrOCR fine-tuning + Docling inference; cost-justified at >1K forms/day |
| **Storage** | S3 + server-side encryption | AES-256; versioning for audit trail immutability |
| **PII Redaction** | Microsoft Presidio (self-hosted) | Apache 2.0; no egress; GLiNER-PII integration |
| **Validation** | Pydantic v2 | Field validators + cross-field model validators |
| **HITL Queue** | Custom web app or Label Studio | Threshold-based routing; capture corrections for active learning |
| **Audit Log** | Append-only DynamoDB table or PostgreSQL with trigger | Immutable; timestamp + extractor version + confidence |
| **Monitoring** | Prometheus + Grafana | FER trend, HITL rate, latency P95, error rate by field type |

### 8.2 Infrastructure Flow

```
    PRODUCTION INFRASTRUCTURE FLOW
    ================================

    Customer Portal / Mail Scan
            │
            ▼
    ┌───────────────┐    ┌─────────────────────────────────────────┐
    │  S3 Intake    │───►│  SQS Queue (complaint_forms_raw)        │
    │  Bucket       │    │  Visibility timeout: 30s                │
    │  (encrypted)  │    │  DLQ after 3 failures                   │
    └───────────────┘    └──────────────────┬──────────────────────┘
                                            │
                                            ▼
                         ┌─────────────────────────────────────────┐
                         │  ECS Task: Document Classifier           │
                         │  (LayoutLM) → Routes to correct worker  │
                         └────────┬──────────────┬─────────────────┘
                                  │              │
                         ┌────────▼──────┐  ┌───▼────────────────────┐
                         │ Digital PDF   │  │ Scanned/Mixed PDF       │
                         │ Worker (ECS)  │  │ Worker (ECS + GPU)      │
                         │ PyMuPDF       │  │ Preprocessing Pipeline  │
                         │ 2 vCPU/4GB    │  │ Docling + TrOCR         │
                         └────────┬──────┘  │ 4 vCPU/16GB + T4 GPU   │
                                  │         └───────────┬─────────────┘
                                  └──────────┬──────────┘
                                             │
                                             ▼
                         ┌─────────────────────────────────────────┐
                         │  Pydantic v2 Validation Worker           │
                         │  → Structured JSON output               │
                         │  → Confidence scores per field          │
                         └──────────────────┬──────────────────────┘
                                            │
                         ┌──────────────────┼──────────────────────┐
                         │                  │                       │
                    High conf.         Medium conf.           Low conf.
                    (>0.90)           (0.70–0.90)             (<0.70)
                         │                  │                       │
                         ▼                  ▼                       ▼
                   ┌──────────┐    ┌────────────────┐    ┌───────────────────┐
                   │Auto      │    │Spot-check queue│    │Full HITL review   │
                   │process   │    │(5% sample)     │    │Label Studio /     │
                   │          │    │                │    │custom review UI   │
                   └────┬─────┘    └───────┬────────┘    └────────┬──────────┘
                        └──────────────────┴─────────────────────┘
                                            │
                                            ▼
                         ┌─────────────────────────────────────────┐
                         │  Presidio PII Redaction                  │
                         │  → Redacted PDF stored in S3            │
                         │  → PII fields encrypted separately      │
                         └──────────────────┬──────────────────────┘
                                            │
                                            ▼
                         ┌─────────────────────────────────────────┐
                         │  Audit Log (append-only)                 │
                         │  → Downstream CRM / Case Management     │
                         └─────────────────────────────────────────┘
```

---

## 9. Compliance and PII Handling

### 9.1 Regulatory Requirements Matrix

| Regulation | Requirement | Implementation |
|---|---|---|
| **GDPR Art. 28** | DPA required before any PII to cloud processor | Execute DPA with AWS/Azure/Google before any complaint PDF upload; LlamaParse requires enterprise request |
| **GDPR Art. 22** | Automated decisions affecting individuals: lawful basis + human review rights | Document lawful basis; HITL route ensures human review availability; disclose in privacy notice |
| **CCPA** | Cloud API vendor must be contracted as "Service Provider" | Include in MSA / DPA; verify data not used for vendor's own purposes |
| **CFPB** | 45-day response window; mandatory audit trail | Timestamp all intake events; audit log with doc_id + timestamps |
| **ECOA** | Records retention 25 months | Retention policy on S3; lifecycle rules; immutable audit log |
| **RESPA** | Records retention 3 years | Same S3 lifecycle; separate retention class if mixed portfolio |
| **HIPAA** (if applicable) | BAA required; PHI handling | AWS Textract has HIPAA BAA; design data flows to isolate PHI fields |

### 9.2 PII Entity Coverage — Presidio + GLiNER

| PII Entity | Presidio Default | GLiNER-PII Enhancement | Action |
|---|---|---|---|
| Social Security Number | Yes | Yes | Redact + flag |
| Account / Reference Number | Partial | Yes | Redact + encrypt |
| Full Name | Yes | Yes | Redact in stored doc |
| Date of Birth | Yes | Yes | Redact |
| Home Address | Yes | Yes | Redact |
| Phone Number | Yes | Yes | Redact |
| Email Address | Yes | Yes | Redact |
| Financial Account (ABA/IBAN) | Partial | Yes | Redact + encrypt |
| IP Address | Yes | No | Redact |
| Biometrics / Signature | No | No | Policy: do not extract |

### 9.3 Data Egress Risk by Tool

```
    DATA EGRESS RISK CLASSIFICATION
    ==================================

    ┌─────────────────────────────────────────────────────┐
    │  ZERO EGRESS (local only)                            │
    │  PyMuPDF, pypdf, pdfplumber, Tesseract, PaddleOCR,  │
    │  EasyOCR, TrOCR, Docling, Presidio, Aryn Sycamore  │
    └─────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────┐
    │  CONTROLLED EGRESS (DPA available, region pinnable)  │
    │  AWS Textract (HIPAA BAA available)                  │
    │  Azure Document Intelligence (EU Data Boundary)      │
    │  Google Document AI (Data Processing Amendment)      │
    └─────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────┐
    │  UNCONTROLLED EGRESS (do NOT use without legal       │
    │  review and enterprise DPA negotiation)              │
    │  LlamaParse (DPA requires enterprise request)        │
    │  OpenAI API (verify current DPA; check EU options)  │
    │  Generic LLM APIs without explicit DPA              │
    └─────────────────────────────────────────────────────┘
```

---

## 10. Cost Model Summary

### 10.1 Per-Page Pricing Reference

| Service | OCR / Basic Extraction | Form KVP / Structured | Custom Model | Notes |
|---|---|---|---|---|
| AWS Textract | $0.0015 | $0.065 | — | HIPAA BAA; region pinning |
| Azure Document Intelligence | $0.0015 | $0.010 | $0.030 | EU Data Boundary; best custom pricing |
| Google Document AI | $0.00065 | $0.030 | Variable | Lowest base OCR cost |
| LlamaParse (basic) | $0.00375 | — | $0.075 (premium) | No DPA standard; high cost |
| Mistral OCR 3 (batch) | $0.001/1K pages | — | — | New entrant; verify DPA |
| Docling (self-hosted) | ~$0 API | ~$0 API | ~$0 API | Compute cost only |

### 10.2 Monthly Cost Model at Scale

```
    MONTHLY COST COMPARISON (Forms/month; 1 form ≈ 3 pages avg)
    =============================================================

    Volume:        10K forms    100K forms   500K forms   1M forms
                   (30K pages)  (300K pages) (1.5M pages) (3M pages)

    AWS Textract
    (Forms API):   $1,950       $19,500      $97,500      $195,000
                   [$0.065/pg]

    Azure DI
    (Custom):      $900         $9,000       $45,000      $90,000
                   [$0.030/pg]

    Google DAI
    (Form Parser): $900         $9,000       $45,000      $90,000
                   [$0.030/pg]

    Docling
    (self-hosted): ~$200        ~$800        ~$2,500      ~$4,500
    [EC2/ECS est.] (t3.xlarge)  (2x c5.2xl) (ECS+GPU)    (ECS+GPU×2)

    BREAK-EVEN vs Docling:
    Azure DI / Google DAI: ~500K pages/month (~167K forms/month)
    AWS Textract (Forms):  ~77K pages/month (~26K forms/month)
```

### 10.3 Total Cost of Ownership Factors

- **Self-hosted adds:**
  - 1.0–1.5 FTE engineering for pipeline maintenance, model updates, infrastructure
  - GPU instance for TrOCR/Docling inference (~$300–900/month for A10G spot)
  - HITL reviewer labor: at 5% escalation rate, budget 1 FTE per ~500 forms/day throughput
- **Cloud adds:**
  - DPA negotiation and legal review: one-time 20–40 hours
  - Per-document API cost grows linearly with volume
  - Vendor lock-in and API change risk

---

## 11. Red Flags and Anti-Patterns to Avoid

### 11.1 Architecture Anti-Patterns

- **Using a single tool for all form types.** OmniDocBench shows 55+ point variance by document type — route by form type, don't use one tool universally
- **Deploying without a preprocessing pipeline.** Skipping deskew/denoise/contrast on scanned forms foregoes +22% accuracy for effectively zero cost
- **Setting HITL thresholds without empirical calibration.** Cloud API confidence scores are not calibrated probabilities — they are ordinal rankings. Setting threshold of 0.90 without measuring actual accuracy at that band will produce wrong routing
- **Using page-level chunking on short focused forms.** Short focused documents should NOT be chunked — preserve full form as single context unit
- **Unstructured for real-time complaint intake.** 51–140 seconds per form is disqualifying. Use only for offline batch processing

### 11.2 ML/AI Anti-Patterns

- **Using LLMs as primary OCR for numeric financial fields.** Documented number extraction failures (Fernández, 2025) make this unacceptable for forms with monetary amounts, account numbers, or reference IDs
- **Few-shot prompting without contamination controls.** Production evidence (Alan, 2025) shows few-shot examples can cause hallucination via example contamination
- **Trusting VLM output for chart/graph data.** NVIDIA benchmark: VLMs hallucinate chart data; 32× throughput disadvantage vs OCR
- **Treating benchmark numbers as production estimates.** Domain composition drives 55+ point variance; measure on your actual forms
- **Fine-tuning on un-anonymized PII data.** Never use real complaint forms with customer PII as TrOCR fine-tuning data

### 11.3 Compliance Anti-Patterns

- **Sending complaint PDFs to any cloud API before DPA is executed.** GDPR Art. 28 violation
- **Using LlamaParse in production without enterprise DPA.** Standard plan has no DPA
- **Building a pipeline without CFPB-compliant audit trail from day one.** Retrofitting is significantly harder than designing it in
- **Treating compliance as a one-time checkbox.** Build a compliance review cadence into your MLOps calendar

### 11.4 Evaluation Anti-Patterns

- **Evaluating on vendor-provided sample documents.** These are typically best-case examples
- **Using form-level accuracy instead of field-level accuracy.** A form with 20 fields and 1 error scores 95% form-level but may have a critical missing field
- **Skipping handwriting-specific evaluation.** Most benchmarks are printed-text-heavy; handwriting is where complaint forms fail in production

---

## 12. Final Recommendation Matrix

### 12.1 Scoring Matrix — Primary Tools

Scoring: 1 (poor) → 5 (excellent). Weights reflect complaint form priorities.

| Tool | Accuracy: Printed (w=0.15) | Accuracy: Handwritten (w=0.25) | Table Extraction (w=0.10) | Latency (w=0.10) | Compliance/Local (w=0.20) | Cost at Scale (w=0.15) | Maintenance Burden (w=0.05) | **Weighted Score** |
|---|---|---|---|---|---|---|---|---|
| **Docling + TrOCR (hybrid)** | 5 | 5 | 5 | 3 | 5 | 5 | 2 | **4.55** |
| **Docling (self-hosted)** | 5 | 3 | 5 | 4 | 5 | 5 | 3 | **4.30** |
| **Azure DI Custom** | 4 | 4 | 4 | 4 | 4 | 3 | 4 | **3.90** |
| **PyMuPDF (digital only)** | 5 | 1 | 3 | 5 | 5 | 5 | 5 | **3.80** |
| **AWS Textract Forms** | 4 | 4 | 4 | 5 | 3 | 2 | 5 | **3.65** |
| **PaddleOCR** | 4 | 2 | 2 | 4 | 5 | 5 | 3 | **3.55** |
| **Unstructured** | 3 | 2 | 3 | 1 | 5 | 4 | 4 | **2.95** |
| **GPT-4/LLM direct** | 3 | 4 | 3 | 3 | 1 | 2 | 5 | **2.70** |
| **LlamaParse** | 4 | 3 | 3 | 4 | 1 | 1 | 5 | **2.65** |

### 12.2 Recommendation by Scenario

| Scenario | Primary Recommendation | Fallback / Supplement | Avoid |
|---|---|---|---|
| **All-local, PII-sensitive, scale >167K forms/month** | Docling + TrOCR + Presidio (CAT-6 hybrid) | PaddleOCR for multilingual scans | Any cloud API without DPA |
| **Cloud OK, low volume (<26K forms/month)** | AWS Textract Forms API | Azure DI Custom (lower price) | LlamaParse (no standard DPA) |
| **Cloud OK, medium volume (26K–167K forms/month)** | Azure DI Custom | Google Document AI Form Parser | AWS Textract (cost too high) |
| **Digital AcroForm submissions only** | PyMuPDF AcroForm extraction | pypdf as fallback | Any OCR (unnecessary overhead) |
| **Handwriting-dominant forms** | Docling + TrOCR (fine-tuned) | Azure DI Custom Model | GPT-4 direct (number errors) |
| **Multilingual complaint forms** | PaddleOCR (80+ languages) | Docling + language-specific OCR | Tesseract (language coverage gaps) |
| **EU data residency mandatory** | Docling self-hosted | Azure DI (EU Data Boundary + containers) | AWS Textract (unless EU region + DPA confirmed) |
| **Fast POC / prototype** | Docling on local machine | AWS Textract sandbox | Unstructured (too slow for interactive use) |

### 12.3 Build Order Priority

```
    IMPLEMENTATION PRIORITY ORDER
    ===============================

    SPRINT 1–2 (Foundations):
    ┌─────────────────────────────────────────────────────┐
    │ 1. Annotated test corpus (200 forms, ground truth)  │
    │ 2. Evaluation harness (metrics from §5.1)           │
    │ 3. Preprocessing pipeline (deskew/denoise)          │
    │ 4. Docling baseline (all form types)                │
    └─────────────────────────────────────────────────────┘

    SPRINT 3–4 (Production Core):
    ┌─────────────────────────────────────────────────────┐
    │ 5. PyMuPDF AcroForm extraction for digital PDFs     │
    │ 6. Pydantic v2 validation models                    │
    │ 7. Presidio PII redaction integration               │
    │ 8. Audit log (append-only)                          │
    └─────────────────────────────────────────────────────┘

    SPRINT 5–6 (HITL + Handwriting):
    ┌─────────────────────────────────────────────────────┐
    │ 9.  HITL routing and review interface               │
    │ 10. TrOCR fine-tuning on handwritten form samples   │
    │ 11. Confidence calibration (§5.3)                   │
    │ 12. SQS + ECS deployment                            │
    └─────────────────────────────────────────────────────┘

    SPRINT 7–8 (Scale + Compliance):
    ┌─────────────────────────────────────────────────────┐
    │ 13. Load testing at 2× peak                         │
    │ 14. Active learning feedback loop                   │
    │ 15. Legal/compliance audit + DPA sign-off           │
    │ 16. Monitoring dashboard (FER, HITL rate, latency)  │
    └─────────────────────────────────────────────────────┘
```

---

## Appendix: Quick Reference — Key Numbers

| Metric | Value | Source |
|---|---|---|
| Docling table accuracy | 97.9% | Procycons 2025 benchmark |
| Preprocessing accuracy gain | +22% median (70% → 92%) | R2 handwriting research |
| Printed text DPI threshold | 300 DPI → 99%+ accuracy | Industry standard |
| HITL efficiency target | 5% of forms → human review | R2 production patterns |
| Active learning improvement | 20% → 5% error rate over 6 months | R2 production evidence |
| Throughput gap: OCR vs VLM | 32× (8.47 vs 0.26 pages/sec) | NVIDIA benchmark |
| Cloud break-even vs self-hosted | ~500K–1M pages/month | R2 pricing analysis |
| Per-type variance (benchmark) | 55+ points | Applied AI 2025 / OmniDocBench |
| LayoutLMv3 F1 on FUNSD | 0.9472 | MS CVPR 2022 |
| TrOCR CER (clean handwriting) | ~2.9% on IAM | R2 HTR research |
| Uber Engineering improvement | 90% accuracy, 70% handling time reduction | R2 production case study |
| CFPB audit trail | Mandatory | CFPB regulation |
| ECOA retention | 25 months | ECOA regulation |
| RESPA retention | 3 years | RESPA regulation |
