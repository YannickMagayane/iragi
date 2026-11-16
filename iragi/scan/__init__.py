"""Iragi Scan engine: Tabular data inspection, profiling, and quality auditing.

Provides tools for inspecting CSV, Excel, and JSON files, computing column
distributions, identifying anomalies, and calculating explainable quality scores.

Example:
    >>> from iragi import scan
    >>> import tempfile
    >>> tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    >>> _ = tmp.write("col_a,col_b\\n1,2\\n3,4")
    >>> tmp.close()
    >>> res = scan(tmp.name)
    >>> res.quality_score.total_score
    100.0
"""

from iragi.scan.engine import scan, scan_dataframe, scan_csv_stream, compute_quality_score, generate_recommendations
from iragi.scan.readers import (
    load_tabular_file,
    read_csv_file,
    read_excel_file,
    read_json_file,
    read_parquet_file,
    read_csv_chunked,
    iter_csv_chunks,
)
from iragi.scan.profiler import profile_dataframe, infer_column_type, detect_outliers_iqr, detect_outliers_modified_zscore
from iragi.scan.reports import to_json_report, inspection_result_to_dict
from iragi.scan.contract import DataContract, ContractViolation, validate_contract
from iragi.scan.cleaner import auto_clean, CleaningResult
from iragi.scan.drift import compare_scans, DriftReport

__all__ = [
    "scan",
    "scan_dataframe",
    "scan_csv_stream",
    "compute_quality_score",
    "generate_recommendations",
    "load_tabular_file",
    "read_csv_file",
    "read_csv_chunked",
    "iter_csv_chunks",
    "read_excel_file",
    "read_json_file",
    "read_parquet_file",
    "profile_dataframe",
    "infer_column_type",
    "detect_outliers_iqr",
    "detect_outliers_modified_zscore",
    "to_json_report",
    "inspection_result_to_dict",
    "DataContract",
    "ContractViolation",
    "validate_contract",
    "auto_clean",
    "CleaningResult",
    "compare_scans",
    "DriftReport",
]
