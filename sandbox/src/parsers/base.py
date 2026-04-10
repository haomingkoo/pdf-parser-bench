"""
Abstract base class for all PDF parsers in the evaluation sandbox.

Every parser must implement extract() and return a ParseResult.
This ensures all parsers are evaluated on identical interfaces.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ExtractedField:
    """A single extracted field (key-value pair or free-text region)."""
    name: str                          # Field label / key
    value: str                         # Extracted text value
    confidence: Optional[float] = None # 0.0–1.0 if parser provides it; None otherwise
    page_number: int = 1
    bbox: Optional[tuple[float, float, float, float]] = None  # (x0, y0, x1, y1)
    field_type: str = "text"           # "text" | "checkbox" | "table_cell" | "handwritten"


@dataclass
class ExtractedTable:
    """A table extracted from the document."""
    page_number: int
    rows: list[list[str]]              # List of rows; each row is list of cell strings
    confidence: Optional[float] = None
    bbox: Optional[tuple[float, float, float, float]] = None


@dataclass
class ParseResult:
    """
    Standardized output from any parser.

    All parsers return this structure so metrics can be computed identically.
    None values indicate the parser does not support that output type.
    """
    parser_name: str
    pdf_path: str

    # Raw text (full document, in reading order where supported)
    full_text: Optional[str] = None

    # Structured field extraction (key-value pairs from forms)
    fields: list[ExtractedField] = field(default_factory=list)

    # Tables
    tables: list[ExtractedTable] = field(default_factory=list)

    # Per-page text (useful for multi-page form + attachment PDFs)
    pages_text: list[str] = field(default_factory=list)

    # Performance
    wall_time_seconds: float = 0.0
    peak_memory_mb: Optional[float] = None

    # Error tracking (partial success is fine; total failure is tracked here)
    errors: list[str] = field(default_factory=list)
    success: bool = True

    # Parser metadata
    parser_version: str = ""
    preprocessing_applied: list[str] = field(default_factory=list)


class BaseParser(ABC):
    """
    Abstract base class. All parser wrappers must inherit from this.

    Usage:
        parser = DoclingParser()
        result = parser.extract(Path("form.pdf"))
    """

    def __init__(self, apply_preprocessing: bool = False):
        """
        Args:
            apply_preprocessing: If True, run the preprocessing pipeline
                (deskew, denoise, contrast) before extraction. Only relevant
                for scanned PDFs. Adds latency.
        """
        self.apply_preprocessing = apply_preprocessing

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this parser, e.g. 'docling', 'pymupdf'."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Package version string."""
        ...

    @property
    def license(self) -> str:
        """SPDX license identifier."""
        return "unknown"

    @property
    def supports_handwriting(self) -> bool:
        """Whether this parser has meaningful handwriting recognition."""
        return False

    @property
    def supports_tables(self) -> bool:
        """Whether this parser extracts table structure."""
        return False

    @property
    def supports_scanned(self) -> bool:
        """Whether this parser handles image/scanned PDFs (requires OCR)."""
        return False

    @abstractmethod
    def _extract(self, pdf_path: Path) -> ParseResult:
        """
        Core extraction logic. Implement in each subclass.
        Do not call this directly — use extract() which wraps timing/errors.
        """
        ...

    def extract(self, pdf_path: Path) -> ParseResult:
        """
        Public extraction entry point. Handles:
        - Timing
        - Optional preprocessing
        - Exception catching (partial failures should not crash the harness)
        """
        start = time.perf_counter()
        try:
            if self.apply_preprocessing and self.supports_scanned:
                pdf_path = self._preprocess(pdf_path)
            result = self._extract(pdf_path)
        except Exception as e:
            result = ParseResult(
                parser_name=self.name,
                pdf_path=str(pdf_path),
                success=False,
                errors=[f"{type(e).__name__}: {e}"],
            )
        result.wall_time_seconds = time.perf_counter() - start
        result.parser_version = self.version
        return result

    def _preprocess(self, pdf_path: Path) -> Path:
        """
        Run the image preprocessing pipeline on a scanned PDF.
        Returns path to preprocessed PDF (may be same path if no-op).
        Import is deferred to avoid loading OpenCV for text-only parsers.
        """
        from src.preprocessing.pipeline import PreprocessingPipeline
        pipeline = PreprocessingPipeline()
        return pipeline.run(pdf_path)
