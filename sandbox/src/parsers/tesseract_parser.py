"""
Tesseract parser — industry-standard open-source OCR baseline.

License: Apache-2.0 (free, commercial-friendly)
Scanned PDFs: YES — primary use case
Tables: NO — returns text regions, no table structure
Handwriting: NO — CER collapses on cursive; not reliable
Best for: Clean printed text in scanned PDFs, baseline comparison

Important notes:
- Tesseract requires the `tesseract-ocr` system package (installed in Dockerfile)
- 300 DPI is mandatory — below 200 DPI accuracy collapses to ~56%
- Preprocessing (deskew, denoise) is highly recommended: can add +22% accuracy
- pytesseract is just a thin Python wrapper; actual OCR is done by tesseract binary
- Use apply_preprocessing=True for fax/low-quality scans

Language packs: English installed by default. See Dockerfile for additional languages.
To list installed languages: tesseract --list-langs
"""

from __future__ import annotations

from pathlib import Path

from src.parsers.base import BaseParser, ParseResult


class TesseractParser(BaseParser):

    def __init__(
        self,
        apply_preprocessing: bool = False,
        lang: str = "eng",
        psm: int = 6,  # 6 = assume a uniform block of text (best for forms)
    ):
        """
        Args:
            lang: Tesseract language code(s), e.g. 'eng', 'eng+chi_sim'
            psm: Page segmentation mode.
                 3=auto, 6=uniform block, 11=sparse text, 12=sparse text with OSD
                 PSM 6 is best for complaint forms with clear text blocks.
        """
        super().__init__(apply_preprocessing)
        self.lang = lang
        self.psm = psm

    @property
    def name(self) -> str:
        suffix = "+preproc" if self.apply_preprocessing else ""
        return f"tesseract_{self.lang}_psm{self.psm}{suffix}"

    @property
    def version(self) -> str:
        try:
            import pytesseract
            return pytesseract.get_tesseract_version().vstring
        except Exception:
            return "not installed or not in PATH"

    @property
    def license(self) -> str:
        return "Apache-2.0"

    @property
    def supports_scanned(self) -> bool:
        return True

    @property
    def supports_tables(self) -> bool:
        return False  # No table structure; use camelot/tabula for text PDFs or PaddleOCR for scanned

    @property
    def supports_handwriting(self) -> bool:
        return False  # CER is unacceptable on any real handwriting

    def _extract(self, pdf_path: Path) -> ParseResult:
        import pytesseract
        from pdf2image import convert_from_path
        from PIL import Image

        result = ParseResult(parser_name=self.name, pdf_path=str(pdf_path))

        # Render PDF at 300 DPI — do not go below this
        # At 200 DPI, accuracy drops to ~56%; at 300 DPI, 99%+ on clean printed text
        try:
            images = convert_from_path(str(pdf_path), dpi=300)
        except Exception as e:
            result.success = False
            result.errors.append(f"PDF render failed: {e}")
            return result

        config = f"--psm {self.psm} --oem 3"  # OEM 3 = LSTM + legacy (best accuracy)
        pages_text: list[str] = []

        for page_num, img in enumerate(images, start=1):
            try:
                text = pytesseract.image_to_string(img, lang=self.lang, config=config)
                pages_text.append(text)
            except Exception as e:
                pages_text.append("")
                result.errors.append(f"Page {page_num} OCR error: {e}")

        result.full_text = "\n\n".join(pages_text)
        result.pages_text = pages_text
        return result
