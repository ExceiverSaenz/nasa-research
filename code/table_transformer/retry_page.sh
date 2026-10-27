#!/usr/bin/env bash
# Only an existing, user-authorized session. Never creates/stops a VM.
set -euo pipefail
cd "$(dirname "$0")/../.."
SESSION="${1:?Uso: bash code/table_transformer/retry_page.sh SESION_EXISTENTE}"
python3 code/table_transformer/prepare.py
colab status -s "$SESSION"
colab usage
colab upload -s "$SESSION" code/packages/table-transformer-page.zip /content/table-transformer-page.zip
colab upload -s "$SESSION" code/packages/table-transformer-page.sha256 /content/table-transformer-page.sha256
colab upload -s "$SESSION" code/table_transformer/prepare.py /content/nasa_tatr_prepare.py
colab upload -s "$SESSION" code/table_transformer/remote_job.py /content/nasa_tatr_remote.py
colab upload -s "$SESSION" code/layoutlmv3/cli_job.py /content/nasa_tatr_archive.py
colab upload -s "$SESSION" code/table_transformer/retry_job.py /content/nasa_tatr_retry.py
RUN_DIR="code/results/table-transformer-page/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"
set +e
colab exec -s "$SESSION" --timeout 1800 <<'PY' 2>&1 | tee "$RUN_DIR/cli-console.log"
import runpy
job = runpy.run_path('/content/nasa_tatr_remote.py', run_name='remote_helper')
code = job['execute_archived_job']('/content/nasa_tatr_archive.py', '/content/nasa_tatr_retry.py', '/content/tatr-retry-state', '/content/tatr-retry-result.zip')
print('TATR_RETURN_CODE:', code)
PY
REMOTE_CODE=${PIPESTATUS[0]}
set -e
if [ "$REMOTE_CODE" -ne 0 ]; then
    echo "Error/timeout CLI. No repetir: comprobar si el trabajo sigue activo."
    echo "La sesion sigue activa. Registro: $RUN_DIR/cli-console.log"
    exit "$REMOTE_CODE"
fi
colab download -s "$SESSION" /content/tatr-retry-result.zip "$RUN_DIR/result.zip"
colab download -s "$SESSION" /content/tatr-retry-result.sha256 "$RUN_DIR/result.sha256"
python3 code/layoutlmv3/verify_download.py "$RUN_DIR/result.zip"
echo "Respaldo TATR verificado: $RUN_DIR"
echo "La sesion sigue activa. Revisar resultados antes de detener exclusivamente la propia."
