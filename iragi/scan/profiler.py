"""Column and tabular data profiling for Iragi Scan.

Computes column-level distributions, statistical outliers via IQR method,
type inference, and missing value metrics.

Example:
    >>> import pandas as pd
    >>> from iragi.scan.profiler import profile_dataframe
    >>> df = pd.DataFrame({"age": [25, 30, 35, 120, None]})
    >>> profiles, dupes, outliers, invalid_dates = profile_dataframe(df)
    >>> len(profiles)
    1
    >>> profiles[0].missing_count
    1
"""

from typing import Dict, List, Tuple, Any
import numpy as np
import pandas as pd
from iragi.core.config import IragiConfig, get_default_config
from iragi.core.models import ColumnProfile


def infer_column_type(series: pd.Series) -> str:
    """Infer the general semantic data type of a pandas Series.

    :param series: Pandas series to inspect.
    :type series: pd.Series
    :return: Inferred category: 'numeric', 'datetime', 'boolean', 'categorical', or 'text'.
    :rtype: str

    Example:
        >>> s = pd.Series([1.5, 2.0, 3.5])
        >>> infer_column_type(s)
        'numeric'
    """
    clean_series = series.dropna()
    if clean_series.empty:
        return "empty"

    # Boolean check
    if pd.api.types.is_bool_dtype(clean_series):
        return "boolean"

    # Numeric check
    if pd.api.types.is_numeric_dtype(clean_series):
        return "numeric"

    # Datetime check
    if pd.api.types.is_datetime64_any_dtype(clean_series):
        return "datetime"

    # Attempt string to datetime conversion if string-like
    if pd.api.types.is_string_dtype(clean_series) or clean_series.dtype == object:
        # Check if small unique count relative to total -> categorical
        sample = clean_series.astype(str).head(50)
        # Check datetime parseability only if string contains date separators
        first_val = sample.iloc[0] if not sample.empty else ""
        if any(char in first_val for char in ["-", "/", ":"]):
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    converted = pd.to_datetime(sample, errors="coerce")
                    if converted.notna().sum() / len(sample) > 0.8:
                        return "datetime"
            except Exception:
                pass

        # Check if numbers stored as formatted strings (e.g. currency, commas, spaces)
        cleaned_num = (
            sample.str.replace(" ", "", regex=False)
            .str.replace("\xa0", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.replace("€", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.replace("%", "", regex=False)
        )
        converted_num = pd.to_numeric(cleaned_num, errors="coerce")
        if converted_num.notna().sum() / len(sample) >= 0.7:
            return "numeric"

        unique_ratio = clean_series.nunique() / len(clean_series)
        if unique_ratio < 0.2 and clean_series.nunique() <= 50:
            return "categorical"
        return "text"

    return "text"


def detect_outliers_iqr(series: pd.Series, multiplier: float = 1.5) -> int:
    """Detect potential numerical outliers using the Interquartile Range (IQR) rule.

    :param series: Numerical series to evaluate.
    :type series: pd.Series
    :param multiplier: IQR multiplier (default: 1.5).
    :type multiplier: float
    :return: Count of detected outlier points.
    :rtype: int

    Example:
        >>> s = pd.Series([10, 12, 11, 13, 10, 100])
        >>> detect_outliers_iqr(s, multiplier=1.5)
        1
    """
    if pd.api.types.is_numeric_dtype(series):
        clean = series.dropna()
    else:
        cleaned_str = (
            series.dropna()
            .astype(str)
            .str.replace(" ", "", regex=False)
            .str.replace("\xa0", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.replace("€", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.replace("%", "", regex=False)
        )
        clean = pd.to_numeric(cleaned_str, errors="coerce").dropna()

    if len(clean) < 4:
        return 0

    q25 = clean.quantile(0.25)
    q75 = clean.quantile(0.75)
    iqr = q75 - q25

    if iqr == 0:
        return 0

    lower_bound = q25 - (multiplier * iqr)
    upper_bound = q75 + (multiplier * iqr)

    outliers = clean[(clean < lower_bound) | (clean > upper_bound)]
    return int(len(outliers))


def detect_invalid_dates(series: pd.Series) -> int:
    """Count non-parseable values in a column flagged as date-like.

    :param series: Date series to evaluate.
    :type series: pd.Series
    :return: Count of invalid date entries.
    :rtype: int

    Example:
        >>> s = pd.Series(["2024-01-01", "2024-01-02", "not_a_date"])
        >>> detect_invalid_dates(s)
        1
    """
    non_null = series.dropna().astype(str)
    if non_null.empty:
        return 0

    parsed = pd.to_datetime(non_null, errors="coerce")
    return int(parsed.isna().sum())


def compute_column_summary(series: pd.Series, inferred_type: str) -> Dict[str, Any]:
    """Compute basic statistical summary for a column based on its inferred type.

    :param series: Column data.
    :type series: pd.Series
    :param inferred_type: Inferred data type of the column.
    :type inferred_type: str
    :return: Dictionary containing statistical metrics.
    :rtype: Dict[str, Any]

    Example:
        >>> s = pd.Series([1, 2, 3, 4, 5])
        >>> stats = compute_column_summary(s, "numeric")
        >>> stats["mean"]
        3.0
    """
    clean = series.dropna()
    if clean.empty:
        return {}

    summary: Dict[str, Any] = {}
    if inferred_type == "numeric":
        if pd.api.types.is_numeric_dtype(clean):
            num_clean = clean
        else:
            cleaned_str = (
                clean.astype(str)
                .str.replace(" ", "", regex=False)
                .str.replace("\xa0", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.replace("€", "", regex=False)
                .str.replace("$", "", regex=False)
                .str.replace("%", "", regex=False)
            )
            num_clean = pd.to_numeric(cleaned_str, errors="coerce").dropna()
        if not num_clean.empty:
            summary["mean"] = float(num_clean.mean())
            summary["std"] = float(num_clean.std()) if len(num_clean) > 1 else 0.0
            summary["min"] = float(num_clean.min())
            summary["max"] = float(num_clean.max())
            summary["median"] = float(num_clean.median())
    elif inferred_type in ["categorical", "text"]:
        top_counts = clean.value_counts().head(5).to_dict()
        summary["top_values"] = {str(k): int(v) for k, v in top_counts.items()}
    elif inferred_type == "datetime":
        parsed = pd.to_datetime(clean, errors="coerce").dropna()
        if not parsed.empty:
            summary["earliest"] = str(parsed.min())
            summary["latest"] = str(parsed.max())

    return summary


def profile_dataframe(
    df: pd.DataFrame, config: IragiConfig = get_default_config()
) -> Tuple[List[ColumnProfile], int, int, int]:
    """Analyze all columns of a dataframe and generate detailed profiles.

    :param df: Target DataFrame to profile.
    :type df: pd.DataFrame
    :param config: Runtime configuration with anomaly thresholds.
    :type config: IragiConfig
    :return: A tuple containing (list of ColumnProfiles, duplicate rows count, total outliers count, total invalid dates count).
    :rtype: Tuple[List[ColumnProfile], int, int, int]

    Example:
        >>> df = pd.DataFrame({"a": [1, 2, 2], "b": ["x", "y", "y"]})
        >>> profiles, duplicates, outliers, invalid_dates = profile_dataframe(df)
        >>> duplicates
        1
    """
    column_profiles: List[ColumnProfile] = []
    total_outliers = 0
    total_invalid_dates = 0

    duplicate_rows = int(df.duplicated().sum())

    for col_name in df.columns:
        series = df[col_name]
        total_count = len(series)
        missing_count = int(series.isna().sum())
        unique_count = int(series.nunique())

        inferred_type = infer_column_type(series)

        outliers_count = 0
        if inferred_type == "numeric":
            outliers_count = detect_outliers_iqr(series, multiplier=config.outlier_iqr_multiplier)
            total_outliers += outliers_count

        invalid_dates_count = 0
        if inferred_type == "datetime":
            invalid_dates_count = detect_invalid_dates(series)
            total_invalid_dates += invalid_dates_count

        summary_stats = compute_column_summary(series, inferred_type)

        profile = ColumnProfile(
            name=str(col_name),
            inferred_type=inferred_type,
            total_count=total_count,
            missing_count=missing_count,
            unique_count=unique_count,
            invalid_dates_count=invalid_dates_count,
            outliers_count=outliers_count,
            summary_stats=summary_stats,
        )
        column_profiles.append(profile)

    return column_profiles, duplicate_rows, total_outliers, total_invalid_dates
