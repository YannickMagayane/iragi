"""Iragi: Modular File Inspection, Extraction, and Analytics Toolkit.

Unifies Scan, PDF, and orchestration pipelines for reliable data quality workflows.

Example:
    >>> import iragi
    >>> print(iragi.__version__)
    '0.5.0'
"""

from iragi.scan import scan, scan_dataframe, scan_csv_stream, scan_excel_stream
from iragi.scan.contract import DataContract, ContractViolation, validate_contract
from iragi.scan.readers import (
    read_csv_chunked,
    iter_csv_chunks,
    iter_excel_chunks,
    read_parquet_file,
)
from iragi.scan.cleaner import auto_clean, CleaningResult
from iragi.scan.drift import compare_scans, DriftReport
from iragi.scan.profiler import detect_outliers_modified_zscore
from iragi.reconcile import (
    reconcile,
    reconcile_multi,
    ReconciliationResult,
    MultiReconciliationResult,
)
from iragi.all import analyze, batch_analyze
import iragi.pdf as pdf
import iragi.all as all

# Compatibility shim: allows both iragi.scan(...) and iragi.scan.scan(...)
scan.scan = scan
scan.scan_dataframe = scan_dataframe
scan.scan_csv_stream = scan_csv_stream
scan.scan_excel_stream = scan_excel_stream

__version__ = "0.6.2"
__all__ = [
    "__version__",
    "scan",
    "scan_dataframe",
    "scan_csv_stream",
    "scan_excel_stream",
    "analyze",
    "batch_analyze",
    "pdf",
    "all",
    "DataContract",
    "ContractViolation",
    "validate_contract",
    "read_csv_chunked",
    "iter_csv_chunks",
    "iter_excel_chunks",
    "read_parquet_file",
    "auto_clean",
    "CleaningResult",
    "compare_scans",
    "DriftReport",
    "detect_outliers_modified_zscore",
    "reconcile",
    "reconcile_multi",
    "ReconciliationResult",
    "MultiReconciliationResult",
]
