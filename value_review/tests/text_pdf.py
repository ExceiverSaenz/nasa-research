"""A small PDF with real text lines, for the tests that look for quoted text (72-extraction-interface-contract.md).

``make_text_pdf(path, [["line", …], …])`` writes one US-letter page per list, each line in Helvetica 12 pt, from the
top. The file is built by hand (no new dependency) and read by pypdfium2 like any other PDF.
"""
from pathlib import Path


def _escape(text):
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def make_text_pdf(path, pages):
    objects = ['<< /Type /Catalog /Pages 2 0 R >>', None, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>']
    kids = []
    for lines in pages:
        ops = ['BT', '/F1 12 Tf']
        for i, line in enumerate(lines):
            ops.append(f'1 0 0 1 72 {720 - 20 * i} Tm ({_escape(line)}) Tj')
        ops.append('ET')
        stream = '\n'.join(ops).encode('cp1252')
        content_no = len(objects) + 2
        page_no = len(objects) + 1
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_no} 0 R >>')
        objects.append(stream)
        kids.append(f'{page_no} 0 R')
    objects[1] = f'<< /Type /Pages /Kids [{" ".join(kids)}] /Count {len(kids)} >>'
    out, offsets = bytearray(b'%PDF-1.4\n'), []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        if isinstance(obj, bytes):
            out += f'{i} 0 obj\n<< /Length {len(obj)} >>\nstream\n'.encode() + obj + b'\nendstream\nendobj\n'
        else:
            out += f'{i} 0 obj\n{obj}\nendobj\n'.encode('cp1252')
    xref = len(out)
    out += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode()
    out += b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets)
    out += f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    Path(path).write_bytes(bytes(out))
