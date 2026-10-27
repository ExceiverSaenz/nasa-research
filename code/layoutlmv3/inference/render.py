"""Renderizado PDF a RGB, sin escritura de salidas ni importación del detector.

Consume types.RenderedPage; run_page.run_page coordina su uso.
"""
from pathlib import Path

import numpy as np

from .types import RenderedPage, _positive_int


def render_page(pdf_path: Path, page_number: int, dpi: int = 200) -> RenderedPage:
    """Renderiza la caja visible con rotación intrínseca aplicada.

    Args:
        pdf_path: Ruta de un PDF existente y legible.
        page_number: Página física, entero positivo desde 1.
        dpi: Resolución, entero positivo; default 200 puntos por pulgada.
    Returns:
        RenderedPage con RGB uint8 (height, width, 3), caja PDF en puntos
        de 1/72 de pulgada y rotación en grados.
    Raises:
        ValueError: Página/dpi inválidos, página fuera de rango o UserUnit distinto de 1.
        OSError: Archivo inexistente o inaccesible.
        Exception: Errores de lectura de pypdf/PDFium se propagan.
    Notes:
        Lee el PDF con pypdf y PDFium; libera page y bitmap. No escribe archivos.
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
