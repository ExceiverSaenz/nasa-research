"""PDF discovery and shared 200-DPI page rendering, without model imports."""
import hashlib
import json
from pathlib import Path
import re


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def count_pages(path):
    import pypdfium2 as pdfium
    with pdfium.PdfDocument(str(path)) as document:
        return len(document)


def source_stat(path):
    stat = Path(path).stat()
    return {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}


def collect_papers(paths, input_dir=None, *, page_counter=count_pages):
    candidates = [Path(path).expanduser().resolve(strict=True) for path in paths]
    if input_dir is not None:
        directory = Path(input_dir).expanduser().resolve(strict=True)
        if not directory.is_dir():
            raise ValueError('Input directory is not a directory')
        candidates.extend(sorted((p.resolve() for p in directory.iterdir()
                                  if p.is_file() and p.suffix.lower() == '.pdf'),
                                 key=lambda p: (p.name.casefold(), str(p))))
    if not candidates:
        raise ValueError('At least one PDF is required')
    seen_paths, seen_hashes, papers = set(), set(), []
    for path in candidates:
        if not path.is_file() or path.suffix.lower() != '.pdf':
            raise ValueError('Each input must be a PDF file: ' + str(path))
        if path in seen_paths:
            raise ValueError('Duplicate input path: ' + str(path))
        before = source_stat(path)
        with path.open('rb') as stream:
            if b'%PDF-' not in stream.read(1024):
                raise ValueError('Invalid PDF header: ' + str(path))
        sha = digest(path)
        if sha in seen_hashes:
            raise ValueError('Duplicate PDF content: ' + str(path))
        pages = page_counter(path)
        if type(pages) is not int or pages < 1:
            raise ValueError('PDF must contain at least one page')
        if source_stat(path) != before:
            raise ValueError('PDF changed during input planning: ' + str(path))
        name = re.sub(r'[^A-Za-z0-9_-]+', '-', path.stem).strip('-')[:60] or 'paper'
        papers.append({'id': name + '-' + sha, 'path': str(path),
                       'sha256': sha, 'page_count': pages, 'source_stat': before})
        seen_paths.add(path)
        seen_hashes.add(sha)
    return papers


def render_page_job(paper, page, destination):
    source = Path(paper['path'])
    if source_stat(source) != paper.get('source_stat') or not 1 <= page <= paper['page_count']:
        raise ValueError('PDF changed or page is out of range')
    from PIL import Image
    from parsing.adapters.layoutlmv3.inference.render import render_page
    from parsing.adapters.layoutlmv3.inference.outputs import render_geometry
    rendered = render_page(source, page, 200)
    if source_stat(source) != paper['source_stat']:
        raise ValueError('PDF changed while rendering')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    png, metadata = destination / 'render.png', destination / 'identity.json'
    if png.exists() or metadata.exists():
        raise FileExistsError('Shared page output already exists')
    Image.fromarray(rendered.image).save(png, dpi=(200, 200))
    identity = {'document_sha256': paper['sha256'], 'physical_page': page,
                'render_sha256': digest(png), 'width_px': rendered.width_px,
                'height_px': rendered.height_px, 'dpi': 200,
                'geometry': render_geometry(rendered),
                'renderer': {'engine': 'pypdfium2', 'version': __import__('importlib.metadata', fromlist=['version']).version('pypdfium2'),
                             'format': 'PNG', 'color': 'RGB', 'dpi': 200}}
    if paper.get('execution_id'):
        identity['execution_id'] = paper['execution_id']
    identity = json.loads(json.dumps(identity, allow_nan=False))
    with metadata.open('x', encoding='utf-8') as stream:
        json.dump(identity, stream, indent=2, allow_nan=False)
    return {'paper_id': paper['id'], 'page': page, 'pdf_path': str(source), 'render_path': str(png),
            'identity': identity}
