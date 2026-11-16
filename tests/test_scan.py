"""Unit tests for the Iragi Scan engine (Phase 2).

Validates file readers (CSV, Excel, JSON), column profiling, outlier detection,
quality score calculations, actionable recommendations, and JSON report generation.

Example:
    To run this test suite manually:
    $ pytest tests/test_scan.py
"""

import json
import tempfile
from pathlib import Path
import pytest
import pandas as pd
from iragi.core.exceptions import IragiDataError
from iragi.scan import scan, scan_dataframe, to_json_report
from iragi.scan.readers import load_tabular_file, read_csv_file, read_excel_file, read_json_file
from iragi.scan.profiler import infer_column_type, detect_outliers_iqr, detect_invalid_dates


def test_read_csv_comma_and_semicolon() -> None:
    """Verify CSV reading handles comma and semicolon delimiters automatically.

    Example:
        >>> with tempfile.NamedTemporaryFile(suffix='.csv') as f:
        ...     pass
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("name;age;city\nAlice;30;Paris\nBob;25;Lyon\n")
        csv_path = f.name

    df = read_csv_file(csv_path)
    assert len(df) == 2
    assert list(df.columns) == ["name", "age", "city"]
    Path(csv_path).unlink()


def test_read_json_records() -> None:
    """Verify JSON reader parses array of record objects.

    Example:
        >>> df = read_json_file("tests/data/sample.json")
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump([{"item": "Laptop", "price": 1200}, {"item": "Mouse", "price": 25}], f)
        json_path = f.name

    df = read_json_file(json_path)
    assert len(df) == 2
    assert "price" in df.columns
    Path(json_path).unlink()


def test_read_excel_file() -> None:
    """Verify Excel reading extracts sheet data accurately into a DataFrame.

    Example:
        >>> df = read_excel_file("tests/data/sample.xlsx")
    """
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        excel_path = f.name

    source_df = pd.DataFrame({"product": ["A", "B", "C"], "qty": [10, 20, 30]})
    source_df.to_excel(excel_path, index=False)

    loaded_df = read_excel_file(excel_path)
    assert len(loaded_df) == 3
    assert list(loaded_df.columns) == ["product", "qty"]
    Path(excel_path).unlink()


def test_unsupported_file_format_raises_error() -> None:
    """Verify that unsupported extensions trigger an explicit IragiDataError.

    Example:
        >>> with pytest.raises(IragiDataError):
        ...     load_tabular_file("unknown.parquet")
    """
    with tempfile.NamedTemporaryFile(suffix=".unsupported", delete=False) as f:
        bad_path = f.name

    with pytest.raises(IragiDataError) as exc_info:
        load_tabular_file(bad_path)

    assert "Unsupported file format" in str(exc_info.value)
    Path(bad_path).unlink()


def test_column_profiler_types_and_outliers() -> None:
    """Verify column semantic type inference and IQR-based outlier detection.

    Example:
        >>> s = pd.Series([1, 2, 3, 100])
        >>> count = detect_outliers_iqr(s)
    """
    num_series = pd.Series([10, 11, 12, 10, 11, 12, 100])
    assert infer_column_type(num_series) == "numeric"
    assert detect_outliers_iqr(num_series) == 1

    date_series = pd.Series(["2024-01-01", "2024-01-02", "bad_date"])
    assert detect_invalid_dates(date_series) == 1


def test_scan_dataframe_and_quality_score() -> None:
    """Verify that scan_dataframe computes quality score deductions for duplicates and nulls.

    Example:
        >>> df = pd.DataFrame({"x": [1, 1], "y": [2, 2]})
        >>> res = scan_dataframe(df)
        >>> assert res.duplicate_rows_count == 1
    """
    df = pd.DataFrame({
        "id": [1, 2, 2, 4],
        "value": [10.0, None, None, 40.0],
        "date": ["2024-01-01", "2024-01-02", "2024-01-02", "invalid_date"],
    })

    result = scan_dataframe(df, source_name="test_data")
    assert result.row_count == 4
    assert result.column_count == 3
    assert result.missing_values_count == 2
    assert result.duplicate_rows_count == 1
    assert result.quality_score.total_score < 100.0
    assert len(result.recommendations) > 0


def test_scan_full_pipeline_with_csv() -> None:
    """Verify high-level scan function parses a CSV file and produces valid results.

    Example:
        >>> res = scan("data.csv")
        >>> assert res.row_count > 0
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("user,status,balance\nAlice,active,100\nBob,pending,200\nCharlie,active,300\n")
        csv_path = f.name

    result = scan(csv_path)
    assert result.row_count == 3
    assert result.column_count == 3
    assert result.missing_values_count == 0
    assert result.quality_score.total_score == 100.0
    assert len(result.column_profiles) == 3
    Path(csv_path).unlink()


def test_json_report_generation() -> None:
    """Verify that to_json_report produces valid, formatted JSON.

    Example:
        >>> res = scan("data.csv")
        >>> json_str = to_json_report(res)
    """
    df = pd.DataFrame({"col": [1, 2, 3]})
    result = scan_dataframe(df)

    json_str = to_json_report(result)
    parsed = json.loads(json_str)

    assert "quality_score" in parsed
    assert "column_profiles" in parsed
    assert parsed["row_count"] == 3


def test_read_csv_utf8_bom_and_delimiter_attribute() -> None:
    """Verify CSV reader handles UTF-8 with BOM and exposes detected delimiter.

    Example:
        >>> df = read_csv_file("bom.csv")
        >>> assert df.attrs["delimiter"] == ";"
    """
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
        # Write UTF-8 BOM (\xef\xbb\xbf) followed by semicolon-separated data
        content = "\ufeffid;produit;montant\n1;Pomme;12,50\n2;Banane;8,00\n".encode("utf-8-sig")
        f.write(content)
        csv_path = f.name

    result = scan(csv_path)
    assert result.row_count == 2
    assert result.delimiter == ";"
    Path(csv_path).unlink()


def test_excel_sheet_names_and_selection() -> None:
    """Verify Excel reader exposes all available sheet names and allows sheet selection.

    Example:
        >>> res = scan("data.xlsx", sheet_name=0)
        >>> assert "Sheet1" in res.sheet_names
    """
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        excel_path = f.name

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        pd.DataFrame({"x": [1, 2]}).to_excel(writer, sheet_name="Synthese", index=False)
        pd.DataFrame({"y": [10, 20, 30]}).to_excel(writer, sheet_name="Donnees", index=False)

    result = scan(excel_path, sheet_name="Donnees")
    assert result.row_count == 3
    assert result.sheet_names is not None
    assert "Synthese" in result.sheet_names
    assert "Donnees" in result.sheet_names
    Path(excel_path).unlink()


def test_formatted_numbers_inferred_as_numeric_with_outliers() -> None:
    """Verify that columns with formatted numbers (commas, spaces) are recognized as numeric and tested for outliers.

    Example:
        >>> s = pd.Series(["1 000,50", "1 010,00", "100 000,00"])
        >>> assert infer_column_type(s) == "numeric"
    """
    s = pd.Series(["100,50", "102,00", "99,80", "101,20", "5 000,00"])
    assert infer_column_type(s) == "numeric"
    outliers = detect_outliers_iqr(s)
    assert outliers == 1


def test_api_shadowing_shim_compatibility() -> None:
    """Verify that iragi.scan.scan(...) and scan.scan(...) are both callable without AttributeError.

    Example:
        >>> import iragi
        >>> res = iragi.scan.scan(path)
    """
    import iragi
    import iragi.scan as scan_module

    assert callable(iragi.scan)
    assert callable(iragi.scan.scan)
    assert callable(scan_module.scan)
    assert callable(scan_module.scan.scan)
