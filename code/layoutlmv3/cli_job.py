"""Run the transferred installer and archive diagnostics, including on failure."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
import zipfile


def run_job(setup, state, archive):
    setup, state, archive = Path(setup), Path(state), Path(archive)
    state.mkdir(parents=True, exist_ok=True)
    archive.parent.mkdir(parents=True, exist_ok=True)
    code = 1
    started = datetime.now(timezone.utc).isoformat()
    try:
        with (state / 'setup-console.log').open('w', encoding='utf-8') as log:
            with subprocess.Popen([sys.executable, '-u', str(setup)],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding='utf-8', errors='replace') as process:
                for line in process.stdout:
                    print(line, end='', flush=True)
                    log.write(line)
                    log.flush()
                code = process.wait()
    finally:
        status = {'returncode': code, 'started_utc': started,
                  'finished_utc': datetime.now(timezone.utc).isoformat(),
                  'scope': 'Installer: ' + setup.name + '; consult detailed check artifacts for scope',
                  'setup_sha256': hashlib.sha256(setup.read_bytes()).hexdigest() if setup.exists() else None}
        (state / 'job-status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            for path in sorted(state.rglob('*')):
                if path.is_file() and not path.is_symlink():
                    output.write(path, path.relative_to(state).as_posix())
        digest = hashlib.sha256()
        with archive.open('rb') as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                digest.update(block)
        archive.with_suffix('.sha256').write_text(digest.hexdigest() + '\n', encoding='ascii')
        print('Respaldo remoto:', archive, 'SHA-256:', digest.hexdigest(), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(run_job('/content/nasa_setup_env.py', '/content/nasa-layoutlm-state',
                             '/content/nasa-layoutlm-setup.zip'))
