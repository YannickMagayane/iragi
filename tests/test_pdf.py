"""Unit tests for the Iragi PDF engine (Phase 3).

Validates PDF metadata reading, text extraction, page scanning detection,
and table model conversion.

Example:
    To run this test suite manually:
    $ pytest tests/test_pdf.py
"""

import tempfile
from pathlib import Path
import pytest
import pymupdf as fitz
import pandas as pd
from iragi.core.exceptions import IragiDataError
from iragi.pdf import extract, extract_text, extract_metadata, ExtractedTable, is_page_likely_scanned


def create_sample_pdf(file_path: str, text: str = "Invoice Summary\nTotal: 500 USD") -> None:
    """Create a minimal real PDF file using PyMuPDF for testing.

    :param file_path: Target path to write PDF file.
    :type file_path: str
    :param text: Text string to insert on page 1.
    :type text: str

    Example:
        >>> create_sample_pdf("sample.pdf", "Hello World")
    """
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=12)
    doc.set_metadata({"title": "Test Invoice", "author": "Iragi Tester"})
    doc.save(file_path)
    doc.close()


def test_extract_metadata() -> None:
    """Verify that extract_metadata extracts title and page count.

    Example:
        >>> meta = extract_metadata("sample.pdf")
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    create_sample_pdf(pdf_path, "Content")
    meta = extract_metadata(pdf_path)

    assert meta["title"] == "Test Invoice"
    assert meta["author"] == "Iragi Tester"
    assert meta["page_count"] == 1
    Path(pdf_path).unlink()


def test_extract_text() -> None:
    """Verify that extract_text retrieves text content across pages.

    Example:
        >>> text = extract_text("sample.pdf")
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    create_sample_pdf(pdf_path, "Quarterly Report Q3\nRevenue: 100000")
    text = extract_text(pdf_path)

    assert "Quarterly Report Q3" in text
    assert "Revenue: 100000" in text
    Path(pdf_path).unlink()


def test_extract_document_full() -> None:
    """Verify full extract() returns an ExtractedDocument object.

    Example:
        >>> doc = extract("sample.pdf")
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    create_sample_pdf(pdf_path, "Page One Content")
    doc = extract(pdf_path)

    assert doc.page_count == 1
    assert "Page One Content" in doc.full_text
    assert doc.metadata.get("title") == "Test Invoice"
    assert len(doc.pages) == 1
    Path(pdf_path).unlink()


def test_extracted_table_to_dataframe() -> None:
    """Verify conversion of ExtractedTable to pandas DataFrame.

    Example:
        >>> tbl = ExtractedTable(1, 0, ["a"], [[1]])
        >>> df = tbl.to_dataframe()
    """
    table = ExtractedTable(
        page_number=1,
        table_index=0,
        headers=["Product", "Price"],
        rows=[["Apples", "3.50"], ["Oranges", "4.00"]],
    )
    df = table.to_dataframe()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ["Product", "Price"]


def test_scanned_page_detection_heuristics() -> None:
    """Verify heuristic detection of likely scanned pages without text.

    Example:
        >>> is_page_likely_scanned("", 1)
        True
    """
    assert is_page_likely_scanned("", 0) is True
    assert is_page_likely_scanned("A", 1) is True
    assert is_page_likely_scanned("A lengthy native digital paragraph exceeding thirty characters.", 0) is False


def test_missing_pdf_raises_error() -> None:
    """Verify that attempting to extract a missing PDF raises IragiDataError.

    Example:
        >>> with pytest.raises(IragiDataError):
        ...     extract("missing.pdf")
    """
    with pytest.raises(IragiDataError):
        extract("non_existent_file.pdf")
