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
import re
import zipfile
from pathlib import Path
from typing import Iterator, Tuple, Union, Optional
import pandas as pd
from iragi.core.exceptions import IragiDataError

# Characters that trigger formula injection in spreadsheet apps (CSV Injection)
_FORMULA_INJECTION_CHARS = re.compile(r"^[=+\-@\t\r]+")


def _check_zip_bomb(
    path: Path, max_ratio: float = 100.0, max_uncompressed_bytes: int = 500 * 1024 * 1024
) -> None:
    """Detect potential Zip Bomb or abnormal decompression ratios in archive-based files.

    Protects against Billion Laughs / Zip Bomb attacks where tiny archives decompress
    into gigabytes of repetitive data, exhausting server memory.

    :param path: Path to archive file.
    :type path: Path
    :param max_ratio: Maximum allowable uncompressed-to-compressed size ratio (default: 100).
    :type max_ratio: float
    :param max_uncompressed_bytes: Maximum total uncompressed payload size (default: 500MB).
    :type max_uncompressed_bytes: int
    :raises IragiDataError: If compression ratio or total uncompressed size violates limits.

    Example:
        >>> from pathlib import Path
        >>> _check_zip_bomb(Path("sample.xlsx"))
    """
    if not zipfile.is_zipfile(path):
        return

    total_uncompressed = 0
    total_compressed = max(1, path.stat().st_size)

    try:
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                total_uncompressed += info.file_size
                if total_uncompressed > max_uncompressed_bytes:
                    raise IragiDataError(
                        f"Potential Zip Bomb detected: uncompressed size ({total_uncompressed} bytes) "
                        f"exceeds safety threshold ({max_uncompressed_bytes} bytes)."
                    )
    except zipfile.BadZipFile as exc:
        raise IragiDataError(f"Corrupted or invalid zip archive: {exc}") from exc

    ratio = total_uncompressed / total_compressed
    if ratio > max_ratio and total_uncompressed > 5 * 1024 * 1024:
        raise IragiDataError(
            f"Potential Zip Bomb detected: compression ratio ({ratio:.1f}x) "
            f"exceeds safety limit ({max_ratio}x)."
        )


def _sanitize_formulas(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading formula-injection characters from all string columns.

    Removes leading ``=``, ``+``, ``-``, ``@``, ``\\t``, ``\\r`` characters
    from string values to prevent CSV Formula Injection when the output is
    opened in a spreadsheet application.

    :param df: DataFrame to sanitize (in-place on a copy).
    :type df: pd.DataFrame
    :return: Sanitized DataFrame copy.
    :rtype: pd.DataFrame

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({"cmd": ["=FORMULA", "+SUM(1)", "safe"]})
        >>> out = _sanitize_formulas(df)
        >>> out["cmd"].tolist()
        ['FORMULA', 'SUM(1)', 'safe']
    """
    df = df.copy()
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].apply(
            lambda v: _FORMULA_INJECTION_CHARS.sub("", str(v)) if isinstance(v, str) else v
        )
    return df


def read_csv_file(file_path: Union[str, Path], delimiter: Optional[str] = None, sanitize_formulas: bool = False) -> pd.DataFrame:
    """Read a CSV file into a pandas DataFrame with automatic delimiter and BOM inference.

    Handles UTF-8 with BOM (\\ufeff), standard UTF-8, Latin-1, and infers
    common delimiters (',', ';', '\\t', '|'). Exposes detected delimiter
    via DataFrame.attrs['delimiter'].

    :param file_path: Path to the CSV file.
    :type file_path: Union[str, Path]
    :param delimiter: Optional explicit column delimiter.
    :type delimiter: Optional[str]
    :param sanitize_formulas: If True, strip leading ``= + - @`` from string cells
        to prevent CSV Formula Injection. Default: False (backward compatible).
    :type sanitize_formulas: bool
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
                    if sanitize_formulas:
                        df = _sanitize_formulas(df)
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

    _check_zip_bomb(path)

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

    _check_zip_bomb(path)

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


def iter_csv_chunks(
    file_path: Union[str, Path],
    chunksize: int = 50_000,
    delimiter: Optional[str] = None,
    sanitize_formulas: bool = False,
) -> Iterator[pd.DataFrame]:
    """Yield successive DataFrame chunks from a CSV file.

    Enables bounded-memory streaming without loading the full file in RAM.

    :param file_path: Path to the CSV file.
    :type file_path: Union[str, Path]
    :param chunksize: Number of rows per chunk (default: 50 000).
    :type chunksize: int
    :param delimiter: Optional explicit delimiter.
    :type delimiter: Optional[str]
    :param sanitize_formulas: Strip leading formula injection characters.
    :type sanitize_formulas: bool
    :return: Iterator yielding DataFrame slices.
    :rtype: Iterator[pd.DataFrame]
    :raises IragiDataError: If reading fails.

    Example:
        >>> for chunk in iter_csv_chunks("file.csv", chunksize=10_000):
        ...     assert len(chunk) <= 10_000
    """
    path = Path(file_path)
    if not path.is_file():
        raise IragiDataError(f"File not found: {path}")

    probe = read_csv_file(path, delimiter=delimiter)
    detected_delimiter = probe.attrs.get("delimiter", ",")
    detected_encoding = probe.attrs.get("encoding", "utf-8-sig")

    try:
        reader = pd.read_csv(
            path,
            sep=detected_delimiter,
            encoding=detected_encoding,
            chunksize=chunksize,
            engine="python",
        )
        for chunk in reader:
            if sanitize_formulas:
                chunk = _sanitize_formulas(chunk)
            chunk.attrs["delimiter"] = detected_delimiter
            chunk.attrs["encoding"] = detected_encoding
            yield chunk
    except Exception as exc:
        raise IragiDataError(f"Failed streaming CSV chunks from '{path}': {exc}") from exc


def read_csv_chunked(
    file_path: Union[str, Path],
    chunksize: int = 50_000,
    delimiter: Optional[str] = None,
    sanitize_formulas: bool = False,
) -> pd.DataFrame:
    """Read a large CSV file in chunks and assemble into a single DataFrame.

    :param file_path: Path to the CSV file.
    :type file_path: Union[str, Path]
    :param chunksize: Number of rows per chunk (default: 50 000).
    :type chunksize: int
    :param delimiter: Optional explicit delimiter; inferred when omitted.
    :type delimiter: Optional[str]
    :param sanitize_formulas: Strip leading formula injection characters.
    :type sanitize_formulas: bool
    :return: Assembled DataFrame with attrs['delimiter'] populated.
    :rtype: pd.DataFrame
    :raises IragiDataError: If the file cannot be read.

    Example:
        >>> import tempfile
        >>> tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        >>> _ = tmp.write("x,y\\n1,2\\n3,4")
        >>> tmp.close()
        >>> df = read_csv_chunked(tmp.name, chunksize=1)
        >>> len(df)
        2
    """
    chunks = list(
        iter_csv_chunks(
            file_path,
            chunksize=chunksize,
            delimiter=delimiter,
            sanitize_formulas=sanitize_formulas,
        )
    )
    if not chunks:
        return pd.DataFrame()
    df = pd.concat(chunks, ignore_index=True)
    df.attrs["delimiter"] = chunks[0].attrs.get("delimiter")
    df.attrs["encoding"] = chunks[0].attrs.get("encoding")
    return df


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
