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

from iragi.scan.engine import scan, scan_dataframe, compute_quality_score, generate_recommendations
from iragi.scan.readers import load_tabular_file, read_csv_file, read_excel_file, read_json_file, read_csv_chunked
from iragi.scan.profiler import profile_dataframe, infer_column_type, detect_outliers_iqr
from iragi.scan.reports import to_json_report, inspection_result_to_dict
from iragi.scan.contract import DataContract, ContractViolation, validate_contract

__all__ = [
    "scan",
    "scan_dataframe",
    "compute_quality_score",
    "generate_recommendations",
    "load_tabular_file",
    "read_csv_file",
    "read_csv_chunked",
    "read_excel_file",
    "read_json_file",
    "profile_dataframe",
    "infer_column_type",
    "detect_outliers_iqr",
    "to_json_report",
    "inspection_result_to_dict",
    "DataContract",
    "ContractViolation",
    "validate_contract",
]
