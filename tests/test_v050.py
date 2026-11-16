"""Unit tests for Iragi v0.5.0 features and enterprise resilience.

Covers:
- Multi-source reconciliation (iragi.reconcile.reconcile_multi)
- Apache Parquet file format support (read_parquet_file, scan)
- Fuzzy deduplication in auto_clean (Levenshtein / SequenceMatcher)
- Cross-platform ReDoS protection fallback (Windows-compatible timeout)
- Excel Billion Laughs XML entity injection defense
- Weighted column scoring (column_weights)
- Memory-efficient Excel read (read_only=True)

Example:
    $ pytest tests/test_v050.py
"""

import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from iragi.core.exceptions import IragiDataError
from iragi.reconcile import reconcile_multi
from iragi.scan.cleaner import auto_clean
from iragi.scan.contract import DataContract, validate_contract
from iragi.scan.engine import compute_quality_score, scan, scan_dataframe
from iragi.scan.readers import read_excel_file, read_parquet_file


# ---------------------------------------------------------------------------
# 1. Multi-source reconciliation (reconcile_multi)
# ---------------------------------------------------------------------------


def test_reconcile_multi_three_sources() -> None:
    """reconcile_multi matches records across 3 sources simultaneously.

    Example:
        >>> res = reconcile_multi({"crm": df_crm, "erp": df_erp, "pdf": df_pdf}, on="order_id")
        >>> assert res.all_matched_count == 2
    """
    df_crm = pd.DataFrame({"order_id": [1, 2, 3], "client": ["A", "B", "C"]})
    df_erp = pd.DataFrame({"order_id": [2, 3, 4], "amount": [200, 300, 400]})
    df_pdf = pd.DataFrame({"order_id": [2, 3, 5], "tax": [20, 30, 50]})

    result = reconcile_multi({"crm": df_crm, "erp": df_erp, "pdf": df_pdf}, on="order_id")

    # IDs 2 and 3 exist in ALL 3 sources
    assert result.all_matched_count == 2
    assert result.total_unique_keys == 5
    # Overall consensus match rate (keys present in all sources / all distinct keys)
    assert result.consensus_match_rate == 0.4  # 2 / 5
    # Per-source orphan count
    assert result.orphans_by_source["crm"] == 1  # ID 1
    assert result.orphans_by_source["erp"] == 1  # ID 4
    assert result.orphans_by_source["pdf"] == 1  # ID 5


# ---------------------------------------------------------------------------
# 2. Apache Parquet file format support
# ---------------------------------------------------------------------------


def test_read_parquet_file_and_scan() -> None:
    """read_parquet_file reads a parquet dataset into a DataFrame and scan() inspects it.

    Example:
        >>> res = scan("data.parquet")
        >>> assert res.row_count > 0
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
    path = Path(tmp.name)
    tmp.close()

    df_orig = pd.DataFrame({"product_id": [101, 102, 103], "price": [10.5, 20.0, 30.5]})
    df_orig.to_parquet(path, index=False)

    try:
        loaded = read_parquet_file(path)
        assert len(loaded) == 3
        assert list(loaded.columns) == ["product_id", "price"]

        # Universal scan() works on .parquet directly
        res = scan(path)
        assert res.row_count == 3
        assert res.column_count == 2
        assert res.quality_score.total_score == 100.0
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 3. Fuzzy deduplication in auto_clean
# ---------------------------------------------------------------------------


def test_auto_clean_fuzzy_deduplication() -> None:
    """auto_clean with fuzzy_dedup detects and collapses near-duplicate strings with typos.

    Example:
        >>> res = auto_clean(df, fuzzy_dedup=True, fuzzy_columns=["company"], fuzzy_threshold=0.85)
        >>> assert res.changes["fuzzy_duplicates_removed"] == 1
    """
    # "Google Inc" and "Google Inc." or "Google Inc," have minor punctuation/typo difference
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "company": ["Acme Corp", "Google Inc", "Google Inc."],
        "revenue": [100, 200, 200],
    })

    result = auto_clean(df, fuzzy_dedup=True, fuzzy_columns=["company"], fuzzy_threshold=0.85)
    assert result.changes["fuzzy_duplicates_removed"] == 1
    assert len(result.df) == 2


# ---------------------------------------------------------------------------
# 4. Cross-platform ReDoS protection fallback
# ---------------------------------------------------------------------------


def test_contract_regex_timeout_without_sigalrm() -> None:
    """validate_contract enforces regex timeout even when SIGALRM is unavailable (Windows emulation).

    Example:
        >>> contract = DataContract().require_regex("col", pattern, timeout_seconds=0.5)
        >>> validate_contract(df, contract, force_process_timeout=True)
    """
    redos_pattern = r"^(a+)+$"
    catastrophic_input = "a" * 28 + "X"

    df = pd.DataFrame({"col": [catastrophic_input]})
    contract = DataContract().require_regex("col", redos_pattern, timeout_seconds=0.5)

    with pytest.raises(TimeoutError, match="[Rr]egex"):
        validate_contract(df, contract, force_process_timeout=True)


# ---------------------------------------------------------------------------
# 5. XML Billion Laughs entity injection defense
# ---------------------------------------------------------------------------


def test_read_excel_file_blocks_xml_entity_injection() -> None:
    """read_excel_file rejects Excel archives containing XML entity declarations (Billion Laughs).

    Example:
        >>> with pytest.raises(IragiDataError, match="XML entity"):
        ...     read_excel_file(malicious_xlsx)
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    path = Path(tmp.name)
    tmp.close()

    # Create a zip containing an XML entry with <!ENTITY expansion attempt
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        malicious_xml = b"""<?xml version="1.0"?>
        <!DOCTYPE lolz [
         <!ENTITY lol "lol">
         <!ELEMENT lolz (#PCDATA)>
         <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
        ]>
        <lolz>&lol1;</lolz>"""
        zf.writestr("xl/workbook.xml", malicious_xml)

    try:
        with pytest.raises(IragiDataError, match="XML entity"):
            read_excel_file(path)
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 6. Weighted column scoring (column_weights)
# ---------------------------------------------------------------------------


def test_column_weights_scales_deductions_by_importance() -> None:
    """Missing values in heavily-weighted columns trigger proportionally higher penalties.

    Example:
        >>> res = scan_dataframe(df, column_weights={"user_id": 5.0, "notes": 0.2})
        >>> assert res.quality_score.total_score < standard_score
    """
    # 2 columns with equal number of nulls (1 null out of 4 rows)
    df = pd.DataFrame({
        "critical_id": [1, 2, None, 4],
        "optional_notes": ["A", None, "C", "D"],
    })

    # Standard unweighted
    res_unweighted = scan_dataframe(df)

    # Weighted: critical_id has weight 5.0, optional_notes has weight 0.5
    res_weighted = scan_dataframe(
        df,
        column_weights={"critical_id": 5.0, "optional_notes": 0.5},
    )

    assert "column_weights_penalty" in res_weighted.quality_score.breakdown
    assert res_weighted.quality_score.total_score < res_unweighted.quality_score.total_score


# ---------------------------------------------------------------------------
# 7. Memory-efficient Excel read (read_only mode)
# ---------------------------------------------------------------------------


def test_read_excel_file_read_only_mode() -> None:
    """read_excel_file supports read_only=True for memory-constrained environments.

    Example:
        >>> df = read_excel_file("data.xlsx", read_only=True)
        >>> assert len(df) == 3
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    path = Path(tmp.name)
    tmp.close()

    source_df = pd.DataFrame({"col_a": [10, 20, 30], "col_b": ["x", "y", "z"]})
    source_df.to_excel(path, index=False)

    try:
        loaded = read_excel_file(path, read_only=True)
        assert len(loaded) == 3
        assert list(loaded.columns) == ["col_a", "col_b"]
    finally:
        path.unlink(missing_ok=True)
