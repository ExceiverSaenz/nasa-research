#!/usr/bin/env bash
# Existing, explicitly authorized session only. Never creates/stops a session.
set -euo pipefail
cd "$(dirname "$0")/../.."
SESSION="${1:?Uso: bash code/layoutlmv3/test_page.sh NOMBRE_SESION}"
python3 code/layoutlmv3/prepare_page.py
# Reconstruct and verify the isolated env on the NEW VM, with existing proven flow.
bash code/layoutlmv3/test_detector.sh "$SESSION"
colab upload -s "$SESSION" code/packages/layoutlmv3-page.zip /content/layoutlmv3-page.zip
colab upload -s "$SESSION" code/packages/layoutlmv3-page.sha256 /content/layoutlmv3-page.sha256
colab upload -s "$SESSION" code/layoutlmv3/page_remote.py /content/nasa_page_remote.py
RUN_DIR="code/results/layoutlmv3-page/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"
set +e
colab exec -s "$SESSION" --timeout 1800 <<'PY' 2>&1 | tee "$RUN_DIR/cli-console.log"
import runpy
job = runpy.run_path('/content/nasa_cli_job.py', run_name='cli_helper')
code = job['run_job']('/content/nasa_page_remote.py', '/content/nasa-page-state', '/content/nasa-page-result.zip')
print('PAGE_RETURN_CODE:', code)
PY
REMOTE_CODE=${PIPESTATUS[0]}
set -e
if [ "$REMOTE_CODE" -ne 0 ]; then
    echo "Error o timeout del CLI. No repetir: comprobar si el trabajo sigue activo."
    echo "La sesion sigue activa; registro: $RUN_DIR/cli-console.log"
    exit "$REMOTE_CODE"
fi
colab download -s "$SESSION" /content/nasa-page-result.zip "$RUN_DIR/result.zip"
colab download -s "$SESSION" /content/nasa-page-result.sha256 "$RUN_DIR/result.sha256"
python3 code/layoutlmv3/verify_download.py "$RUN_DIR/result.zip"
echo "Ensayo finalizado y respaldo verificado: $RUN_DIR"
echo "La sesion sigue activa. Revisar resultados antes de detener exclusivamente la propia."
