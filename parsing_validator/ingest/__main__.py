"""Batch command: python -m parsing_validator.ingest [--collection DIR] [--pdfs DIR] [--out DIR] [paper ...]

Generates ``<out>/<n>.json`` for the given papers (all if none). Existing files are never overwritten:
if one would change, the command fails for that paper (BR-03). Read-only over sealed data.
"""
import argparse
import sys
import time
from pathlib import Path

from .adapter import ROOT, CollectionRepository
from .original import write_original

DEFAULT_COLLECTION = ROOT / 'src/raw_results/code_results/tensile_papers'
DEFAULT_PDFS = ROOT / 'papers/Tensile_Properties_of_Sub-sized_Specimens_papers'
DEFAULT_OUT = ROOT / 'parsing_validator/originals'


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m parsing_validator.ingest')
    parser.add_argument('papers', nargs='*')
    parser.add_argument('--collection', default=str(DEFAULT_COLLECTION))
    parser.add_argument('--pdfs', default=str(DEFAULT_PDFS))
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    papers = args.papers or list(CollectionRepository(args.collection).papers())
    failed = 0
    for n in papers:
        started = time.time()
        try:
            path = write_original(args.collection, args.pdfs, n, Path(args.out))
            print(f'{n}: ok {path} ({time.time() - started:.1f}s)', flush=True)
        except Exception as error:  # report and continue with the next paper
            failed += 1
            print(f'{n}: FAILED {type(error).__name__}: {str(error)[:200]}', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
