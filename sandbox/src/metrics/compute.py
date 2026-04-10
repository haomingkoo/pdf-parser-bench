"""
Evaluation metrics for PDF parsing comparison.

Metrics implemented:
- Character Error Rate (CER): edit distance / total ground truth chars
- Word Error Rate (WER): word-level edit distance
- Field Extraction Rate (FER): correctly extracted fields / total expected fields
- Table Cell Accuracy: correctly extracted cells / total cells
- Field F1: precision + recall on field names found vs expected
- Latency: wall_time_seconds from ParseResult
- Calibration data: (confidence, is_correct) pairs for reliability diagram

Ground truth format (JSON):
{
  "full_text": "...",
  "fields": [{"name": "complainant_name", "value": "John Smith"}, ...],
  "tables": [{"rows": [["header1", "header2"], ["val1", "val2"]]}],
  "page_count": 3
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class FieldMetrics:
    """Per-field-type accuracy breakdown."""
    field_type: str                  # e.g. "handwritten", "printed", "checkbox", "date"
    total: int = 0
    correct: int = 0
    cer_values: list[float] = None

    def __post_init__(self):
        if self.cer_values is None:
            self.cer_values = []

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0

    @property
    def mean_cer(self) -> float:
        return float(np.mean(self.cer_values)) if self.cer_values else 1.0


@dataclass
class EvaluationResult:
    """Complete evaluation result for one (parser, document) pair."""
    parser_name: str
    document_id: str
    doc_type: str = ""        # e.g. "digital_acroform", "scanned_clean_300dpi"

    # Text accuracy
    cer: float = 1.0          # 0.0 = perfect; 1.0 = all wrong
    wer: float = 1.0

    # Field extraction
    fer: float = 0.0          # Field Extraction Rate (0.0–1.0)
    field_precision: float = 0.0
    field_recall: float = 0.0
    field_f1: float = 0.0
    field_metrics_by_type: dict[str, FieldMetrics] = None

    # Table accuracy
    table_cell_accuracy: float = 0.0
    table_structure_accuracy: float = 0.0  # Row/col count match

    # Performance
    wall_time_seconds: float = 0.0
    pages_per_second: float = 0.0

    # Calibration
    confidence_pairs: list[tuple[float, bool]] = None  # (confidence, is_correct)

    # Error analysis
    systematic_errors: list[str] = None   # Detected patterns (0↔O, date format, etc.)
    parse_errors: list[str] = None        # Parser-level errors

    def __post_init__(self):
        if self.field_metrics_by_type is None:
            self.field_metrics_by_type = {}
        if self.confidence_pairs is None:
            self.confidence_pairs = []
        if self.systematic_errors is None:
            self.systematic_errors = []
        if self.parse_errors is None:
            self.parse_errors = []

    def to_dict(self) -> dict:
        return {
            "parser": self.parser_name,
            "document": self.document_id,
            "doc_type": self.doc_type,
            "cer": round(self.cer, 4),
            "wer": round(self.wer, 4),
            "fer": round(self.fer, 4),
            "field_f1": round(self.field_f1, 4),
            "table_cell_accuracy": round(self.table_cell_accuracy, 4),
            "wall_time_s": round(self.wall_time_seconds, 3),
            "pages_per_second": round(self.pages_per_second, 3),
            "systematic_errors": self.systematic_errors,
            "parse_errors": self.parse_errors,
        }


class MetricsComputer:

    def compute(
        self,
        parse_result,          # ParseResult from any parser
        ground_truth_path: Path,
        page_count: int = 1,
    ) -> EvaluationResult:
        """
        Compute all metrics for a (parse_result, ground_truth) pair.

        Args:
            parse_result: ParseResult from BaseParser.extract()
            ground_truth_path: Path to ground truth JSON file
            page_count: Number of pages in the document (for pages/sec calc)
        """
        with open(ground_truth_path) as f:
            gt = json.load(f)

        eval_result = EvaluationResult(
            parser_name=parse_result.parser_name,
            document_id=ground_truth_path.stem,
            wall_time_seconds=parse_result.wall_time_seconds,
            pages_per_second=page_count / parse_result.wall_time_seconds
                if parse_result.wall_time_seconds > 0 else 0.0,
            parse_errors=parse_result.errors,
        )

        if not parse_result.success:
            return eval_result  # Parser failed; all metrics default to worst case

        # --- Text accuracy ---
        if gt.get("full_text") and parse_result.full_text:
            eval_result.cer = self._cer(parse_result.full_text, gt["full_text"])
            eval_result.wer = self._wer(parse_result.full_text, gt["full_text"])

        # --- Field extraction ---
        if gt.get("fields"):
            self._compute_field_metrics(parse_result, gt["fields"], eval_result)

        # --- Table accuracy ---
        if gt.get("tables") and parse_result.tables:
            eval_result.table_cell_accuracy = self._table_cell_accuracy(
                parse_result.tables, gt["tables"]
            )
            eval_result.table_structure_accuracy = self._table_structure_accuracy(
                parse_result.tables, gt["tables"]
            )

        # --- Confidence calibration ---
        if parse_result.fields:
            eval_result.confidence_pairs = self._confidence_pairs(
                parse_result.fields, gt.get("fields", [])
            )

        # --- Systematic error detection ---
        if parse_result.full_text and gt.get("full_text"):
            eval_result.systematic_errors = self._detect_systematic_errors(
                parse_result.full_text, gt["full_text"]
            )

        return eval_result

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize text before CER/WER computation.
        Without this, cross-parser differences reflect whitespace/unicode
        serialization artifacts more than extraction quality.

        Steps:
        - Unicode NFC normalization (handles different accent encodings)
        - Replace non-breaking spaces (U+00A0) with regular space
        - Collapse multiple whitespace to single space
        - Strip leading/trailing whitespace
        - Lowercase (optional: comment out if case matters for your GT)
        """
        import unicodedata
        import re
        text = unicodedata.normalize("NFC", text)
        text = text.replace("\u00a0", " ")          # non-breaking space
        text = text.replace("\u2019", "'")           # right single quotation mark
        text = re.sub(r"\s+", " ", text)
        return text.strip().lower()

    @staticmethod
    def _cer(hypothesis: str, reference: str) -> float:
        """
        Character Error Rate = Levenshtein(hyp, ref) / len(normalized_ref)
        Returns 1.0 if reference is empty (avoid division by zero).
        Both strings are normalized before comparison.
        """
        if not reference:
            return 1.0
        import editdistance
        # Note: normalization is called here but _normalize_text is a static method
        # on the same class; call via the module-level helper to avoid self dependency
        import unicodedata, re
        def norm(t):
            t = unicodedata.normalize("NFC", t).replace("\u00a0", " ")
            return re.sub(r"\s+", " ", t).strip().lower()
        h, r = norm(hypothesis), norm(reference)
        if not r:
            return 1.0
        dist = editdistance.eval(h, r)
        return min(dist / len(r), 1.0)

    @staticmethod
    def _wer(hypothesis: str, reference: str) -> float:
        """
        Word Error Rate = word-level Levenshtein / word count in reference.
        Clamped to 1.0: WER can exceed 1.0 when the hypothesis has more
        insertions than the reference has words. Clamping prevents summary
        statistics from being pulled above the [0, 1] expected range.

        Normalization (lowercase, whitespace collapse) is applied here before
        passing to jiwer so the result is purely about word-level accuracy.
        """
        import unicodedata, re
        from jiwer import wer as _jiwer_wer

        def _norm(t: str) -> str:
            t = unicodedata.normalize("NFC", t).replace("\u00a0", " ")
            return re.sub(r"\s+", " ", t).strip().lower()

        ref_n = _norm(reference)
        hyp_n = _norm(hypothesis)
        if not ref_n:
            return 1.0
        try:
            score = _jiwer_wer(ref_n, hyp_n)
            return min(float(score), 1.0)
        except Exception:
            return 1.0

    def _compute_field_metrics(
        self,
        parse_result,
        gt_fields: list[dict],
        eval_result: EvaluationResult,
    ) -> None:
        """
        Compute FER, precision, recall, F1 for field extraction.

        Field name matching uses fuzzy similarity (rapidfuzz token_sort_ratio ≥ 80)
        so that OCR parsers that slightly mangle field labels (e.g. "Complaint Date:"
        vs "Complaint Date") still score correctly.

        Checkbox fields use exact normalized match (not CER threshold) because a
        checkbox is either checked or unchecked — partial credit is meaningless.
        """
        from rapidfuzz import fuzz

        gt_by_name = {f["name"].lower().strip(): f for f in gt_fields}
        extracted_by_name = {
            f.name.lower().strip(): f for f in parse_result.fields
        }

        def _fuzzy_match(name: str, candidates: dict, threshold: int = 80) -> str | None:
            """Return the best matching key in candidates, or None if below threshold."""
            if name in candidates:
                return name
            best, best_score = None, 0
            for cand in candidates:
                score = fuzz.token_sort_ratio(name, cand)
                if score > best_score:
                    best, best_score = cand, score
            return best if best_score >= threshold else None

        # Field presence: which expected fields were found (fuzzy)?
        gt_to_ext: dict[str, str | None] = {}
        for gt_name in gt_by_name:
            gt_to_ext[gt_name] = _fuzzy_match(gt_name, extracted_by_name)

        found_count = sum(1 for v in gt_to_ext.values() if v is not None)
        eval_result.fer = found_count / len(gt_by_name) if gt_by_name else 0.0

        # Which extracted names have no GT match?
        matched_ext_names = set(v for v in gt_to_ext.values() if v is not None)
        fp = sum(1 for ext_name in extracted_by_name if ext_name not in matched_ext_names)
        fn = len(gt_by_name) - found_count
        tp = found_count
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)
               if (precision + recall) > 0 else 0.0)

        eval_result.field_precision = precision
        eval_result.field_recall = recall
        eval_result.field_f1 = f1

        # Per-field-type breakdown
        field_type_metrics: dict[str, FieldMetrics] = {}
        for gt_field in gt_fields:
            gt_name = gt_field["name"].lower().strip()
            ftype = gt_field.get("type", "text")
            if ftype not in field_type_metrics:
                field_type_metrics[ftype] = FieldMetrics(field_type=ftype)
            field_type_metrics[ftype].total += 1

            ext_name = gt_to_ext.get(gt_name)
            if ext_name is not None:
                extracted_val = extracted_by_name[ext_name].value or ""
                gt_val = gt_field.get("value", "")

                if ftype == "checkbox":
                    # Exact normalized match — no partial credit for checkboxes
                    is_correct = (
                        extracted_val.strip().lower() == (gt_val or "").strip().lower()
                    )
                    field_type_metrics[ftype].cer_values.append(0.0 if is_correct else 1.0)
                    if is_correct:
                        field_type_metrics[ftype].correct += 1
                else:
                    cer = self._cer(extracted_val, gt_val) if gt_val else 1.0
                    field_type_metrics[ftype].cer_values.append(cer)
                    if cer <= 0.05:  # ≤5% CER = correct
                        field_type_metrics[ftype].correct += 1

        eval_result.field_metrics_by_type = field_type_metrics

    @staticmethod
    def _table_cell_accuracy(extracted_tables, gt_tables: list[dict]) -> float:
        """
        Cell-level table accuracy.
        Computes the ratio of correctly extracted cells to total expected cells.

        Uses fuzzy matching (rapidfuzz ratio ≥ 85%) to handle minor OCR differences.
        """
        from rapidfuzz import fuzz

        total_cells = 0
        correct_cells = 0

        for i, gt_table in enumerate(gt_tables):
            if i >= len(extracted_tables):
                # Table not extracted
                gt_rows = gt_table.get("rows", [])
                total_cells += sum(len(row) for row in gt_rows)
                continue

            ext_rows = extracted_tables[i].rows
            gt_rows = gt_table.get("rows", [])

            for r_idx, gt_row in enumerate(gt_rows):
                for c_idx, gt_cell in enumerate(gt_row):
                    total_cells += 1
                    if r_idx < len(ext_rows) and c_idx < len(ext_rows[r_idx]):
                        ext_cell = ext_rows[r_idx][c_idx] or ""
                        similarity = fuzz.ratio(
                            (gt_cell or "").strip().lower(),
                            ext_cell.strip().lower()
                        )
                        if similarity >= 85:
                            correct_cells += 1

        return correct_cells / total_cells if total_cells > 0 else 0.0

    @staticmethod
    def _table_structure_accuracy(extracted_tables, gt_tables: list[dict]) -> float:
        """
        Structure accuracy: are row and column counts correct?
        A table with correct row/col counts scores 1.0; otherwise proportional.
        """
        if not gt_tables:
            return 0.0
        scores = []
        for i, gt_table in enumerate(gt_tables):
            if i >= len(extracted_tables):
                scores.append(0.0)
                continue
            gt_rows = gt_table.get("rows", [])
            ext_rows = extracted_tables[i].rows
            if not gt_rows:
                continue
            gt_col_count = max(len(row) for row in gt_rows) if gt_rows else 0
            ext_col_count = max(len(row) for row in ext_rows) if ext_rows else 0
            row_score = 1.0 - abs(len(gt_rows) - len(ext_rows)) / len(gt_rows)
            col_score = (1.0 if gt_col_count == ext_col_count
                         else 1.0 - abs(gt_col_count - ext_col_count) / gt_col_count)
            scores.append(max(0.0, (row_score + col_score) / 2))
        return float(np.mean(scores)) if scores else 0.0

    @staticmethod
    def _confidence_pairs(
        extracted_fields,
        gt_fields: list[dict],
    ) -> list[tuple[float, bool]]:
        """
        Build (confidence, is_correct) pairs for calibration analysis.
        Only includes fields that have a confidence score.
        """
        from rapidfuzz import fuzz
        gt_by_name = {f["name"].lower().strip(): f.get("value", "") for f in gt_fields}
        pairs = []
        for ef in extracted_fields:
            if ef.confidence is None:
                continue
            name = ef.name.lower().strip()
            gt_val = gt_by_name.get(name, "")
            is_correct = fuzz.ratio(ef.value or "", gt_val) >= 85
            pairs.append((ef.confidence, is_correct))
        return pairs

    @staticmethod
    def _detect_systematic_errors(hypothesis: str, reference: str) -> list[str]:
        """
        Detect known systematic OCR error patterns.
        These are fixable with post-processing rules.

        Patterns checked:
        - 0/O confusion
        - 1/l/I confusion
        - Date format ambiguity
        - Missing accented characters
        """
        errors = []
        hyp = hypothesis
        ref = reference

        # Zero vs O confusion
        if ("0" in ref and "O" in hyp and "0" not in hyp):
            errors.append("systematic_zero_O_confusion")

        # One/l/I confusion
        import re
        if re.search(r'\b1\b', ref) and re.search(r'\bl\b', hyp):
            errors.append("systematic_one_l_confusion")

        # Date format ambiguity: DD/MM vs MM/DD
        date_pattern = r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b'
        ref_dates = re.findall(date_pattern, ref)
        hyp_dates = re.findall(date_pattern, hyp)
        if ref_dates and hyp_dates:
            for ref_d, hyp_d in zip(ref_dates, hyp_dates):
                if ref_d != hyp_d and ref_d[0] == hyp_d[1] and ref_d[1] == hyp_d[0]:
                    errors.append("systematic_date_format_ambiguity_DDMM_vs_MMDD")
                    break

        return errors
