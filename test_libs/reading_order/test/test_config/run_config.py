"""Local configuration test controller, executed explicitly from WSL.

Example (existing dedicated session):
python3 -B test_libs/reading_order/test/test_config/run_config.py live \
  --session NAME --prepare --paper 12 --close

Only test code, dependency manifests and a private expiring request are uploaded.
MinerU JSONs and PDF contents are never copied to Colab or output directories.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

from validation import ConfigReport, FunctionCheck, verify_mineru_references, verify_pdf

HERE = Path(__file__).resolve().parent
REMOTE = '/content/order-config-20261102'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    PROJECT = HERE.parents[3]
    SOURCE = PROJECT / 'test_libs/bounding_boxes/raw_results/code/mineru-nativefix-20261101T034122Z/assembled/basic'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'prepare', 'seal', 'live'])
    parser.add_argument('--session')
    parser.add_argument('--colab', default=shutil.which('colab') or str(Path.home() / '.local/bin/colab'),
                        help='Existing Colab CLI executable; never installed or updated by the tests')
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--prepared-run', help='Earlier successful preparation receipt for explicit seal continuation')
    parser.add_argument('--paper', action='append', default=[])
    parser.add_argument('--r2-location', choices=['local', 'remote'], default='local',
                        help='Default reads PDFs only in WSL. Remote requires explicit private-PDF destination authorization.')
    parser.add_argument('--close', action='store_true', help='Close dedicated session after verified receipt recovery')
    args = parser.parse_args(argv)
    sources = verify_mineru_references(SOURCE)
    if args.action == 'inspect':
        print(json.dumps(sources, indent=2))
        return 0
    if sys.platform != 'linux' or not re.fullmatch(r'[a-zA-Z0-9-]+', args.session or ''):
        parser.error('live requires WSL/Linux and an explicit existing dedicated session')
    if args.action == 'live' and (not args.paper or any(not re.fullmatch(r'[0-9]+', p) for p in args.paper) or len(set(args.paper)) != len(args.paper)):
        parser.error('Select unique PDF IDs explicitly with --paper')
    selected = []
    for name in args.paper:
        selected.append(next(row for row in sources['files'] if row['paper'] == name + '.pdf'))
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-config-' + uuid.uuid4().hex[:6]
    output = PROJECT / 'test_libs/reading_order/raw_results/tests_results' / run_id
    output.mkdir(parents=True, exist_ok=False)
    state = {'run_id': run_id, 'session': args.session, 'status': 'prepared', 'session_closed': False,
             'automatic_retries': False, 'mineru_source_check': sources,
             'test_sources': {p.name: sha(p) for p in HERE.iterdir() if p.is_file()}}
    def save():
        (output / 'status.json').write_text(json.dumps(state, indent=2))
    save()

    def command(argv, log_name):
        # Commands never carry credentials or bearer URLs. Upstream CLI output is public test output.
        if argv[0] == 'colab':
            argv = [args.colab, *argv[1:]]
        with (output / log_name).open('a') as log:
            result = subprocess.run(list(map(str, argv)), stdout=log, stderr=subprocess.STDOUT, timeout=2400)
        return result.returncode

    def upload(path, destination):
        if command(['colab', 'upload', '-s', args.session, path, destination], 'transport.log'):
            raise RuntimeError('Test-code upload failed')

    def execute_script(path, log_name, marker):
        code = command(['colab', 'exec', '-s', args.session, '-f', path, '--timeout', '2300'], log_name)
        if code or marker not in (output / log_name).read_text():
            raise RuntimeError('Remote phase did not confirm completion: ' + log_name)

    try:
        # Test code only; private temp files are transport, never a copied dataset.
        with tempfile.TemporaryDirectory(prefix='order-config-') as temp:
            temp = Path(temp)
            initialize = temp / 'initialize.py'
            initialize.write_text("from pathlib import Path\np=Path('" + REMOTE + "')\np.mkdir(exist_ok=True)\nprint('ORDER_CONFIG_DIRECTORY_READY')\n")
            execute_script(initialize, 'initialize.log', 'ORDER_CONFIG_DIRECTORY_READY')
            for name in ('validation.py', 'probe_environment.py', 'test_validation.py', 'sources.json',
                         'requirements.in', 'xy_smoke.rs', 'prepare_environment.py', 'inspect_host.py',
                         'run_config.py', 'environment_identity.py'):
                upload(HERE / name, REMOTE + '/' + name)
            if args.action == 'seal':
                if not re.fullmatch(r'[a-zA-Z0-9-]+', args.prepared_run or ''):
                    raise ValueError('Explicit successful preparation receipt required')
                previous = json.loads((output.parent / args.prepared_run / 'status.json').read_text())
                if previous['status'] != 'environment_prepared_not_tested' or previous['session'] != args.session:
                    raise ValueError('Preparation receipt does not identify this environment')
                expected = previous['test_sources']
                if expected['requirements.in'] != sha(HERE / 'requirements.in') or expected['sources.json'] != sha(HERE / 'sources.json'):
                    raise ValueError('Preparation inputs have changed')
                seal_script = temp / 'seal.py'
                seal_script.write_text("import subprocess\nresult=subprocess.run(['" + REMOTE + "/venv/bin/python','-B','-c',"
                    + repr("import sys; from pathlib import Path; sys.path.insert(0,'" + REMOTE + "'); from environment_identity import seal; seal(Path('" + REMOTE + "'),'" + expected['requirements.in'] + "','" + expected['sources.json'] + "')")
                    + "],capture_output=True,text=True)\nprint(result.stdout)\nprint(result.stderr)\nresult.check_returncode()\nprint('ORDER_CONFIG_SEALED')\n")
                execute_script(seal_script, 'seal.log', 'ORDER_CONFIG_SEALED')
                state.update(status='environment_identity_sealed', prepared_run=args.prepared_run)
                save()
                print(json.dumps({'run_id': run_id, 'status': state['status'], 'output': str(output)}))
                return 0
            if args.prepare or args.action == 'prepare':
                execute_script(HERE / 'prepare_environment.py', 'prepare.log', 'ORDER_CONFIG_PREPARED')
            if args.action == 'prepare':
                state['status'] = 'environment_prepared_not_tested'
                save()
                print(json.dumps({'run_id': run_id, 'status': state['status'], 'output': str(output)}))
                return 0
            # Only an explicit live invocation reads signing settings. Preparation never accesses R2.
            sys.path.insert(0, str(PROJECT / 'new_code'))
            from prepare_papers import read_settings, presign
            settings = read_settings(Path.home() / '.config/nasa-research/r2.env')
            request = temp / 'r2-request.json'
            files = []
            for row in selected:
                key = settings['R2_PREFIX'].strip('/') + '/' + row['paper']
                files.append({'name': row['paper'], 'sha256': row['paper_sha256'],
                              'url': presign(settings, key, 1800)})
            descriptor = os.open(request, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as stream:
                json.dump({'files': files}, stream)
            if args.r2_location == 'remote':
                upload(request, REMOTE + '/r2-request.json')
            else:
                import urllib.request
                def read_local():
                    rows = []
                    for item in files:
                        with urllib.request.urlopen(item['url'], timeout=90) as response:
                            content = response.read(128 * 1024 * 1024 + 1)
                        if len(content) > 128 * 1024 * 1024:
                            raise ValueError('PDF exceeds configuration-test limit')
                        row = verify_pdf(content, item['sha256'])
                        row['paper'] = item['name']
                        rows.append(row)
                    return {'files': rows, 'storage': 'R2', 'persistence': 'memory_only', 'host': 'WSL'}
                local_result = FunctionCheck('r2_pdf_local', read_local).run()
                state['r2_local'] = {'status': local_result.status, 'details': local_result.details}
                save()
            request.unlink()
            launch = temp / 'launch.py'
            remote_pdf_args = ",'--r2-request',root+'/r2-request.json'" if args.r2_location == 'remote' else ''
            launch.write_text("import subprocess\nfrom pathlib import Path\nroot='" + REMOTE + "'\np=root+'/venv/bin/python'\ntry:\n"
                              " tests=subprocess.run([p,'-B','-m','pytest',root+'/test_validation.py','-q','-p','no:cacheprovider'],capture_output=True,text=True)\n"
                              " print(tests.stdout,flush=True)\n print(tests.stderr,flush=True)\n"
                              " tests.check_returncode()\n"
                              " result=subprocess.run([p,'-B',root+'/probe_environment.py','--root',root,'--run-id','" + run_id + "'" + remote_pdf_args + "],capture_output=True,text=True)\n"
                              " print(result.stdout,flush=True)\n print(result.stderr,flush=True)\n"
                              " print('ORDER_CONFIG_DRIVER_COMPLETED',flush=True)\n"
                              "finally:\n Path(root+'/r2-request.json').unlink(missing_ok=True)\n")
            execute_script(launch, 'probe.log', 'ORDER_CONFIG_COMPLETED:' + run_id)
            recovered = ('config-report.json', 'requirements.lock', 'source-hashes.json', 'prepared-identity.json')
            for name in recovered:
                if command(['colab', 'download', '-s', args.session, REMOTE + '/' + name, output / name], 'transport.log'):
                    raise RuntimeError('Receipt recovery failed')
            value = json.loads((output / 'config-report.json').read_text())
            report = ConfigReport.from_dict(value, run_id)
            from probe_environment import REQUIRED
            if value['probe_sha256'] != sha(HERE / 'probe_environment.py'):
                raise ValueError('Probe source identity mismatch')
            if value.get('lock_sha256') != sha(output / 'requirements.lock') or value.get('sources_sha256') != sha(HERE / 'sources.json'):
                raise ValueError('Lock or source identity mismatch')
            identity_check = next(check for check in report.checks if check.name == 'prepared_identity')
            if identity_check.details.get('prepared_identity_sha256') != sha(output / 'prepared-identity.json'):
                raise ValueError('Recovered prepared-environment identity mismatch')
            # Downloaded receipt is verified for identity; content hashes are retained locally.
            state['recovered_sha256'] = {name: sha(output / name) for name in recovered}
            state['status'] = ('configuration_checks_passed' if report.ready(REQUIRED) else
                               'configuration_checks_failed' if any(c.status == 'FAIL' for c in report.checks) else
                               'configuration_checks_incomplete')
            state['pipeline_ready'] = False
            state['r2_scope'] = [row['paper'] for row in selected]
            if args.close:
                if command(['colab', 'stop', '-s', args.session], 'close.log'):
                    raise RuntimeError('Session close not confirmed')
                state['session_closed'] = True
            save()
            print(json.dumps({'run_id': run_id, 'status': state['status'], 'session_closed': state['session_closed'],
                              'output': str(output), 'checks': [(c.name, c.status) for c in report.checks]}))
            return 0 if report.ready(REQUIRED) else 1
    except Exception as exc:
        state.update(status='manual_review', error_type=type(exc).__name__)
        save()
        print(json.dumps({'run_id': run_id, 'status': 'manual_review', 'error_type': type(exc).__name__,
                          'output': str(output), 'session': args.session}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
