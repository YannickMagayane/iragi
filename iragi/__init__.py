"""Iragi: Modular File Inspection, Extraction, and Analytics Toolkit.

Unifies Scan, PDF, and orchestration pipelines for reliable data quality workflows.

Example:
    >>> import iragi
    >>> print(iragi.__version__)
    '0.1.0'
"""

from iragi.scan import scan, scan_dataframe
from iragi.all import analyze, batch_analyze

__version__ = "0.2.0"
__all__ = ["__version__", "scan", "scan_dataframe", "analyze", "batch_analyze"]
