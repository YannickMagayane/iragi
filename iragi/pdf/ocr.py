"""OCR and scanned page detection for Iragi PDF engine.

Detects document pages with low or non-existent digital text densities
and optionally performs Optical Character Recognition using Tesseract.

Example:
    >>> from iragi.pdf.ocr import is_page_likely_scanned
    >>> is_page_likely_scanned("short", 0)
    True
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


def is_page_likely_scanned(extracted_text: str, image_count: int = 0) -> bool:
    """Determine if a PDF page is likely an image scan lacking a text layer.

    :param extracted_text: Text extracted by standard PDF parser.
    :type extracted_text: str
    :param image_count: Number of raster images detected on the page.
    :type image_count: int
    :return: True if the page is likely scanned without native text.
    :rtype: bool

    Example:
        >>> is_page_likely_scanned("Hello world", 0)
        False
        >>> is_page_likely_scanned("", 1)
        True
    """
    clean = extracted_text.strip()
    if len(clean) < 30 and image_count > 0:
        return True
    if len(clean) == 0:
        return True
    return False


def run_ocr_on_image(image: "Image.Image", lang: str = "eng") -> str:
    """Execute Tesseract OCR on a PIL Image if pytesseract is installed.

    :param image: Input PIL Image.
    :type image: Image.Image
    :param lang: Tesseract language code (default: 'eng').
    :type lang: str
    :return: Recognized text string or empty string on failure.
    :rtype: str

    Example:
        >>> from PIL import Image
        >>> img = Image.new('RGB', (100, 30), color='white')
        >>> text = run_ocr_on_image(img)
        >>> isinstance(text, str)
        True
    """
    try:
        import pytesseract
        return pytesseract.image_to_string(image, lang=lang).strip()
    except Exception:
        # Graceful fallback if tesseract binary is not installed on system
        return ""
