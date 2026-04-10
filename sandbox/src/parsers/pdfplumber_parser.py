"""
pdfplumber parser — best rule-based table extraction from text-layer PDFs.

License: MIT (free, commercial-friendly)
Scanned PDFs: NOT supported (text layer only)
Tables: YES — extract_table() with lattice/stream detection
Handwriting: NOT supported
Best for: Text PDFs with embedded tables, bounding-box-level text access

Note: pdfplumber is built on pdfminer.six. It is slower than PyMuPDF
but provides the most granular access to character positions, which is
useful for detecting checkbox states from geometry (checkbox_rect near text).
"""

from __future__ import annotations

from pathlib import Path

from src.parsers.base import BaseParser, ExtractedTable, ParseResult


class PDFPlumberParser(BaseParser):

    # Table extraction settings tunable per document type
    # See pdfplumber docs: https://github.com/jsvine/pdfplumber#extracting-tables
    TABLE_SETTINGS = {
        "vertical_strategy": "lines",      # "lines" | "lines_strict" | "text" | "explicit"
        "horizontal_strategy": "lines",
        "snap_tolerance": 3,
        "join_tolerance": 3,
        "edge_min_length": 3,
        "min_words_vertical": 3,
        "min_words_horizontal": 1,
        "intersection_tolerance": 3,
    }

    @property
    def name(self) -> str:
        return "pdfplumber"

    @property
    def version(self) -> str:
        try:
            import pdfplumber
            return pdfplumber.__version__
        except ImportError:
            return "not installed"

    @property
    def license(self) -> str:
        return "MIT"

    @property
    def supports_scanned(self) -> bool:
        return False

    @property
    def supports_tables(self) -> bool:
        return True

    @property
    def supports_handwriting(self) -> bool:
        return False

    def _extract(self, pdf_path: Path) -> ParseResult:
        import pdfplumber

        result = ParseResult(parser_name=self.name, pdf_path=str(pdf_path))
        pages_text: list[str] = []
        all_text_parts: list[str] = []
        all_tables: list[ExtractedTable] = []
        errors: list[str] = []

        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Text extraction
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                pages_text.append(text)
                all_text_parts.append(text)

                # Table extraction
                # pdfplumber may raise on pages with complex layouts
                try:
                    tables = page.extract_tables(self.TABLE_SETTINGS)
                    for table in tables:
                        if table:
                            # Replace None cells with empty string
                            clean_rows = [
                                [cell if cell is not None else "" for cell in row]
                                for row in table
                            ]
                            all_tables.append(
                                ExtractedTable(
                                    page_number=page_num,
                                    rows=clean_rows,
                                    confidence=None,
                                )
                            )
                except Exception as e:
                    errors.append(f"Page {page_num} table extraction error: {e}")

        result.full_text = "\n\n".join(all_text_parts)
        result.pages_text = pages_text
        result.tables = all_tables
        result.errors = errors

        return result
