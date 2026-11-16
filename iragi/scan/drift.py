"""Data drift detection engine for Iragi Scan.

Compares two DataInspectionResult objects to detect quality degradation,
distribution shifts, and structural changes between two time-based snapshots.

Example:
    >>> from iragi.scan.drift import compare_scans
    >>> report = compare_scans(scan_yesterday, scan_today)
    >>> report.score_delta
    -4.2
"""

from dataclasses import dataclass, field
from typing import List

from iragi.core.models import DataInspectionResult


@dataclass
class DriftReport:
    """Comparison result between two DataInspectionResult snapshots.

    :param score_delta: Difference in quality score (after - before). Negative means degradation.
    :type score_delta: float
    :param row_count_delta: Difference in row count (after - before).
    :type row_count_delta: int
    :param missing_delta: Difference in total missing cell count (after - before).
    :type missing_delta: int
    :param duplicate_delta: Difference in duplicate row count (after - before).
    :type duplicate_delta: int
    :param outlier_delta: Difference in potential outlier count (after - before).
    :type outlier_delta: int
    :param drifted_columns: Column names where missing or outlier count changed.
    :type drifted_columns: List[str]
    :param summary: Human-readable drift summary.
    :type summary: str

    Example:
        >>> report = DriftReport(score_delta=-5.0, row_count_delta=100, missing_delta=50,
        ...                      duplicate_delta=0, outlier_delta=10, drifted_columns=["price"])
        >>> report.score_delta
        -5.0
    """

    score_delta: float
    row_count_delta: int
    missing_delta: int
    duplicate_delta: int
    outlier_delta: int
    drifted_columns: List[str] = field(default_factory=list)
    summary: str = ""


def compare_scans(
    before: DataInspectionResult,
    after: DataInspectionResult,
) -> DriftReport:
    """Compare two DataInspectionResult snapshots and produce a DriftReport.

    :param before: Reference inspection result (earlier snapshot).
    :type before: DataInspectionResult
    :param after: Current inspection result (later snapshot).
    :type after: DataInspectionResult
    :return: DriftReport detailing changes between the two scans.
    :rtype: DriftReport

    Example:
        >>> from iragi.scan.engine import scan_dataframe
        >>> import pandas as pd
        >>> before = scan_dataframe(pd.DataFrame({"x": [1, 2, 3]}))
        >>> after = scan_dataframe(pd.DataFrame({"x": [1, None, 3]}))
        >>> report = compare_scans(before, after)
        >>> report.score_delta < 0
        True
    """
    score_delta = round(
        after.quality_score.total_score - before.quality_score.total_score, 4
    )
    row_count_delta = after.row_count - before.row_count
    missing_delta = after.missing_values_count - before.missing_values_count
    duplicate_delta = after.duplicate_rows_count - before.duplicate_rows_count
    outlier_delta = after.potential_outliers_count - before.potential_outliers_count

    # Detect drifted columns: compare missing_count and outliers_count per column
    before_profiles = {p.name: p for p in before.column_profiles}
    after_profiles = {p.name: p for p in after.column_profiles}
    drifted: List[str] = []

    for col_name, after_profile in after_profiles.items():
        before_profile = before_profiles.get(col_name)
        if before_profile is None:
            drifted.append(col_name)
            continue
        if (
            after_profile.missing_count != before_profile.missing_count
            or after_profile.outliers_count != before_profile.outliers_count
        ):
            drifted.append(col_name)

    # Build human-readable summary
    direction = "improved" if score_delta > 0 else ("degraded" if score_delta < 0 else "stable")
    summary = (
        f"Quality {direction} by {abs(score_delta):.2f} pts "
        f"(before={before.quality_score.total_score:.2f}, after={after.quality_score.total_score:.2f}). "
        f"Missing delta: {missing_delta:+d}, Rows delta: {row_count_delta:+d}. "
        f"Drifted columns: {drifted if drifted else 'none'}."
    )

    return DriftReport(
        score_delta=score_delta,
        row_count_delta=row_count_delta,
        missing_delta=missing_delta,
        duplicate_delta=duplicate_delta,
        outlier_delta=outlier_delta,
        drifted_columns=drifted,
        summary=summary,
    )
