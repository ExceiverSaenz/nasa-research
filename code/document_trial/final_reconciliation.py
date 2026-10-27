"""Compose recorded human decisions. No detection, candidate generation or repair."""
import copy
import html
import json
from pathlib import Path
from .explicit_association import digest, encoded

BASE = Path('analytics/results/sic12_document')
EVAL = BASE/'evaluation-v1-20261025'
HUMAN = BASE/'multipanel-candidates-v1-human-review/human-review.json'
EXPLICIT = BASE/'fig6-explicit-association-v1'
EXPECTED = {(5, 'Fig. 6'), (6, 'Fig. 7'), (10, 'Fig. 17'),
            (10, 'Fig. 18'), (11, 'Fig. 19'), (11, 'Fig. 20')}


def read_json(path):
    return json.loads(Path(path).read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pointer(value, path):
    try:
        for key in path.strip('/').split('/'):
            value = value[int(key)] if isinstance(value, list) else value[key]
        return value
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError('Unresolvable pointer: '+path) from exc


def protected_hashes(root):
    root = Path(root).resolve()
    folders = ['evaluation-v1-20261025', 'fig6-explicit-association-v1',
               'fig6-explicit-association-v1-visual-review', 'multipanel-candidates-v1',
               'multipanel-candidates-v1-human-review', 'multipanel-candidates-v1-visual-review',
               'multipanel-candidates-v1-negative-controls']
    return {p.relative_to(root).as_posix(): digest(p.read_bytes())
            for folder in folders for p in sorted((root/BASE/folder).rglob('*')) if p.is_file()}


def build(root):
    root = Path(root).resolve()
    inputs = {}

    def load(relative, expected=None):
        path = (root/relative).resolve()
        require(path.is_relative_to(root), 'Source outside workspace')
        sha = digest(path.read_bytes())
        require(expected is None or sha == expected, 'Source SHA256 mismatch: '+str(relative))
        inputs[path.relative_to(root).as_posix()] = sha
        return read_json(path)

    evaluation_manifest = load(EVAL/'evaluation-manifest.json')
    pages, native_pages, page_records = {}, {}, []
    document_key = None
    for page in range(1, 14):
        folder = EVAL/f'page-{page:04d}'
        def baseline_file(name):
            expected = evaluation_manifest['outputs'][f'page-{page:04d}/{name}']
            return load(folder/name, expected)
        r = baseline_file('R-reconciled.json')
        manifest = baseline_file('source-manifest.json')
        native = baseline_file('M0-native.json')
        if page == 3:
            baseline_file('historical-table2-acceptance.json')
        identity = r['identity']
        require(identity == manifest['identity'] and identity['physical_page'] == page,
                'Baseline identity mismatch')
        key = (identity['document_sha256'], identity['execution_id'])
        document_key = document_key or key
        require(key == document_key, 'Document/execution mismatch')
        # M0 is reserialized locally: its byte hash belongs to the evaluation
        # manifest, not the original archive member in source-manifest.json.
        render = root/folder/'render.png'
        require(digest(render.read_bytes()) == identity['render_sha256'], 'Render mismatch')
        inputs[(folder/'render.png').as_posix()] = identity['render_sha256']
        pages[page], native_pages[page] = r, native
        page_records.append(dict(page=page, baseline=(folder/'R-reconciled.json').as_posix(),
            identity=copy.deepcopy(identity), segments_pointer='/segments',
            containers_pointer='/containers', relations_pointer='/relations',
            object_links_pointer='/object_links', evidence_pointer='/evidence',
            external_evidence=[dict(id=x['id'], model=x['model'], status=x['status']) for x in r['evidence']],
            localized_enrichment=copy.deepcopy(r.get('localized_enrichment')),
            transcription_status='not_validated', reading_order_status='not_validated'))

    human = load(HUMAN)
    require(human.get('reviewer') == 'user' and human.get('authorization_evidence'), 'Missing human authority')
    load(Path(human['review_source'].replace('\\', '/')), human['review_sha256'])
    explicit_manifest = load(EXPLICIT/'manifest.json')
    explicit = load(EXPLICIT/'group.json', explicit_manifest['outputs']['group.json'])
    require(explicit['identity'] == pages[5]['identity'], 'Explicit identity mismatch')
    require(explicit_manifest['baseline']['sha256'] == inputs[(EVAL/'page-0005/R-reconciled.json').as_posix()],
            'Explicit baseline mismatch')
    groups, controls, seen, candidates_index = [], [], set(), {}
    for index, case in enumerate(human['cases']):
        page = case['page']
        require(page in pages, 'Invalid human page')
        source = Path(case['source'].replace('\\', '/'))
        require(source == BASE/'multipanel-candidates-v1'/f'page-{page:04d}.json', 'Unexpected candidate source')
        candidate_page = load(source, case['source_sha256'])
        require(candidate_page['identity'] == pages[page]['identity'], 'Candidate identity mismatch')
        provenance = candidate_page['provenance']
        folder = EVAL/f'page-{page:04d}'
        require(provenance['baseline_sha256'] == inputs[(folder/'R-reconciled.json').as_posix()]
                and provenance['source_manifest_sha256'] == inputs[(folder/'source-manifest.json').as_posix()],
                'Candidate baseline/manifest mismatch')
        candidate_index = case['candidate_index']
        require(isinstance(candidate_index, int) and 0 <= candidate_index < len(candidate_page['candidates']),
                'Invalid candidate index')
        candidate = candidate_page['candidates'][candidate_index]
        require(candidate['members'] == case['members'] and candidate['captions'] == case['captions'],
                'Human composition differs from candidate')
        require(len(candidate['captions']) == 1 and candidate['captions'][0]['literal'] == case['figure'],
                'Caption identity mismatch')
        key = (page, case['figure'])
        require(key not in seen, 'Duplicate human case')
        seen.add(key)
        segments = {s['id']: s for s in pages[page]['segments']}
        for role, refs in [('figure', candidate['members']), ('caption', candidate['captions'])]:
            for ref in refs:
                segment = segments.get(ref['id'])
                require(segment is not None and segment['type'] == role, 'Missing reference or wrong role')
                require(all(segment[k] == ref[k] for k in ('id', 'local_id', 'source_pointer')), 'Reference mismatch')
                prefix = document_key[0]+':'+document_key[1]+':p'+str(page)+':'
                require(ref['id'] == prefix+ref['local_id'], 'Foreign segment identity')
                require(pointer(native_pages[page], ref['source_pointer']) == segment['native_content'],
                        'Native pointer content mismatch')
        evidence_ids = {x['id'] for x in pages[page]['evidence']}
        require(all(x in evidence_ids for x in candidate['anchors']+
                    candidate['captions'][0]['lm_text_support']), 'External reference missing')
        acceptance = dict(source=HUMAN.as_posix(), pointer=f'/cases/{index}',
                          sha256=inputs[HUMAN.as_posix()], decision=case['decision'], reviewer='user')
        record = dict(id=f'{document_key[0]}:p{page}:{case["figure"].replace(" ", "").lower()}',
            page=page, figure=case['figure'], candidate=copy.deepcopy(candidate),
            acceptance_provenance=[acceptance], relation_status=case['decision'],
            geometry_status=case['geometry_status'], transcription_status='not_validated',
            reading_order_status='not_validated')
        if case['decision'] == 'human_validated_composition':
            require(key in EXPECTED and len(candidate['members']) >= 2, 'Unexpected accepted group')
            if key == (5, 'Fig. 6'):
                def refs(values):
                    return sorted((v['id'], v['local_id'], v['source_pointer']) for v in values)
                require(refs(explicit['panels']) == refs(candidate['members']) and
                        refs([explicit['caption']]) == refs(candidate['captions']), 'Conflicting explicit Fig6')
                record['acceptance_provenance'].append(dict(source=(EXPLICIT/'group.json').as_posix(),
                    sha256=inputs[(EXPLICIT/'group.json').as_posix()], role='equivalent_explicit_declaration_not_human_authority'))
            groups.append(record)
        else:
            require(key == (5, 'Fig. 5') and case['decision'] == 'human_validated_simple_figure_control'
                    and len(candidate['members']) == 1, 'Unapproved human decision')
            controls.append(record)
        candidates_index[source.as_posix()] = dict(source=source.as_posix(),
            sha256=inputs[source.as_posix()], candidates=[dict(index=i, status=c['status'],
                original_accepted=c['accepted']) for i, c in enumerate(candidate_page['candidates'])])
    require({(g['page'], g['figure']) for g in groups} == EXPECTED and len(controls) == 1,
            'Incomplete human review scope')
    p4 = Path('analytics/analyses/paper/sic12-p4-review.md')
    inputs[p4.as_posix()] = digest((root/p4).read_bytes())
    warnings = [
        ('fig6_overlap', [5], 'Paneles Fig6 solapados; corrección geométrica pendiente.'),
        ('missing_labels', [3, 6], 'Table1 y Table4: rótulo no localizado; vínculo no aceptado.'),
        ('table_edges', [3, 4, 6], 'Bordes p3 con cortes/indeterminación; evidencia fina p4/p6 insuficiente.'),
        ('mixed_lm', [3], 'Cajas mixtas LM; r12 puede ser continuación entre columnas.'),
        ('tatr_discordance', [11], 'Candidato TATR sobre texto; no promover a tabla aceptada.'),
        ('transcription', [2, 3, 7], 'Variantes/errores documentados; exactitud científica no validada.'),
        ('reading_order', list(range(1, 14)), 'Orden global de lectura no validado.')]
    return dict(schema_version='document-human-reconciliation/1', status='relational_delivery_with_limits',
        parsers=['mineru', 'table_transformer', 'layoutlmv3'], pages=page_records,
        accepted_groups=sorted(groups, key=lambda g: (g['page'], g['figure'])), simple_controls=controls,
        candidate_sources=list(candidates_index.values()),
        warnings=[dict(id=i, pages=p, description=d, source=p4.as_posix()) for i, p, d in warnings],
        automatic_acceptance=False, source_inputs=dict(sorted(inputs.items())))


def review_html(root, document):
    sections = []
    for group in document['accepted_groups']:
        page = group['page']
        folder = root/EVAL/f'page-{page:04d}'
        baseline = read_json(folder/'R-reconciled.json')
        segments = {x['id']: x for x in baseline['segments']}
        rects = []
        for refs, color in [(group['candidate']['members'], '#00a75a'),
                            (group['candidate']['captions'], '#d00084')]:
            for ref in refs:
                x0,y0,x1,y1 = segments[ref['id']]['bbox']
                rects.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="none" stroke="{color}" stroke-width="4"/>')
        identity = baseline['identity']
        sections.append(f'<section><h2>{html.escape(group["figure"])} · página {page}</h2>'
            f'<p>Vínculo: validado por usuario. Geometría: {html.escape(group["geometry_status"])}.</p>'
            '<p>Verde: paneles nativos. Rosa: caption. Texto y lectura sin validar.</p>'
            f'<svg viewBox="0 0 {identity["width_px"]} {identity["height_px"]}">'
            f'<image href="{html.escape((folder/"render.png").as_uri(), quote=True)}" width="{identity["width_px"]}" height="{identity["height_px"]}"/>'
            + ''.join(rects)+'</svg><p>'+html.escape(group['candidate']['captions'][0]['native_text'])+'</p></section>')
    notices = ''.join('<li>'+html.escape(w['description'])+'</li>' for w in document['warnings'])
    pages = ''.join(f'<li><a href="{(root/EVAL/f"page-{p:04d}"/"review.html").as_uri()}">Página {p}: baseline y alternativas</a></li>' for p in range(1,14))
    return ('<!doctype html><html lang="es"><meta charset="utf-8"><title>12.pdf — reconciliación relacional</title>'
        '<style>body{font:16px system-ui;margin:24px;max-width:1100px}section{border-top:1px solid #aaa;margin-top:30px}svg{width:100%;max-width:660px;background:#fff}li{margin:8px 0}</style>'
        '<h1>12.pdf — seis composiciones aceptadas</h1><p>Entrega relacional con límites. MinerU, TATR y LayoutLMv3 conservados mediante referencias a los trece baselines.</p>'
        '<p>Fig5 permanece simple. Fig6 conserva su solapamiento pendiente. Ninguna caja ha sido corregida.</p>'
        '<h2>Advertencias</h2><ul>'+notices+'</ul>'+''.join(sections)+'<h2>Documento y evidencia original</h2><ul>'+pages+'</ul></html>').encode('utf-8')


def export(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    protected_folders = [root/BASE/x for x in ('evaluation-v1-20261025', 'multipanel-candidates-v1',
        'multipanel-candidates-v1-human-review', 'fig6-explicit-association-v1',
        'multipanel-candidates-v1-visual-review', 'fig6-explicit-association-v1-visual-review',
        'multipanel-candidates-v1-negative-controls')]
    require(not any(destination == p or destination.is_relative_to(p) for p in protected_folders), 'Protected destination')
    before = protected_hashes(root)
    document = build(root)
    files = {'document.json': encoded(document), 'review.html': review_html(root, document),
             'protected-before.json': encoded(before)}
    files['manifest.json'] = encoded(dict(schema_version='final-reconciliation-manifest/1',
        source_inputs=document['source_inputs'], outputs={n:digest(v) for n,v in files.items()}))
    require(before == protected_hashes(root), 'Protected sources changed during composition')
    if destination.exists():
        require({p.name for p in destination.iterdir()} == set(files) and
                all((destination/n).read_bytes() == v for n,v in files.items()), 'Incompatible output destination')
        return document
    destination.mkdir(parents=True)
    for name, raw in files.items():
        with (destination/name).open('xb') as stream:
            stream.write(raw)
    return document
