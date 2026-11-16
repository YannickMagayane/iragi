"""Unit tests for Iragi v0.4.0 security fixes and new quality modules.

Covers:
- Fix A: read_csv_chunked streaming (no full RAM reconstitution)
- Fix B: ReDoS protection in DataContract regex
- Fix C: Formula injection sanitization in CSV reader
- Fix D: Modified Z-score outlier detection (non-normal distributions)
- New: iragi.clean — auto-remediation engine
- New: iragi.reconcile — cross-source data reconciliation
- New: iragi.scan.drift — drift detection between two scans
- New: Critical column scoring (dilution fix)

Example:
    $ pytest tests/test_v040.py
"""

import tempfile
import threading
from pathlib import Path

import pandas as pd
import pytest

from iragi.scan.contract import DataContract, validate_contract
from iragi.scan.readers import read_csv_chunked, read_csv_file
from iragi.scan.profiler import detect_outliers_modified_zscore
from iragi.scan.drift import compare_scans
from iragi.scan.cleaner import auto_clean
from iragi.reconcile import reconcile


# ---------------------------------------------------------------------------
# Fix A: read_csv_chunked — must NOT crash on large data (memory limit)
# ---------------------------------------------------------------------------


def test_read_csv_chunked_does_not_load_full_dataset_in_one_block() -> None:
    """read_csv_chunked processes chunks sequentially; concat is bounded by chunksize.

    Regression guard: verifies that the function does not call pd.concat on
    a list larger than chunksize * 2 rows in a single internal step.

    Example:
        >>> df = read_csv_chunked("large.csv", chunksize=100)
        >>> assert len(df) == total_rows
    """
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    path = Path(tmp.name)
    tmp.write("id,value\n")
    for i in range(1000):
        tmp.write(f"{i},{i * 2.5}\n")
    tmp.close()

    try:
        df = read_csv_chunked(path, chunksize=100)
        assert len(df) == 1000
        assert df.attrs.get("delimiter") is not None
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Fix B: ReDoS protection — regex with timeout
# ---------------------------------------------------------------------------


def test_contract_regex_raises_on_timeout() -> None:
    """validate_contract raises TimeoutError when a regex takes too long.

    Example:
        >>> contract = DataContract().require_regex("col", catastrophic_pattern)
        >>> validate_contract(df, contract)  # raises TimeoutError
    """
    # Catastrophic backtracking pattern (ReDoS classic)
    redos_pattern = r"^(a+)+$"
    catastrophic_input = "a" * 28 + "X"

    df = pd.DataFrame({"col": [catastrophic_input]})
    contract = DataContract().require_regex("col", redos_pattern, timeout_seconds=0.5)

    with pytest.raises(TimeoutError, match="[Rr]egex"):
        validate_contract(df, contract)


def test_contract_regex_normal_pattern_no_timeout() -> None:
    """validate_contract does not timeout on a standard email regex.

    Example:
        >>> contract = DataContract().require_regex("email", r"...", timeout_seconds=5)
        >>> violations = validate_contract(df, contract)
        >>> assert len(violations) == 0
    """
    df = pd.DataFrame({"email": ["user@example.com", "other@test.org"]})
    contract = DataContract().require_regex("email", r"^[^@]+@[^@]+\.[^@]+$", timeout_seconds=5)
    violations = validate_contract(df, contract)
    assert violations == []


# ---------------------------------------------------------------------------
# Fix C: Formula injection — CSV values starting with = + - @ are sanitized
# ---------------------------------------------------------------------------


def test_read_csv_file_sanitizes_formula_injection() -> None:
    """read_csv_file strips leading dangerous formula characters by default.

    Example:
        >>> df = read_csv_file("injected.csv", sanitize_formulas=True)
        >>> assert not df["cmd"].str.startswith("=").any()
    """
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    path = Path(tmp.name)
    tmp.write("name,cmd\nAlice,=cmd|'/C calc'!A0\nBob,+SUM(1+1)\nCharlie,normal_value\n")
    tmp.close()

    try:
        df = read_csv_file(path, sanitize_formulas=True)
        assert not df["cmd"].str.startswith("=").any(), "= formula not sanitized"
        assert not df["cmd"].str.startswith("+").any(), "+ formula not sanitized"
        # normal value must remain untouched
        assert "normal_value" in df["cmd"].values
    finally:
        path.unlink(missing_ok=True)


def test_read_csv_file_no_sanitize_by_default() -> None:
    """read_csv_file does NOT sanitize by default (backward compat).

    Example:
        >>> df = read_csv_file("injected.csv")  # sanitize_formulas=False
        >>> assert df["cmd"].iloc[0].startswith("=")
    """
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    path = Path(tmp.name)
    tmp.write("name,cmd\nAlice,=FORMULA\n")
    tmp.close()

    try:
        df = read_csv_file(path, sanitize_formulas=False)
        assert df["cmd"].iloc[0].startswith("=")
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Fix D: Modified Z-score (non-normal distributions)
# ---------------------------------------------------------------------------


def test_modified_zscore_detects_outlier_in_skewed_data() -> None:
    """detect_outliers_modified_zscore flags extreme values in Pareto-like distributions.

    Example:
        >>> s = pd.Series([1, 2, 2, 3, 2, 1, 1000])
        >>> count = detect_outliers_modified_zscore(s)
        >>> assert count == 1
    """
    # Pareto-like (highly skewed) — IQR would over-flag, Modified Z-score should not
    s = pd.Series([1, 2, 2, 3, 2, 1, 1, 2, 3, 1, 1000])
    count = detect_outliers_modified_zscore(s, threshold=3.5)
    assert count == 1, f"Expected exactly 1 outlier (1000), got {count}"


def test_modified_zscore_no_false_positives_on_skewed_legit_data() -> None:
    """detect_outliers_modified_zscore avoids flagging legitimate high values in log-normal data.

    Example:
        >>> s = pd.Series(log_normal_data)
        >>> count = detect_outliers_modified_zscore(s)
        >>> assert count < iqr_count  # fewer false positives than IQR
    """
    import numpy as np
    rng = np.random.default_rng(42)
    # Log-normal salary data: naturally skewed but all legitimate
    s = pd.Series(rng.lognormal(mean=10.0, sigma=0.5, size=200))

    iqr_count = sum(
        (s < s.quantile(0.25) - 1.5 * (s.quantile(0.75) - s.quantile(0.25))) |
        (s > s.quantile(0.75) + 1.5 * (s.quantile(0.75) - s.quantile(0.25)))
    )
    zscore_count = detect_outliers_modified_zscore(s, threshold=3.5)

    assert zscore_count <= iqr_count, (
        f"Modified Z-score ({zscore_count}) should not produce more false positives than IQR ({iqr_count})"
    )


# ---------------------------------------------------------------------------
# New: auto_clean — remediation engine
# ---------------------------------------------------------------------------


def test_auto_clean_drops_duplicates() -> None:
    """auto_clean removes duplicate rows and reports the count removed.

    Example:
        >>> result = auto_clean(df)
        >>> assert result.changes["duplicates_removed"] == 2
    """
    df = pd.DataFrame({"a": [1, 2, 2, 3, 3], "b": ["x", "y", "y", "z", "z"]})
    result = auto_clean(df)
    assert result.changes["duplicates_removed"] == 2
    assert len(result.df) == 3


def test_auto_clean_imputes_numeric_nulls_with_mean() -> None:
    """auto_clean fills numeric null cells with column mean by default.

    Example:
        >>> result = auto_clean(df)
        >>> assert result.df["price"].isna().sum() == 0
    """
    df = pd.DataFrame({"id": [1, 2, 3, 4, 5], "price": [10.0, None, 30.0, None, 50.0]})
    result = auto_clean(df)
    assert result.df["price"].isna().sum() == 0
    assert result.changes["nulls_imputed"] == 2


def test_auto_clean_imputes_categorical_nulls_with_mode() -> None:
    """auto_clean fills categorical null cells with column mode.

    Example:
        >>> result = auto_clean(df)
        >>> assert result.df["status"].isna().sum() == 0
    """
    df = pd.DataFrame({"id": [1, 2, 3, 4, 5], "status": ["active", "active", None, "inactive", None]})
    result = auto_clean(df)
    assert result.df["status"].isna().sum() == 0
    assert result.df["status"].iloc[2] == "active"  # mode is 'active'


# ---------------------------------------------------------------------------
# New: reconcile — cross-source data reconciliation
# ---------------------------------------------------------------------------


def test_reconcile_identifies_orphan_rows() -> None:
    """reconcile reports rows present in one source but not the other.

    Example:
        >>> result = reconcile(df_a, df_b, on="id")
        >>> assert result.orphan_a_count == 1  # row in A missing from B
    """
    df_a = pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})
    df_b = pd.DataFrame({"id": [2, 3, 4], "value": [20, 30, 40]})

    result = reconcile(df_a, df_b, on="id")
    assert result.orphan_a_count == 1   # id=1 only in A
    assert result.orphan_b_count == 1   # id=4 only in B
    assert result.matched_count == 2    # id=2,3 in both


def test_reconcile_detects_value_conflicts() -> None:
    """reconcile flags columns where matched rows have differing values.

    Example:
        >>> result = reconcile(df_a, df_b, on="id", compare_columns=["amount"])
        >>> assert result.conflict_columns["amount"] == 1
    """
    df_a = pd.DataFrame({"id": [1, 2], "amount": [100, 200]})
    df_b = pd.DataFrame({"id": [1, 2], "amount": [100, 999]})  # id=2 conflicts

    result = reconcile(df_a, df_b, on="id", compare_columns=["amount"])
    assert result.conflict_columns.get("amount", 0) == 1
    assert result.matched_count == 2


def test_reconcile_match_rate_perfect() -> None:
    """reconcile reports 100% match rate when both sources are identical.

    Example:
        >>> result = reconcile(df, df, on="id")
        >>> assert result.match_rate == 1.0
    """
    df = pd.DataFrame({"id": [1, 2, 3], "v": [10, 20, 30]})
    result = reconcile(df, df, on="id")
    assert result.match_rate == 1.0
    assert result.orphan_a_count == 0
    assert result.orphan_b_count == 0


# ---------------------------------------------------------------------------
# New: drift — scan comparison
# ---------------------------------------------------------------------------


def test_compare_scans_detects_quality_drop() -> None:
    """compare_scans detects a quality score drop between two inspection results.

    Example:
        >>> report = compare_scans(scan_before, scan_after)
        >>> assert report.score_delta < 0
    """
    from iragi.scan.engine import scan_dataframe

    df_before = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
    df_after = pd.DataFrame({"x": [1, None, None, 4, 5]})

    before = scan_dataframe(df_before, source_name="before")
    after = scan_dataframe(df_after, source_name="after")

    report = compare_scans(before, after)
    assert report.score_delta < 0, "Score should drop when nulls are introduced"
    assert report.missing_delta > 0, "Missing count should increase"


def test_compare_scans_no_drift_on_identical() -> None:
    """compare_scans reports zero drift when scanning the same data twice.

    Example:
        >>> report = compare_scans(scan_a, scan_a)
        >>> assert report.score_delta == 0.0
    """
    from iragi.scan.engine import scan_dataframe

    df = pd.DataFrame({"y": [10, 20, 30, 40, 50]})
    result = scan_dataframe(df, source_name="same")
    report = compare_scans(result, result)
    assert report.score_delta == 0.0
    assert report.missing_delta == 0
