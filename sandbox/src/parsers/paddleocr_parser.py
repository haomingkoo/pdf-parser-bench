"""
PaddleOCR parser — most comprehensive open-source OCR suite.

License: Apache-2.0 (free, commercial-friendly)
Scanned PDFs: YES — primary use case
Tables: YES — PP-StructureV2 table recognition module
Handwriting: LIMITED — handwriting models available but not default
Best for: Scanned PDFs, multilingual (80+ languages), table structure

Key capabilities:
- PP-OCRv4: text detection + recognition (state of the art open source)
- PP-StructureV2: layout analysis + table structure recognition
- Faster than EasyOCR; supports GPU for high-throughput
- Handles 80+ languages including Chinese (strong Baidu origin)

Note on handwriting:
- PP-OCRv4 is primarily trained on printed documents
- For handwriting, use TrOCR or fine-tuned models separately
- PaddleOCR's recognition accuracy on cursive handwriting is poor (~CER 0.24)

Note on setup:
- Requires paddlepaddle + paddleocr packages
- First run downloads models (~100-300MB depending on language/mode)
- Subsequent runs work offline
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.parsers.base import BaseParser, ExtractedTable, ParseResult


class PaddleOCRParser(BaseParser):

    def __init__(
        self,
        apply_preprocessing: bool = False,
        lang: str = "en",
        use_gpu: bool = False,
        use_table: bool = True,
        use_layout: bool = True,
    ):
        """
        Args:
            lang: Language code for OCR (e.g., 'en', 'ch', 'fr', 'de')
            use_gpu: Enable GPU acceleration (requires CUDA)
            use_table: Enable table structure recognition (PP-StructureV2)
            use_layout: Enable layout analysis
        """
        super().__init__(apply_preprocessing)
        self.lang = lang
        self.use_gpu = use_gpu
        self.use_table = use_table
        self.use_layout = use_layout
        self._ocr = None       # Lazy init
        self._structure = None

    def _get_ocr(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                use_angle_cls=True,  # Auto-rotate text at any angle
                lang=self.lang,
                use_gpu=self.use_gpu,
                show_log=False,
            )
        return self._ocr

    def _get_structure(self):
        """PP-StructureV2 for table + layout analysis."""
        if self._structure is None and self.use_table:
            from paddleocr import PPStructure
            self._structure = PPStructure(
                table=self.use_table,
                ocr=True,
                show_log=False,
                lang=self.lang,
                use_gpu=self.use_gpu,
            )
        return self._structure

    @property
    def name(self) -> str:
        suffix = "+preproc" if self.apply_preprocessing else ""
        return f"paddleocr_{self.lang}{suffix}"

    @property
    def version(self) -> str:
        try:
            import paddleocr
            return paddleocr.__version__
        except ImportError:
            return "not installed"

    @property
    def license(self) -> str:
        return "Apache-2.0"

    @property
    def supports_scanned(self) -> bool:
        return True

    @property
    def supports_tables(self) -> bool:
        return True

    @property
    def supports_handwriting(self) -> bool:
        return False  # CER ~0.24 on handwritten notes; not recommended for HW fields

    def _extract(self, pdf_path: Path) -> ParseResult:
        import numpy as np
        from pdf2image import convert_from_path

        result = ParseResult(parser_name=self.name, pdf_path=str(pdf_path))
        ocr = self._get_ocr()

        # Render PDF pages as images at 300 DPI
        # 300 DPI is the industry minimum for reliable OCR accuracy
        try:
            images = convert_from_path(str(pdf_path), dpi=300)
        except Exception as e:
            result.success = False
            result.errors.append(f"PDF to image conversion failed: {e}")
            return result

        pages_text: list[str] = []
        all_tables: list[ExtractedTable] = []

        for page_num, img in enumerate(images, start=1):
            img_array = np.array(img)

            # OCR for text extraction
            ocr_result = ocr.ocr(img_array, cls=True)
            page_text_lines: list[str] = []
            if ocr_result and ocr_result[0]:
                for line in ocr_result[0]:
                    if line and len(line) >= 2:
                        text_info = line[1]
                        if text_info:
                            text, confidence = text_info[0], text_info[1]
                            page_text_lines.append(text)

            pages_text.append("\n".join(page_text_lines))

            # Table structure recognition (PP-StructureV2)
            if self.use_table:
                try:
                    structure = self._get_structure()
                    struct_result = structure(img_array)
                    for region in struct_result:
                        if region.get("type") == "table":
                            html_table = region.get("res", {}).get("html", "")
                            if html_table:
                                rows = self._html_table_to_rows(html_table)
                                if rows:
                                    all_tables.append(
                                        ExtractedTable(
                                            page_number=page_num,
                                            rows=rows,
                                        )
                                    )
                except Exception as e:
                    result.errors.append(f"Page {page_num} table extraction error: {e}")

        result.full_text = "\n\n".join(pages_text)
        result.pages_text = pages_text
        result.tables = all_tables
        return result

    @staticmethod
    def _html_table_to_rows(html: str) -> list[list[str]]:
        """Parse HTML table string into list of row lists."""
        try:
            from html.parser import HTMLParser

            class TableParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.rows: list[list[str]] = []
                    self._current_row: list[str] = []
                    self._current_cell: list[str] = []
                    self._in_cell = False

                def handle_starttag(self, tag, attrs):
                    if tag == "tr":
                        self._current_row = []
                    elif tag in ("td", "th"):
                        self._current_cell = []
                        self._in_cell = True

                def handle_endtag(self, tag):
                    if tag in ("td", "th"):
                        self._current_row.append("".join(self._current_cell).strip())
                        self._in_cell = False
                    elif tag == "tr" and self._current_row:
                        self.rows.append(self._current_row)

                def handle_data(self, data):
                    if self._in_cell:
                        self._current_cell.append(data)

            parser = TableParser()
            parser.feed(html)
            return parser.rows
        except Exception:
            return []
