"""Core domain models for Iragi.

Provides structured representations for tabular inspection results,
individual column profiles, log analysis summaries, and quality metrics.

Example:
    >>> from iragi.core.models import QualityScore, DataInspectionResult
    >>> score = QualityScore(total_score=85.5, breakdown={"missing_penalty": 10.0})
    >>> score.total_score
    85.5
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class QualityScore:
    """Represents an explainable data quality score.

    :param total_score: The final computed quality score between 0 and 100.
    :type total_score: float
    :param breakdown: Penalty and bonus components contributing to the score.
    :type breakdown: Dict[str, float]
    :param explanations: Human-readable explanations for applied deductions.
    :type explanations: List[str]

    Example:
        >>> qs = QualityScore(total_score=90.0, breakdown={"missing": -10.0}, explanations=["10% missing rows"])
        >>> qs.total_score
        90.0
    """

    total_score: float
    breakdown: Dict[str, float] = field(default_factory=dict)
    explanations: List[str] = field(default_factory=list)


@dataclass
class ColumnProfile:
    """Detailed profile metrics for a single tabular column.

    :param name: Column header name.
    :type name: str
    :param inferred_type: Inferred data type (e.g. numeric, datetime, categorical).
    :type inferred_type: str
    :param total_count: Total number of values processed.
    :type total_count: int
    :param missing_count: Number of missing/null values.
    :type missing_count: int
    :param unique_count: Number of unique distinct values.
    :type unique_count: int
    :param invalid_dates_count: Count of unparseable date strings if column is date-like.
    :type invalid_dates_count: int
    :param outliers_count: Count of potential numerical outliers detected.
    :type outliers_count: int
    :param summary_stats: Descriptive numerical or categorical summary statistics.
    :type summary_stats: Dict[str, Any]

    Example:
        >>> col = ColumnProfile("age", "numeric", 100, 5, 45, 0, 2, {"mean": 32.4})
        >>> col.name
        'age'
    """

    name: str
    inferred_type: str
    total_count: int
    missing_count: int
    unique_count: int
    invalid_dates_count: int = 0
    outliers_count: int = 0
    type_mismatches_count: int = 0
    summary_stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataInspectionResult:
    """Consolidated findings from tabular data inspection.

    :param file_path: Source path of the analyzed file.
    :type file_path: str
    :param row_count: Total row count in tabular dataset.
    :type row_count: int
    :param column_count: Total column count.
    :type column_count: int
    :param missing_values_count: Aggregated count of missing cells.
    :type missing_values_count: int
    :param duplicate_rows_count: Number of duplicate rows detected.
    :type duplicate_rows_count: int
    :param invalid_dates_count: Total invalid date formats encountered.
    :type invalid_dates_count: int
    :param potential_outliers_count: Total potential statistical outliers.
    :type potential_outliers_count: int
    :param quality_score: Computed quality score with breakdown.
    :type quality_score: QualityScore
    :param column_profiles: Detailed profiles per column.
    :type column_profiles: List[ColumnProfile]
    :param recommendations: Actionable cleaning and quality improvement recommendations.
    :type recommendations: List[str]
    :param delimiter: Inferred CSV delimiter (e.g. ',', ';', '\t') if applicable.
    :type delimiter: Optional[str]
    :param sheet_names: List of all sheet names if Excel workbook.
    :type sheet_names: Optional[List[str]]
    :param analyzed_at: Timestamp of inspection completion.
    :type analyzed_at: datetime

    Example:
        >>> score = QualityScore(total_score=95.0)
        >>> res = DataInspectionResult("data.csv", 100, 3, 2, 0, 0, 1, score)
        >>> res.row_count
        100
    """

    file_path: str
    row_count: int
    column_count: int
    missing_values_count: int
    duplicate_rows_count: int
    invalid_dates_count: int
    potential_outliers_count: int
    quality_score: QualityScore
    column_profiles: List[ColumnProfile] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    delimiter: Optional[str] = None
    encoding: Optional[str] = None
    sheet_names: Optional[List[str]] = None
    analyzed_at: datetime = field(default_factory=datetime.now)

    @property
    def columns(self) -> List[str]:
        """List names of all profiled columns in inspection order.

        :return: List of column names.
        :rtype: List[str]

        Example:
            >>> score = QualityScore(total_score=100.0)
            >>> res = DataInspectionResult("data.csv", 10, 1, 0, 0, 0, 0, score, [ColumnProfile("age", "numeric", 10, 0, 10)])
            >>> res.columns
            ['age']
        """
        return [col.name for col in self.column_profiles]


@dataclass
class LogEntry:
    """Structured representation of a parsed log record.

    :param raw: Original unmodified raw log line.
    :type raw: str
    :param timestamp: Parsed timestamp if available.
    :type timestamp: Optional[datetime]
    :param level: Log level (e.g. INFO, WARN, ERROR, CRITICAL).
    :type level: str
    :param message: Extracted log message or request payload.
    :type message: str
    :param status_code: HTTP status code if present in the line.
    :type status_code: Optional[int]
    :param ip_address: Client IP address if present.
    :type ip_address: Optional[str]
    :param source: Originating parser or format identifier (e.g. nginx, django).
    :type source: str

    Example:
        >>> entry = LogEntry("line 1", None, "ERROR", "Failed db connection", None, None, "django")
        >>> entry.level
        'ERROR'
    """

    raw: str
    timestamp: Optional[datetime]
    level: str
    message: str
    status_code: Optional[int] = None
    ip_address: Optional[str] = None
    source: str = "generic"


@dataclass
class LogAnalysisResult:
    """Consolidated output from technical log inspection.

    :param file_path: Path of the inspected log file.
    :type file_path: str
    :param total_lines: Total lines processed.
    :type total_lines: int
    :param parsed_lines: Number of successfully parsed log lines.
    :type parsed_lines: int
    :param unparsed_lines: Number of lines failing parser structure.
    :type unparsed_lines: int
    :param level_counts: Distribution of records by log level.
    :type level_counts: Dict[str, int]
    :param http_status_counts: Distribution of HTTP response status codes.
    :type http_status_counts: Dict[int, int]
    :param top_errors: Frequently repeated error messages and their occurrence counts.
    :type top_errors: List[Dict[str, Any]]
    :param unique_ips: List of distinct anonymized or extracted IP addresses.
    :type unique_ips: List[str]
    :param peak_error_periods: Time windows exhibiting highest error densities.
    :type peak_error_periods: List[Dict[str, Any]]
    :param recommendations: Diagnostics summary and operational tips.
    :type recommendations: List[str]
    :param analyzed_at: Timestamp of inspection.
    :type analyzed_at: datetime

    Example:
        >>> res = LogAnalysisResult("app.log", 100, 98, 2, {"ERROR": 5}, {500: 2}, [], [], [])
        >>> res.total_lines
        100
    """

    file_path: str
    total_lines: int
    parsed_lines: int
    unparsed_lines: int
    level_counts: Dict[str, int] = field(default_factory=dict)
    http_status_counts: Dict[int, int] = field(default_factory=dict)
    top_errors: List[Dict[str, Any]] = field(default_factory=list)
    unique_ips: List[str] = field(default_factory=list)
    peak_error_periods: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=datetime.now)
