"""Read completed hybrid parser attempts as canonical reconciliation evidence.

The adapter never runs parsers, extracts archives, copies files or rewrites native
records. New runs use an exact per-file manifest; historical runs retain ZIP
validation. PDF identity and geometry are checked without requiring saved pixels. These integrity checks do not
certify semantic accuracy or authenticate the producer with a digital signature.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import struct
import zipfile

from .reconciliation.consolidated_inputs import canonical_page

VERSION = 'hybrid-parser-input/1'
ENGINES = ('layoutlmv3', 'table_transformer', 'mineru')
SHA256 = re.compile(r'[0-9a-f]{64}')


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, 'Duplicate JSON key: ' + key)
        value[key] = item
    return value


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _identity(identity, sha, page, render):
    _require(isinstance(identity, dict), 'Missing page identity')
    _require(identity.get('document_sha256') == sha and type(identity.get('physical_page')) is int
             and identity['physical_page'] == page, 'Document/page identity mismatch')
    _require(SHA256.fullmatch(str(identity.get('render_sha256', ''))), 'Invalid render hash')
    width, height = identity.get('width_px'), identity.get('height_px')
    _require(all(type(v) is int and v > 0 for v in (width, height)) and identity.get('dpi') == 200,
             'Expected positive 200 DPI page dimensions')
    g = identity.get('geometry', {})
    _require(isinstance(g, dict) and g.get('width_px') == width and g.get('height_px') == height
             and g.get('dpi') == 200 and g.get('color') == 'RGB'
             and g.get('coordinate_system') == dict(unit='pixel', origin='top-left', bbox_format='xyxy'),
             'Unknown page geometry or coordinate system')
    box = g.get('crop_box_pt')
    _require(isinstance(box, list) and len(box) == 4 and all(_finite(x) for x in box)
             and box[0] < box[2] and box[1] < box[3] and type(g.get('rotation_deg')) is int
             and g['rotation_deg'] in (0, 90, 180, 270), 'Invalid PDF crop box/rotation')
    matrices = [g.get('pdf_to_render_matrix'), g.get('render_to_pdf_matrix')]
    for matrix in matrices:
        _require(isinstance(matrix, list) and len(matrix) == 3
                 and all(isinstance(row, list) and len(row) == 3 and all(_finite(v) for v in row) for row in matrix)
                 and matrix[2] == [0, 0, 1], 'Invalid affine PDF/render matrix')
    forward, inverse = matrices
    for i in range(3):
        for j in range(3):
            value = sum(forward[i][k] * inverse[k][j] for k in range(3))
            _require(math.isclose(value, float(i == j), rel_tol=1e-8, abs_tol=1e-7), 'PDF/render matrices are not inverse')
    # The declared transform must map the four crop corners onto the full render.
    corners = [(forward[0][0]*x + forward[0][1]*y + forward[0][2],
                forward[1][0]*x + forward[1][1]*y + forward[1][2])
               for x in (box[0], box[2]) for y in (box[1], box[3])]
    expected = [(0., 0.), (0., float(height)), (float(width), 0.), (float(width), float(height))]
    for corner in corners:
        match = next((target for target in expected
                      if all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(corner, target))), None)
        _require(match is not None, 'PDF/render matrix does not match crop dimensions')
        expected.remove(match)
    if render is None:
        return
    raw = render.read_bytes()
    _require(len(raw) >= 33 and raw[:8] == b'\x89PNG\r\n\x1a\n' and raw[12:16] == b'IHDR'
             and struct.unpack('>I', raw[8:12])[0] == 13 and struct.unpack('>II', raw[16:24]) == (width, height),
             'Render is not a PNG with the declared dimensions')


def load_run(run_directory, *, paper_ids=None, pdf_directory=None):
    """Validate and return documents ready for existing reconciliation algorithms.

    Return value includes ``documents`` (id, document path/hash, canonical pages,
    parser_configuration and source_inputs), plus the shared source_inputs map.
    Only completed attempts with exactly one completed tuple per page and engine
    are accepted. Invalid/missing child geometry remains an abstention incident.
    """
    root = Path(run_directory).expanduser().resolve(strict=True)
    _require(root.is_dir(), 'Parser input must be a run directory')
    if (root / 'manifest.json').exists():
        manifest_path = root / 'manifest.json'
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw, object_pairs_hook=_unique_object)
        _require(manifest.get('schema') == 'parsing-hybrid-files/2', 'Unsupported parser manifest')
        outputs = manifest.get('outputs')
        _require(isinstance(outputs, dict) and outputs, 'Empty parser manifest')
        if paper_ids is not None:
            raw_inputs = json.loads((root/'inputs.json').read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
            chosen = set(paper_ids)
            _require(chosen and len(chosen)==len(paper_ids) and chosen <= {p['id'] for p in raw_inputs}, 'Invalid selected paper ids')
            outputs = {name:sha for name,sha in outputs.items() if name in ('inputs.json','status.json','configuration.json')
                       or (len(PurePosixPath(name).parts)>1 and PurePosixPath(name).parts[0] in ('results','renders')
                           and PurePosixPath(name).parts[1] in chosen)}
        observed = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != manifest_path}
        # Accept either the exact reduced transport or the original complete inventory.
        # Only selected evidence is consumed/protected when paper_ids is explicit.
        _require(observed == set(outputs) or (paper_ids is not None and observed == set(manifest['outputs'])),
                 'Manifest file inventory differs')
        protected = {str(manifest_path): hashlib.sha256(raw).hexdigest()}
        for name, sha in outputs.items():
            path = PurePosixPath(name)
            _require(name == path.as_posix() and not path.is_absolute() and not any(x in ('', '.', '..') for x in name.split('/'))
                     and '\\' not in name and ':' not in name and SHA256.fullmatch(str(sha)), 'Unsafe manifest entry')
            source = (root / name).resolve(strict=True)
            _require(source.is_relative_to(root) and _digest(source) == sha, 'Manifest source differs: ' + name)
            protected[str(source)] = sha
        return _load_run(root, None, protected, paper_ids=paper_ids, pdf_directory=pdf_directory)
    _require(paper_ids is None and pdf_directory is None, 'Selection requires a per-file parser manifest')
    archive_path = root.with_name(root.name + '.zip')
    sidecar = archive_path.with_suffix('.zip.sha256')
    archive_hash = _digest(archive_path)
    raw_sidecar = sidecar.read_bytes()
    try:
        fields = raw_sidecar.decode('ascii').strip().split(maxsplit=1)
    except UnicodeError as error:
        raise ValueError('Invalid parser archive SHA256 sidecar') from error
    _require(len(fields) == 2 and SHA256.fullmatch(fields[0]) and fields[1] == archive_path.name,
             'Invalid parser archive SHA256 sidecar')
    _require(archive_hash == fields[0], 'Archive SHA256 mismatch')
    protected = {str(archive_path): archive_hash, str(sidecar): hashlib.sha256(raw_sidecar).hexdigest()}
    try:
        with zipfile.ZipFile(archive_path, 'r') as archived:
            names = archived.namelist()
            _require(len(names) == len(set(names)), 'Duplicate archive member')
            for info in archived.infolist():
                name = info.filename
                path = PurePosixPath(name)
                _require(name and not path.is_absolute() and name == path.as_posix()
                         and not any(part in ('', '.', '..') for part in name.split('/'))
                         and '\\' not in name and ':' not in name and not info.is_dir()
                         and not stat.S_ISLNK(info.external_attr >> 16), 'Unsafe archive member: ' + name)
            return _load_run(root, archived, protected)
    except zipfile.BadZipFile as error:
        raise ValueError('Invalid parser archive ZIP') from error


def _load_run(root, archived, protected, *, paper_ids=None, pdf_directory=None):
    all_sources = dict(protected)
    archive_hashes = {}

    def asset(relative, sources):
        path = (root / relative).resolve(strict=True)
        _require(path.is_relative_to(root) and path.is_file(), 'Parser source escapes run directory: ' + str(relative))
        observed = _digest(path)
        member = Path(relative).as_posix()
        if archived is not None:
            try:
                info = archived.getinfo(member)
            except KeyError as error:
                raise ValueError('Required parser source missing from archive: ' + member) from error
            _require(info.file_size == path.stat().st_size, 'Archived source differs: ' + member)
            if member not in archive_hashes:
                hashed = hashlib.sha256()
                with archived.open(info) as stream:
                    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                        hashed.update(block)
                archive_hashes[member] = hashed.hexdigest()
            _require(observed == archive_hashes[member], 'Archived source differs: ' + member)
        else:
            _require(str(path) in protected and observed == protected[str(path)], 'Manifest source differs: ' + member)
        _require(str(path) not in all_sources or all_sources[str(path)] == observed,
                 'Parser source changed while reading: ' + str(path))
        sources[str(path)] = observed
        all_sources[str(path)] = observed
        return path

    def load(relative, sources):
        path = asset(relative, sources)
        try:
            raw = path.read_bytes()
            _require(hashlib.sha256(raw).hexdigest() == sources[str(path)], 'Parser source changed: ' + str(path))
            return json.loads(raw, object_pairs_hook=_unique_object), path
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError('Invalid parser JSON: ' + str(path)) from error

    common = dict(protected)
    papers, _ = load('inputs.json', common)
    if archived is None:
        load('configuration.json', common)
    status, _ = load('status.json', common)
    _require(isinstance(status, dict) and status.get('status') == 'completed' and not status.get('error'),
             'Only completed parser attempts can be reconciled')
    for name in ('runtime_fingerprint', 'package_fingerprint'):
        _require(SHA256.fullmatch(str(status.get(name, ''))), 'Missing parser ' + name)
    env_hash = status.get('env_manifest_sha256')
    _require(env_hash is None or SHA256.fullmatch(str(env_hash)), 'Invalid parser environment manifest hash')
    configuration = dict(adapter=VERSION, runtime_fingerprint=status['runtime_fingerprint'],
                         package_fingerprint=status['package_fingerprint'], env_manifest_sha256=env_hash,
                         engine_names=list(ENGINES), models_executed_by_integration=False)
    _require(isinstance(papers, list) and papers, 'Parser inputs must contain at least one paper')
    ids, hashes, expected = set(), set(), set()
    for paper in papers:
        _require(isinstance(paper, dict), 'Malformed paper input')
        pid, sha = paper.get('id'), paper.get('sha256')
        _require(isinstance(pid, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,255}', pid), 'Unsafe paper id')
        _require(pid.casefold() not in ids and SHA256.fullmatch(str(sha)) and sha not in hashes,
                 'Duplicate/invalid paper identity')
        _require(type(paper.get('page_count')) is int and paper['page_count'] > 0, 'Invalid page count')
        _require(isinstance(paper.get('path'), str) and paper['path'], 'Missing source PDF path')
        ids.add(pid.casefold()); hashes.add(sha)
        expected.update((pid, page, engine) for page in range(1, paper['page_count'] + 1) for engine in ENGINES)
    tuples = status.get('tuples')
    _require(isinstance(tuples, list), 'Parser tuples required')
    actual = {}
    for item in tuples:
        _require(isinstance(item, dict) and type(item.get('page')) is int, 'Malformed parser tuple')
        key = (item.get('paper_id'), item['page'], item.get('model'))
        _require(all(isinstance(x, (str, int)) for x in key) and key in expected and key not in actual,
                 'Duplicate or out-of-scope parser tuple')
        _require(item.get('status') == 'completed' and isinstance(item.get('result'), dict)
                 and item['result'].get('status') == 'completed' and item['result'].get('model') == key[2],
                 'Incomplete parser tuple')
        actual[key] = item
    _require(set(actual) == expected, 'Missing page/engine tuples')
    if paper_ids is not None:
        _require({pid.casefold() for pid in paper_ids} <= ids, 'Unknown selected paper identity')
        papers = [p for p in papers if p['id'] in set(paper_ids)]
    documents = []
    for paper in papers:
        pid, sha = paper['id'], paper['sha256']
        sources = dict(common)
        pdf = ((Path(pdf_directory)/PureWindowsPath(paper['path']).name).resolve(strict=True)
               if pdf_directory is not None else Path(paper['path']).expanduser().resolve(strict=True))
        if pdf_directory is not None:
            _require(pdf.is_relative_to(Path(pdf_directory).resolve()), 'PDF escapes download directory')
        _require(pdf.is_file() and pdf.suffix.lower() == '.pdf' and _digest(pdf) == sha, 'Source PDF identity mismatch')
        with pdf.open('rb') as stream:
            _require(b'%PDF-' in stream.read(1024), 'Invalid source PDF header')
        sources[str(pdf)] = sha; all_sources[str(pdf)] = sha
        pages = []
        for number in range(1, paper['page_count'] + 1):
            prefix = Path('renders') / pid / str(number)
            identity, _ = load(prefix / 'identity.json', sources)
            render = asset(prefix / 'render.png', sources) if archived is not None else None
            _identity(identity, sha, number, render)
            if render is not None:
                _require(sources[str(render)] == identity['render_sha256'], 'Render SHA256 differs from page identity')
            data, provenance = {}, {}
            for engine in ENGINES:
                branch = Path('results') / pid / str(number) / engine
                saved_identity, _ = load(branch / 'identity.json', sources)
                _require(saved_identity == identity and actual[(pid, number, engine)]['result'].get('identity') == identity,
                         'Engine result identity differs from shared render')
                data[engine], path = load(branch / ('middle-native.json' if engine == 'mineru' else 'regions.json'), sources)
                provenance[engine] = dict(path=str(path), sha256=sources[str(path)])
                for name in ('detector.json', 'regions-raw.json', 'model-native.json'):
                    if (root / branch / name).exists(): asset(branch / name, sources)
            derived, _ = load(Path('results') / pid / str(number) / 'mineru/regions.json', sources)
            try:
                page = canonical_page(identity, data['mineru'], data['layoutlmv3'], data['table_transformer'], derived,
                                      {engine: 'completed' for engine in ENGINES}, provenance, render)
            except (KeyError, TypeError, AttributeError) as error:
                raise ValueError('Malformed native parser format for ' + pid + ' page ' + str(number)) from error
            if render is None:
                page['render_path'] = None
                page['render_source'] = dict(pdf=str(pdf), physical_page=number, identity=identity)
            pages.append(page)
        documents.append(dict(id=pid, paper_id=pid, document=str(pdf), document_sha256=sha,
                              document_source=dict(original_path=paper['path'], resolved_path=str(pdf), sha256=sha),
                              pages=pages, source_inputs=sources, parser_configuration=dict(configuration)))
    _require(all(_digest(path) == sha for path, sha in all_sources.items()), 'Parser inputs changed during adaptation')
    return dict(adapter=VERSION, source_run=str(root), documents=documents,
                source_inputs=all_sources, parser_configuration=configuration)
