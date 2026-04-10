"""
pypdf parser — text-layer PDFs and AcroForm field extraction.

License: BSD-3-Clause (free, commercial-friendly)
Scanned PDFs: NOT supported (no OCR)
Tables: NOT supported
Handwriting: NOT supported
Best for: Digital AcroForms, simple text extraction

Note: pypdf is the maintained successor to PyPDF2. Use pypdf, not PyPDF2.
"""

from __future__ import annotations

from pathlib import Path

from src.parsers.base import BaseParser, ExtractedField, ParseResult


class PyPDFParser(BaseParser):

    @property
    def name(self) -> str:
        return "pypdf"

    @property
    def version(self) -> str:
        try:
            import pypdf
            return pypdf.__version__
        except ImportError:
            return "not installed"

    @property
    def license(self) -> str:
        return "BSD-3-Clause"

    @property
    def supports_scanned(self) -> bool:
        return False  # Text layer only

    @property
    def supports_tables(self) -> bool:
        return False

    @property
    def supports_handwriting(self) -> bool:
        return False

    def _extract(self, pdf_path: Path) -> ParseResult:
        import pypdf

        result = ParseResult(parser_name=self.name, pdf_path=str(pdf_path))

        reader = pypdf.PdfReader(str(pdf_path))
        pages_text: list[str] = []
        all_text_parts: list[str] = []

        for page in reader.pages:
            text = page.extract_text() or ""
            pages_text.append(text)
            all_text_parts.append(text)

        result.full_text = "\n\n".join(all_text_parts)
        result.pages_text = pages_text

        # AcroForm field extraction — only works on digitally fillable PDFs
        # Returns empty dict for print-sign-scan forms
        raw_fields = reader.get_fields()
        if raw_fields:
            for field_name, field_obj in raw_fields.items():
                value = ""
                if field_obj:
                    # PdfReader returns Field objects or dicts depending on version
                    value = str(field_obj.get("/V", "")) if hasattr(field_obj, "get") else str(field_obj)
                result.fields.append(
                    ExtractedField(
                        name=field_name,
                        value=value,
                        field_type="acroform",
                        confidence=None,  # AcroForm extraction is deterministic, no confidence score
                    )
                )

        return result
