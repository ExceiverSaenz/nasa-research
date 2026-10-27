# Minimal trial with Colab CLI 0.7.4

## Common operational entry point

Before using any Colab CLI launcher, follow
[`EXECUTION.md`](EXECUTION.md) and record the run in
[`analytics/config/remote_runs.json`](../../analytics/config/remote_runs.json).
This guide contains historical smoke-test context; do not repeat it to
recover context.

## Historical infrastructure guide

The stage described here has already been superseded by successful LayoutLMv3 installation and
imports/configuration. See `docs/continuidad/04-estado-de-la-prueba.md` and evidence in
`code/results/layoutlmv3-import/20261018T201957Z/`. Do not repeat this smoke test to
start a conversation. Later session `nasa-layout-env`, stopped according to the
user; next milestone: single-page inference. The balances and limitations
below are historical, not current queries.

Historical state checked by the user: 280.14 units, 0.00/h, no active sessions. Check again before running. Automated WSL access is blocked; run these commands in Ubuntu as exceiver.

This trial checks infrastructure, transfer and recovery. It does not install dependencies or run LayoutLMv3. Preparation runs locally. Future detector inference will run on GPU; inventory, box validation and result analysis can run locally.

## Local preparation (no GPU)

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
python3 -m py_compile code/colab/smoke_remote.py
colab version
colab usage
colab sessions
```

## Run only after resource consumption is authorized

Request a T4 for this small trial; an A100 is not needed to validate the connection. If a suitable existing session appears, review its owner and status before reusing it. Do not stop other people's sessions.

```bash
colab new -s nasa-cli-smoke --gpu T4
colab status -s nasa-cli-smoke
colab usage
colab upload -s nasa-cli-smoke code/colab/smoke_remote.py /content/nasa_smoke_source.py
colab exec -s nasa-cli-smoke --timeout 180 -f code/colab/smoke_remote.py
mkdir -p code/results/smoke
colab download -s nasa-cli-smoke /content/nasa-smoke-result.json code/results/smoke/result.json
python3 - <<'PY'
import hashlib, json
from pathlib import Path
r = json.loads(Path('code/results/smoke/result.json').read_text())
expected = hashlib.sha256(Path('code/colab/smoke_remote.py').read_bytes()).hexdigest()
assert r['uploaded_source_sha256'] == expected, 'Transferred file does not match'
assert r['gpu_ok'] is True, 'CUDA operation did not pass'
print(json.dumps(r, indent=2))
print('Transfer, GPU and recovery verified')
PY
```

Run each step separately; do not continue after a failure. Before stopping, check that result.json exists, is readable and contains gpu_ok=true. If execution fails, check status and recover available results before closing. A client timeout does not prove that the remote process stopped.

If you created the nasa-cli-smoke session exclusively for this trial and the results are already verified:

```bash
colab stop -s nasa-cli-smoke
colab sessions
colab usage
```

## Next stage: the detector

The isolated environment and LayoutLMv3 installation have already been checked in Colab.
Use `code/layoutlmv3/test_detector.sh` only when a VM needs rebuilding for
an authorized trial. The inference wrapper still needs implementation. Do not install
historical packages in the modern kernel with `colab install`.

To run several modules, prepare a distribution file with an explicit list of scripts, configuration and selected PDFs; upload it with colab upload and extract it into a dedicated remote folder. colab exec -f transmits only the specified file: it does not synchronize imports, data or checkpoints. Do not upload the entire repository indiscriminately.

Record versions, weights and hashes, test PDF/pages and parameters. Save outputs and checkpoints in a run folder, package them, download them and compare their hashes before stopping the VM. Do not rely on temporary remote storage. Keep CLI credentials and metadata outside the project.
