"""Cross-source data reconciliation engine for Iragi.

Provides join-based matching between two DataFrames to identify orphan rows,
matched records, and column-level value conflicts on common keys.

Example:
    >>> import pandas as pd
    >>> from iragi.reconcile.engine import reconcile
    >>> df_a = pd.DataFrame({"id": [1, 2, 3], "amount": [100, 200, 300]})
    >>> df_b = pd.DataFrame({"id": [2, 3, 4], "amount": [200, 999, 400]})
    >>> result = reconcile(df_a, df_b, on="id", compare_columns=["amount"])
    >>> result.matched_count
    2
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import pandas as pd


@dataclass
class ReconciliationResult:
    """Outcome of a cross-source reconciliation operation.

    :param matched_count: Number of key values present in both sources.
    :type matched_count: int
    :param orphan_a_count: Number of key values in source A but not source B.
    :type orphan_a_count: int
    :param orphan_b_count: Number of key values in source B but not source A.
    :type orphan_b_count: int
    :param match_rate: Proportion of keys matched out of all unique keys across both sources.
    :type match_rate: float
    :param source_a_only: Rows present only in source A.
    :type source_a_only: pd.DataFrame
    :param source_b_only: Rows present only in source B.
    :type source_b_only: pd.DataFrame
    :param conflict_columns: Mapping of column name to count of conflicting values in matched rows.
    :type conflict_columns: Dict[str, int]

    Example:
        >>> result = ReconciliationResult(matched_count=10, orphan_a_count=2,
        ...     orphan_b_count=1, match_rate=0.77, source_a_only=pd.DataFrame(),
        ...     source_b_only=pd.DataFrame(), conflict_columns={})
        >>> result.match_rate
        0.77
    """

    matched_count: int
    orphan_a_count: int
    orphan_b_count: int
    match_rate: float
    source_a_only: pd.DataFrame
    source_b_only: pd.DataFrame
    conflict_columns: Dict[str, int] = field(default_factory=dict)


@dataclass
class MultiReconciliationResult:
    """Outcome of reconciling multiple DataFrames simultaneously.

    :param all_matched_count: Number of keys present in ALL provided sources.
    :type all_matched_count: int
    :param total_unique_keys: Total unique keys across all sources combined.
    :type total_unique_keys: int
    :param consensus_match_rate: Proportion of keys shared across all sources.
    :type consensus_match_rate: float
    :param orphans_by_source: Count of keys unique to each specific source.
    :type orphans_by_source: Dict[str, int]
    :param source_names: Names or labels of reconciled sources.
    :type source_names: List[str]

    Example:
        >>> res = MultiReconciliationResult(all_matched_count=5, total_unique_keys=10,
        ...     consensus_match_rate=0.5, orphans_by_source={"a": 1, "b": 2}, source_names=["a", "b"])
        >>> res.consensus_match_rate
        0.5
    """

    all_matched_count: int
    total_unique_keys: int
    consensus_match_rate: float
    orphans_by_source: Dict[str, int] = field(default_factory=dict)
    source_names: List[str] = field(default_factory=list)


def reconcile_multi(
    sources: Dict[str, pd.DataFrame],
    on: Union[str, List[str]],
) -> MultiReconciliationResult:
    """Reconcile three or more DataFrames simultaneously by key column(s).

    Computes consensus matches (keys present in every dataset), union of keys,
    and orphan keys isolated to single sources.

    :param sources: Mapping of source name to target DataFrame.
    :type sources: Dict[str, pd.DataFrame]
    :param on: Key column name or list of columns for joining.
    :type on: Union[str, List[str]]
    :return: MultiReconciliationResult with consensus match metrics.
    :rtype: MultiReconciliationResult

    Example:
        >>> import pandas as pd
        >>> df1 = pd.DataFrame({"id": [1, 2]})
        >>> df2 = pd.DataFrame({"id": [2, 3]})
        >>> df3 = pd.DataFrame({"id": [2, 4]})
        >>> res = reconcile_multi({"s1": df1, "s2": df2, "s3": df3}, on="id")
        >>> res.all_matched_count
        1
    """
    if not sources:
        return MultiReconciliationResult(
            all_matched_count=0,
            total_unique_keys=0,
            consensus_match_rate=1.0,
            orphans_by_source={},
            source_names=[],
        )

    key = [on] if isinstance(on, str) else on
    key_sets: Dict[str, set] = {}

    for name, df in sources.items():
        key_sets[name] = set(map(tuple, df[key].values.tolist()))

    all_matched = set.intersection(*key_sets.values()) if key_sets else set()
    total_unique = set.union(*key_sets.values()) if key_sets else set()

    orphans_by_source: Dict[str, int] = {}
    for name, kset in key_sets.items():
        other_keys = set.union(*(s for other_name, s in key_sets.items() if other_name != name))
        orphans_by_source[name] = len(kset - other_keys)

    consensus_match_rate = round(len(all_matched) / len(total_unique), 4) if total_unique else 1.0

    return MultiReconciliationResult(
        all_matched_count=len(all_matched),
        total_unique_keys=len(total_unique),
        consensus_match_rate=consensus_match_rate,
        orphans_by_source=orphans_by_source,
        source_names=list(sources.keys()),
    )


def reconcile(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    on: Union[str, List[str]],
    compare_columns: Optional[List[str]] = None,
) -> ReconciliationResult:
    """Reconcile two DataFrames by key column(s) and report matches, orphans, and conflicts.

    :param df_a: First source DataFrame (reference).
    :type df_a: pd.DataFrame
    :param df_b: Second source DataFrame (to reconcile against).
    :type df_b: pd.DataFrame
    :param on: Column name(s) to use as join key(s).
    :type on: Union[str, List[str]]
    :param compare_columns: Optional list of columns to compare values in matched rows.
        If None, all common columns (excluding key) are compared.
    :type compare_columns: Optional[List[str]]
    :return: ReconciliationResult with orphan rows, match rate, and conflict counts.
    :rtype: ReconciliationResult

    Example:
        >>> import pandas as pd
        >>> from iragi.reconcile.engine import reconcile
        >>> df_a = pd.DataFrame({"id": [1, 2], "value": [10, 20]})
        >>> df_b = pd.DataFrame({"id": [2, 3], "value": [20, 30]})
        >>> result = reconcile(df_a, df_b, on="id")
        >>> result.matched_count
        1
    """
    key = [on] if isinstance(on, str) else on

    keys_a = set(map(tuple, df_a[key].values.tolist()))
    keys_b = set(map(tuple, df_b[key].values.tolist()))

    matched_keys = keys_a & keys_b
    only_a_keys = keys_a - keys_b
    only_b_keys = keys_b - keys_a

    matched_count = len(matched_keys)
    orphan_a_count = len(only_a_keys)
    orphan_b_count = len(only_b_keys)

    total_unique = len(keys_a | keys_b)
    match_rate = round(matched_count / total_unique, 4) if total_unique > 0 else 1.0

    # Build orphan DataFrames
    def _filter_by_keys(df: pd.DataFrame, key_set: set) -> pd.DataFrame:
        mask = df[key].apply(lambda row: tuple(row), axis=1).isin(key_set)
        return df[mask].reset_index(drop=True)

    source_a_only = _filter_by_keys(df_a, only_a_keys)
    source_b_only = _filter_by_keys(df_b, only_b_keys)

    # Detect value conflicts in matched rows
    conflict_columns: Dict[str, int] = {}
    if matched_keys:
        matched_a = _filter_by_keys(df_a, matched_keys).set_index(key)
        matched_b = _filter_by_keys(df_b, matched_keys).set_index(key)

        # Determine columns to compare
        if compare_columns is None:
            common_cols = [
                c for c in matched_a.columns if c in matched_b.columns and c not in key
            ]
        else:
            common_cols = [c for c in compare_columns if c in matched_a.columns and c in matched_b.columns]

        for col in common_cols:
            # Align on index then compare
            aligned_a = matched_a[[col]].rename(columns={col: "_a"})
            aligned_b = matched_b[[col]].rename(columns={col: "_b"})
            merged = aligned_a.join(aligned_b, how="inner")
            conflicts = int((merged["_a"] != merged["_b"]).sum())
            if conflicts > 0:
                conflict_columns[col] = conflicts

    return ReconciliationResult(
        matched_count=matched_count,
        orphan_a_count=orphan_a_count,
        orphan_b_count=orphan_b_count,
        match_rate=match_rate,
        source_a_only=source_a_only,
        source_b_only=source_b_only,
        conflict_columns=conflict_columns,
    )
