"""A review service on synthetic papers, for the browser tests (frontend/e2e, ADR-008).

    python -B -m value_review.tests.e2e_server --root <empty folder> --port <port>

Builds two folder pairs under ``--root`` and serves them with the real launcher:
- ``default`` ("Model A"): papers 7 and 8 (the synthetic paper of test_ingest, two pages, partial model run);
- ``model-b`` ("Model B"): paper 7, plus an LLM result without its PDF (11) and a PDF without a result (12).
Nothing outside ``--root`` is read or written; the caller deletes the folder.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from value_review.__main__ import main as launch  # noqa: E402
from value_review.ingest import ingest_run  # noqa: E402
from value_review.tests.fake_provider import FakeProvider  # noqa: E402
from value_review.tests.test_ingest import make_pdf, result, sha  # noqa: E402

RESULT = '-pdf_with_feature_guide.json'


def paper(run, pdfs, pid, title):
    pdf = pdfs / f'{pid}.pdf'
    make_pdf(pdf, [(612, 792), (612, 792)])
    data = result(sha(pdf))
    data['paper'].update(paper_id=pid, title=title)
    (run / f'{pid}{RESULT}').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def build(root):
    root = Path(root)
    run, pdfs, run_b, pdfs_b, data = (root / n for n in ('run', 'pdfs', 'run-b', 'pdfs-b', 'data'))
    for folder in (run, pdfs, run_b, pdfs_b, data / 'annotations'):
        folder.mkdir(parents=True, exist_ok=True)
    paper(run, pdfs, '7', 'Sub-size specimens of FeCrAl')
    paper(run, pdfs, '8', 'Tensile tests of Zircaloy-4')
    shutil.copy(run / f'7{RESULT}', run_b / f'7{RESULT}')
    shutil.copy(pdfs / '7.pdf', pdfs_b / '7.pdf')
    shutil.copy(run / f'8{RESULT}', run_b / f'11{RESULT}')   # a result whose PDF is missing
    make_pdf(pdfs_b / '12.pdf', [(612, 792)])                 # a PDF without a result
    ingest_run(run, pdfs, data / 'originals')
    ingest_run(run_b, pdfs_b, data / 'sources' / 'model-b' / 'originals', ['7'])
    settings = {'reviewer_name': 'Expert reviewer', 'keep_versions': 20, 'autosave_minutes': 5, 'active_source': 'default',
                'sources': [{'id': 'default', 'name': 'Model A', 'run_dir': str(run), 'pdf_dir': str(pdfs)},
                            {'id': 'model-b', 'name': 'Model B', 'run_dir': str(run_b), 'pdf_dir': str(pdfs_b)}]}
    (data / 'annotations' / 'settings.json').write_text(json.dumps(settings, indent=1), encoding='utf-8')
    return data


def build_workspace(root, data_root):
    """A workspace (62-workspace-interface-contract.md): set "tensile" with PDFs 7, 8 and 9 and two runs, "gpt-low"
    with a result for paper 7 and "gpt-high" with results for 7 and 8."""
    folder = Path(root) / 'workspace'
    papers = folder / 'papers' / 'tensile'
    papers.mkdir(parents=True)
    shutil.copy(data_root.parent / 'pdfs' / '7.pdf', papers / '7.pdf')
    shutil.copy(data_root.parent / 'pdfs' / '8.pdf', papers / '8.pdf')
    make_pdf(papers / '9.pdf', [(612, 792)])
    for name, ids in (('gpt-low', ['7']), ('gpt-high', ['7', '8'])):
        run = folder / 'results' / 'tensile' / name
        run.mkdir(parents=True)
        for pid in ids:
            shutil.copy(data_root.parent / 'run' / f'{pid}{RESULT}', run / f'{pid}{RESULT}')
    return folder


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -B -m value_review.tests.e2e_server')
    parser.add_argument('--root', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--with-workspace', action='store_true')
    args = parser.parse_args(argv)
    data = build(args.root)
    # A local fake of the model providers (fake_provider.py): no request leaves the machine. Its address is written
    # next to the data so a browser test can type the own-server URL.
    fake = FakeProvider()
    os.environ.update(fake.env())
    os.environ['VALUE_REVIEW_WARM_UP'] = '0'   # a test server starts in seconds; the SDK loads on the first model call
    (Path(args.root) / 'fake-provider.txt').write_text(fake.url, encoding='utf-8')
    extra = ['--workspace', str(build_workspace(args.root, data))] if args.with_workspace else []
    return launch(['--no-browser', '--data', str(data), '--port', str(args.port), *extra])


if __name__ == '__main__':
    sys.exit(main())
