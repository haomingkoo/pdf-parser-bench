"""
PyMuPDF (fitz) parser — fast text extraction + AcroForm fields.

License: AGPL-3.0 (free for open-source and internal use;
         commercial redistribution requires paid Artifex license)
Scanned PDFs: Only via Tesseract integration (not enabled by default here)
Tables: Basic bordered table detection via find_tables()
Handwriting: NOT supported (requires external OCR)
Best for: Fast text extraction, AcroForm fields, rendering pages as images

Performance: ~10-50x faster than pdfminer-based tools on large documents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.parsers.base import BaseParser, ExtractedField, ExtractedTable, ParseResult


class PyMuPDFParser(BaseParser):

    @property
    def name(self) -> str:
        return "pymupdf"

    @property
    def version(self) -> str:
        try:
            import fitz
            return fitz.version[0]
        except ImportError:
            return "not installed"

    @property
    def license(self) -> str:
        return "AGPL-3.0"

    @property
    def supports_scanned(self) -> bool:
        return False  # True only with Tesseract integration (not enabled here)

    @property
    def supports_tables(self) -> bool:
        return True  # Basic table detection via find_tables()

    @property
    def supports_handwriting(self) -> bool:
        return False

    def _extract(self, pdf_path: Path) -> ParseResult:
        import fitz  # PyMuPDF

        result = ParseResult(parser_name=self.name, pdf_path=str(pdf_path))
        doc = fitz.open(str(pdf_path))

        pages_text: list[str] = []
        all_text_parts: list[str] = []
        all_tables: list[ExtractedTable] = []

        for page_num, page in enumerate(doc, start=1):
            # Extract text preserving reading order (uses layout analysis)
            text = page.get_text("text")
            pages_text.append(text)
            all_text_parts.append(text)

            # Basic table extraction (works for bordered tables in text-layer PDFs)
            # Note: merged cells and borderless tables require custom post-processing
            try:
                tabs = page.find_tables()
                for tab in tabs:
                    rows = tab.extract()  # list[list[str]]
                    if rows:
                        all_tables.append(
                            ExtractedTable(
                                page_number=page_num,
                                rows=rows,
                                confidence=None,
                            )
                        )
            except Exception:
                pass  # find_tables() may fail on complex pages; non-fatal

        result.full_text = "\n\n".join(all_text_parts)
        result.pages_text = pages_text
        result.tables = all_tables

        # AcroForm widget fields (for digitally fillable PDFs)
        for page in doc:
            for widget in page.widgets():
                if widget.field_name:
                    value = widget.field_value or ""
                    result.fields.append(
                        ExtractedField(
                            name=widget.field_name,
                            value=str(value),
                            field_type="acroform",
                            page_number=page.number + 1,
                            bbox=tuple(widget.rect) if widget.rect else None,
                            confidence=None,
                        )
                    )

        doc.close()
        return result

    def render_page_as_image(self, pdf_path: Path, page_num: int = 0, dpi: int = 300) -> bytes:
        """
        Render a PDF page as a PNG image at the specified DPI.
        Useful for feeding scanned-quality pages to OCR engines.
        Not used in the main evaluation loop, but available as a utility.
        """
        import fitz
        doc = fitz.open(str(pdf_path))
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes
