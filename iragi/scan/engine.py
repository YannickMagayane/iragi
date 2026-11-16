"""Core execution engine for Iragi Scan.

Coordinates file loading, column profiling, explainable quality scoring,
and actionable cleaning recommendations.

Example:
    >>> from iragi.scan.engine import scan
    >>> import tempfile
    >>> tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    >>> _ = tmp.write("name,score\\nAlice,95\\nBob,80")
    >>> tmp.close()
    >>> res = scan(tmp.name)
    >>> res.quality_score.total_score >= 90.0
    True
"""

from pathlib import Path
from typing import List, Tuple, Union, Optional
from datetime import datetime
import pandas as pd
from iragi.core.config import IragiConfig, get_default_config
from iragi.core.models import QualityScore, DataInspectionResult
from iragi.scan.readers import load_tabular_file
from iragi.scan.profiler import profile_dataframe


def compute_quality_score(
    row_count: int,
    column_count: int,
    missing_count: int,
    duplicate_rows: int,
    outliers_count: int,
    invalid_dates_count: int,
    config: IragiConfig,
) -> QualityScore:
    """Calculate an explainable data quality score on a 0-100 scale.

    :param row_count: Number of rows in dataset.
    :type row_count: int
    :param column_count: Number of columns.
    :type column_count: int
    :param missing_count: Total missing cell values.
    :type missing_count: int
    :param duplicate_rows: Number of duplicated rows.
    :type duplicate_rows: int
    :param outliers_count: Total potential statistical outliers.
    :type outliers_count: int
    :param invalid_dates_count: Total invalid date formats.
    :type invalid_dates_count: int
    :param config: Runtime scoring weights configuration.
    :type config: IragiConfig
    :return: QualityScore instance with exact deduction breakdown.
    :rtype: QualityScore

    Example:
        >>> from iragi.core.config import get_default_config
        >>> qs = compute_quality_score(100, 5, 0, 0, 0, 0, get_default_config())
        >>> qs.total_score
        100.0
    """
    if row_count == 0 or column_count == 0:
        return QualityScore(
            total_score=0.0,
            breakdown={"empty_dataset": 100.0},
            explanations=["Dataset contains zero rows or zero columns."],
        )

    total_cells = row_count * column_count
    missing_ratio = missing_count / total_cells if total_cells > 0 else 0.0
    duplicate_ratio = duplicate_rows / row_count if row_count > 0 else 0.0
    outlier_ratio = min(1.0, outliers_count / row_count) if row_count > 0 else 0.0
    invalid_date_ratio = min(1.0, invalid_dates_count / row_count) if row_count > 0 else 0.0

    missing_penalty = round(missing_ratio * config.missing_penalty_weight, 2)
    duplicate_penalty = round(duplicate_ratio * config.duplicate_penalty_weight, 2)
    outlier_penalty = round(outlier_ratio * config.outlier_penalty_weight, 2)
    invalid_date_penalty = round(invalid_date_ratio * config.invalid_date_penalty_weight, 2)

    total_deductions = missing_penalty + duplicate_penalty + outlier_penalty + invalid_date_penalty
    final_score = max(0.0, round(100.0 - total_deductions, 2))

    breakdown = {
        "missing_penalty": missing_penalty,
        "duplicate_penalty": duplicate_penalty,
        "outlier_penalty": outlier_penalty,
        "invalid_date_penalty": invalid_date_penalty,
    }

    explanations: List[str] = []
    if missing_penalty > 0:
        explanations.append(f"Missing values deducted {missing_penalty} pts ({missing_count} null cells).")
    if duplicate_penalty > 0:
        explanations.append(f"Duplicate rows deducted {duplicate_penalty} pts ({duplicate_rows} duplicate rows).")
    if outlier_penalty > 0:
        explanations.append(f"Outliers deducted {outlier_penalty} pts ({outliers_count} extreme values).")
    if invalid_date_penalty > 0:
        explanations.append(f"Invalid dates deducted {invalid_date_penalty} pts ({invalid_dates_count} invalid entries).")

    if not explanations:
        explanations.append("Excellent data hygiene: zero missing, duplicate, or outlier entries detected.")

    return QualityScore(total_score=final_score, breakdown=breakdown, explanations=explanations)


def generate_recommendations(
    missing_count: int,
    duplicate_rows: int,
    outliers_count: int,
    invalid_dates_count: int,
) -> List[str]:
    """Generate prioritized, actionable cleaning recommendations.

    :param missing_count: Total missing cell values.
    :type missing_count: int
    :param duplicate_rows: Number of duplicated rows.
    :type duplicate_rows: int
    :param outliers_count: Total potential statistical outliers.
    :type outliers_count: int
    :param invalid_dates_count: Total invalid date formats.
    :type invalid_dates_count: int
    :return: List of recommended cleaning operations.
    :rtype: List[str]

    Example:
        >>> recs = generate_recommendations(10, 2, 0, 0)
        >>> len(recs)
        2
    """
    recommendations: List[str] = []

    if duplicate_rows > 0:
        recommendations.append(
            f"Deduplicate dataset: {duplicate_rows} identical rows detected. Apply row deduplication."
        )

    if missing_count > 0:
        recommendations.append(
            f"Handle missing values: {missing_count} null cells found. Consider imputation (mean/median) or dropping empty records."
        )

    if invalid_dates_count > 0:
        recommendations.append(
            f"Standardize date formats: {invalid_dates_count} date strings could not be parsed to ISO standard."
        )

    if outliers_count > 0:
        recommendations.append(
            f"Audit statistical outliers: {outliers_count} numerical values exceed 1.5x IQR boundaries."
        )

    if not recommendations:
        recommendations.append("Dataset passes all quality checks. No immediate cleaning actions required.")

    return recommendations


def scan_dataframe(
    df: pd.DataFrame,
    source_name: str = "in_memory_dataframe",
    config: Optional[IragiConfig] = None,
) -> DataInspectionResult:
    """Inspect and profile an in-memory pandas DataFrame.

    :param df: Target pandas DataFrame.
    :type df: pd.DataFrame
    :param source_name: Identifier for the data source.
    :type source_name: str
    :param config: Optional custom configuration instance.
    :type config: Optional[IragiConfig]
    :return: Comprehensive DataInspectionResult.
    :rtype: DataInspectionResult

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({"col1": [1, 2, 3]})
        >>> res = scan_dataframe(df)
        >>> res.column_count
        1
    """
    cfg = config or get_default_config()

    row_count = int(df.shape[0])
    column_count = int(df.shape[1])
    missing_values_count = int(df.isna().sum().sum())

    column_profiles, duplicate_rows, outliers_count, invalid_dates = profile_dataframe(df, config=cfg)

    quality_score = compute_quality_score(
        row_count=row_count,
        column_count=column_count,
        missing_count=missing_values_count,
        duplicate_rows=duplicate_rows,
        outliers_count=outliers_count,
        invalid_dates_count=invalid_dates,
        config=cfg,
    )

    recommendations = generate_recommendations(
        missing_count=missing_values_count,
        duplicate_rows=duplicate_rows,
        outliers_count=outliers_count,
        invalid_dates_count=invalid_dates,
    )

    return DataInspectionResult(
        file_path=source_name,
        row_count=row_count,
        column_count=column_count,
        missing_values_count=missing_values_count,
        duplicate_rows_count=duplicate_rows,
        invalid_dates_count=invalid_dates,
        potential_outliers_count=outliers_count,
        quality_score=quality_score,
        column_profiles=column_profiles,
        recommendations=recommendations,
        analyzed_at=datetime.now(),
    )


def scan(file_path: Union[str, Path], config: Optional[IragiConfig] = None) -> DataInspectionResult:
    """Inspect, profile, and evaluate the quality of a CSV, Excel, or JSON file.

    :param file_path: Path to target file.
    :type file_path: Union[str, Path]
    :param config: Optional custom configuration instance.
    :type config: Optional[IragiConfig]
    :return: Comprehensive DataInspectionResult.
    :rtype: DataInspectionResult

    Example:
        >>> import tempfile
        >>> tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        >>> _ = tmp.write("id,value\\n1,100\\n2,200")
        >>> tmp.close()
        >>> res = scan(tmp.name)
        >>> res.row_count
        2
    """
    path = Path(file_path)
    df, _ = load_tabular_file(path)
    return scan_dataframe(df, source_name=str(path), config=config)
