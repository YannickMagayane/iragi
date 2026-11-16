"""Domain models for Iragi PDF extraction engine.

Provides structured representations for extracted PDF pages, tabular grids,
metadata, and consolidated multi-page document results.

Example:
    >>> from iragi.pdf.models import ExtractedTable, ExtractedDocument
    >>> table = ExtractedTable(page_number=1, table_index=0, headers=["A", "B"], rows=[["1", "2"]])
    >>> len(table.rows)
    1
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import pandas as pd


@dataclass
class ExtractedTable:
    """Represents a tabular grid extracted from a document page.

    :param page_number: 1-indexed page number containing the table.
    :type page_number: int
    :param table_index: 0-indexed order of table within the page.
    :type table_index: int
    :param headers: Extracted column headers.
    :type headers: List[str]
    :param rows: Extracted row values.
    :type rows: List[List[Any]]
    :param dataframe: Optional pandas DataFrame representation.
    :type dataframe: Optional[pd.DataFrame]

    Example:
        >>> t = ExtractedTable(1, 0, ["Item", "Qty"], [["Pen", 10]])
        >>> t.headers[0]
        'Item'
    """

    page_number: int
    table_index: int
    headers: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)
    dataframe: Optional[pd.DataFrame] = None

    def to_dataframe(self) -> pd.DataFrame:
        """Convert extracted table data into a pandas DataFrame.

        :return: DataFrame containing table data.
        :rtype: pd.DataFrame

        Example:
            >>> t = ExtractedTable(1, 0, ["x", "y"], [[1, 2], [3, 4]])
            >>> df = t.to_dataframe()
            >>> df.shape
            (2, 2)
        """
        if self.dataframe is not None:
            return self.dataframe
        if self.headers and self.rows:
            return pd.DataFrame(self.rows, columns=self.headers)
        if self.rows:
            return pd.DataFrame(self.rows)
        return pd.DataFrame()


@dataclass
class ExtractedPage:
    """Represents text and tables extracted from a single document page.

    :param page_number: 1-indexed page number.
    :type page_number: int
    :param text: Extracted plain text content.
    :type text: str
    :param is_scanned: Flag indicating whether page lacks selectable text (likely scanned).
    :type is_scanned: bool
    :param tables: Tables identified and extracted from this page.
    :type tables: List[ExtractedTable]

    Example:
        >>> page = ExtractedPage(page_number=1, text="Invoice #123", is_scanned=False)
        >>> page.page_number
        1
    """

    page_number: int
    text: str = ""
    is_scanned: bool = False
    tables: List[ExtractedTable] = field(default_factory=list)


@dataclass
class ExtractedDocument:
    """Consolidated document extraction output.

    :param file_path: Source file path.
    :type file_path: str
    :param page_count: Total page count.
    :type page_count: int
    :param metadata: Document metadata (title, author, creation_date, etc.).
    :type metadata: Dict[str, Any]
    :param pages: List of individual extracted pages.
    :type pages: List[ExtractedPage]
    :param full_text: Aggregated document text content.
    :type full_text: str
    :param tables: All tabular grids extracted across the entire document.
    :type tables: List[ExtractedTable]
    :param requires_ocr: True if any pages are detected as scanned without text.
    :type requires_ocr: bool

    Example:
        >>> doc = ExtractedDocument("report.pdf", 1, {"title": "Annual Report"}, [], "Summary text", [], False)
        >>> doc.page_count
        1
    """

    file_path: str
    page_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    pages: List[ExtractedPage] = field(default_factory=list)
    full_text: str = ""
    tables: List[ExtractedTable] = field(default_factory=list)
    requires_ocr: bool = False
