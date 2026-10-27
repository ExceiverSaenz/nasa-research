"""Offline presentation of immutable segmentation; no reconciliation decisions."""
import base64
import copy
import json
from pathlib import Path
from .explicit_association import digest, encoded
from .final_reconciliation import protected_hashes as earlier_hashes

BASE = Path('analytics/results/sic12_document')
EVAL = BASE/'evaluation-v1-20261025'
FINAL = BASE/'final-reconciliation-v1'


def read_json(path):
    return json.loads(Path(path).read_bytes())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def resolve(value, pointer):
    try:
        for token in pointer.strip('/').split('/'):
            value = value[int(token)] if isinstance(value, list) else value[token]
        return value
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise ValueError('Unresolvable native pointer') from exc


def native_text(node):
    if isinstance(node, list):
        return ' '.join(t for t in (native_text(n) for n in node) if t)
    if not isinstance(node, dict):
        return ''
    content = node.get('content')
    if isinstance(content, str):
        return content if node.get('type') not in ('image', 'image_body', 'chart_body') else ''
    return native_text(content)


def protected_hashes(root):
    root = Path(root).resolve()
    values = earlier_hashes(root)
    for name in ['final-reconciliation-v1', 'reconciliation-comparison-v1']:
        for path in sorted((root/BASE/name).rglob('*')):
            if path.is_file():
                values[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    return values


def build(root):
    root = Path(root).resolve()
    sources = {}

    def load(relative, expected=None):
        raw = (root/relative).read_bytes()
        sha = digest(raw)
        require(expected is None or sha == expected, 'Source hash mismatch: '+str(relative))
        sources[relative.as_posix()] = sha
        return read_json(root/relative)

    final_manifest = load(FINAL/'manifest.json')
    final = load(FINAL/'document.json', final_manifest['outputs']['document.json'])
    for path, sha in final_manifest['source_inputs'].items():
        require(digest((root/path).read_bytes()) == sha, 'Final source changed: '+path)
    evaluation = load(EVAL/'evaluation-manifest.json')
    pages = []
    for number in range(1, 14):
        folder = EVAL/f'page-{number:04d}'
        def baseline(name):
            return load(folder/name, evaluation['outputs'][f'page-{number:04d}/{name}'])
        result = baseline('R-reconciled.json')
        native = baseline('M0-native.json')
        manifest = baseline('source-manifest.json')
        identity = result['identity']
        require(identity['physical_page'] == number and identity == manifest['identity']
                and identity == final['pages'][number-1]['identity'], 'Identity mismatch')
        raw_image = (root/folder/'render.png').read_bytes()
        require(digest(raw_image) == identity['render_sha256'], 'Render hash mismatch')
        sources[(folder/'render.png').as_posix()] = identity['render_sha256']
        segments = []
        for layer, values in [('segment', result['segments']), ('container', result['containers'])]:
            for index, item in enumerate(values):
                node = resolve(native, item['source_pointer'])
                require(node == item['native_content'], 'Native content mismatch')
                segments.append(dict(id=item['id'], local_id=item['local_id'], type=item['type'],
                    bbox=copy.deepcopy(item['bbox']), layer=layer, text=native_text(node),
                    level=node.get('level'), source=(folder/'M0-native.json').as_posix(),
                    pointer=item['source_pointer'], native_type=node['type'],
                    source_data=copy.deepcopy(node), native_status=item['status']))
        alternatives = {}
        for model, key in [('table_transformer', 'tatr'), ('layoutlmv3', 'lm')]:
            alternatives[key] = []
            for index, item in enumerate(result['evidence']):
                if item['model'] != model:
                    continue
                record = item['native_record']
                alternatives[key].append(dict(id=item['id'],
                    local_id=str(record.get('region_id', 'q'+str(record.get('query_id', index)))),
                    type=record.get('type', record.get('native_label', 'unknown')),
                    bbox=copy.deepcopy(record['bbox']), layer='external', text='',
                    level=None, source=(folder/'R-reconciled.json').as_posix(),
                    pointer=f'/evidence/{index}/native_record', source_data=copy.deepcopy(record),
                    native_status=item['status']))
        groups = []
        for index, group in enumerate(final['accepted_groups']):
            if group['page'] == number:
                groups.append(dict(id=group['id'], figure=group['figure'],
                    members=[x['id'] for x in group['candidate']['members']],
                    caption=group['candidate']['captions'][0]['id'],
                    geometry_status=group['geometry_status'], source=(FINAL/'document.json').as_posix(),
                    pointer=f'/accepted_groups/{index}', acceptance=group['acceptance_provenance'][0]))
        historical = []
        enrichment = result.get('localized_enrichment') or {}
        for i, accepted in enumerate(enrichment.get('accepted_components', [])):
            for j, candidate in enumerate(accepted['proposal']['candidates']):
                historical.append(dict(id=f'p{number}-historical-table2-{i}-{j}',
                    local_id='Table2 histórica', type='caption', layer='historical',
                    bbox=copy.deepcopy(candidate['bbox']), text=candidate['text'], level=None,
                    source=(folder/'R-reconciled.json').as_posix(),
                    pointer=f'/localized_enrichment/accepted_components/{i}/proposal/candidates/{j}',
                    source_data=copy.deepcopy(candidate), native_status='historical_agent_visual_acceptance'))
        pages.append(dict(number=number, identity=copy.deepcopy(identity), baseline=(folder/'R-reconciled.json').as_posix(),
            image='data:image/png;base64,'+base64.b64encode(raw_image).decode('ascii'),
            views=dict(reconciled=segments, mineru=copy.deepcopy(segments), **alternatives),
            outline=[copy.deepcopy(x) for x in segments if x['layer']=='segment' and x['type'] in ('title','doc_title','paragraph_title')],
            groups=groups, historical=historical,
            paragraph_section_membership_validated=False,
            warnings=[copy.deepcopy(w) for w in final['warnings'] if number in w['pages']]))
    return dict(schema_version='full-paper-comparison-view/1', pages=pages, sources=dict(sorted(sources.items())),
                note='Presentation only. Native title levels; no inferred paragraph-to-section membership.')


def safe_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


HTML = '''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>12.pdf · Comparación de segmentación</title><link rel="stylesheet" href="comparison_view.css"></head>
<body><header><div class="brand"><b>12.pdf</b><span>Comparación de segmentación</span></div>
<nav aria-label="Página"><button id="prev" aria-label="Página anterior">←</button><select id="page" aria-label="Página"></select><button id="next" aria-label="Página siguiente">→</button></nav>
<div class="zoom"><label for="zoom">Zoom</label><input id="zoom" type="range" min="100" max="250" step="25" value="100"><output id="zoomValue">100%</output></div>
<button id="all">Ver las cuatro</button></header>
<div class="workspace"><aside><section><h2>Vistas</h2><div id="viewOptions"></div></section>
<section><h2>Capas</h2><label><input id="boxes" type="checkbox" checked>Regiones</label><label><input id="labels" type="checkbox">Identificadores</label><label><input id="containers" type="checkbox">Contenedores nativos</label><label><input id="groups" type="checkbox" checked>Vínculos aceptados</label><label><input id="historical" type="checkbox" checked>Recuperación histórica</label><label><input id="alternatives" type="checkbox">Alternativas en conciliada</label><div id="types" class="typeOptions"></div></section>
<section><h2>Títulos y subsecciones</h2><p class="hint">Niveles nativos de MinerU. Pertenencia de párrafos y orden de lectura sin validar.</p><div id="outline"></div></section>
<section><h2>Grupos aceptados</h2><div id="groupList"></div></section>
<details><summary>Advertencias de página</summary><ul id="warnings"></ul></details></aside>
<main><div id="summary" class="summary" aria-live="polite"></div><div id="panes" class="panes"></div>
<section class="inspector" aria-live="polite"><div class="inspectorHead"><h2 id="detailTitle">Selecciona una región</h2><button id="clear">Limpiar selección</button></div><div id="detail"><p class="hint">Pulsa una caja, un título o un grupo para ver su texto, origen y estado.</p></div></section>
<footer>Solo visualización de salidas existentes · Texto nativo, sin nueva validación OCR · TATR localiza tablas; no produce segmentación de texto ni figuras.</footer></main></div>
<script id="view-data" type="application/json">__DATA__</script><script src="comparison_view.js"></script></body></html>'''


def export(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    existing = [root/BASE/name for name in ['evaluation-v1-20261025', 'final-reconciliation-v1',
        'reconciliation-comparison-v1', 'multipanel-candidates-v1', 'multipanel-candidates-v1-human-review',
        'multipanel-candidates-v1-negative-controls', 'multipanel-candidates-v1-visual-review',
        'fig6-explicit-association-v1', 'fig6-explicit-association-v1-visual-review']]
    require(not any(destination == p or destination.is_relative_to(p) for p in existing), 'Protected destination')
    before = protected_hashes(root)
    data = build(root)
    folder = Path(__file__).parent
    files = {'index.html': HTML.replace('__DATA__', safe_json(data)).encode('utf-8'),
             'data.json': encoded(data), 'protected-before.json': encoded(before)}
    for name in ['comparison_view.js', 'comparison_view.css']:
        files[name] = (folder/name).read_bytes()
    files['manifest.json'] = encoded(dict(schema_version='comparison-view-manifest/1',
        inputs=data['sources'], code={p.name:digest(p.read_bytes()) for p in [Path(__file__), folder/'comparison_view.js', folder/'comparison_view.css']},
        outputs={n:digest(raw) for n,raw in files.items()}))
    require(before == protected_hashes(root), 'Sources changed')
    if destination.exists():
        require({x.name for x in destination.iterdir()} == set(files) and
                all((destination/n).read_bytes() == raw for n,raw in files.items()), 'Incompatible destination')
        return data
    destination.mkdir(parents=True)
    for name, raw in files.items():
        with (destination/name).open('xb') as stream:
            stream.write(raw)
    return data
