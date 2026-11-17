"""PDF Document extraction engine for Iragi.

Provides text extraction via PyMuPDF (fitz), metadata parsing, scanned page
detection, and structured multi-format document representations with streaming
page support for large files.

Example:
    >>> from iragi.pdf.extractor import extract_text_from_pdf, extract_metadata_from_pdf
    >>> # text = extract_text_from_pdf("document.pdf")
"""

from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union
from iragi.core.exceptions import IragiDataError
from iragi.pdf.models import ExtractedDocument, ExtractedPage, ExtractedTable
from iragi.pdf.tables import extract_tables_from_pdf, extract_tables_stream
from iragi.pdf.ocr import is_page_likely_scanned, run_ocr_on_image


def extract_metadata_from_pdf(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Extract standard document metadata properties from a PDF.

    :param file_path: Path to target PDF file.
    :type file_path: Union[str, Path]
    :return: Dictionary containing title, author, producer, creation date, etc.
    :rtype: Dict[str, Any]
    :raises IragiDataError: If file is missing or unreadable.

    Example:
        >>> # meta = extract_metadata_from_pdf("document.pdf")
    """
    path = Path(file_path)
    if not path.is_file():
        raise IragiDataError(f"PDF file not found: {path}")

    # Try PyMuPDF first
    try:
        import pymupdf as fitz
        doc = fitz.open(path)
        meta = dict(doc.metadata) if doc.metadata else {}
        meta["page_count"] = len(doc)
        doc.close()
        return meta
    except Exception:
        pass

    # Fallback to pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        raw_meta = reader.metadata or {}
        meta = {str(k).replace("/", ""): str(v) for k, v in raw_meta.items()}
        meta["page_count"] = len(reader.pages)
        return meta
    except Exception as exc:
        raise IragiDataError(f"Failed to read PDF metadata from '{path}': {exc}") from exc


def extract_text_from_pdf(file_path: Union[str, Path]) -> str:
    """Extract all raw text content across all pages of a PDF document.

    :param file_path: Path to target PDF file.
    :type file_path: Union[str, Path]
    :return: Full extracted text string.
    :rtype: str
    :raises IragiDataError: If extraction fails.

    Example:
        >>> # text = extract_text_from_pdf("document.pdf")
    """
    path = Path(file_path)
    if not path.is_file():
        raise IragiDataError(f"PDF file not found: {path}")

    # PyMuPDF
    try:
        import pymupdf as fitz
        doc = fitz.open(path)
        pages_text = [page.get_text() for page in doc]
        doc.close()
        return "\n\n".join(pages_text).strip()
    except Exception:
        pass

    # Fallback to pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        pages_text = [p.extract_text() or "" for p in reader.pages]
        return "\n\n".join(pages_text).strip()
    except Exception as exc:
        raise IragiDataError(f"Failed to extract text from PDF '{path}': {exc}") from exc


def iter_pdf_pages(
    file_path: Union[str, Path],
    batch_size: int = 10,
    page_range: Optional[Tuple[int, int]] = None,
    enable_ocr: bool = False,
) -> Iterator[ExtractedPage]:
    """Yield pages one by one from a PDF document to prevent excessive memory usage.

    :param file_path: Path to target PDF file.
    :type file_path: Union[str, Path]
    :param batch_size: Number of pages processed per iteration batch (default: 10).
    :type batch_size: int
    :param page_range: Optional 1-based start and end page index tuple (inclusive).
    :type page_range: Optional[Tuple[int, int]]
    :param enable_ocr: Whether to run OCR on scanned pages lacking text.
    :type enable_ocr: bool
    :return: Iterator yielding ExtractedPage instances.
    :rtype: Iterator[ExtractedPage]
    :raises IragiDataError: If file is missing or unreadable.

    Example:
        >>> # for page in iter_pdf_pages("large_doc.pdf", batch_size=5):
        >>> #     print(page.page_number, len(page.text))
    """
    path = Path(file_path)
    if not path.is_file():
        raise IragiDataError(f"PDF file not found: {path}")

    try:
        import pymupdf as fitz

        doc = fitz.open(path)
        total_pages = len(doc)
        start_p = 1
        end_p = total_pages
        if page_range:
            start_p = max(1, page_range[0])
            end_p = min(total_pages, page_range[1])

        try:
            for idx in range(start_p, end_p + 1):
                page = doc[idx - 1]
                text = page.get_text() or ""
                images = page.get_images()
                is_scanned = is_page_likely_scanned(text, image_count=len(images))
                if is_scanned and enable_ocr:
                    pix = page.get_pixmap()
                    from PIL import Image
                    import io

                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = run_ocr_on_image(img)
                    if ocr_text:
                        text = ocr_text

                yield ExtractedPage(
                    page_number=idx,
                    text=text,
                    is_scanned=is_scanned,
                    tables=[],
                )
        finally:
            doc.close()
    except Exception:
        from pypdf import PdfReader

        reader = PdfReader(path)
        total_pages = len(reader.pages)
        start_p = 1
        end_p = total_pages
        if page_range:
            start_p = max(1, page_range[0])
            end_p = min(total_pages, page_range[1])

        for idx in range(start_p, end_p + 1):
            p = reader.pages[idx - 1]
            text = p.extract_text() or ""
            is_scanned = len(text.strip()) == 0
            yield ExtractedPage(
                page_number=idx,
                text=text,
                is_scanned=is_scanned,
                tables=[],
            )


def extract(
    file_path: Union[str, Path],
    extract_tables: bool = True,
    enable_ocr: bool = False,
    page_range: Optional[Tuple[int, int]] = None,
    max_pages: Optional[int] = None,
) -> ExtractedDocument:
    """Extract full content from a PDF document into an ExtractedDocument model.

    :param file_path: Path to target PDF file.
    :type file_path: Union[str, Path]
    :param extract_tables: Whether to detect and extract tabular grids.
    :type extract_tables: bool
    :param enable_ocr: Whether to run OCR on scanned pages lacking text.
    :type enable_ocr: bool
    :param page_range: Optional 1-based start and end page index tuple (inclusive).
    :type page_range: Optional[Tuple[int, int]]
    :param max_pages: Maximum total number of pages to process.
    :type max_pages: Optional[int]
    :return: ExtractedDocument instance.
    :rtype: ExtractedDocument
    :raises IragiDataError: If parsing or extraction encounters a failure.

    Example:
        >>> # doc = extract("document.pdf")
    """
    path = Path(file_path)
    if not path.is_file():
        raise IragiDataError(f"PDF file not found: {path}")

    if max_pages and not page_range:
        page_range = (1, max_pages)

    pages: List[ExtractedPage] = []
    full_text_parts: List[str] = []
    requires_ocr = False
    try:
        import pymupdf as fitz

        doc = fitz.open(path)
        try:
            metadata = dict(doc.metadata) if doc.metadata else {}
            metadata["page_count"] = len(doc)
            start_page = max(1, page_range[0]) if page_range else 1
            end_page = min(len(doc), page_range[1]) if page_range else len(doc)
            for page_number in range(start_page, end_page + 1):
                page = doc[page_number - 1]
                text = page.get_text() or ""
                is_scanned = is_page_likely_scanned(text, image_count=len(page.get_images()))
                if is_scanned:
                    requires_ocr = True
                    if enable_ocr:
                        import io
                        from PIL import Image

                        image = Image.open(io.BytesIO(page.get_pixmap().tobytes("png")))
                        recognized = run_ocr_on_image(image)
                        if recognized:
                            text = recognized
                pages.append(ExtractedPage(
                    page_number=page_number, text=text, is_scanned=is_scanned, tables=[]
                ))
                if text:
                    full_text_parts.append(text)
        finally:
            doc.close()
    except Exception:
        metadata = extract_metadata_from_pdf(path)
        pages = list(iter_pdf_pages(path, page_range=page_range, enable_ocr=enable_ocr))
        full_text_parts = [page.text for page in pages if page.text]
        requires_ocr = any(page.is_scanned for page in pages)

    # Extract tables if enabled
    tables: List[ExtractedTable] = []
    if extract_tables:
        try:
            tables = extract_tables_from_pdf(path, page_range=page_range)
        except Exception:
            tables = []

    # Map tables by page number
    tables_by_page: Dict[int, List[ExtractedTable]] = {}
    for tbl in tables:
        tables_by_page.setdefault(tbl.page_number, []).append(tbl)

    for page_item in pages:
        page_tables = tables_by_page.get(page_item.page_number, [])
        page_item.tables = page_tables

    return ExtractedDocument(
        file_path=str(path),
        page_count=len(pages),
        metadata=metadata,
        pages=pages,
        full_text="\n\n".join(full_text_parts).strip(),
        tables=tables,
        requires_ocr=requires_ocr,
    )
