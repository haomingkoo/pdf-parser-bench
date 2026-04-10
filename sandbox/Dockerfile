FROM python:3.11-slim-bookworm

# System dependencies:
# - tesseract-ocr: Tesseract OCR engine + English language data
# - poppler-utils: pdf2image and OCRmyPDF backend (pdfinfo, pdftoppm)
# - libgl1: OpenCV headless requirement
# - ghostscript: camelot lattice mode dependency
# - default-jre: tabula-py (Java-based table extraction)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-chi-sim \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-spa \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    ghostscript \
    default-jre-headless \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    # Pre-download Docling models so first run doesn't need internet
    python -c "from docling.document_converter import DocumentConverter; DocumentConverter()" || true

# Install Jupyter for notebooks profile
RUN pip install --no-cache-dir jupyter nbconvert

COPY . .

# Smoke test: verify key imports work
RUN python -c "import pypdf; import pdfplumber; import fitz; print('Core PDF libs OK')" && \
    python -c "import pytesseract; print('Tesseract OK')" && \
    python -c "import docling; print('Docling OK')" || true

CMD ["python", "evaluate.py", "--help"]
