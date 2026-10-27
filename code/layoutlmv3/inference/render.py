"""PDF-to-RGB rendering, without writing outputs or importing the detector.

Consumes types.RenderedPage; run_page.run_page coordinates its use.
"""
from pathlib import Path

import numpy as np

from .types import RenderedPage, _positive_int


def render_page(pdf_path: Path, page_number: int, dpi: int = 200) -> RenderedPage:
    """Renders the visible box with intrinsic rotation applied.

    Args:
        pdf_path: Path to an existing readable PDF.
        page_number: Physical page, positive integer starting at 1.
        dpi: Resolution, positive integer; default 200 dots per inch.
    Returns:
        RenderedPage with RGB uint8 (height, width, 3), PDF box in points
        of 1/72 inch and rotation in degrees.
    Raises:
        ValueError: Invalid page/dpi, out-of-range page or UserUnit other than 1.
        OSError: Missing or inaccessible file.
        Exception: pypdf/PDFium read errors propagate.
    Notes:
        Reads the PDF with pypdf and PDFium; releases page and bitmap. Writes no files.
        Doc-Refs: INF-003, INF-007.
    """
    import pypdfium2 as pdfium
    from pypdf import PdfReader

    _positive_int(page_number, 'page_number')
    _positive_int(dpi, 'dpi')
    pdf_path = Path(pdf_path).resolve(strict=True)
    # PDFium does not apply UserUnit consistently across versions; don't silently
    # record a false physical resolution for these uncommon files.
    reader = PdfReader(pdf_path)
    if page_number > len(reader.pages):
        raise ValueError('Page number exceeds PDF page count')
    if float(reader.pages[page_number - 1].get('/UserUnit', 1)) != 1:
        raise ValueError('Nonstandard PDF UserUnit is not supported in this MVP')
    with pdfium.PdfDocument(str(pdf_path)) as document:
        page = document[page_number - 1]
        try:
            crop = tuple(float(x) for x in page.get_bbox())
            rotation = page.get_rotation()
            bitmap = page.render(scale=dpi / 72)
            try:
                image = np.asarray(bitmap.to_pil().convert('RGB')).copy()
            finally:
                bitmap.close()
        finally:
            page.close()
    return RenderedPage(pdf_path, page_number, dpi, image, crop, rotation)
