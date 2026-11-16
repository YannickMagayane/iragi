"""Auto-remediation engine for Iragi Scan.

Applies standard data cleaning operations (deduplication, null imputation)
to a DataFrame based on inspection findings, without modifying the source file.

Example:
    >>> import pandas as pd
    >>> from iragi.scan.cleaner import auto_clean
    >>> df = pd.DataFrame({"price": [10.0, None, 30.0], "cat": ["a", "a", None]})
    >>> result = auto_clean(df)
    >>> result.df["price"].isna().sum()
    0
"""

import difflib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from iragi.scan.profiler import infer_column_type


@dataclass
class CleaningResult:
    """Outcome of an auto-cleaning operation.

    :param df: Cleaned copy of the original DataFrame.
    :type df: pd.DataFrame
    :param changes: Mapping of operation names to counts of affected rows/cells.
    :type changes: Dict[str, Any]

    Example:
        >>> result = CleaningResult(df=cleaned_df, changes={"duplicates_removed": 2})
        >>> result.changes["duplicates_removed"]
        2
    """

    df: pd.DataFrame
    changes: Dict[str, Any] = field(default_factory=dict)


def auto_clean(
    df: pd.DataFrame,
    drop_duplicates: bool = True,
    impute_numeric: str = "mean",
    impute_categorical: str = "mode",
    fuzzy_dedup: bool = False,
    fuzzy_columns: Optional[List[str]] = None,
    fuzzy_threshold: float = 0.85,
) -> CleaningResult:
    """Apply standard remediation and fuzzy cleaning operations to a DataFrame.

    Performs, in order:
    1. Exact duplicate row removal.
    2. Fuzzy duplicate removal (similarity threshold via difflib).
    3. Numeric null imputation (mean or median).
    4. Categorical null imputation (mode).

    The source DataFrame is never modified — the result is always a copy.

    :param df: Input DataFrame to clean.
    :type df: pd.DataFrame
    :param drop_duplicates: Whether to remove exact duplicate rows (default: True).
    :type drop_duplicates: bool
    :param impute_numeric: Strategy for numeric nulls: ``'mean'`` or ``'median'``.
    :type impute_numeric: str
    :param impute_categorical: Strategy for categorical/text nulls: only ``'mode'`` supported.
    :type impute_categorical: str
    :param fuzzy_dedup: Whether to detect and remove near-duplicate string records.
    :type fuzzy_dedup: bool
    :param fuzzy_columns: List of string columns to check for fuzzy near-duplicates.
    :type fuzzy_columns: Optional[List[str]]
    :param fuzzy_threshold: Similarity cutoff between 0.0 and 1.0 (default: 0.85).
    :type fuzzy_threshold: float
    :return: CleaningResult containing the cleaned DataFrame and a change log.
    :rtype: CleaningResult

    Example:
        >>> import pandas as pd
        >>> from iragi.scan.cleaner import auto_clean
        >>> df = pd.DataFrame({"x": [1, 2, 2, None], "label": ["a", "a", "a", None]})
        >>> result = auto_clean(df)
        >>> result.changes["duplicates_removed"]
        1
        >>> result.df["x"].isna().sum()
        0
    """
    cleaned = df.copy()
    changes: Dict[str, Any] = {}

    # Step 1: Exact Deduplication
    if drop_duplicates:
        before_rows = len(cleaned)
        cleaned = cleaned.drop_duplicates().reset_index(drop=True)
        changes["duplicates_removed"] = before_rows - len(cleaned)

    # Step 1b: Fuzzy Deduplication
    if fuzzy_dedup and fuzzy_columns:
        keep_indices = set(range(len(cleaned)))
        fuzzy_removed = 0
        for col in fuzzy_columns:
            if col not in cleaned.columns:
                continue
            values = cleaned[col].astype(str).tolist()
            seen_representatives: Dict[int, str] = {}
            for i, val in enumerate(values):
                if i not in keep_indices:
                    continue
                norm_val = val.strip().lower()
                matched_dup = False
                for rep_idx, rep_str in seen_representatives.items():
                    sim = difflib.SequenceMatcher(None, norm_val, rep_str).ratio()
                    if sim >= fuzzy_threshold:
                        keep_indices.discard(i)
                        matched_dup = True
                        fuzzy_removed += 1
                        break
                if not matched_dup:
                    seen_representatives[i] = norm_val

        cleaned = cleaned.iloc[sorted(keep_indices)].reset_index(drop=True)
        changes["fuzzy_duplicates_removed"] = fuzzy_removed

    # Step 2: Null imputation per column
    nulls_imputed = 0
    for col in cleaned.columns:
        null_count = int(cleaned[col].isna().sum())
        if null_count == 0:
            continue

        # Use dtype directly for numeric detection (more reliable than infer_column_type on nulled columns)
        if pd.api.types.is_numeric_dtype(cleaned[col]):
            fill_value = (
                cleaned[col].mean() if impute_numeric == "mean" else cleaned[col].median()
            )
            cleaned[col] = cleaned[col].fillna(fill_value)
            nulls_imputed += null_count

        else:
            # For object/string columns, use mode — take the most frequent non-null value
            mode_vals = cleaned[col].dropna().mode()
            if not mode_vals.empty:
                cleaned[col] = cleaned[col].fillna(mode_vals.iloc[0])
                nulls_imputed += null_count

    changes["nulls_imputed"] = nulls_imputed

    return CleaningResult(df=cleaned, changes=changes)
