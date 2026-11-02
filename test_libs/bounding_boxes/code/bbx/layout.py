"""Resolve the approved local layout while preserving flat remote bundles."""
from functools import lru_cache
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


def project_root(filename=__file__):
    for parent in Path(filename).resolve().parents:
        if (parent / '.layout.json').is_file():
            return parent
        if (parent / 'experiment.json').is_file() and (parent / 'bbx').is_dir():
            return parent
    raise ValueError('Cannot identify bounding_boxes workspace')


@lru_cache(maxsize=8)
def _mapping(path, stamp):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def resolve_path(path, *, root=None):
    """Translate legacy local paths; never change remote provenance strings."""
    path = Path(path).absolute()
    root = Path(root).resolve() if root is not None else project_root()
    marker = root / '.layout.json'
    if not marker.is_file() or not path.is_relative_to(root):
        return path
    layout = _mapping(str(marker), marker.stat().st_mtime_ns)
    rel = path.relative_to(root).as_posix()
    if rel in layout['files']:
        return root / layout['files'][rel]
    for old, new in sorted(layout['prefixes'].items(), key=lambda item: -len(item[0])):
        if rel == old.rstrip('/'):
            return root / new.rstrip('/')
        if rel.startswith(old):
            return root / (new + rel[len(old):])
    return path


def wheel_directory(lock):
    """Locks live in config/requirements locally, requirements in flat bundles."""
    base = Path(lock).absolute().parent.parent
    if base.name == 'config':
        base = base.parent
        if base.name == 'code':
            base = base.parent
    return base / 'runtime/reused-wheels'


def authored_report_path(data_dir):
    data_dir = Path(data_dir).resolve()
    try:
        root = project_root(data_dir/'report.md')
    except ValueError:
        root = project_root()
    raw = root/'raw_results/analytics'
    if data_dir.is_relative_to(raw):
        return resolve_path(root/'reports/analytics'/data_dir.relative_to(raw)/'report.md',root=root)
    return data_dir/'report.md'


def write_authored_report(data_dir, text):
    """Place narrative separately from data and rebase generated Markdown links."""
    data_dir = Path(data_dir).resolve()
    target = authored_report_path(data_dir)
    try:
        root = project_root(data_dir/'report.md')
    except ValueError:
        root = project_root()
    legacy = data_dir
    marker = root/'.layout.json'
    if marker.is_file() and data_dir.is_relative_to(root):
        mapping = _mapping(str(marker), marker.stat().st_mtime_ns)
        rel = data_dir.relative_to(root).as_posix()
        for old, new in sorted(mapping['prefixes'].items(), key=lambda item:-len(item[1])):
            if rel.startswith(new):
                legacy = root/(old+rel[len(new):])
                break
    def rewrite(match):
        raw = match[2]
        u = urlsplit(raw)
        if u.scheme or raw.startswith(('#','//')) or not u.path:
            return match[0]
        p = resolve_path((legacy/unquote(u.path)).resolve(),root=root)
        if p.is_relative_to(data_dir) and p.suffix=='.md':
            relative=p.relative_to(data_dir)
            if relative.parts[0]=='review' or p.name=='report.md':
                p=target.parent/relative
        link=Path(os.path.relpath(p,target.parent)).as_posix().replace(' ','%20')
        if u.fragment:link+='#'+u.fragment
        return match[1]+link+')'
    text=re.sub(r'(!?\[[^\]]*\]\()([^\n]+?)\)',rewrite,text)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as f:
        f.write(text)
    return target
