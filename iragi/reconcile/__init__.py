"""Iragi Reconcile: Cross-source data reconciliation engine.

Identifies matching, orphan, and conflicting records across two DataFrames.

Example:
    >>> from iragi.reconcile import reconcile
    >>> result = reconcile(df_csv, df_excel, on="order_id")
    >>> result.match_rate
    0.95
"""

from iragi.reconcile.engine import reconcile, ReconciliationResult

__all__ = ["reconcile", "ReconciliationResult"]
