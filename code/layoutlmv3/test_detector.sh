#!/usr/bin/env bash
# Requires an existing session; never creates or stops a VM.
set -euo pipefail
cd "$(dirname "$0")/../.."
SESSION="${1:-nasa-layoutlm-env}"
for file in code/layoutlmv3/{setup_env.py,cli_job.py,install_detector.py,requirements-inference.txt,unilm-commit.txt} code/packages/layoutlmv3-source.tar.gz code/models/layoutlmv3-publaynet/download-manifest.json; do
    test -f "$file" || { echo "Falta: $file"; exit 1; }
done
colab status -s "$SESSION"
colab usage
colab upload -s "$SESSION" code/layoutlmv3/setup_env.py /content/nasa_setup_env.py
colab upload -s "$SESSION" code/layoutlmv3/cli_job.py /content/nasa_cli_job.py
colab upload -s "$SESSION" code/layoutlmv3/install_detector.py /content/nasa_install_detector.py
colab upload -s "$SESSION" code/layoutlmv3/requirements-inference.txt /content/requirements-inference.txt
colab upload -s "$SESSION" code/layoutlmv3/unilm-commit.txt /content/unilm-commit.txt
colab upload -s "$SESSION" code/packages/layoutlmv3-source.tar.gz /content/layoutlmv3-source.tar.gz
colab upload -s "$SESSION" code/models/layoutlmv3-publaynet/download-manifest.json /content/layoutlmv3-model-manifest.json
RUN_DIR="code/results/layoutlmv3-import/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"
set +e
colab exec -s "$SESSION" --timeout 1800 <<'PY' 2>&1 | tee "$RUN_DIR/cli-console.log"
import runpy
job = runpy.run_path('/content/nasa_cli_job.py', run_name='cli_helper')
code = job['run_job']('/content/nasa_install_detector.py', '/content/nasa-layoutlm-state', '/content/nasa-detector-check.zip')
print('INSTALLER_RETURN_CODE:', code)
PY
REMOTE_CODE=${PIPESTATUS[0]}
set -e
if [ "$REMOTE_CODE" -ne 0 ]; then
    echo "El CLI devolvio error o timeout. No repetir instalacion: comprobar si sigue ejecutandose."
    echo "La sesion sigue activa. Registro local: $RUN_DIR/cli-console.log"
    exit "$REMOTE_CODE"
fi
colab download -s "$SESSION" /content/nasa-detector-check.zip "$RUN_DIR/check.zip"
colab download -s "$SESSION" /content/nasa-detector-check.sha256 "$RUN_DIR/check.sha256"
python3 code/layoutlmv3/verify_download.py "$RUN_DIR/check.zip"
echo "Respaldo verificado en $RUN_DIR"
echo "Esta prueba NO carga los pesos del detector ni procesa PDFs."
echo "La sesion sigue activa. Tras revisar, detenla solo si la creaste para esta tarea:"
printf 'colab stop -s %q\n' "$SESSION"
