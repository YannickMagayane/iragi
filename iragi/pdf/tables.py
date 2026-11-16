"""Table extraction module for Iragi PDF engine.

Extracts structured tables from PDF pages using pdfplumber and converts them
into ExtractedTable domain models and pandas DataFrames.

Example:
    >>> from iragi.pdf.tables import extract_tables_from_pdf
    >>> # tables = extract_tables_from_pdf("document.pdf")
"""

from pathlib import Path
from typing import List, Union, Optional
import pandas as pd
from iragi.core.exceptions import IragiDataError
from iragi.pdf.models import ExtractedTable


def extract_tables_from_pdf(file_path: Union[str, Path]) -> List[ExtractedTable]:
    """Extract all tabular structures from a PDF document using pdfplumber.

    :param file_path: Path to target PDF file.
    :type file_path: Union[str, Path]
    :return: List of ExtractedTable instances.
    :rtype: List[ExtractedTable]
    :raises IragiDataError: If the document cannot be opened or parsed.

    Example:
        >>> import tempfile
        >>> # tables = extract_tables_from_pdf("tests/data/sample.pdf")
    """
    path = Path(file_path)
    if not path.is_file():
        raise IragiDataError(f"PDF file not found: {path}")

    extracted_tables: List[ExtractedTable] = []

    try:
        import logging
        import warnings
        import pdfplumber

        # Suppress harmless pdfminer FontBBox warnings during table extraction
        logging.getLogger("pdfminer").setLevel(logging.ERROR)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*FontBBox.*")
            with pdfplumber.open(path) as pdf:
                for page_idx, page in enumerate(pdf.pages, start=1):
                    raw_tables = page.extract_tables()
                    if not raw_tables:
                        continue

                    for table_idx, raw_table in enumerate(raw_tables):
                        if not raw_table or len(raw_table) < 2:
                            continue

                        # First row as headers, remainder as rows
                        raw_headers = [str(cell).strip() if cell is not None else f"col_{i}" for i, cell in enumerate(raw_table[0])]
                        rows: List[List[str]] = []
                        for raw_row in raw_table[1:]:
                            clean_row = [str(c).strip() if c is not None else "" for c in raw_row]
                            # Pad or truncate row length to match header count
                            if len(clean_row) < len(raw_headers):
                                clean_row.extend([""] * (len(raw_headers) - len(clean_row)))
                            rows.append(clean_row[: len(raw_headers)])

                        df = pd.DataFrame(rows, columns=raw_headers)
                        table_obj = ExtractedTable(
                            page_number=page_idx,
                            table_index=table_idx,
                            headers=raw_headers,
                            rows=rows,
                            dataframe=df,
                        )
                        extracted_tables.append(table_obj)

    except Exception as exc:
        raise IragiDataError(f"Failed to extract tables from PDF '{path}': {exc}") from exc

    return extracted_tables
