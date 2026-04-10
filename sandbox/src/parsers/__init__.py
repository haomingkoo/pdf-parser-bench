"""
Parser registry — maps parser names to their classes.
Add new parsers here to include them in the ablation runner.

Heavy parser imports are wrapped in try/except so the sandbox can run
with only a subset of parsers installed (e.g. just pypdf + pymupdf + pdfplumber
without needing Docling, PaddleOCR, or PyTorch).
"""

from src.parsers.base import BaseParser, ParseResult, ExtractedField, ExtractedTable
from src.parsers.pypdf_parser import PyPDFParser
from src.parsers.pymupdf_parser import PyMuPDFParser
from src.parsers.pdfplumber_parser import PDFPlumberParser

try:
    from src.parsers.docling_parser import DoclingParser
    _have_docling = True
except ImportError:
    DoclingParser = None
    _have_docling = False

try:
    from src.parsers.paddleocr_parser import PaddleOCRParser
    _have_paddle = True
except ImportError:
    PaddleOCRParser = None
    _have_paddle = False

try:
    from src.parsers.tesseract_parser import TesseractParser
    _have_tesseract = True
except ImportError:
    TesseractParser = None
    _have_tesseract = False

try:
    from src.parsers.trocr_parser import TrOCRParser
    _have_trocr = True
except ImportError:
    TrOCRParser = None
    _have_trocr = False

# Claude parser: requires ANTHROPIC_API_KEY and anthropic package (not on-prem)
# Uncomment to include in comparisons:
# from src.parsers.claude_parser import ClaudeParser

# Parser registry: name -> callable that returns a parser instance.
# Only registers parsers whose dependencies are available.
PARSER_REGISTRY: dict[str, type[BaseParser]] = {
    # --- Text-layer parsers (digital PDFs) ---
    "pypdf": PyPDFParser,
    "pymupdf": PyMuPDFParser,
    "pdfplumber": PDFPlumberParser,
}

if _have_docling:
    PARSER_REGISTRY["docling"] = DoclingParser
    PARSER_REGISTRY["docling+preproc"] = lambda: DoclingParser(apply_preprocessing=True)

if _have_paddle:
    PARSER_REGISTRY["paddleocr_en"] = lambda: PaddleOCRParser(lang="en")
    PARSER_REGISTRY["paddleocr_en+preproc"] = lambda: PaddleOCRParser(lang="en", apply_preprocessing=True)

if _have_tesseract:
    PARSER_REGISTRY["tesseract_eng"] = lambda: TesseractParser(lang="eng")
    PARSER_REGISTRY["tesseract_eng+preproc"] = lambda: TesseractParser(lang="eng", apply_preprocessing=True)

if _have_trocr:
    PARSER_REGISTRY["trocr_large"] = lambda: TrOCRParser(model_name=TrOCRParser.MODEL_LARGE)
    PARSER_REGISTRY["trocr_base"] = lambda: TrOCRParser(model_name=TrOCRParser.MODEL_SMALL)
    PARSER_REGISTRY["trocr_large+preproc"] = lambda: TrOCRParser(
        model_name=TrOCRParser.MODEL_LARGE, apply_preprocessing=True
    )

# API-based (NOT on-prem) — uncomment and set ANTHROPIC_API_KEY to enable:
# from src.parsers.claude_parser import ClaudeParser
# PARSER_REGISTRY["claude_sonnet"] = ClaudeParser

__all__ = [
    "BaseParser",
    "ParseResult",
    "ExtractedField",
    "ExtractedTable",
    "PyPDFParser",
    "PyMuPDFParser",
    "PDFPlumberParser",
    "PARSER_REGISTRY",
]
