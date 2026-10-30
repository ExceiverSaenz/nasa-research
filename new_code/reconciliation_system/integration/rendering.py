"""Explicit, in-memory regeneration for inspection; never used by reconciliation."""
import hashlib
import io
from importlib.metadata import version
from pathlib import Path


def regenerate_png(identity, pdf):
    """Return original PNG bytes or reject a renderer/geometry/hash mismatch."""
    from .common import digest
    import pypdfium2 as pdfium
    from pypdf import PdfReader
    pdf = Path(pdf)
    if digest(pdf) != identity['document_sha256']:
        raise ValueError('Source PDF identity mismatch')
    renderer = identity.get('renderer', {})
    if renderer.get('engine') != 'pypdfium2' or renderer.get('version') != version('pypdfium2'):
        raise ValueError('Original renderer version required for exact regeneration')
    number = identity['physical_page']
    reader = PdfReader(pdf)
    if not 1 <= number <= len(reader.pages) or float(reader.pages[number-1].get('/UserUnit',1)) != 1:
        raise ValueError('Unsupported PDF page geometry')
    with pdfium.PdfDocument(str(pdf)) as document:
        page = document[number-1]
        try:
            geometry = identity['geometry']
            if list(page.get_bbox()) != geometry['crop_box_pt'] or page.get_rotation() != geometry['rotation_deg']:
                raise ValueError('PDF geometry changed')
            bitmap = page.render(scale=identity['dpi']/72)
            try:
                image = bitmap.to_pil().convert('RGB')
                if image.size != (identity['width_px'],identity['height_px']):
                    raise ValueError('Regenerated dimensions differ')
                stream = io.BytesIO()
                image.save(stream,format='PNG',dpi=(identity['dpi'],identity['dpi']))
                raw = stream.getvalue()
            finally:
                bitmap.close()
        finally:
            page.close()
    if hashlib.sha256(raw).hexdigest() != identity['render_sha256']:
        raise ValueError('Regenerated PNG differs from model input')
    return raw
