"""
TrOCR parser (Microsoft) — best open-source handwritten text recognition (HTR).

License: MIT (free, commercial-friendly)
Scanned PDFs: YES — image-based input
Tables: NO — text recognition only; no structural understanding
Handwriting: YES — best open-source HTR; CER ~2.9% on IAM clean dataset
Best for: Handwritten field extraction from complaint forms

Important limitations (do not overclaim):
- CER ~2.9% is on the IAM clean benchmark (neat, isolated handwriting)
- Real-world degraded handwriting (fax, cursive, rushed writing) will be significantly worse
- English-focused public model; non-English handwriting needs fine-tuning
- TrOCR processes text LINES, not full pages — requires upstream segmentation
  to isolate handwritten field regions (use Docling or Aryn Sycamore upstream)
- For complaint forms: best workflow is Docling (layout) → TrOCR (handwritten regions)

Fine-tuning recommendation:
- Collect 50–200 handwritten complaint form samples
- Fine-tune microsoft/trocr-large-handwritten on your domain vocabulary
- Expected CER improvement: from ~10-15% → ~3-5% on your specific form handwriting style

Models used:
- microsoft/trocr-base-handwritten (smaller, faster, less accurate)
- microsoft/trocr-large-handwritten (recommended for production)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.parsers.base import BaseParser, ParseResult


class TrOCRParser(BaseParser):

    MODEL_SMALL = "microsoft/trocr-base-handwritten"
    MODEL_LARGE = "microsoft/trocr-large-handwritten"  # Recommended

    def __init__(
        self,
        apply_preprocessing: bool = True,  # Default True: preprocessing critical for HTR
        model_name: str = MODEL_LARGE,
    ):
        super().__init__(apply_preprocessing)
        self.model_name = model_name
        self._processor = None
        self._model = None

    def _load_model(self):
        """Lazy-load TrOCR model. Downloads on first call (~1.5GB for large)."""
        if self._processor is None:
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
            self._processor = TrOCRProcessor.from_pretrained(self.model_name)
            self._model = VisionEncoderDecoderModel.from_pretrained(self.model_name)
            self._model.eval()

    @property
    def name(self) -> str:
        size = "large" if "large" in self.model_name else "base"
        return f"trocr_{size}"

    @property
    def version(self) -> str:
        try:
            import transformers
            return transformers.__version__
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
        return False

    @property
    def supports_handwriting(self) -> bool:
        return True  # Primary strength; CER ~2.9% on IAM clean

    def _extract(self, pdf_path: Path) -> ParseResult:
        """
        WARNING: TrOCR processes text LINE IMAGES, not full document pages.
        This implementation renders the full page and runs TrOCR on it,
        which is NOT the recommended workflow for production.

        For production: use Docling to segment field regions, then pass
        each handwritten field image to TrOCR for recognition.

        This implementation is provided for baseline comparison purposes only.
        """
        import torch
        from pdf2image import convert_from_path

        self._load_model()
        result = ParseResult(parser_name=self.name, pdf_path=str(pdf_path))
        result.errors.append(
            "Note: TrOCR is designed for text-line images, not full pages. "
            "Running on full pages will produce degraded results. "
            "In production, use Docling for layout segmentation first."
        )

        try:
            images = convert_from_path(str(pdf_path), dpi=300)
        except Exception as e:
            result.success = False
            result.errors.append(f"PDF render failed: {e}")
            return result

        pages_text: list[str] = []
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model.to(device)

        for page_num, img in enumerate(images, start=1):
            try:
                # TrOCR expects PIL Image
                pixel_values = self._processor(img, return_tensors="pt").pixel_values.to(device)
                with torch.no_grad():
                    generated_ids = self._model.generate(pixel_values)
                text = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
                pages_text.append(text)
            except Exception as e:
                pages_text.append("")
                result.errors.append(f"Page {page_num} TrOCR error: {e}")

        result.full_text = "\n\n".join(pages_text)
        result.pages_text = pages_text
        return result

    def recognize_region(self, image: "PIL.Image.Image") -> tuple[str, float]:
        """
        Recognize a cropped text-line or field-region image.
        This is the CORRECT way to use TrOCR in a complaint form pipeline:

            # 1. Use Docling to get field bounding boxes
            # 2. Crop each handwritten field region from the page image
            # 3. Pass each crop to this method

        Returns: (recognized_text, confidence_score)
        Note: TrOCR does not natively produce per-token confidence scores.
        We approximate confidence using token-level log probabilities.
        """
        import torch

        self._load_model()
        device = next(self._model.parameters()).device
        pixel_values = self._processor(image, return_tensors="pt").pixel_values.to(device)

        with torch.no_grad():
            outputs = self._model.generate(
                pixel_values,
                output_scores=True,
                return_dict_in_generate=True,
                max_new_tokens=128,
            )

        text = self._processor.batch_decode(outputs.sequences, skip_special_tokens=True)[0]

        # Approximate confidence: mean of softmax max probability across tokens
        if outputs.scores:
            import torch.nn.functional as F
            token_confidences = [F.softmax(score, dim=-1).max().item() for score in outputs.scores]
            confidence = float(np.mean(token_confidences)) if token_confidences else 0.0
        else:
            confidence = 0.0

        return text, confidence
