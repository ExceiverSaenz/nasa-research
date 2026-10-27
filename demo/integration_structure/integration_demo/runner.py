"""User-run stage controller. Scientific modules are imported only inside stages."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import traceback
import uuid

from .common import digest, read_json, write_json, make_archive

STAGES = ('prepare', 'reconcile', 'classify', 'capsules', 'integrate', 'verify')


def now():
    return datetime.now(timezone.utc).isoformat()


def replace_json(path, data):
    path = Path(path)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    write_json(temp, data)
    os.replace(temp, path)


def execute_stage(state, name, action):
    state = Path(state)
    receipt = state / 'stages' / (name + '.json')
    start = dict(stage=name, status='running', started_utc=now(), automatic_retries=False)
    write_json(receipt, start)  # Exclusive: a started stage is never silently repeated.
    replace_json(state / 'status.json', dict(status='running', active_stage=name))
    print(f'START {name}', flush=True)
    try:
        result = action()
        replace_json(receipt, dict(start, status='completed', ended_utc=now(), result=result))
        print(f'DONE {name}', flush=True)
        return result
    except BaseException:
        error = traceback.format_exc()
        replace_json(receipt, dict(start, status='failed', ended_utc=now(), error=error))
        replace_json(state / 'status.json', dict(status='failed', failed_stage=name, error=error,
                     outputs_may_be_partial=True, automatic_retries=False))
        print(error, file=sys.stderr, flush=True)
        raise


def initialize(payload, state, hardware):
    payload, state = Path(payload).resolve(), Path(state).resolve()
    if state.exists():
        raise FileExistsError(state)
    if platform.system() != 'Linux' or len(hardware) != 1 or 'A100' not in hardware[0]:
        raise ValueError('Linux with one A100 required')
    spec = read_json(payload / 'package-spec.json')
    state.mkdir(parents=True, exist_ok=False)
    shutil.copytree(payload / 'code', state / 'source-code')
    shutil.copytree(payload / 'pdfs', state / 'pdfs')
    for name in ('package-spec.json', 'bundle-manifest.json', 'requirements-runtime.lock', 'requirements-docling.txt'):
        shutil.copyfile(payload / name, state / name)
    write_json(state / 'execution-profile.json', dict(
        schema='integration-structure-execution/1', attempt_id=uuid.uuid4().hex,
        initiated_utc=now(), initiator='human_jupyter', hardware_report=hardware,
        python_required='3.13.5', actual_compute='CPU geometric/rule-based integration',
        input_payload=str(payload), native_archive_sha256=spec['native_archive']['sha256'],
        expected=spec['expected'], automatic_retries=False, models_executed=False,
        OCR_executed=False, cache_policy='recompute_all_no_historical_caches',
        comparison='new execution; not byte-identical reproduction of historical cached run',
        semantic_validation='pending_after_full_mvp', visual_QA=False))
    write_json(state / 'status.json', dict(status='prepared', next_stage=STAGES[0]))
    return state


def stage_action(state, name):
    profile = read_json(state / 'execution-profile.json')
    payload = Path(profile['input_payload'])
    if name == 'prepare':
        from reconciliation.consolidated_inputs import prepare
        spec = read_json(state / 'package-spec.json')
        archive = payload / spec['native_archive']['path']
        if digest(archive) != spec['native_archive']['sha256']:
            raise ValueError('Native archive differs from package')
        result = prepare(archive, state / 'prepared')
        if len(result['documents']) != profile['expected']['papers'] or result['physical_pages'] != profile['expected']['pages']:
            raise ValueError('Prepared collection scope mismatch')
        return dict(papers=len(result['documents']), pages=result['physical_pages'],
                    records_by_parser=result['records_by_parser'])
    if name == 'reconcile':
        from .reconcile_collection import export_collection
        result = export_collection(state / 'prepared', state / 'pdfs', state / 'reconciliation')
        return {k: v for k, v in result.items() if k != 'documents'}
    if name == 'classify':
        from functional_classification.export_reconciled import export_collection
        result = export_collection(state / 'reconciliation', state / 'classification-v2')
        return {k: result[k] for k in ('papers', 'pages', 'classified_regions', 'logical_groups')}
    if name == 'capsules':
        from reading_order.export import export_collection
        result = export_collection(state / 'classification-v2', state / 'capsules-reading-v1')
        return dict(papers=result['papers'], pages=result['pages'],
                    role='intermediate inventory/capsules contract; operational baseline is Docling')
    if name == 'integrate':
        from document_pipeline.pipeline import export_collection
        result = export_collection(state / 'capsules-reading-v1', state / 'operational')
        return {k: result[k] for k in ('papers', 'pages', 'inventory_units', 'content_appearances',
                                      'deferred_children', 'abstained_pages', 'sections', 'semantic_accuracy')}
    if name == 'verify':
        return verify_run(state)
    raise ValueError('Unknown stage')


def verify_run(state):
    """Check newly generated outputs and frozen source copies, without re-exporting."""
    state = Path(state).resolve()
    spec = read_json(state / 'package-spec.json')
    expected = spec['expected']
    protected_count = output_count = 0
    for folder in ('reconciliation', 'classification-v2', 'capsules-reading-v1', 'operational'):
        root = state / folder
        manifest = read_json(root / 'manifest.json')
        for rel, h in manifest['outputs'].items():
            path = (root / rel).resolve()
            if not path.is_relative_to(root) or digest(path) != h:
                raise ValueError('Output manifest mismatch: ' + str(path))
            output_count += 1
        for path, h in manifest.get('protected_inputs', {}).items():
            if not Path(path).resolve().is_relative_to(state) or digest(path) != h:
                raise ValueError('Protected source mismatch: ' + path)
            protected_count += 1
    bundle_manifest = read_json(state / 'bundle-manifest.json')
    for rel, meta in bundle_manifest['files'].items():
        if rel.startswith('code/'):
            path = state / 'source-code' / rel.removeprefix('code/')
            if digest(path) != meta['sha256']:
                raise ValueError('Scientific/orchestration source changed: ' + rel)
        elif rel.startswith('pdfs/'):
            if digest(state / rel) != meta['sha256']:
                raise ValueError('PDF changed: ' + rel)
    rec = read_json(state / 'reconciliation/summary.json')
    result = read_json(state / 'operational/summary.json')
    for key in ('papers', 'pages', 'inventory_units', 'content_appearances', 'deferred_children', 'abstained_pages'):
        if result[key] != expected[key]:
            raise ValueError(f'Conservation/scope mismatch: {key}: {result[key]} != {expected[key]}')
    if rec['records'] != expected['parser_records']:
        raise ValueError('Parser evidence record loss')
    # All final data references are checked by canonical validate() during export.
    # Verify views and paper JSON exist and each original PNG is byte-identical.
    for item in result['documents']:
        folder = state / 'operational' / Path(item['data']).parent
        if not (state / 'operational' / item['view']).is_file():
            raise ValueError('Missing paper view')
        view = read_json(folder / 'view/verification.json')
        for rel, h in view['render_copies'].items():
            if digest(folder / 'view' / rel) != h:
                raise ValueError('Render copy changed')
    report = dict(technical_contract='verified', outputs_checked=output_count,
                  protected_references_checked=protected_count, scope=expected,
                  models_executed=False, OCR_executed=False, semantic_accuracy=None,
                  semantic_validation='pending_after_full_mvp', browser_visual_QA=False,
                  final_index='operational/index.html', provenance_paths='absolute paths from execution retained')
    write_json(state / 'verification.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=STAGES + ('archive', 'status'))
    parser.add_argument('state', type=Path)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    state = args.state.resolve()
    if args.stage == 'status':
        print(json.dumps(read_json(state / 'status.json'), ensure_ascii=False, indent=2))
        return
    if args.stage == 'archive':
        if not args.archive:
            parser.error('--archive is required')
        print(json.dumps(make_archive(state, args.archive), ensure_ascii=False, indent=2))
        return
    pos = STAGES.index(args.stage)
    if read_json(state / 'stages/setup.json')['status'] != 'completed' or read_json(state / 'runtime-probe.json')['geometric_probe'] != 'passed':
        raise ValueError('Frozen environment setup/probe required before integration')
    if pos and read_json(state / 'stages' / (STAGES[pos - 1] + '.json'))['status'] != 'completed':
        raise ValueError('Previous stage did not complete')
    if read_json(state / 'status.json')['status'] in ('failed', 'completed', 'partial'):
        raise ValueError('Terminal run; do not relaunch stages')
    result = execute_stage(state, args.stage, lambda: stage_action(state, args.stage))
    if args.stage == 'verify':
        replace_json(state / 'status.json', dict(status='completed', technical_verification=True,
                     semantic_validation='pending_after_full_mvp', visual_QA=False, ended_utc=now()))
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
