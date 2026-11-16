"""FastAPI framework integration example for Iragi.

Demonstrates an asynchronous REST API endpoint that receives a multipart file
and returns an automated quality audit report and score breakdown.

Example:
    To run this example pattern:
    $ python examples/fastapi_integration.py
"""

from typing import Any, Dict
import tempfile
from pathlib import Path
from iragi.all import analyze
from iragi.scan.reports import to_json_report


def audit_document_endpoint_example(file_path: str) -> Dict[str, Any]:
    """Simulate a FastAPI endpoint auditing an uploaded document.

    :param file_path: Path to the uploaded document on disk.
    :type file_path: str
    :return: Formatted API response dict.
    :rtype: Dict[str, Any]

    Example:
        >>> with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as f:
        ...     _ = f.write("a,b\\n1,2")
        ...     res = audit_document_endpoint_example(f.name)
        >>> res["status"]
        200
    """
    result = analyze(file_path)

    return {
        "status": 200,
        "filename": Path(file_path).name,
        "format": result.file_type,
        "quality_score": result.overall_quality_score,
        "recommendations": result.recommendations,
        "summary": result.summary(),
    }


if __name__ == "__main__":
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        tmp.write("metric,value\nlatency,24\nerrors,0\n")
        path = tmp.name

    api_resp = audit_document_endpoint_example(path)
    print("FastAPI Endpoint Simulation Response:", api_resp)
    Path(path).unlink()
