"""Unit tests for the Iragi All orchestration module (Phase 4).

Validates end-to-end unified analysis combining PDF/tabular data and batch processing.

Example:
    To run this test suite manually:
    $ pytest tests/test_all.py
"""

import tempfile
from pathlib import Path
import pytest
fitz = pytest.importorskip("pymupdf", reason="PyMuPDF is required for PDF tests")
from iragi.all import analyze, batch_analyze, UnifiedAnalysisResult
from iragi.core.exceptions import IragiDataError


def test_analyze_tabular_csv() -> None:
    """Verify analyze() processes CSV files and produces a UnifiedAnalysisResult.

    Example:
        >>> res = analyze("data.csv")
        >>> assert res.file_type == "csv"
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("id,amount\n1,100\n2,200\n")
        csv_path = f.name

    result = analyze(csv_path)
    assert isinstance(result, UnifiedAnalysisResult)
    assert result.file_type == "csv"
    assert result.overall_quality_score == 100.0
    assert len(result.tabular_inspections) == 1
    Path(csv_path).unlink()


def test_analyze_pdf_document() -> None:
    """Verify analyze() extracts PDF content and performs unified audit.

    Example:
        >>> res = analyze("doc.pdf")
        >>> assert res.file_type == "pdf"
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Company Annual Report 2026", fontsize=14)
    doc.save(pdf_path)
    doc.close()

    result = analyze(pdf_path)
    assert result.file_type == "pdf"
    assert result.document is not None
    assert "Company Annual Report 2026" in result.document.full_text
    summary = result.summary()
    assert "overall_quality_score" in summary
    Path(pdf_path).unlink()


def test_batch_analyze_multiple_files() -> None:
    """Verify batch_analyze() operates across a list of mixed files.

    Example:
        >>> results = batch_analyze(["f1.csv", "f2.csv"])
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f1:
        f1.write("a,b\n1,2\n")
        p1 = f1.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f2:
        f2.write("x,y\n3,4\n")
        p2 = f2.name

    results = batch_analyze([p1, p2])
    assert len(results) == 2
    assert all(isinstance(r, UnifiedAnalysisResult) for r in results)

    Path(p1).unlink()
    Path(p2).unlink()


def test_analyze_unsupported_format() -> None:
    """Verify analyze() raises IragiDataError on unsupported file extensions.

    Example:
        >>> with pytest.raises(IragiDataError):
        ...     analyze("data.bin")
    """
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        p = f.name

    with pytest.raises(IragiDataError):
        analyze(p)

    Path(p).unlink()
