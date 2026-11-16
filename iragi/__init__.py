"""Iragi: Modular File Inspection, Extraction, and Analytics Toolkit.

Unifies Scan, PDF, and orchestration pipelines for reliable data quality workflows.

Example:
    >>> import iragi
    >>> print(iragi.__version__)
    '0.3.0'
"""

from iragi.scan import scan, scan_dataframe
from iragi.scan.contract import DataContract, ContractViolation, validate_contract
from iragi.scan.readers import read_csv_chunked
from iragi.all import analyze, batch_analyze
import iragi.pdf as pdf
import iragi.all as all

# Compatibility shim: allows both iragi.scan(...) and iragi.scan.scan(...)
scan.scan = scan
scan.scan_dataframe = scan_dataframe

__version__ = "0.3.0"
__all__ = [
    "__version__",
    "scan",
    "scan_dataframe",
    "analyze",
    "batch_analyze",
    "pdf",
    "all",
    "DataContract",
    "ContractViolation",
    "validate_contract",
    "read_csv_chunked",
]
