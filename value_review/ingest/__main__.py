"""python -B -m value_review.ingest [--run DIR] [--pdfs DIR] [--out DIR] [--paper N ...]

Exit code 0 when every paper is written or unchanged, 1 when any failed, 2 when an original with
different content already exists (left untouched).
"""
import argparse
import sys

from .. import config
from . import ingest_run


def main(argv=None):
    ap = argparse.ArgumentParser(prog='value_review.ingest', description='Build immutable originals from an LLM run.')
    ap.add_argument('--run', default=None, help='LLM run folder (default: %s under the source root)' % config.RUN_REL.as_posix())
    ap.add_argument('--pdfs', default=None, help='PDF folder (default: %s under the source root)' % config.PDFS_REL.as_posix())
    ap.add_argument('--out', default=None, help='Originals folder (default: value_review/originals)')
    ap.add_argument('--paper', action='append', help='Only this paper id (repeatable)')
    args = ap.parse_args(argv)
    rows = ingest_run(args.run or config.default_run_dir(), args.pdfs or config.default_pdf_dir(),
                      args.out or config.originals_dir(), args.paper)
    if not rows:
        print('No result files found.', file=sys.stderr)
        return 1
    for r in rows:
        print(f"paper {r['paper']:>3}  {r['outcome']:<9} values {r['values']:>4}  needs a check {r['needs_check']:>3}  issues {r['issues']}"
              + (f"  {r['error']}" if r['error'] else ''))
    print(f"total values {sum(r['values'] for r in rows)}, needs a check {sum(r['needs_check'] for r in rows)}")
    if any(r['outcome'] == 'failed' for r in rows):
        return 1
    if any(r['outcome'] == 'changed' for r in rows):
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
