"""Iragi Reconcile: Cross-source data reconciliation engine.

Identifies matching, orphan, and conflicting records across two or more DataFrames.

Example:
    >>> from iragi.reconcile import reconcile, reconcile_multi
    >>> result = reconcile(df_csv, df_excel, on="order_id")
    >>> result.match_rate
    0.95
"""

from iragi.reconcile.engine import (
    reconcile,
    reconcile_multi,
    ReconciliationResult,
    MultiReconciliationResult,
)

__all__ = [
    "reconcile",
    "reconcile_multi",
    "ReconciliationResult",
    "MultiReconciliationResult",
]
