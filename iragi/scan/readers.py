"""Tabular data readers for Iragi Scan engine.

Provides unified loading functions for CSV, Excel, and JSON data formats
with automatic encoding detection and delimiter inference.

Example:
    >>> from iragi.scan.readers import load_tabular_file
    >>> df, file_type = load_tabular_file("tests/data/sample.csv")
    >>> df.shape[0] > 0
    True
"""

import json
from pathlib import Path
from typing import Tuple, Union, Optional
import pandas as pd
from iragi.core.exceptions import IragiDataError


def read_csv_file(file_path: Union[str, Path], delimiter: Optional[str] = None) -> pd.DataFrame:
    """Read a CSV file into a pandas DataFrame with automatic delimiter and BOM inference.

    Handles UTF-8 with BOM (\\ufeff), standard UTF-8, Latin-1, and infers
    common delimiters (',', ';', '\\t', '|'). Exposes detected delimiter
    via DataFrame.attrs['delimiter'].

    :param file_path: Path to the CSV file.
    :type file_path: Union[str, Path]
    :param delimiter: Optional explicit column delimiter.
    :type delimiter: Optional[str]
    :return: Loaded pandas DataFrame with attrs['delimiter'] populated.
    :rtype: pd.DataFrame
    :raises IragiDataError: If the CSV file cannot be read or is invalid.

    Example:
        >>> import tempfile
        >>> tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        >>> _ = tmp.write("a;b\\n1;2\\n3;4")
        >>> tmp.close()
        >>> df = read_csv_file(tmp.name)
        >>> df.attrs.get("delimiter")
        ';'
    """
    path = Path(file_path)
    if not path.is_file():
        raise IragiDataError(f"File not found: {path}")

    # Encodings to try, starting with utf-8-sig to automatically strip BOM (\ufeff)
    encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
    delimiters = [delimiter] if delimiter else [",", ";", "\t", "|"]
    last_error: Optional[Exception] = None

    for encoding in encodings:
        for sep in delimiters:
            try:
                df = pd.read_csv(path, sep=sep, encoding=encoding, engine="python")
                # If multiple columns found, or it's the only delimiter specified
                if len(df.columns) > 1 or delimiter is not None or sep == delimiters[-1]:
                    df.attrs["delimiter"] = sep
                    df.attrs["encoding"] = encoding
                    return df
            except Exception as exc:
                last_error = exc

    raise IragiDataError(f"Failed to parse CSV file '{path}': {last_error}")


def read_excel_file(
    file_path: Union[str, Path], sheet_name: Optional[Union[str, int]] = 0
) -> pd.DataFrame:
    """Read an Excel workbook (.xlsx or .xls) into a pandas DataFrame.

    Exposes all available workbook sheet names via DataFrame.attrs['sheet_names'].

    :param file_path: Path to the Excel workbook.
    :type file_path: Union[str, Path]
    :param sheet_name: Target sheet name or index (default: 0).
    :type sheet_name: Optional[Union[str, int]]
    :return: Loaded pandas DataFrame.
    :rtype: pd.DataFrame
    :raises IragiDataError: If Excel reading fails.

    Example:
        >>> import tempfile
        >>> import pandas as pd
        >>> tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        >>> pd.DataFrame({"col": [1, 2]}).to_excel(tmp.name, index=False)
        >>> df = read_excel_file(tmp.name)
        >>> len(df)
        2
    """
    path = Path(file_path)
    if not path.is_file():
        raise IragiDataError(f"File not found: {path}")

    try:
        excel_file = pd.ExcelFile(path)
        all_sheets = excel_file.sheet_names
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        df.attrs["sheet_names"] = all_sheets
        df.attrs["sheet_name"] = str(sheet_name)
        return df
    except Exception as exc:
        raise IragiDataError(f"Failed to parse Excel file '{path}': {exc}") from exc


def read_json_file(file_path: Union[str, Path]) -> pd.DataFrame:
    """Read a JSON or JSON Lines file into a tabular pandas DataFrame.

    :param file_path: Path to the JSON file.
    :type file_path: Union[str, Path]
    :return: Loaded pandas DataFrame.
    :rtype: pd.DataFrame
    :raises IragiDataError: If JSON reading fails or format is non-tabular.

    Example:
        >>> import tempfile
        >>> tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        >>> _ = tmp.write('[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]')
        >>> tmp.close()
        >>> df = read_json_file(tmp.name)
        >>> df.iloc[0]["name"]
        'Alice'
    """
    path = Path(file_path)
    if not path.is_file():
        raise IragiDataError(f"File not found: {path}")

    try:
        # First attempt standard JSON loading
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            # Check if dict values are lists (columnar format)
            if all(isinstance(v, list) for v in data.values()):
                return pd.DataFrame(data)
            # Otherwise treat as single-row record
            return pd.DataFrame([data])
        else:
            raise IragiDataError(f"JSON root structure must be an array or object, got {type(data).__name__}")
    except json.JSONDecodeError:
        # Fallback to JSON Lines (ndjson)
        try:
            return pd.read_json(path, lines=True)
        except Exception as exc:
            raise IragiDataError(f"Failed to parse JSON file '{path}': {exc}") from exc
    except Exception as exc:
        raise IragiDataError(f"Failed to read JSON data from '{path}': {exc}") from exc


def load_tabular_file(
    file_path: Union[str, Path],
    sheet_name: Optional[Union[str, int]] = 0,
    delimiter: Optional[str] = None,
) -> Tuple[pd.DataFrame, str]:
    """Inspect file extension and load supported tabular data format.

    :param file_path: File system path of the target file.
    :type file_path: Union[str, Path]
    :param sheet_name: Target sheet name or index for Excel files (default: 0).
    :type sheet_name: Optional[Union[str, int]]
    :param delimiter: Optional explicit CSV delimiter.
    :type delimiter: Optional[str]
    :return: A tuple of (loaded DataFrame, format string 'csv'|'excel'|'json').
    :rtype: Tuple[pd.DataFrame, str]
    :raises IragiDataError: When the file format is unsupported or loading fails.

    Example:
        >>> import tempfile
        >>> tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        >>> _ = tmp.write("x,y\\n10,20")
        >>> tmp.close()
        >>> df, fmt = load_tabular_file(tmp.name)
        >>> fmt
        'csv'
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in [".csv", ".tsv", ".txt"]:
        return read_csv_file(path, delimiter=delimiter), "csv"
    elif suffix in [".xlsx", ".xls", ".xlsm"]:
        return read_excel_file(path, sheet_name=sheet_name), "excel"
    elif suffix in [".json", ".jsonl", ".ndjson"]:
        return read_json_file(path), "json"
    else:
        raise IragiDataError(
            f"Unsupported file format '{suffix}'. Supported formats are: CSV (.csv, .tsv), Excel (.xlsx, .xls), JSON (.json, .jsonl)."
        )
