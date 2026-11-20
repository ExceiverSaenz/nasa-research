"""Resolve immutable original files in place; freeze stores references only."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path, PureWindowsPath
from .contracts import Block, InputDocument, identity
from .context import validate_parents
from .geometry import convert_box

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def resolve_reference(value, *, relative_to=None):
    """Resolve repository-relative references and relocate historical checkouts.

    Frozen strings remain untouched: identity and file hashes are still checked
    by their callers. Colab /content paths are not repository locations.
    """
    text = str(value).replace('\\', '/')
    path = Path(text)
    absolute = text.startswith('/') or PureWindowsPath(text).is_absolute()
    if not absolute and relative_to is not None:
        return (Path(relative_to) / path).resolve()
    if absolute:
        if path.is_absolute() and path.resolve().is_relative_to(PROJECT_ROOT.resolve()):
            return path.resolve()
        for anchor in ('test_libs', 'new_code', 'history'):
            marker = '/' + anchor + '/'
            if marker in text:
                text = anchor + '/' + text.rsplit(marker, 1)[1]
                break
        else:
            if not path.is_absolute():
                raise ValueError('Absolute reference has no repository mapping')
            return path.resolve()
    relative = Path(text)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Repository reference escapes the project')
    target = (PROJECT_ROOT / relative).resolve()
    if not target.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError('Repository reference escapes the project')
    return target


def portable_reference(value):
    """Serialize local repository paths as POSIX paths relative to its root."""
    path = resolve_reference(value)
    if path.is_relative_to(PROJECT_ROOT.resolve()):
        return path.relative_to(PROJECT_ROOT.resolve()).as_posix()
    return path.as_posix()  # Explicit external data roots stay external.


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class LocalReferences:
    def __init__(self, root):
        self.root = resolve_reference(root)

    def read(self, paper, name, expected=None):
        path = (self.root / paper / name).resolve()
        if not path.is_relative_to(self.root) or path.name not in ('normalized.json', 'middle.json'):
            raise ValueError('Source path is outside the registered reference root')
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected and digest != expected:
            raise ValueError('Source SHA256 changed')
        return json.loads(raw), digest

    @staticmethod
    def pointer(document, pointer):
        if not pointer.startswith('/'):
            raise ValueError('Invalid JSON Pointer')
        value = document
        for part in pointer[1:].split('/'):
            key = part.replace('~1', '/').replace('~0', '~')
            if isinstance(value, list):
                if not key.isdigit():
                    raise ValueError('Invalid array pointer')
                value = value[int(key)]
            else:
                value = value[key]
        return value


def _text_parts(node):
    if not isinstance(node, dict):
        return []
    content = node.get('content')
    if isinstance(content, str):
        return [content] if node.get('type') in ('text', 'equation') else []
    return [text for child in content or [] for text in _text_parts(child)]


class Ingestor:
    def __init__(self, references):
        self.references = references

    def read(self, paper, pdf_pages=None, expected=None):
        expected = expected or {}
        rows, norm_sha = self.references.read(paper, 'normalized.json', expected.get('normalized_sha256'))
        middle, mid_sha = self.references.read(paper, 'middle.json', expected.get('middle_sha256'))
        ids = [row['id'] for row in rows]
        if len(ids) != len(set(ids)) or not rows:
            raise ValueError('Duplicate IDs or empty original')
        papers = {row['paper_sha256'] for row in rows}
        if len(papers) != 1:
            raise ValueError('Ambiguous paper identity')
        by_ref = {row['original_ref']: row['id'] for row in rows}
        declared = middle.get('metadata', {}).get('document', {}).get('page_count')
        count = declared if isinstance(declared, int) else max(row['page_idx'] for row in rows) + 1
        dimensions = {p['page_idx']: p for p in middle.get('extensions', {}).get('docvortex_layout', {}).get('pages', [])}
        if pdf_pages is not None and len(pdf_pages) != count:
            raise ValueError('PDF and MinerU page inventories differ')
        pages = []
        for index in range(count):
            meta = dimensions.get(index, {})
            page = dict(page_idx=index, width=meta.get('width_pt'), height=meta.get('height_pt'), rotation=None)
            if pdf_pages is not None:
                measured = pdf_pages[index]
                # PDF coordinates are unrotated; MinerU boxes use displayed page coordinates.
                w, h = measured['width'], measured['height']
                if measured['rotation'] in (90, 270):
                    w, h = h, w
                if page['width'] is not None and (abs(page['width']-w) > .1 or abs(page['height']-h) > .1):
                    raise ValueError('MinerU/PDF page dimensions disagree')
                page.update(width=w, height=h, rotation=measured['rotation'],
                            pdf_width=measured['width'],pdf_height=measured['height'])
            pages.append(page)
        blocks = []
        for row in rows:
            original, separator, pointer = row['original_ref'].partition('#')
            if (row['original_sha256'] != mid_sha or not separator
                    or not original.endswith('/' + paper + '/middle.json')):
                raise ValueError('Unresolved original identity')
            try:
                node = self.references.pointer(middle, pointer)
            except (KeyError, IndexError, TypeError) as error:
                raise ValueError('Unresolved source pointer') from error
            parent_ref = row.get('native_parent_ref')
            if parent_ref and parent_ref not in by_ref:
                raise ValueError('Parent reference was not found')
            parent = by_ref.get(parent_ref)
            bbox = row.get('bbox_normalized')
            reason = 'internal_child' if parent else None
            if row.get('geometry_error'):
                reason = reason or 'invalid_geometry'
            if row.get('coordinate_system','normalized_top_left')!='normalized_top_left':
                raise ValueError('Unsupported source coordinate system; no implicit conversion')
            if bbox is None:
                reason = reason or 'missing_bbox'
            else:
                try:
                    convert_box(bbox, 1000, 1000)
                except (TypeError, ValueError):
                    reason = reason or 'invalid_geometry'
            parts = _text_parts(node) if row['raw_label'] not in ('image', 'chart', 'table') else []
            blocks.append(Block(row['id'], next(iter(papers)), row['page_idx'], row['raw_label'], bbox,
                                parent, row['original_ref'], ''.join(parts) if parts else None, parts,
                                exclusion=reason))
        validate_parents({b.id: b.parent_id for b in blocks})
        return InputDocument(paper, next(iter(papers)), pages, blocks,
                             dict(paper_id=paper, normalized_sha256=norm_sha, middle_sha256=mid_sha))

    def freeze(self, paper_ids, destination, pdf_metadata=None):
        destination = Path(destination)
        if not paper_ids or len(set(paper_ids)) != len(paper_ids):
            raise ValueError('Expected unique explicit document IDs')
        docs = [self.read(paper, (pdf_metadata or {}).get(paper)) for paper in paper_ids]
        manifest = {'schema': 'reading-order-input/1', 'source_root': portable_reference(self.references.root),
                    'documents': [dict(doc.references, paper_sha256=doc.paper_sha256,
                                       pages=doc.pages, exclusions=[{'id': b.id, 'reason': b.exclusion}
                                                                 for b in doc.blocks if b.exclusion]) for doc in docs]}
        manifest['input_profile_id'] = identity(manifest)
        destination.mkdir(parents=True, exist_ok=False)
        (destination / 'input-manifest.json').write_text(json.dumps(manifest, indent=2))
        return manifest

    def resolve(self, manifest):
        if resolve_reference(manifest['source_root']) != self.references.root:
            raise ValueError('Input source root changed')
        content = {key: value for key, value in manifest.items() if key != 'input_profile_id'}
        if identity(content) != manifest['input_profile_id']:
            raise ValueError('Frozen manifest changed')
        return [self.read(row['paper_id'], pdf_pages=[dict(width=p.get('pdf_width',p['width']),
                          height=p.get('pdf_height',p['height']),rotation=p['rotation']) for p in row['pages']]
                          if all(p['rotation'] is not None for p in row['pages']) else None, expected=row)
                for row in manifest['documents']]
