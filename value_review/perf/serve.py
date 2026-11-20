"""Serve a temporary copy of the real run (or the stress set) for the browser measurements (frontend/perf).

    python -B -m value_review.perf.serve --root <empty folder> --port <port> [--dataset real|stress]

The LLM run and PDFs are only read; originals, drafts, versions and the page cache go under ``--root``.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review.__main__ import main as launch  # noqa: E402
from value_review.perf.server_bench import build_real, build_stress  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -B -m value_review.perf.serve')
    parser.add_argument('--root', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--dataset', choices=['real', 'stress'], default='real')
    args = parser.parse_args(argv)
    data = build_real(args.root) if args.dataset == 'real' else build_stress(args.root)
    return launch(['--no-browser', '--data', str(data), '--port', str(args.port)])


if __name__ == '__main__':
    sys.exit(main())
