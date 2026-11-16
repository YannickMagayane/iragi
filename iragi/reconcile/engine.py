"""Cross-source data reconciliation engine for Iragi.

Provides join-based matching between two or more DataFrames to identify orphan rows,
consensus matches, and column-level value conflicts on common or transformed keys.

Example:
    >>> import pandas as pd
    >>> from iragi.reconcile.engine import reconcile
    >>> df_a = pd.DataFrame({"id": [1, 2, 3], "amount": [100, 200, 300]})
    >>> df_b = pd.DataFrame({"id": [2, 3, 4], "amount": [200, 999, 400]})
    >>> result = reconcile(df_a, df_b, on="id", compare_columns=["amount"])
    >>> result.matched_count
    2
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

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


def _make_key_transformer(
    transform_spec: Optional[Union[Callable[[Any], Any], str]],
) -> Callable[[Any], Any]:
    """Create a standardized key transformation callable.

    :param transform_spec: A regex string pattern or a callable function.
    :type transform_spec: Optional[Union[Callable[[Any], Any], str]]
    :return: Callable taking a raw key component and returning its normalized form.
    :rtype: Callable[[Any], Any]

    Example:
        >>> t = _make_key_transformer(r"(\\d+)")
        >>> t("TRX-101")
        '101'
    """
    if transform_spec is None:
        return lambda val: val

    if isinstance(transform_spec, str):
        regex = re.compile(transform_spec)

        def _regex_transform(val: Any) -> str:
            m = regex.search(str(val))
            if not m:
                return str(val)
            return m.group(1) if m.groups() else m.group(0)

        return _regex_transform

    if callable(transform_spec):
        return transform_spec

    return lambda val: val


def reconcile_multi(
    sources: Dict[str, pd.DataFrame],
    on: Union[str, List[str]],
    key_transform: Optional[
        Union[Callable[[Any], Any], str, Dict[str, Union[Callable[[Any], Any], str]]]
    ] = None,
) -> MultiReconciliationResult:
    """Reconcile three or more DataFrames simultaneously by key column(s).

    Computes consensus matches (keys present in every dataset), union of keys,
    and orphan keys isolated to single sources, with optional key normalization.

    :param sources: Mapping of source name to target DataFrame.
    :type sources: Dict[str, pd.DataFrame]
    :param on: Key column name or list of columns for joining.
    :type on: Union[str, List[str]]
    :param key_transform: Optional regex pattern, callable, or per-source mapping to normalize keys.
    :type key_transform: Optional[Union[Callable[[Any], Any], str, Dict[str, Union[Callable, str]]]]
    :return: MultiReconciliationResult with consensus match metrics.
    :rtype: MultiReconciliationResult

    Example:
        >>> import pandas as pd
        >>> df1 = pd.DataFrame({"id": ["TRX-1", "TRX-2"]})
        >>> df2 = pd.DataFrame({"id": ["LOG-1", "LOG-2"]})
        >>> df3 = pd.DataFrame({"id": ["ACC-1", "ACC-3"]})
        >>> res = reconcile_multi({"s1": df1, "s2": df2, "s3": df3}, on="id", key_transform=r"(\\d+)")
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

    key = [on] if isinstance(on, str) else list(on)
    key_sets: Dict[str, set] = {}

    for name, df in sources.items():
        if isinstance(key_transform, dict):
            spec = key_transform.get(name)
        else:
            spec = key_transform
        transformer = _make_key_transformer(spec)

        raw_rows = df[key].values.tolist()
        norm_keys = [tuple(transformer(c) for c in row) for row in raw_rows]
        key_sets[name] = set(norm_keys)

    all_matched = set.intersection(*key_sets.values()) if key_sets else set()
    total_unique = set.union(*key_sets.values()) if key_sets else set()

    orphans_by_source: Dict[str, int] = {}
    for name, kset in key_sets.items():
        other_keys = (
            set.union(*(s for other_name, s in key_sets.items() if other_name != name))
            if len(key_sets) > 1
            else set()
        )
        orphans_by_source[name] = len(kset - other_keys)

    consensus_match_rate = (
        round(len(all_matched) / len(total_unique), 4) if total_unique else 1.0
    )

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
    on: Union[str, List[str], Tuple[Union[str, List[str]], Union[str, List[str]]]],
    compare_columns: Optional[List[str]] = None,
    key_transform: Optional[
        Union[Callable[[Any], Any], str, Dict[str, Union[Callable[[Any], Any], str]]]
    ] = None,
) -> ReconciliationResult:
    """Reconcile two DataFrames by key column(s) and report matches, orphans, and conflicts.

    Supports heterogeneous key names across sources via tuple `on=('col_a', 'col_b')`,
    and prefix/format normalization via `key_transform`.

    :param df_a: First source DataFrame (reference).
    :type df_a: pd.DataFrame
    :param df_b: Second source DataFrame (to reconcile against).
    :type df_b: pd.DataFrame
    :param on: Column name(s) or pair of columns `(key_a, key_b)` to join on.
    :type on: Union[str, List[str], Tuple[Union[str, List[str]], Union[str, List[str]]]]
    :param compare_columns: Optional list of columns to compare values in matched rows.
    :type compare_columns: Optional[List[str]]
    :param key_transform: Optional regex pattern or function to normalize keys across sources.
    :type key_transform: Optional[Union[Callable[[Any], Any], str, Dict[str, Union[Callable, str]]]]
    :return: ReconciliationResult with orphan rows, match rate, and conflict counts.
    :rtype: ReconciliationResult

    Example:
        >>> import pandas as pd
        >>> from iragi.reconcile.engine import reconcile
        >>> df_a = pd.DataFrame({"order_id": ["TRX-101", "TRX-102"], "price": [10, 20]})
        >>> df_b = pd.DataFrame({"facture_id": ["FACT_101", "FACT_999"], "price": [10, 30]})
        >>> res = reconcile(df_a, df_b, on=("order_id", "facture_id"), key_transform=r"(\\d+)")
        >>> res.matched_count
        1
    """
    if isinstance(on, tuple) and len(on) == 2:
        key_a = [on[0]] if isinstance(on[0], str) else list(on[0])
        key_b = [on[1]] if isinstance(on[1], str) else list(on[1])
    else:
        key_a = [on] if isinstance(on, str) else list(on)
        key_b = key_a

    if isinstance(key_transform, dict):
        spec_a = key_transform.get("df_a") or key_transform.get("a")
        spec_b = key_transform.get("df_b") or key_transform.get("b")
    else:
        spec_a = key_transform
        spec_b = key_transform

    transform_a = _make_key_transformer(spec_a)
    transform_b = _make_key_transformer(spec_b)

    rows_a = df_a[key_a].values.tolist()
    keys_a_norm = [tuple(transform_a(c) for c in row) for row in rows_a]

    rows_b = df_b[key_b].values.tolist()
    keys_b_norm = [tuple(transform_b(c) for c in row) for row in rows_b]

    set_a = set(keys_a_norm)
    set_b = set(keys_b_norm)

    matched_keys = set_a & set_b
    only_a_keys = set_a - set_b
    only_b_keys = set_b - set_a

    matched_count = len(matched_keys)
    orphan_a_count = len(only_a_keys)
    orphan_b_count = len(only_b_keys)

    total_unique = len(set_a | set_b)
    match_rate = round(matched_count / total_unique, 4) if total_unique > 0 else 1.0

    mask_a = [k in only_a_keys for k in keys_a_norm]
    source_a_only = df_a[mask_a].reset_index(drop=True)

    mask_b = [k in only_b_keys for k in keys_b_norm]
    source_b_only = df_b[mask_b].reset_index(drop=True)

    # Detect value conflicts in matched rows
    conflict_columns: Dict[str, int] = {}
    if matched_keys:
        matched_mask_a = [k in matched_keys for k in keys_a_norm]
        matched_mask_b = [k in matched_keys for k in keys_b_norm]

        matched_df_a = df_a[matched_mask_a].copy()
        matched_df_a["_rec_norm_key"] = [k for k in keys_a_norm if k in matched_keys]

        matched_df_b = df_b[matched_mask_b].copy()
        matched_df_b["_rec_norm_key"] = [k for k in keys_b_norm if k in matched_keys]

        if compare_columns is None:
            common_cols = [
                c
                for c in matched_df_a.columns
                if c in matched_df_b.columns
                and c not in key_a
                and c not in key_b
                and c != "_rec_norm_key"
            ]
        else:
            common_cols = [
                c
                for c in compare_columns
                if c in matched_df_a.columns and c in matched_df_b.columns
            ]

        for col in common_cols:
            merged = matched_df_a[["_rec_norm_key", col]].merge(
                matched_df_b[["_rec_norm_key", col]],
                on="_rec_norm_key",
                suffixes=("_a", "_b"),
            )
            conflicts = int((merged[f"{col}_a"] != merged[f"{col}_b"]).sum())
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
