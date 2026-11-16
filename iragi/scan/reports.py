"""Reporting module for Iragi Scan engine.

Formats DataInspectionResult instances into structured, traceable JSON representations.

Example:
    >>> from iragi.scan.reports import to_json_report
    >>> from iragi.core.models import QualityScore, DataInspectionResult
    >>> score = QualityScore(total_score=90.0)
    >>> res = DataInspectionResult("data.csv", 10, 2, 0, 0, 0, 0, score)
    >>> json_str = to_json_report(res)
    >>> "quality_score" in json_str
    True
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import asdict
from iragi.core.models import DataInspectionResult


def inspection_result_to_dict(result: DataInspectionResult) -> Dict[str, Any]:
    """Convert a DataInspectionResult dataclass into a JSON-serializable dictionary.

    :param result: DataInspectionResult object.
    :type result: DataInspectionResult
    :return: Serialized dictionary.
    :rtype: Dict[str, Any]

    Example:
        >>> from iragi.core.models import QualityScore, DataInspectionResult
        >>> score = QualityScore(total_score=100.0)
        >>> res = DataInspectionResult("data.csv", 5, 2, 0, 0, 0, 0, score)
        >>> d = inspection_result_to_dict(res)
        >>> d["row_count"]
        5
    """
    data = asdict(result)
    # Ensure datetime is formatted as ISO 8601 string
    if "analyzed_at" in data and result.analyzed_at:
        data["analyzed_at"] = result.analyzed_at.isoformat()
    return data


def to_json_report(
    result: DataInspectionResult,
    output_path: Optional[Union[str, Path]] = None,
    indent: int = 2,
) -> str:
    """Generate a structured JSON report from a DataInspectionResult.

    :param result: DataInspectionResult object to serialize.
    :type result: DataInspectionResult
    :param output_path: Optional filesystem path where JSON report should be saved.
    :type output_path: Optional[Union[str, Path]]
    :param indent: Indentation level for pretty JSON output (default: 2).
    :type indent: int
    :return: Serialized JSON report string.
    :rtype: str

    Example:
        >>> from iragi.core.models import QualityScore, DataInspectionResult
        >>> score = QualityScore(total_score=85.0)
        >>> res = DataInspectionResult("data.csv", 10, 2, 1, 0, 0, 0, score)
        >>> report = to_json_report(res)
        >>> isinstance(report, str)
        True
    """
    dict_repr = inspection_result_to_dict(result)
    json_output = json.dumps(dict_repr, indent=indent, default=str)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json_output)

    return json_output
