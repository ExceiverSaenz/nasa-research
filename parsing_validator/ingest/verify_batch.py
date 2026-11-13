"""Generate all originals into parsing_validator/originals and prove the sealed trees did not change.

    python -m parsing_validator.ingest.verify_batch
"""
import hashlib
import sys

from .__main__ import DEFAULT_COLLECTION, DEFAULT_OUT, DEFAULT_PDFS, main


def inventory(folder):
    h, n = hashlib.sha256(), 0
    for p in sorted(folder.rglob('*')):
        if p.is_file():
            st = p.stat()
            h.update(f'{p.relative_to(folder).as_posix()}|{st.st_size}|{st.st_mtime_ns}\n'.encode())
            n += 1
    return n, h.hexdigest()


if __name__ == '__main__':
    before = (inventory(DEFAULT_COLLECTION), inventory(DEFAULT_PDFS))
    code = main([])
    after = (inventory(DEFAULT_COLLECTION), inventory(DEFAULT_PDFS))
    print('sealed trees unchanged:', before == after, '| files:', before[0][0], 'collection,', before[1][0], 'pdfs')
    print('output folder:', DEFAULT_OUT)
    sys.exit(code if before == after else 2)
