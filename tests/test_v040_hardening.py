"""Unit tests for Iragi v0.4.0 hardening features.

Covers:
- True streaming CSV scan (scan_csv_stream) with bounded memory
- Zip bomb / XML bomb detection in read_excel_file
- Critical column penalty in quality scoring (preventing dilution)
- Empty column penalty in quality scoring

Example:
    $ pytest tests/test_v040_hardening.py
"""

import io
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from iragi.core.config import IragiConfig
from iragi.core.exceptions import IragiDataError
from iragi.scan.engine import compute_quality_score, scan_csv_stream, scan_dataframe
from iragi.scan.readers import iter_csv_chunks, read_excel_file


# ---------------------------------------------------------------------------
# 1. True streaming scan — iter_csv_chunks & scan_csv_stream
# ---------------------------------------------------------------------------


def test_iter_csv_chunks_yields_slices() -> None:
    """iter_csv_chunks yields pandas DataFrame slices without full concatenation.

    Example:
        >>> for chunk in iter_csv_chunks("file.csv", chunksize=10):
        ...     assert len(chunk) <= 10
    """
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    path = Path(tmp.name)
    tmp.write("id,name\n")
    for i in range(25):
        tmp.write(f"{i},user_{i}\n")
    tmp.close()

    try:
        chunks = list(iter_csv_chunks(path, chunksize=10))
        assert len(chunks) == 3  # 10, 10, 5
        assert len(chunks[0]) == 10
        assert len(chunks[1]) == 10
        assert len(chunks[2]) == 5
    finally:
        path.unlink(missing_ok=True)


def test_scan_csv_stream_profiles_without_full_memory_load() -> None:
    """scan_csv_stream produces a valid DataInspectionResult through one-pass streaming.

    Example:
        >>> result = scan_csv_stream("large.csv", chunksize=1000)
        >>> assert result.row_count == 2500
    """
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    path = Path(tmp.name)
    tmp.write("id,score\n")
    for i in range(50):
        score_val = "" if i % 10 == 0 else str(i * 2)
        tmp.write(f"{i},{score_val}\n")
    tmp.close()

    try:
        result = scan_csv_stream(path, chunksize=15)
        assert result.row_count == 50
        assert result.column_count == 2
        assert result.missing_values_count == 5
        assert result.quality_score.total_score < 100.0
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 2. Security: Zip bomb / abnormal compression ratio detection
# ---------------------------------------------------------------------------


def test_read_excel_file_detects_zip_bomb() -> None:
    """read_excel_file raises IragiDataError if a workbook exhibits zip bomb ratios.

    Example:
        >>> with pytest.raises(IragiDataError, match="[Zz]ip [Bb]omb"):
        ...     read_excel_file(zip_bomb_path)
    """
    # Create an artificial zip file pretending to be .xlsx with abnormal uncompressed size
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    path = Path(tmp.name)
    tmp.close()

    # Create a zip containing a file compressed with extreme ratio (zeros)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 10 MB of zeros compresses to a few hundred bytes (>1000x ratio)
        zf.writestr("xl/workbook.xml", b"\x00" * (15 * 1024 * 1024))

    try:
        with pytest.raises(IragiDataError, match="[Zz]ip [Bb]omb"):
            read_excel_file(path)
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 3. Quality score: Critical columns penalty (dilution fix)
# ---------------------------------------------------------------------------


def test_critical_column_penalty_prevents_dilution() -> None:
    """A completely empty critical column causes a severe quality score deduction.

    Example:
        >>> res = scan_dataframe(df, critical_columns=["ssn"])
        >>> assert res.quality_score.total_score <= 70.0
    """
    # 10 columns, only 1 column has nulls (but it's critical!)
    data = {f"col_{i}": [1, 2, 3, 4, 5] for i in range(9)}
    data["ssn"] = [None, None, None, None, None]  # 100% empty critical column
    df = pd.DataFrame(data)

    # Without critical column declared: dilution leads to minimal penalty
    res_normal = scan_dataframe(df)

    # With critical column declared: severe deduction
    res_critical = scan_dataframe(df, critical_columns=["ssn"])

    assert res_critical.quality_score.total_score < res_normal.quality_score.total_score
    assert any("critical" in exp.lower() for exp in res_critical.quality_score.explanations)
    # The deduction on critical column should be at least 20 points
    assert (res_normal.quality_score.total_score - res_critical.quality_score.total_score) >= 20.0


def test_empty_column_penalty_applied_automatically() -> None:
    """Columns that are 100% missing receive an automatic empty-column deduction.

    Example:
        >>> res = scan_dataframe(df)
        >>> assert "empty_column_penalty" in res.quality_score.breakdown
    """
    df = pd.DataFrame({
        "valid_1": [1, 2, 3],
        "valid_2": ["a", "b", "c"],
        "completely_empty": [None, None, None],
    })
    res = scan_dataframe(df)
    assert "empty_column_penalty" in res.quality_score.breakdown
    assert res.quality_score.breakdown["empty_column_penalty"] > 0
