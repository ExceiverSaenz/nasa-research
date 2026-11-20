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
    """``VALUE_REVIEW_SOURCE_ROOT`` if set; else the repository root, or the nearest folder above it
    that holds the LLM run (a git worktree under ``.claude/worktrees/`` has no sources of its own)."""
    env = os.environ.get('VALUE_REVIEW_SOURCE_ROOT')
    if env:
        return Path(env)
    for root in (REPO_ROOT, *REPO_ROOT.parents):
        if (root / RUN_REL).is_dir() and (root / PDFS_REL).is_dir():
            return root
    return REPO_ROOT


def data_root():
    return Path(os.environ.get('VALUE_REVIEW_DATA') or PACKAGE)


def default_run_dir():
    """``VALUE_REVIEW_RUN_DIR`` if set (a container mounts the LLM results there), else under the source root."""
    return Path(os.environ.get('VALUE_REVIEW_RUN_DIR') or source_root() / RUN_REL)


def default_pdf_dir():
    """``VALUE_REVIEW_PDF_DIR`` if set, else under the source root."""
    return Path(os.environ.get('VALUE_REVIEW_PDF_DIR') or source_root() / PDFS_REL)


def originals_dir(data=None):
    return Path(data or data_root()) / 'originals'
