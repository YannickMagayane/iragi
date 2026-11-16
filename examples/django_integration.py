"""Django framework integration example for Iragi.

Demonstrates how to inspect uploaded tabular datasets (CSV/Excel) inside a Django view
before executing database migrations or ORM bulk creations.

Example:
    To run or test this example pattern:
    $ python examples/django_integration.py
"""

from typing import Any, Dict
import tempfile
import pandas as pd
from iragi.scan import scan_dataframe


def django_upload_view_example(uploaded_file_content: bytes, filename: str) -> Dict[str, Any]:
    """Simulate a Django view processing an uploaded file using Iragi.

    :param uploaded_file_content: Raw byte stream of uploaded file.
    :type uploaded_file_content: bytes
    :param filename: Original uploaded filename.
    :type filename: str
    :return: Response dictionary containing validation status and recommendations.
    :rtype: Dict[str, Any]

    Example:
        >>> res = django_upload_view_example(b"id,name\\n1,Alice\\n", "users.csv")
        >>> res["status"]
        'success'
    """
    import io
    # Load into memory without writing to disk
    if filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(uploaded_file_content))
    else:
        df = pd.read_excel(io.BytesIO(uploaded_file_content))

    # Audit quality with Iragi
    inspection = scan_dataframe(df, source_name=filename)

    # Reject import if quality score is below acceptable quality threshold
    if inspection.quality_score.total_score < 60.0:
        return {
            "status": "rejected",
            "message": "File rejected due to poor data quality.",
            "score": inspection.quality_score.total_score,
            "issues": inspection.recommendations,
        }

    return {
        "status": "success",
        "message": "File passed quality gate.",
        "score": inspection.quality_score.total_score,
        "rows": inspection.row_count,
        "columns": inspection.column_count,
    }


if __name__ == "__main__":
    csv_bytes = b"user_id,amount,status\n101,45.5,completed\n102,90.0,pending\n"
    response = django_upload_view_example(csv_bytes, "orders.csv")
    print("Django View Simulation Response:", response)
