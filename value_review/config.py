"""Folder layout (02-repository-context.md, "Environment setup").

The repository root is the parent of this package. Sources (the LLM run and the PDFs) can live in
another checkout, so their root is configurable with ``VALUE_REVIEW_SOURCE_ROOT``.
"""
import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE.parent

RUN_REL = Path('llm_baseline/results/gpt-6.1-sol-low-pdf-only')
PDFS_REL = Path('papers/Tensile_Properties_of_Sub-sized_Specimens_papers')
RESULT_SUFFIX = '-pdf_with_feature_guide.json'


def source_root():
    return Path(os.environ.get('VALUE_REVIEW_SOURCE_ROOT') or REPO_ROOT)


def data_root():
    return Path(os.environ.get('VALUE_REVIEW_DATA') or PACKAGE)


def default_run_dir():
    return source_root() / RUN_REL


def default_pdf_dir():
    return source_root() / PDFS_REL


def originals_dir(data=None):
    return Path(data or data_root()) / 'originals'
