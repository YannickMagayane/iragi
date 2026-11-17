"""Unified analysis pipeline orchestrating Iragi Scan and PDF engines.

Combines document extraction, tabular quality auditing, and multi-file
batch processing into a consolidated workflow.

Example:
    >>> from iragi.all.pipeline import analyze
    >>> # result = analyze("document.pdf")
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pandas as pd

from iragi.core.exceptions import IragiDataError
from iragi.core.models import DataInspectionResult, QualityScore
from iragi.core.remote import is_remote_url, resolve_file_source
from iragi.pdf.extractor import extract
from iragi.pdf.models import ExtractedDocument
from iragi.scan.engine import scan, scan_dataframe
from iragi.scan.reports import inspection_result_to_dict


@dataclass
class UnifiedAnalysisResult:
    """Consolidated findings combining document extraction and quality audits.

    :param file_path: Source path of analyzed file.
    :type file_path: str
    :param file_type: Inferred format ('pdf', 'csv', 'excel', 'json').
    :type file_type: str
    :param document: Extracted document model if source is PDF.
    :type document: Optional[ExtractedDocument]
    :param tabular_inspections: Quality inspection results for tabular datasets or extracted tables.
    :type tabular_inspections: List[DataInspectionResult]
    :param overall_quality_score: Aggregated quality score (0-100).
    :type overall_quality_score: float
    :param recommendations: Consolidated prioritized recommendations.
    :type recommendations: List[str]
    :param analyzed_at: Inspection timestamp.
    :type analyzed_at: datetime

    Example:
        >>> res = UnifiedAnalysisResult("sample.csv", "csv", None, [], 95.0, ["Clean data"])
        >>> res.overall_quality_score
        95.0
    """

    file_path: str
    file_type: str
    document: Optional[ExtractedDocument] = None
    tabular_inspections: List[DataInspectionResult] = field(default_factory=list)
    overall_quality_score: float = 100.0
    recommendations: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None
    analyzed_at: datetime = field(default_factory=datetime.now)

    def summary(self) -> Dict[str, Any]:
        """Produce a high-level summary dictionary of the unified analysis.

        :return: Summary metrics dict.
        :rtype: Dict[str, Any]

        Example:
            >>> res = UnifiedAnalysisResult("test.csv", "csv", None, [], 90.0, [])
            >>> summary = res.summary()
            >>> summary["overall_quality_score"]
            90.0
        """
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "success": self.success,
            "error": self.error,
            "overall_quality_score": self.overall_quality_score,
            "tables_audited": len(self.tabular_inspections),
            "recommendations_count": len(self.recommendations),
            "analyzed_at": self.analyzed_at.isoformat(),
        }


def analyze(
    file_path: Union[str, Path],
    enable_ocr: bool = False,
    allowed_hosts=None,
) -> UnifiedAnalysisResult:
    """Execute end-to-end extraction and quality audit on a file.

    For tabular files (CSV, Excel, JSON), it delegates directly to iragi.scan.
    For PDF documents, it extracts text/tables via iragi.pdf and pipes extracted
    tables into iragi.scan for quality auditing.

    :param file_path: Path to target file.
    :type file_path: Union[str, Path]
    :param enable_ocr: Whether to run OCR if scanned PDF pages are detected.
    :type enable_ocr: bool
    :param allowed_hosts: Optional host allowlist for remote URLs.
    :type allowed_hosts: Optional[List[str]]
    :return: UnifiedAnalysisResult.
    :rtype: UnifiedAnalysisResult
    :raises IragiDataError: If file is unsupported or unreadable.

    Example:
        >>> import tempfile
        >>> tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        >>> _ = tmp.write("a,b\\n1,2")
        >>> tmp.close()
        >>> res = analyze(tmp.name)
        >>> res.file_type
        'csv'
    """
    path, is_temp = resolve_file_source(file_path, allowed_hosts=allowed_hosts)
    try:
        if not path.is_file():
            raise IragiDataError(f"Target file not found: {path}")

        suffix = path.suffix.lower()

        # Case 1: Tabular data file
        if suffix in [".csv", ".tsv", ".txt", ".xlsx", ".xls", ".xlsm", ".json", ".jsonl", ".parquet", ".pq"]:
            tabular_res = scan(path)
            if suffix in [".csv", ".tsv", ".txt"]:
                ftype = "csv"
            elif suffix in [".xlsx", ".xls", ".xlsm"]:
                ftype = "excel"
            elif suffix in [".parquet", ".pq"]:
                ftype = "parquet"
            else:
                ftype = "json"
            return UnifiedAnalysisResult(
                file_path=str(path),
                file_type=ftype,
                document=None,
                tabular_inspections=[tabular_res],
                overall_quality_score=tabular_res.quality_score.total_score,
                recommendations=tabular_res.recommendations,
                analyzed_at=datetime.now(),
            )

        # Case 2: PDF Document
        if suffix == ".pdf":
            doc = extract(path, extract_tables=True, enable_ocr=enable_ocr)
            tabular_inspections: List[DataInspectionResult] = []
            scores: List[float] = []
            all_recs: List[str] = []

            for idx, table in enumerate(doc.tables, start=1):
                df = table.to_dataframe()
                if not df.empty:
                    table_source_name = f"{path.name} [Page {table.page_number} Table #{idx}]"
                    inspection = scan_dataframe(df, source_name=table_source_name)
                    tabular_inspections.append(inspection)
                    scores.append(inspection.quality_score.total_score)
                    all_recs.extend(inspection.recommendations)

            if doc.requires_ocr and not enable_ocr:
                all_recs.append("Detected potential scanned pages with missing text layer. Consider re-running with OCR enabled.")

            avg_score = round(sum(scores) / len(scores), 2) if scores else 100.0

            return UnifiedAnalysisResult(
                file_path=str(path),
                file_type="pdf",
                document=doc,
                tabular_inspections=tabular_inspections,
                overall_quality_score=avg_score,
                recommendations=list(dict.fromkeys(all_recs)),
                analyzed_at=datetime.now(),
            )

        raise IragiDataError(f"Unsupported file format '{suffix}' for unified analysis.")
    finally:
        if is_temp:
            path.unlink(missing_ok=True)


def _analyze_excel_all_sheets(
    path: Path,
    enable_ocr: bool,
) -> List["UnifiedAnalysisResult"]:
    """Analyze every sheet of an Excel workbook independently.

    :param path: Path to the Excel file.
    :type path: Path
    :param enable_ocr: Unused for Excel; kept for signature consistency.
    :type enable_ocr: bool
    :return: One UnifiedAnalysisResult per sheet.
    :rtype: List[UnifiedAnalysisResult]

    Example:
        >>> results = _analyze_excel_all_sheets(Path("workbook.xlsx"), enable_ocr=False)
        >>> len(results)  # equals number of sheets in the workbook
        3
    """
    from iragi.scan.readers import read_excel_file

    sheet_results: List[UnifiedAnalysisResult] = []
    probe_df = read_excel_file(path, sheet_name=0)
    sheet_names = probe_df.attrs.get("sheet_names", [path.stem])

    for sheet in sheet_names:
        try:
            df = read_excel_file(path, sheet_name=sheet)
            inspection = scan_dataframe(df, source_name=f"{path} [Sheet: {sheet}]")
            sheet_results.append(UnifiedAnalysisResult(
                file_path=f"{path} [Sheet: {sheet}]",
                file_type="excel",
                document=None,
                tabular_inspections=[inspection],
                overall_quality_score=inspection.quality_score.total_score,
                recommendations=inspection.recommendations,
                analyzed_at=datetime.now(),
            ))
        except Exception as exc:
            sheet_results.append(UnifiedAnalysisResult(
                file_path=f"{path} [Sheet: {sheet}]",
                file_type="excel",
                overall_quality_score=0.0,
                success=False,
                error=str(exc),
                recommendations=[f"Sheet '{sheet}' analysis failed: {exc}"],
                analyzed_at=datetime.now(),
            ))

    return sheet_results


def batch_analyze(
    target_path: Union[str, Path, List[Union[str, Path]]],
    recursive: bool = False,
    enable_ocr: bool = False,
    raise_on_error: bool = False,
    excel_all_sheets: bool = False,
    allowed_hosts=None,
) -> List[UnifiedAnalysisResult]:
    """Execute analysis across a batch list of files or directory path.

    Records explicit failure results if individual files fail during batch ingestion,
    preventing silent data drops while allowing batch workflows to continue.

    When ``excel_all_sheets=True``, each sheet of every Excel workbook in the
    batch is analyzed independently, producing one result per sheet.

    :param target_path: Directory path or list of individual file paths.
    :type target_path: Union[str, Path, List[Union[str, Path]]]
    :param recursive: Search directories recursively if directory path given.
    :type recursive: bool
    :param enable_ocr: Whether to run OCR for detected scanned PDF pages.
    :type enable_ocr: bool
    :param raise_on_error: If True, raise exception on first error instead of logging it in results.
    :type raise_on_error: bool
    :param excel_all_sheets: If True, analyze every sheet of Excel workbooks independently.
    :type excel_all_sheets: bool
    :param allowed_hosts: Optional host allowlist for remote URLs.
    :type allowed_hosts: Optional[List[str]]
    :return: List of UnifiedAnalysisResult objects (including explicit error entries).
    :rtype: List[UnifiedAnalysisResult]

    Example:
        >>> # results = batch_analyze(["data1.csv", "corrupted.csv"])
        >>> # assert results[1].success is False
        >>> # results = batch_analyze(["report.xlsx"], excel_all_sheets=True)
        >>> # assert len(results) == number_of_sheets
    """
    files_to_process: List[Union[str, Path]] = []

    if isinstance(target_path, list):
        files_to_process = list(target_path)
    else:
        path = Path(target_path)
        if path.is_file():
            files_to_process = [path]
        elif path.is_dir():
            pattern = "**/*" if recursive else "*"
            supported_suffixes = {
                ".csv",
                ".tsv",
                ".xlsx",
                ".xls",
                ".xlsm",
                ".json",
                ".jsonl",
                ".parquet",
                ".pq",
                ".pdf",
            }
            for item in path.glob(pattern):
                if item.is_file() and item.suffix.lower() in supported_suffixes:
                    files_to_process.append(item)

    results: List[UnifiedAnalysisResult] = []
    for file_item in files_to_process:
        try:
            if not is_remote_url(file_item) and Path(file_item).suffix.lower() in {".xlsx", ".xls", ".xlsm"} and excel_all_sheets:
                results.extend(_analyze_excel_all_sheets(Path(file_item), enable_ocr=enable_ocr))
            else:
                res = analyze(file_item, enable_ocr=enable_ocr, allowed_hosts=allowed_hosts)
                results.append(res)
        except Exception as exc:
            if raise_on_error:
                raise
            suffix_str = Path(str(file_item)).suffix.lower().lstrip(".")
            error_res = UnifiedAnalysisResult(
                file_path=str(file_item),
                file_type=suffix_str,
                overall_quality_score=0.0,
                success=False,
                error=str(exc),
                recommendations=[f"Analysis failed: {exc}"],
                analyzed_at=datetime.now(),
            )
            results.append(error_res)

    return results
