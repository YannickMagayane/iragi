"""Unit tests for fixes in Iragi v0.6.1:

1. Excel stream headers robustness: handling None, empty strings, and duplicate column names
   (e.g. from merged cells or cover sheets like Synthese_Audit) without crashing.
2. Parquet support in unified pipeline: iragi.all.analyze() and batch_analyze() recognizing
   .parquet and .pq file extensions.
"""

from pathlib import Path
import pandas as pd
import pytest

from iragi.scan.engine import scan_excel_stream
from iragi.scan.readers import iter_excel_chunks, _sanitize_column_names
from iragi.all.pipeline import analyze, batch_analyze, UnifiedAnalysisResult


def test_sanitize_column_names_handles_nones_and_duplicates():
    """Verify that _sanitize_column_names creates unique, non-empty string column names."""
    raw_header = [None, "Montant", None, "Montant", "  ", "Client"]
    clean = _sanitize_column_names(raw_header)
    assert len(clean) == len(raw_header)
    # Must have no None or empty strings
    assert all(isinstance(c, str) and c.strip() != "" for c in clean)
    # Must be strictly unique
    assert len(clean) == len(set(clean))
    assert clean == ["unnamed_0", "Montant", "unnamed_2", "Montant_1", "unnamed_4", "Client"]


def test_scan_excel_stream_with_none_and_duplicate_headers(tmp_path):
    """Verify scan_excel_stream succeeds on worksheets with None and duplicate headers."""
    excel_path = tmp_path / "messy_cover_sheet.xlsx"

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Synthese_Audit"

    # Row 1: Corrupted/merged header with Nones and duplicate labels
    ws.append([None, "Montant", None, "Montant", ""])
    # Row 2 & 3: Data rows
    ws.append([10, 100.5, "A", 200.0, "ok"])
    ws.append([20, 300.0, "B", 400.0, "done"])
    wb.save(excel_path)
    wb.close()

    # 1. Test iter_excel_chunks produces unique string columns
    chunks = list(iter_excel_chunks(excel_path, chunksize=10))
    assert len(chunks) == 1
    assert len(chunks[0].columns) == 5
    assert len(chunks[0].columns) == len(set(chunks[0].columns))

    # 2. Test scan_excel_stream completes without AttributeError
    result = scan_excel_stream(excel_path, chunksize=10)
    assert result.row_count == 2
    assert result.column_count == 5
    assert result.quality_score.total_score > 0.0


def test_analyze_and_batch_analyze_support_parquet(tmp_path):
    """Verify that iragi.all.analyze and batch_analyze dispatch Parquet files correctly."""
    parquet_path = tmp_path / "dataset.parquet"
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "sales": [100.0, 250.5, 300.0],
        "category": ["X", "Y", "Z"],
    })
    df.to_parquet(parquet_path)

    # 1. Single file dispatch via analyze()
    res = analyze(parquet_path)
    assert isinstance(res, UnifiedAnalysisResult)
    assert res.success is True
    assert res.file_type == "parquet"
    assert res.overall_quality_score == 100.0
    assert len(res.tabular_inspections) == 1

    # 2. Batch dispatch via batch_analyze()
    batch_res = batch_analyze([parquet_path])
    assert len(batch_res) == 1
    assert batch_res[0].success is True
    assert batch_res[0].file_type == "parquet"
