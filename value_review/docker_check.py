"""Startup check of the folders mounted into the container (Dockerfile, ADR-009).

Docker Desktop creates an empty folder when a path in value_review/.env is wrong, so the tool would start with no
papers and no explanation. This prints what is missing and which variable to fix. It never stops the container.
"""
import os
import sys
from pathlib import Path

from .config import RESULT_SUFFIX

CHECKS = (
    ('VALUE_REVIEW_RUN_DIR', '/sources/results', '*' + RESULT_SUFFIX, 'REVIEW_LLM_RESULTS', 'LLM results'),
    ('VALUE_REVIEW_PDF_DIR', '/sources/pdfs', '*.pdf', 'REVIEW_PDFS', 'PDFs'),
)


def main():
    ok = True
    for env, default, pattern, variable, what in CHECKS:
        folder = Path(os.environ.get(env) or default)
        count = len(list(folder.glob(pattern))) if folder.is_dir() else 0
        if count:
            print(f'{what}: {count} files in {folder}')
        else:
            ok = False
            print(f'WARNING: no {what} ({pattern}) in {folder}. Check {variable} in value_review/.env: it must be the '
                  f'folder on your computer that holds them. Then run: docker compose -f value_review/compose.yaml up -d',
                  file=sys.stderr)
    return 0 if ok else 1


if __name__ == '__main__':
    main()   # informative only: the tool starts either way
