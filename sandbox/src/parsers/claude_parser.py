"""
Claude parser — uses Claude API as a PDF extraction comparison baseline.

IMPORTANT CAVEATS (read before using):
1. NOT on-prem: Data is sent to Anthropic's API. Do NOT use with real customer PII.
2. Requires ANTHROPIC_API_KEY environment variable.
3. Cost: ~$0.003–$0.015 per page depending on model and page complexity.
4. GDPR/CCPA: A Data Processing Agreement (DPA) or BAA may be required.
   See https://www.anthropic.com/legal/privacy for current data handling policy.
5. Non-deterministic: Outputs may vary between runs (unlike rule-based parsers).

This parser is included ONLY for research comparison purposes to show how
Claude's native multimodal PDF understanding compares to local open-source tools.

For production complaint form processing with PII, use Docling + Presidio instead.

How it works:
- Renders PDF pages as PNG images using PyMuPDF
- Sends images to Claude claude-sonnet-4-6 (vision) with structured extraction prompt
- Returns extracted fields and text

Enabled by: uncomment anthropic in requirements.txt and set ANTHROPIC_API_KEY
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from src.parsers.base import BaseParser, ExtractedField, ParseResult


EXTRACTION_PROMPT = """You are a precise document extraction assistant. Extract ALL visible text and fields from this complaint form page.

Return a JSON object with this exact schema:
{
  "full_text": "<all visible text in reading order>",
  "fields": [
    {"name": "<field label>", "value": "<field value>", "type": "<text|checkbox|date|number>"}
  ],
  "has_handwriting": <true|false>,
  "has_tables": <true|false>,
  "tables": [
    {"headers": [...], "rows": [[...]]}
  ]
}

Rules:
- Extract EXACTLY what is written. Do NOT infer, correct, or fill in missing values.
- For checkboxes: value = "checked" or "unchecked"
- For handwritten fields: transcribe exactly as written, including misspellings
- For empty fields: value = ""
- Return ONLY the JSON object, no commentary
"""


class ClaudeParser(BaseParser):
    """
    Claude multimodal API as a PDF parser.

    This is NOT an on-prem solution. Included for research comparison only.
    """

    def __init__(
        self,
        apply_preprocessing: bool = False,
        model: str = "claude-sonnet-4-6",
        dpi: int = 300,  # 300 DPI matches all other parsers for fair comparison
    ):
        super().__init__(apply_preprocessing)
        self.model = model
        self.dpi = dpi
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    raise EnvironmentError(
                        "ANTHROPIC_API_KEY not set. "
                        "Set this env var to use the Claude parser. "
                        "Note: data will be sent to Anthropic's API (not on-prem)."
                    )
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. "
                    "Uncomment 'anthropic' in requirements.txt and reinstall."
                )
        return self._client

    @property
    def name(self) -> str:
        return f"claude_{self.model.split('-')[1]}"  # e.g. "claude_sonnet"

    @property
    def version(self) -> str:
        return self.model

    @property
    def license(self) -> str:
        return "proprietary_api"  # Not open source; API service

    @property
    def supports_scanned(self) -> bool:
        return True

    @property
    def supports_tables(self) -> bool:
        return True

    @property
    def supports_handwriting(self) -> bool:
        return True  # Claude vision can interpret handwriting, but accuracy varies

    def _extract(self, pdf_path: Path) -> ParseResult:
        import json

        import logging
        logging.warning(
            "ClaudeParser: data is being sent to Anthropic API (not on-prem). "
            "Do NOT use with real customer PII without a signed DPA."
        )
        result = ParseResult(parser_name=self.name, pdf_path=str(pdf_path))

        try:
            client = self._get_client()
        except (ImportError, EnvironmentError) as e:
            result.success = False
            result.errors.append(str(e))
            return result

        # Render PDF pages to images
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            result.success = False
            result.errors.append(f"PDF open failed: {e}")
            return result

        pages_text: list[str] = []
        all_fields: list[ExtractedField] = []

        for page_num, page in enumerate(doc, start=1):
            # Render page as PNG image
            mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")

            try:
                message = client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": img_b64,
                                    },
                                },
                                {"type": "text", "text": EXTRACTION_PROMPT},
                            ],
                        }
                    ],
                )
                response_text = message.content[0].text.strip()

                # Parse JSON response
                # Strip markdown code fences if present
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]

                extracted = json.loads(response_text)
                pages_text.append(extracted.get("full_text", ""))

                for f in extracted.get("fields", []):
                    all_fields.append(
                        ExtractedField(
                            name=f.get("name", ""),
                            value=f.get("value", ""),
                            field_type=f.get("type", "text"),
                            page_number=page_num,
                            confidence=None,  # Claude does not return per-field confidence
                        )
                    )

            except json.JSONDecodeError as e:
                pages_text.append("")
                result.errors.append(f"Page {page_num} JSON parse error: {e}")
            except Exception as e:
                pages_text.append("")
                result.errors.append(f"Page {page_num} API error: {e}")

        doc.close()
        result.full_text = "\n\n".join(pages_text)
        result.pages_text = pages_text
        result.fields = all_fields
        return result
