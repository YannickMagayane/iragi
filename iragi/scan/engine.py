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
from typing import Any, Dict, List, Tuple, Union, Optional
from datetime import datetime
import pandas as pd
from iragi.core.config import IragiConfig, get_default_config
from iragi.core.models import QualityScore, DataInspectionResult, ColumnProfile
from iragi.scan.readers import load_tabular_file
from iragi.scan.profiler import (
    profile_dataframe,
    infer_column_type,
    detect_outliers_iqr,
    detect_invalid_dates,
    compute_column_summary,
)


def compute_quality_score(
    row_count: int,
    column_count: int,
    missing_count: int,
    duplicate_rows: int,
    outliers_count: int,
    invalid_dates_count: int,
    config: IragiConfig,
    empty_columns_count: int = 0,
    critical_columns_penalties: Optional[Dict[str, float]] = None,
    column_weights: Optional[Dict[str, float]] = None,
    column_missing_counts: Optional[Dict[str, int]] = None,
) -> QualityScore:
    """Calculate an explainable data quality score on a 0-100 scale.

    Includes penalty deductions for missing cells, duplicate rows, statistical
    outliers, invalid dates, completely empty columns, critical columns, and
    custom column weights.

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
    :param empty_columns_count: Number of columns that are 100% null.
    :type empty_columns_count: int
    :param critical_columns_penalties: Mapping of critical column names to penalty points.
    :type critical_columns_penalties: Optional[Dict[str, float]]
    :param column_weights: Custom importance weights per column name.
    :type column_weights: Optional[Dict[str, float]]
    :param column_missing_counts: Missing cell counts per column name.
    :type column_missing_counts: Optional[Dict[str, int]]
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

    empty_column_penalty = round(min(30.0, empty_columns_count * 15.0), 2)
    critical_penalty = round(min(40.0, sum((critical_columns_penalties or {}).values())), 2)

    column_weights_penalty = 0.0
    if column_weights and column_missing_counts and row_count > 0:
        extra_penalty = 0.0
        for col, weight in column_weights.items():
            if weight > 1.0:
                missing = column_missing_counts.get(col, 0)
                if missing > 0:
                    extra_penalty += (missing / row_count) * (weight - 1.0) * 10.0
        column_weights_penalty = round(min(40.0, extra_penalty), 2)

    total_deductions = (
        missing_penalty
        + duplicate_penalty
        + outlier_penalty
        + invalid_date_penalty
        + empty_column_penalty
        + critical_penalty
        + column_weights_penalty
    )
    final_score = max(0.0, round(100.0 - total_deductions, 2))

    breakdown = {
        "missing_penalty": missing_penalty,
        "duplicate_penalty": duplicate_penalty,
        "outlier_penalty": outlier_penalty,
        "invalid_date_penalty": invalid_date_penalty,
        "empty_column_penalty": empty_column_penalty,
        "critical_column_penalty": critical_penalty,
        "column_weights_penalty": column_weights_penalty,
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
    if empty_column_penalty > 0:
        explanations.append(
            f"Empty columns deducted {empty_column_penalty} pts ({empty_columns_count} completely empty column(s))."
        )
    if critical_columns_penalties:
        for col_name, pen in critical_columns_penalties.items():
            explanations.append(
                f"Critical column '{col_name}' has missing values (deducted {pen} pts)."
            )
    if column_weights_penalty > 0:
        explanations.append(
            f"Column weights penalty deducted {column_weights_penalty} pts based on custom column importance."
        )

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
    critical_columns: Optional[List[str]] = None,
    column_weights: Optional[Dict[str, float]] = None,
) -> DataInspectionResult:
    """Inspect and profile an in-memory pandas DataFrame.

    :param df: Target pandas DataFrame.
    :type df: pd.DataFrame
    :param source_name: Identifier for the data source.
    :type source_name: str
    :param config: Optional custom configuration instance.
    :type config: Optional[IragiConfig]
    :param critical_columns: Optional column names treated as critical (heavy null penalties).
    :type critical_columns: Optional[List[str]]
    :param column_weights: Optional custom importance weights per column name.
    :type column_weights: Optional[Dict[str, float]]
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

    empty_columns_count = sum(
        1 for p in column_profiles if p.total_count > 0 and p.missing_count == p.total_count
    )

    critical_penalties: Dict[str, float] = {}
    if critical_columns and row_count > 0:
        for col in critical_columns:
            if col in df.columns:
                m_count = int(df[col].isna().sum())
                if m_count > 0:
                    ratio = m_count / row_count
                    critical_penalties[col] = round(min(30.0, max(10.0, ratio * 30.0)), 2)

    column_missing_counts = {p.name: p.missing_count for p in column_profiles}

    quality_score = compute_quality_score(
        row_count=row_count,
        column_count=column_count,
        missing_count=missing_values_count,
        duplicate_rows=duplicate_rows,
        outliers_count=outliers_count,
        invalid_dates_count=invalid_dates,
        config=cfg,
        empty_columns_count=empty_columns_count,
        critical_columns_penalties=critical_penalties,
        column_weights=column_weights,
        column_missing_counts=column_missing_counts,
    )

    recommendations = generate_recommendations(
        missing_count=missing_values_count,
        duplicate_rows=duplicate_rows,
        outliers_count=outliers_count,
        invalid_dates_count=invalid_dates,
    )

    delimiter = df.attrs.get("delimiter")
    sheet_names = df.attrs.get("sheet_names")

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
        delimiter=delimiter,
        sheet_names=sheet_names,
        analyzed_at=datetime.now(),
    )


def scan_csv_stream(
    file_path: Union[str, Path],
    chunksize: int = 50_000,
    config: Optional[IragiConfig] = None,
    delimiter: Optional[str] = None,
    critical_columns: Optional[List[str]] = None,
) -> DataInspectionResult:
    """Inspect and profile a large CSV file using streaming chunked reading.

    Memory consumption is strictly bounded by ``chunksize`` rows, enabling
    safe inspection of multi-gigabyte files without risk of OutOfMemory (OOM).

    :param file_path: Path to the CSV file.
    :type file_path: Union[str, Path]
    :param chunksize: Chunk size in rows (default: 50 000).
    :type chunksize: int
    :param config: Optional custom scoring configuration.
    :type config: Optional[IragiConfig]
    :param delimiter: Optional explicit CSV delimiter.
    :type delimiter: Optional[str]
    :param critical_columns: Optional list of critical column names.
    :type critical_columns: Optional[List[str]]
    :return: DataInspectionResult with accumulated quality metrics.
    :rtype: DataInspectionResult

    Example:
        >>> res = scan_csv_stream("large_data.csv", chunksize=10_000)
        >>> res.row_count > 0
        True
    """
    from iragi.scan.readers import iter_csv_chunks

    cfg = config or get_default_config()
    path = Path(file_path)

    total_rows = 0
    column_count = 0
    missing_counts: Dict[str, int] = {}
    samples_per_col: Dict[str, List[Any]] = {}
    inferred_types: Dict[str, str] = {}
    detected_delimiter: Optional[str] = None

    for chunk in iter_csv_chunks(path, chunksize=chunksize, delimiter=delimiter):
        if total_rows == 0:
            column_count = int(chunk.shape[1])
            detected_delimiter = chunk.attrs.get("delimiter")
            for col in chunk.columns:
                str_col = str(col)
                missing_counts[str_col] = 0
                samples_per_col[str_col] = []
                inferred_types[str_col] = infer_column_type(chunk[col])

        total_rows += len(chunk)
        for col in chunk.columns:
            str_col = str(col)
            missing_counts[str_col] += int(chunk[col].isna().sum())
            if len(samples_per_col[str_col]) < 5000:
                samples_per_col[str_col].extend(chunk[col].dropna().head(500).tolist())

    total_missing = sum(missing_counts.values())

    column_profiles: List[ColumnProfile] = []
    total_outliers = 0
    total_invalid_dates = 0

    for col_name, inf_type in inferred_types.items():
        m_count = missing_counts[col_name]
        sample_series = pd.Series(samples_per_col[col_name])
        outliers_count = 0
        invalid_dates_count = 0

        if inf_type == "numeric" and not sample_series.empty:
            outliers_count = detect_outliers_iqr(sample_series, multiplier=cfg.outlier_iqr_multiplier)
            total_outliers += outliers_count
        elif inf_type == "datetime" and not sample_series.empty:
            invalid_dates_count = detect_invalid_dates(sample_series)
            total_invalid_dates += invalid_dates_count

        summary_stats = compute_column_summary(sample_series, inf_type) if not sample_series.empty else {}

        profile = ColumnProfile(
            name=col_name,
            inferred_type=inf_type,
            total_count=total_rows,
            missing_count=m_count,
            unique_count=int(sample_series.nunique()) if not sample_series.empty else 0,
            invalid_dates_count=invalid_dates_count,
            outliers_count=outliers_count,
            summary_stats=summary_stats,
        )
        column_profiles.append(profile)

    empty_columns_count = sum(
        1 for p in column_profiles if p.total_count > 0 and p.missing_count == p.total_count
    )

    critical_penalties: Dict[str, float] = {}
    if critical_columns and total_rows > 0:
        for col in critical_columns:
            if col in missing_counts:
                m_count = missing_counts[col]
                if m_count > 0:
                    ratio = m_count / total_rows
                    critical_penalties[col] = round(min(30.0, max(10.0, ratio * 30.0)), 2)

    quality_score = compute_quality_score(
        row_count=total_rows,
        column_count=column_count,
        missing_count=total_missing,
        duplicate_rows=0,
        outliers_count=total_outliers,
        invalid_dates_count=total_invalid_dates,
        config=cfg,
        empty_columns_count=empty_columns_count,
        critical_columns_penalties=critical_penalties,
    )

    recommendations = generate_recommendations(
        missing_count=total_missing,
        duplicate_rows=0,
        outliers_count=total_outliers,
        invalid_dates_count=total_invalid_dates,
    )

    return DataInspectionResult(
        file_path=str(path),
        row_count=total_rows,
        column_count=column_count,
        missing_values_count=total_missing,
        duplicate_rows_count=0,
        invalid_dates_count=total_invalid_dates,
        potential_outliers_count=total_outliers,
        quality_score=quality_score,
        column_profiles=column_profiles,
        recommendations=recommendations,
        delimiter=detected_delimiter,
        analyzed_at=datetime.now(),
    )


def scan_excel_stream(
    file_path: Union[str, Path],
    sheet_name: Optional[Union[str, int]] = 0,
    chunksize: int = 50_000,
    config: Optional[IragiConfig] = None,
    critical_columns: Optional[List[str]] = None,
    column_weights: Optional[Dict[str, float]] = None,
) -> DataInspectionResult:
    """Inspect and profile a large Excel spreadsheet in chunks with bounded memory.

    :param file_path: Path to target Excel spreadsheet.
    :type file_path: Union[str, Path]
    :param sheet_name: Target sheet name or index (default: 0).
    :type sheet_name: Optional[Union[str, int]]
    :param chunksize: Number of rows per chunk (default: 50 000).
    :type chunksize: int
    :param config: Optional custom configuration instance.
    :type config: Optional[IragiConfig]
    :param critical_columns: Optional critical columns subjected to heavy penalties.
    :type critical_columns: Optional[List[str]]
    :param column_weights: Optional custom importance weights per column.
    :type column_weights: Optional[Dict[str, float]]
    :return: DataInspectionResult with accumulated quality metrics.
    :rtype: DataInspectionResult

    Example:
        >>> # res = scan_excel_stream("large_data.xlsx", chunksize=10_000)
    """
    from iragi.scan.readers import iter_excel_chunks

    cfg = config or get_default_config()
    path = Path(file_path)

    total_rows = 0
    column_count = 0
    missing_counts: Dict[str, int] = {}
    samples_per_col: Dict[str, List[Any]] = {}
    inferred_types: Dict[str, str] = {}
    sheet_names: List[str] = []

    for chunk in iter_excel_chunks(path, sheet_name=sheet_name, chunksize=chunksize):
        if total_rows == 0:
            column_count = int(chunk.shape[1])
            sheet_names = chunk.attrs.get("sheet_names", [])
            for col in chunk.columns:
                str_col = str(col)
                missing_counts[str_col] = 0
                samples_per_col[str_col] = []
                inferred_types[str_col] = infer_column_type(chunk[col])

        total_rows += len(chunk)
        for col in chunk.columns:
            str_col = str(col)
            missing_counts[str_col] += int(chunk[col].isna().sum())
            if len(samples_per_col[str_col]) < 5000:
                samples_per_col[str_col].extend(chunk[col].dropna().head(500).tolist())

    total_missing = sum(missing_counts.values())

    column_profiles: List[ColumnProfile] = []
    total_outliers = 0
    total_invalid_dates = 0

    for col_name, inf_type in inferred_types.items():
        m_count = missing_counts[col_name]
        sample_series = pd.Series(samples_per_col[col_name])
        outliers_count = 0
        invalid_dates_count = 0

        if inf_type == "numeric" and not sample_series.empty:
            outliers_count = detect_outliers_iqr(sample_series, multiplier=cfg.outlier_iqr_multiplier)
            total_outliers += outliers_count
        elif inf_type == "datetime" and not sample_series.empty:
            invalid_dates_count = detect_invalid_dates(sample_series)
            total_invalid_dates += invalid_dates_count

        summary_stats = compute_column_summary(sample_series, inf_type) if not sample_series.empty else {}

        profile = ColumnProfile(
            name=col_name,
            inferred_type=inf_type,
            total_count=total_rows,
            missing_count=m_count,
            unique_count=int(sample_series.nunique()) if not sample_series.empty else 0,
            invalid_dates_count=invalid_dates_count,
            outliers_count=outliers_count,
            summary_stats=summary_stats,
        )
        column_profiles.append(profile)

    empty_columns_count = sum(
        1 for p in column_profiles if p.total_count > 0 and p.missing_count == p.total_count
    )

    critical_penalties: Dict[str, float] = {}
    if critical_columns and total_rows > 0:
        for col in critical_columns:
            if col in missing_counts:
                m_count = missing_counts[col]
                if m_count > 0:
                    ratio = m_count / total_rows
                    critical_penalties[col] = round(min(30.0, max(10.0, ratio * 30.0)), 2)

    quality_score = compute_quality_score(
        row_count=total_rows,
        column_count=column_count,
        missing_count=total_missing,
        duplicate_rows=0,
        outliers_count=total_outliers,
        invalid_dates_count=total_invalid_dates,
        config=cfg,
        empty_columns_count=empty_columns_count,
        critical_columns_penalties=critical_penalties,
        column_weights=column_weights,
    )

    recommendations = generate_recommendations(
        missing_count=total_missing,
        duplicate_rows=0,
        outliers_count=total_outliers,
        invalid_dates_count=total_invalid_dates,
    )

    return DataInspectionResult(
        file_path=str(path),
        row_count=total_rows,
        column_count=column_count,
        missing_values_count=total_missing,
        duplicate_rows_count=0,
        invalid_dates_count=total_invalid_dates,
        potential_outliers_count=total_outliers,
        quality_score=quality_score,
        column_profiles=column_profiles,
        recommendations=recommendations,
        sheet_names=sheet_names,
        analyzed_at=datetime.now(),
    )


def scan(
    file_path: Union[str, Path],
    config: Optional[IragiConfig] = None,
    sheet_name: Optional[Union[str, int]] = 0,
    delimiter: Optional[str] = None,
    stream: bool = False,
    chunksize: int = 50_000,
    critical_columns: Optional[List[str]] = None,
    column_weights: Optional[Dict[str, float]] = None,
) -> DataInspectionResult:
    """Inspect, profile, and evaluate the quality of a CSV, Excel, or JSON file.

    :param file_path: Path to target file.
    :type file_path: Union[str, Path]
    :param config: Optional custom configuration instance.
    :type config: Optional[IragiConfig]
    :param sheet_name: Target sheet name or index for Excel files (default: 0).
    :type sheet_name: Optional[Union[str, int]]
    :param delimiter: Optional explicit CSV delimiter.
    :type delimiter: Optional[str]
    :param stream: If True and target is CSV, use bounded streaming reader.
    :type stream: bool
    :param chunksize: Chunk size when stream=True (default: 50 000).
    :type chunksize: int
    :param critical_columns: Optional critical columns subjected to heavy null penalties.
    :type critical_columns: Optional[List[str]]
    :param column_weights: Optional custom importance weights per column.
    :type column_weights: Optional[Dict[str, float]]
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
    if stream:
        suf = path.suffix.lower()
        if suf in [".csv", ".tsv", ".txt"]:
            return scan_csv_stream(
                path,
                chunksize=chunksize,
                config=config,
                delimiter=delimiter,
                critical_columns=critical_columns,
            )
        elif suf in [".xlsx", ".xls", ".xlsm"]:
            return scan_excel_stream(
                path,
                sheet_name=sheet_name,
                chunksize=chunksize,
                config=config,
                critical_columns=critical_columns,
                column_weights=column_weights,
            )

    df, _ = load_tabular_file(path, sheet_name=sheet_name, delimiter=delimiter)
    return scan_dataframe(
        df,
        source_name=str(path),
        config=config,
        critical_columns=critical_columns,
        column_weights=column_weights,
    )


# Self-reference for API compatibility: allows both scan(...) and scan.scan(...)
scan.scan = scan  # type: ignore[attr-defined]
scan.scan_dataframe = scan_dataframe  # type: ignore[attr-defined]
scan.scan_csv_stream = scan_csv_stream  # type: ignore[attr-defined]
scan.scan_excel_stream = scan_excel_stream  # type: ignore[attr-defined]
