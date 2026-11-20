"""Folder pairs ("sources"): an LLM results folder with the PDFs it was made from, reviewed on its own.

Each source keeps its own originals, drafts, versions and page cache. The first one, ``default``, uses the data
folder's own ``originals/``, ``annotations/`` and ``cache/`` (the layout before there were several), so data made
before stays where it is; every other source lives under ``sources/<id>/``. Settings stay in ``annotations/``.
Removing a source from Settings never deletes its data.
"""
import re
from pathlib import Path

DEFAULT_ID = 'default'
SOURCE_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,39}')


def source_dir(data, sid):
    return Path(data) if sid == DEFAULT_ID else Path(data) / 'sources' / sid


def slug(name):
    s = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40].strip('-')
    return s or 'source'


def new_id(name, taken):
    """An id made from the name that no source uses and no folder under sources/ holds."""
    base = slug(name)
    sid, k = base, 2
    while sid in taken:
        sid, k = f'{base[:36]}-{k}', k + 1
    return sid


def default_name(run_dir):
    return Path(str(run_dir)).name or 'LLM results'


def _valid(entry):
    return (isinstance(entry, dict) and isinstance(entry.get('id'), str) and SOURCE_ID.fullmatch(entry['id'])
            and all(isinstance(entry.get(k), str) and entry[k] for k in ('name', 'run_dir', 'pdf_dir')))


def normalize(stored, default_run, default_pdf):
    """(sources, active id) from stored settings of any layout. Settings saved before sources existed hold
    ``run_dir``/``pdf_dir``: they become the default source."""
    found = stored.get('sources')
    sources, seen = [], set()
    if isinstance(found, list):
        for e in found:
            if _valid(e) and e['id'] not in seen:
                seen.add(e['id'])
                sources.append({k: e[k] for k in ('id', 'name', 'run_dir', 'pdf_dir')})
    if not sources:
        run = stored.get('run_dir') if isinstance(stored.get('run_dir'), str) and stored.get('run_dir') else str(default_run)
        pdf = stored.get('pdf_dir') if isinstance(stored.get('pdf_dir'), str) and stored.get('pdf_dir') else str(default_pdf)
        sources = [{'id': DEFAULT_ID, 'name': default_name(run), 'run_dir': run, 'pdf_dir': pdf}]
    active = stored.get('active_source')
    if active not in {s['id'] for s in sources}:
        active = sources[0]['id']
    return sources, active
