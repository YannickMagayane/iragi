"""Auto-remediation engine for Iragi Scan.

Applies standard data cleaning operations (deduplication, null imputation,
deterministic computed formulas, and contract-based quarantine) to a DataFrame
based on inspection findings, without modifying the source file.

Example:
    >>> import pandas as pd
    >>> from iragi.scan.cleaner import auto_clean
    >>> df = pd.DataFrame({"price": [10.0, None, 30.0], "cat": ["a", "a", None]})
    >>> result = auto_clean(df)
    >>> result.df["price"].isna().sum()
    0
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

import pandas as pd

from iragi.scan.contract import DataContract, ContractViolation, validate_contract


@dataclass
class CleaningResult:
    """Outcome of an auto-cleaning operation.

    :param df: Cleaned copy of the original DataFrame.
    :type df: pd.DataFrame
    :param changes: Mapping of operation names to counts of affected rows/cells.
    :type changes: Dict[str, Any]
    :param quarantine_df: DataFrame of rows quarantined due to contract violations.
    :type quarantine_df: pd.DataFrame
    :param contract_violations: List of violations detected if a DataContract was supplied.
    :type contract_violations: List[ContractViolation]

    Example:
        >>> import pandas as pd
        >>> result = CleaningResult(df=pd.DataFrame(), changes={"duplicates_removed": 2})
        >>> result.changes["duplicates_removed"]
        2
    """

    df: pd.DataFrame
    changes: Dict[str, Any] = field(default_factory=dict)
    quarantine_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    contract_violations: List[ContractViolation] = field(default_factory=list)


def auto_clean(
    df: pd.DataFrame,
    drop_duplicates: bool = True,
    impute_numeric: str = "mean",
    impute_categorical: str = "mode",
    fuzzy_dedup: bool = False,
    fuzzy_columns: Optional[List[str]] = None,
    fuzzy_threshold: float = 0.85,
    computed_columns: Optional[Dict[str, Callable[[pd.DataFrame], Any]]] = None,
    exclude_columns: Optional[List[str]] = None,
    impute_strategies: Optional[Dict[str, Union[str, Any]]] = None,
    contract: Optional[DataContract] = None,
    contract_action: str = "quarantine",
    sanitize_formulas: bool = True,
) -> CleaningResult:
    """Apply remediation, formula imputation, and contract validation to a DataFrame.

    Performs, in order:
    1. Exact duplicate row removal.
    2. Fuzzy duplicate removal (similarity threshold via difflib).
    3. Deterministic formula computation for computed columns.
    4. Selective null imputation per column based on strategies and exclusions.
    5. DataContract evaluation and optional quarantine/drop of violating rows.

    The source DataFrame is never modified — the result is always a copy.

    :param df: Input DataFrame to clean.
    :type df: pd.DataFrame
    :param drop_duplicates: Whether to remove exact duplicate rows (default: True).
    :type drop_duplicates: bool
    :param impute_numeric: Default strategy for numeric nulls: ``'mean'``, ``'median'``, or ``'none'``.
    :type impute_numeric: str
    :param impute_categorical: Default strategy for categorical nulls: ``'mode'`` or ``'none'``.
    :type impute_categorical: str
    :param fuzzy_dedup: Whether to detect and remove near-duplicate string records.
    :type fuzzy_dedup: bool
    :param fuzzy_columns: List of string columns to check for fuzzy near-duplicates.
    :type fuzzy_columns: Optional[List[str]]
    :param fuzzy_threshold: Similarity cutoff between 0.0 and 1.0 (default: 0.85).
    :type fuzzy_threshold: float
    :param computed_columns: Mapping of column name to formula callable receiving df.
    :type computed_columns: Optional[Dict[str, Callable[[pd.DataFrame], Any]]]
    :param exclude_columns: List of column names to exempt from blind statistical imputation.
    :type exclude_columns: Optional[List[str]]
    :param impute_strategies: Mapping of column name to custom strategy (``'median'``, fixed value, or ``'none'``).
    :type impute_strategies: Optional[Dict[str, Union[str, Any]]]
    :param contract: Optional DataContract for business validation and dead-letter quarantine.
    :type contract: Optional[DataContract]
    :param contract_action: Action for contract-violating rows: ``'quarantine'``, ``'drop'``, or ``'none'``.
    :type contract_action: str
    :param sanitize_formulas: Strip spreadsheet formula prefixes from returned data (default: True).
    :type sanitize_formulas: bool
    :return: CleaningResult containing cleaned DataFrame, quarantined rows, and change log.
    :rtype: CleaningResult

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({"qty": [1, 2, None], "unit": [10.0, 20.0, 30.0], "total": [10.0, 40.0, None]})
        >>> formulas = {"total": lambda d: d["qty"] * d["unit"]}
        >>> res = auto_clean(df, computed_columns=formulas)
        >>> res.changes.get("computed_columns_applied")
        ['total']
    """
    cleaned = df.copy()
    changes: Dict[str, Any] = {}
    excluded = set(exclude_columns or [])
    custom_strategies = impute_strategies or {}

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

    # Step 2: Deterministic Computed Columns
    if computed_columns:
        applied_computed = []
        for col, formula_fn in computed_columns.items():
            if col in cleaned.columns:
                computed_series = formula_fn(cleaned)
                cleaned[col] = cleaned[col].fillna(computed_series)
                applied_computed.append(col)
        changes["computed_columns_applied"] = applied_computed

    # Step 3: Granular Null Imputation
    nulls_imputed = 0
    for col in cleaned.columns:
        if col in excluded:
            continue

        null_count = int(cleaned[col].isna().sum())
        if null_count == 0:
            continue

        if col in custom_strategies:
            strat = custom_strategies[col]
            if strat is None or strat == "none":
                continue
            elif strat == "mean" and pd.api.types.is_numeric_dtype(cleaned[col]):
                cleaned[col] = cleaned[col].fillna(cleaned[col].mean())
                nulls_imputed += null_count
            elif strat == "median" and pd.api.types.is_numeric_dtype(cleaned[col]):
                cleaned[col] = cleaned[col].fillna(cleaned[col].median())
                nulls_imputed += null_count
            elif strat == "mode":
                mode_vals = cleaned[col].dropna().mode()
                if not mode_vals.empty:
                    cleaned[col] = cleaned[col].fillna(mode_vals.iloc[0])
                    nulls_imputed += null_count
            elif callable(strat):
                cleaned[col] = cleaned[col].fillna(strat(cleaned[col]))
                nulls_imputed += null_count
            else:
                # Fixed scalar value (e.g. 0.0 or "UNKNOWN")
                cleaned[col] = cleaned[col].fillna(strat)
                nulls_imputed += null_count
            continue

        # Default fallbacks
        if pd.api.types.is_numeric_dtype(cleaned[col]):
            if impute_numeric in ("mean", "median"):
                fill_value = (
                    cleaned[col].mean() if impute_numeric == "mean" else cleaned[col].median()
                )
                cleaned[col] = cleaned[col].fillna(fill_value)
                nulls_imputed += null_count
        else:
            if impute_categorical == "mode":
                mode_vals = cleaned[col].dropna().mode()
                if not mode_vals.empty:
                    cleaned[col] = cleaned[col].fillna(mode_vals.iloc[0])
                    nulls_imputed += null_count

    changes["nulls_imputed"] = nulls_imputed

    # Step 4: DataContract Remediation & Dead Letter Quarantine (DLQ)
    quarantine_df = pd.DataFrame(columns=cleaned.columns)
    contract_violations: List[ContractViolation] = []

    if contract is not None:
        contract_violations = validate_contract(cleaned, contract)
        if contract_violations and contract_action in ("quarantine", "drop"):
            violating_indices = set()
            for rule in contract._rules:
                if rule.column not in cleaned.columns:
                    continue
                series = cleaned[rule.column]
                if rule.kind == "not_null":
                    violating_indices.update(cleaned[series.isna()].index)
                elif rule.kind == "positive":
                    num = pd.to_numeric(series, errors="coerce")
                    violating_indices.update(cleaned[(num <= 0) | num.isna()].index)
                elif rule.kind == "range":
                    num = pd.to_numeric(series, errors="coerce")
                    cond = (num < rule.min_val) | (num > rule.max_val) | num.isna()
                    violating_indices.update(cleaned[cond].index)
                elif rule.kind == "regex":
                    regex_pat = re.compile(rule.pattern)
                    non_null = series.dropna().astype(str)
                    mismatches = non_null[~non_null.str.match(regex_pat)].index
                    violating_indices.update(mismatches)

            sorted_violating = sorted(violating_indices)
            if sorted_violating:
                if contract_action == "quarantine":
                    quarantine_df = cleaned.loc[sorted_violating].reset_index(drop=True)
                    changes["contract_violations_quarantined"] = len(sorted_violating)
                elif contract_action == "drop":
                    changes["contract_violations_dropped"] = len(sorted_violating)
                cleaned = cleaned.drop(index=sorted_violating).reset_index(drop=True)

    if sanitize_formulas:
        from iragi.scan.readers import _sanitize_formulas

        cleaned = _sanitize_formulas(cleaned)
        quarantine_df = _sanitize_formulas(quarantine_df)

    return CleaningResult(
        df=cleaned,
        changes=changes,
        quarantine_df=quarantine_df,
        contract_violations=contract_violations,
    )
