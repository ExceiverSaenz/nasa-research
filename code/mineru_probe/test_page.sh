#!/usr/bin/env bash
# Only an existing, user-authorized session. Never creates/stops a VM.
set -euo pipefail
cd "$(dirname "$0")/../.."
SESSION="${1:?Uso: bash code/mineru_probe/test_page.sh SESION_EXISTENTE}"
python3 code/mineru_probe/prepare.py
colab status -s "$SESSION"
colab usage
colab upload -s "$SESSION" code/packages/mineru-page.zip /content/mineru-page.zip
colab upload -s "$SESSION" code/packages/mineru-page.sha256 /content/mineru-page.sha256
colab upload -s "$SESSION" code/mineru_probe/prepare.py /content/nasa_mineru_prepare.py
colab upload -s "$SESSION" code/mineru_probe/remote_job.py /content/nasa_mineru_remote.py
colab upload -s "$SESSION" code/layoutlmv3/cli_job.py /content/nasa_mineru_archive.py
RUN_DIR="code/results/mineru-page/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"
set +e
colab exec -s "$SESSION" --timeout 1800 <<'PY' 2>&1 | tee "$RUN_DIR/cli-console.log"
import runpy
job = runpy.run_path('/content/nasa_mineru_remote.py', run_name='remote_helper')
code = job['execute_archived_job']('/content/nasa_mineru_archive.py', '/content/nasa_mineru_remote.py', '/content/mineru-state', '/content/mineru-result.zip')
print('MINERU_RETURN_CODE:', code)
PY
REMOTE_CODE=${PIPESTATUS[0]}
set -e
if [ "$REMOTE_CODE" -ne 0 ]; then
    echo "Error/timeout CLI. No repetir: comprobar si el trabajo sigue activo."
    echo "La sesion sigue activa. Registro: $RUN_DIR/cli-console.log"
    exit "$REMOTE_CODE"
fi
colab download -s "$SESSION" /content/mineru-result.zip "$RUN_DIR/result.zip"
colab download -s "$SESSION" /content/mineru-result.sha256 "$RUN_DIR/result.sha256"
python3 code/layoutlmv3/verify_download.py "$RUN_DIR/result.zip"
echo "Respaldo MINERU verificado: $RUN_DIR"
echo "La sesion sigue activa. Revisar resultados antes de detener exclusivamente la propia."
