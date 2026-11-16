"""Unit tests for Iragi v0.3.0 structural fixes.

Covers:
- batch_analyze multi-sheet Excel support
- DataContract custom rule engine
- Chunked reading for large CSV files

Example:
    To run this test suite:
    $ pytest tests/test_v030.py
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from iragi.all.pipeline import analyze, batch_analyze
from iragi.scan.contract import DataContract, ContractViolation, validate_contract
from iragi.scan.readers import read_csv_chunked


# ---------------------------------------------------------------------------
# 1. batch_analyze — multi-sheet Excel
# ---------------------------------------------------------------------------


def _make_multisheet_excel() -> Path:
    """Create a temporary multi-sheet Excel workbook for tests.

    :return: Path to the created temporary file.
    :rtype: Path
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    path = Path(tmp.name)
    tmp.close()

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"id": [1, 2], "value": [10, 20]}).to_excel(writer, sheet_name="Sheet1", index=False)
        pd.DataFrame({"id": [3, 4], "value": [30, 40]}).to_excel(writer, sheet_name="Sheet2", index=False)
        pd.DataFrame({"id": [5, 6], "value": [50, 60]}).to_excel(writer, sheet_name="Sheet3", index=False)

    return path


def test_batch_analyze_excel_scans_all_sheets() -> None:
    """batch_analyze on an Excel file with all_sheets=True returns one result per sheet.

    Example:
        >>> results = batch_analyze([path], excel_all_sheets=True)
        >>> assert len(results) == 3
    """
    path = _make_multisheet_excel()
    try:
        results = batch_analyze([path], excel_all_sheets=True)
        sheet_paths = [r.file_path for r in results]
        assert len(results) == 3, f"Expected 3 results (one per sheet), got {len(results)}"
        assert all(r.success for r in results), "All sheet results should succeed"
        assert any("Sheet1" in p for p in sheet_paths)
        assert any("Sheet2" in p for p in sheet_paths)
        assert any("Sheet3" in p for p in sheet_paths)
    finally:
        path.unlink(missing_ok=True)


def test_batch_analyze_excel_default_first_sheet_only() -> None:
    """batch_analyze without excel_all_sheets=True reads only the first sheet (backward compat).

    Example:
        >>> results = batch_analyze([path])
        >>> assert len(results) == 1
    """
    path = _make_multisheet_excel()
    try:
        results = batch_analyze([path])
        assert len(results) == 1, f"Expected 1 result (first sheet only), got {len(results)}"
        assert results[0].success
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 2. DataContract — custom rule engine
# ---------------------------------------------------------------------------


def test_contract_passes_on_valid_data() -> None:
    """DataContract with simple rules passes on compliant data without violations.

    Example:
        >>> contract = DataContract().require_not_null("price").require_positive("price")
        >>> violations = validate_contract(df, contract)
        >>> assert len(violations) == 0
    """
    df = pd.DataFrame({"price": [10.0, 20.0, 30.0], "code": ["A001", "B002", "C003"]})
    contract = (
        DataContract()
        .require_not_null("price")
        .require_positive("price")
        .require_regex("code", r"^[A-Z]\d{3}$")
    )
    violations = validate_contract(df, contract)
    assert violations == [], f"Expected no violations, got: {violations}"


def test_contract_detects_null_violation() -> None:
    """DataContract raises ContractViolation entries for null values in required columns.

    Example:
        >>> contract = DataContract().require_not_null("price")
        >>> violations = validate_contract(df, contract)
        >>> assert any(v.rule == "not_null" for v in violations)
    """
    df = pd.DataFrame({"price": [10.0, None, 30.0]})
    contract = DataContract().require_not_null("price")
    violations = validate_contract(df, contract)
    assert len(violations) == 1
    assert violations[0].rule == "not_null"
    assert violations[0].column == "price"
    assert violations[0].failed_count == 1


def test_contract_detects_positive_violation() -> None:
    """DataContract raises ContractViolation entries for non-positive values.

    Example:
        >>> contract = DataContract().require_positive("amount")
        >>> violations = validate_contract(df, contract)
        >>> assert any(v.rule == "positive" for v in violations)
    """
    df = pd.DataFrame({"amount": [5.0, -1.5, 0.0, 100.0]})
    contract = DataContract().require_positive("amount")
    violations = validate_contract(df, contract)
    assert len(violations) == 1
    assert violations[0].rule == "positive"
    assert violations[0].failed_count == 2  # -1.5 and 0.0


def test_contract_detects_regex_violation() -> None:
    """DataContract raises ContractViolation for regex mismatches.

    Example:
        >>> contract = DataContract().require_regex("email", r".+@.+")
        >>> violations = validate_contract(df, contract)
        >>> assert any(v.rule == "regex" for v in violations)
    """
    df = pd.DataFrame({"email": ["user@example.com", "not-an-email", "other@test.org"]})
    contract = DataContract().require_regex("email", r"^[^@]+@[^@]+\.[^@]+$")
    violations = validate_contract(df, contract)
    assert len(violations) == 1
    assert violations[0].rule == "regex"
    assert violations[0].failed_count == 1


def test_contract_detects_range_violation() -> None:
    """DataContract raises ContractViolation for values outside declared range.

    Example:
        >>> contract = DataContract().require_range("score", min_val=0, max_val=100)
        >>> violations = validate_contract(df, contract)
        >>> assert violations[0].rule == "range"
    """
    df = pd.DataFrame({"score": [50, 110, -5, 75]})
    contract = DataContract().require_range("score", min_val=0, max_val=100)
    violations = validate_contract(df, contract)
    assert len(violations) == 1
    assert violations[0].rule == "range"
    assert violations[0].failed_count == 2  # 110 and -5


def test_contract_missing_column_raises() -> None:
    """DataContract raises ValueError when a rule targets a column absent from the DataFrame.

    Example:
        >>> contract = DataContract().require_not_null("unknown_col")
        >>> validate_contract(df, contract)  # raises ValueError
    """
    df = pd.DataFrame({"price": [1.0, 2.0]})
    contract = DataContract().require_not_null("unknown_col")
    with pytest.raises(ValueError, match="unknown_col"):
        validate_contract(df, contract)


# ---------------------------------------------------------------------------
# 3. Chunked reading — large CSV
# ---------------------------------------------------------------------------


def _make_large_csv(n_rows: int = 50_000) -> Path:
    """Create a temporary large CSV file for chunked read tests.

    :param n_rows: Number of rows to generate.
    :type n_rows: int
    :return: Path to the created CSV file.
    :rtype: Path
    """
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    path = Path(tmp.name)
    tmp.write("id,value,category\n")
    for i in range(n_rows):
        tmp.write(f"{i},{i * 1.5},{chr(65 + (i % 26))}\n")
    tmp.close()
    return path


def test_read_csv_chunked_returns_full_dataframe() -> None:
    """read_csv_chunked assembles all chunks into one complete DataFrame.

    Example:
        >>> df = read_csv_chunked("large.csv", chunksize=10_000)
        >>> assert len(df) == 50_000
    """
    path = _make_large_csv(50_000)
    try:
        df = read_csv_chunked(path, chunksize=10_000)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 50_000
        assert list(df.columns) == ["id", "value", "category"]
    finally:
        path.unlink(missing_ok=True)


def test_read_csv_chunked_handles_delimiter() -> None:
    """read_csv_chunked correctly infers semicolon delimiter across chunks.

    Example:
        >>> df = read_csv_chunked("semicolon.csv", chunksize=100)
        >>> assert df.attrs.get("delimiter") == ";"
    """
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    path = Path(tmp.name)
    tmp.write("name;age\nAlice;30\nBob;25\n")
    tmp.close()
    try:
        df = read_csv_chunked(path, chunksize=1)
        assert len(df) == 2
        assert df.attrs.get("delimiter") == ";"
    finally:
        path.unlink(missing_ok=True)
