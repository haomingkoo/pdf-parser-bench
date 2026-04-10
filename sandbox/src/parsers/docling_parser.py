"""
Docling parser (IBM) — best open-source ML layout parser.

License: MIT (free, commercial-friendly, no restrictions)
Scanned PDFs: YES — integrated OCR pipeline
Tables: YES — 97.9% table accuracy in Procycons 2025 benchmark (TableFormer model)
Handwriting: LIMITED — OCR-dependent; not a primary strength
Best for: Complex layouts, tables, mixed digital/scanned, on-prem production

Key capabilities:
- Handles: PDF, DOCX, PPTX, HTML, images
- Outputs: Markdown, JSON, DoclingDocument object
- PII integration: GLiNER-PII model (see docling_pii_pipeline.py)
- LangChain/LlamaIndex native integration
- Air-gap compatible: all models download on first run, then work offline

Performance (CPU, no GPU):
- ~1.26 seconds/page average on mixed corpus
- ~6-8 seconds for a 5-page complaint form
- Significantly faster with GPU

Dependencies:
- docling, docling-core, docling-ibm-models (all MIT)
- Underlying: EasyOCR or Tesseract for OCR; TableFormer for tables
"""

from __future__ import annotations

from pathlib import Path

from src.parsers.base import BaseParser, ExtractedTable, ParseResult


class DoclingParser(BaseParser):

    def __init__(self, apply_preprocessing: bool = False, ocr_enabled: bool = True):
        """
        Args:
            ocr_enabled: Enable OCR for scanned PDFs. Disable for speed
                         when you know documents are text-layer only.
        """
        super().__init__(apply_preprocessing)
        self.ocr_enabled = ocr_enabled
        self._converter = None  # Lazy init (model download on first use)

    def _get_converter(self):
        """Lazy-initialize the Docling DocumentConverter. Downloads models on first call."""
        if self._converter is None:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions

            pipeline_options = PdfPipelineOptions(
                do_ocr=self.ocr_enabled,
                do_table_structure=True,  # TableFormer — the key differentiator
                ocr_options=None,          # Uses EasyOCR by default
            )
            self._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        return self._converter

    @property
    def name(self) -> str:
        return "docling" if not self.apply_preprocessing else "docling+preproc"

    @property
    def version(self) -> str:
        try:
            import docling
            return docling.__version__
        except ImportError:
            return "not installed"

    @property
    def license(self) -> str:
        return "MIT"

    @property
    def supports_scanned(self) -> bool:
        return True

    @property
    def supports_tables(self) -> bool:
        return True

    @property
    def supports_handwriting(self) -> bool:
        return False  # OCR-dependent; not specialized for HTR

    def _extract(self, pdf_path: Path) -> ParseResult:
        converter = self._get_converter()
        result = ParseResult(parser_name=self.name, pdf_path=str(pdf_path))

        try:
            conv_result = converter.convert(str(pdf_path))
            doc = conv_result.document

            # Full text in reading order (Docling preserves layout order)
            # Use export_to_text() — not export_to_markdown() — to avoid markdown
            # decorators (##, **, |) inflating CER vs plain-text ground truth.
            result.full_text = doc.export_to_text()

            # Per-page text
            pages_text: list[str] = []
            for page in doc.pages:
                page_text_parts = []
                for element, _ in doc.iterate_items():
                    # Filter by page number
                    if hasattr(element, "prov") and element.prov:
                        for prov in element.prov:
                            if hasattr(prov, "page_no") and prov.page_no == page.page_no:
                                if hasattr(element, "text"):
                                    page_text_parts.append(element.text)
                pages_text.append("\n".join(page_text_parts))
            result.pages_text = pages_text

            # Table extraction — Docling uses TableFormer for cell-level accuracy
            all_tables: list[ExtractedTable] = []
            from docling.datamodel.document import TableItem
            for element, _ in doc.iterate_items():
                if isinstance(element, TableItem):
                    page_no = 1
                    if element.prov:
                        page_no = element.prov[0].page_no if element.prov else 1
                    try:
                        df = element.export_to_dataframe()
                        rows = [list(df.columns)] + df.values.tolist()
                        rows = [[str(cell) for cell in row] for row in rows]
                        all_tables.append(
                            ExtractedTable(
                                page_number=page_no,
                                rows=rows,
                                confidence=None,
                            )
                        )
                    except Exception:
                        pass
            result.tables = all_tables

        except Exception as e:
            result.success = False
            result.errors.append(f"Docling conversion error: {e}")

        return result
