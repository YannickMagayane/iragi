"""Iragi PDF engine: Document text, table extraction, and OCR detection.

Provides tools for parsing PDF documents, extracting tabular data to pandas,
reading document metadata, and detecting scanned non-digital pages.

Example:
    >>> from iragi.pdf import extract, extract_text, extract_tables
    >>> # doc = extract("document.pdf")
"""

from iragi.pdf.extractor import extract, extract_text_from_pdf as extract_text, extract_metadata_from_pdf as extract_metadata
from iragi.pdf.tables import extract_tables_from_pdf as extract_tables
from iragi.pdf.models import ExtractedDocument, ExtractedPage, ExtractedTable
from iragi.pdf.ocr import is_page_likely_scanned, run_ocr_on_image

__all__ = [
    "extract",
    "extract_text",
    "extract_tables",
    "extract_metadata",
    "ExtractedDocument",
    "ExtractedPage",
    "ExtractedTable",
    "is_page_likely_scanned",
    "run_ocr_on_image",
]
