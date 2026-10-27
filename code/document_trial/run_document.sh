#!/usr/bin/env bash
# USER ONLY. One existing exclusive T4 session; no allocation or automatic retry.
set -euo pipefail
SESSION=${1:?Uso: bash code/document_trial/run_document.sh SESION_T4 --own-session PAQUETE}
if [[ ${2:-} != --own-session ]]; then
  echo 'Se requiere --own-session: declara sesión propia exclusiva y autoriza cierre tras respaldo verificado.' >&2
  exit 2
fi
PACKAGE=${3:?Indica el paquete del PDF que quieres procesar}
export PYTHONPATH=code
CALL_TIMEOUT=${DOC_CALL_TIMEOUT:-600}
DEFAULT_EXEC_TIMEOUT=$(python3 - "$PACKAGE/plan.json" <<'PY'
import json,sys
print(43200 if 'documents' in json.load(open(sys.argv[1])) else 10800)
PY
)
EXEC_TIMEOUT=${DOC_EXEC_TIMEOUT:-$DEFAULT_EXEC_TIMEOUT}
bounded_cli() {
  local logfile=$1 seconds=$2
  shift 2
  if python3 -B -m document_trial.cli --log "$logfile" --timeout "$seconds" -- colab "$@"; then
    return 0
  else
    local code=$?
    # Do not echo raw CLI logs: error URLs can contain runtime access tokens.
    printf 'Fallo en colab %s (codigo %s). Detalle local: %s\n' "$1" "$code" "$logfile" >&2
    return "$code"
  fi
}
python3 - "$PACKAGE" <<'PY'
import sys,zipfile
from pathlib import Path
from document_trial.common import validate_bundle
p=Path(sys.argv[1]);validate_bundle(p/'upload.zip',p/'upload.sha256')
with zipfile.ZipFile(p/'upload.zip') as z:
    if z.read('plan.json')!=(p/'plan.json').read_bytes():raise ValueError('External plan differs from bundled plan; no remote action')
print('Paquete verificado offline; sin inferencia.')
PY
DOCUMENT_KEY=$(python3 - "$PACKAGE/plan.json" <<'PY'
import json,re,sys
plan=json.load(open(sys.argv[1]));digest=plan.get('batch_sha256',plan.get('document_sha256',''))
if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Invalid document hash')
print(digest)
PY
)
mkdir -p "code/results/document-parsing/$DOCUMENT_KEY"
RUN_DIR="code/results/document-parsing/$DOCUMENT_KEY/$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir "$RUN_DIR"
python3 - "$RUN_DIR/attempt.json" <<'PY'
import sys,uuid
from document_trial.common import save
save(sys.argv[1],dict(attempt_id=uuid.uuid4().hex))
PY
bounded_cli "$RUN_DIR/session-status.log" "$CALL_TIMEOUT" status -s "$SESSION"
if ! grep -q 'Hardware: T4' "$RUN_DIR/session-status.log" || ! grep -q 'Status: IDLE' "$RUN_DIR/session-status.log"; then
  echo 'No se confirmó T4 o la sesión no está IDLE; no se ejecuta inferencia ni se cierra una sesión sin respaldo.' >&2
  exit 1
fi
ZIP_BYTES=$(python3 -c 'import os,sys; print(os.path.getsize(sys.argv[1]))' "$PACKAGE/upload.zip")
IS_BATCH=$(python3 -c 'import json,sys; print("yes" if "documents" in json.load(open(sys.argv[1])) else "no")' "$PACKAGE/plan.json")
CHUNK_BYTES=$(python3 -c 'from document_trial.transfer import CHUNK_BYTES; print(CHUNK_BYTES)')
if [[ "$IS_BATCH" == yes ]] && (( ZIP_BYTES > CHUNK_BYTES )); then
  python3 -B -m document_trial.transfer "$PACKAGE/upload.zip" "$RUN_DIR/transfer" "$RUN_DIR/attempt.json"
  ATTEMPT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["attempt_id"])' "$RUN_DIR/attempt.json")
  for part in "$RUN_DIR/transfer"/part-*; do
    name=${part##*/}
    echo "Subiendo $name..."
    bounded_cli "$RUN_DIR/upload-$name.log" "$CALL_TIMEOUT" upload -s "$SESSION" "$part" "/content/sic-transfer-$ATTEMPT-$name"
  done
  bounded_cli "$RUN_DIR/assembly.log" "$CALL_TIMEOUT" exec -s "$SESSION" --timeout "$CALL_TIMEOUT" -f "$RUN_DIR/transfer/assembly.py"
  EXPECTED_SHA=$(tr -d '\r\n' < "$PACKAGE/upload.sha256")
  if ! grep -Fxq "TRANSFER_VERIFIED $EXPECTED_SHA" "$RUN_DIR/assembly.log"; then
    echo "Reconstruccion no verificada. No se inicia parsing, no se reintenta ni se cierra la sesion. Log: $RUN_DIR/assembly.log" >&2
    exit 1
  fi
else
  echo "Subiendo ZIP completo del paper..."
  bounded_cli "$RUN_DIR/upload-zip.log" "$CALL_TIMEOUT" upload -s "$SESSION" "$PACKAGE/upload.zip" /content/nasa-sic12-document-v1-upload.zip
fi
bounded_cli "$RUN_DIR/upload-sha.log" "$CALL_TIMEOUT" upload -s "$SESSION" "$PACKAGE/upload.sha256" /content/nasa-sic12-document-v1-upload.sha256
bounded_cli "$RUN_DIR/upload-attempt.log" "$CALL_TIMEOUT" upload -s "$SESSION" "$RUN_DIR/attempt.json" /content/nasa-sic12-document-v1-attempt.json
echo "Transferencia completada. Iniciando parsing de los tres modelos; log: $RUN_DIR/cli-console.log"
set +e
bounded_cli "$RUN_DIR/cli-console.log" "$EXEC_TIMEOUT" exec -s "$SESSION" --timeout "$EXEC_TIMEOUT" <<'PY'
import os,runpy,sys,traceback,json,hashlib
from pathlib import Path
previous_path=sys.path[:];previous_argv=sys.argv[:]
previous_flag=os.environ.get('NASA_DOCUMENT_USER_RUN')
old={k:v for k,v in sys.modules.copy().items() if k=='document_trial' or k.startswith('document_trial.')}
try:
    for k in old:del sys.modules[k]
    os.environ['NASA_DOCUMENT_USER_RUN']='COLAB_CLI_T4'
    sys.argv=['sic12-document-user-run']
    sys.path.insert(0,'/content/nasa-sic12-document-v1-upload.zip')
    namespace=runpy.run_module('document_trial.remote',run_name='document_trial_user_entry')
    try:
        namespace['main']()
    except (Exception,SystemExit):
        traceback.print_exc()
    try:
        prefix=namespace['PREFIX']
        status=namespace['verify_terminal'](prefix.with_suffix('.zip'),prefix.with_suffix('.sha256'),
            prefix.with_name(prefix.name+'-inputs').joinpath('plan.json').read_bytes(),
            hashlib.sha256(prefix.with_name(prefix.name+'-upload.zip').read_bytes()).hexdigest(),
            json.loads(prefix.with_name(prefix.name+'-attempt.json').read_text())['attempt_id'])
    except Exception:
        print('DOCUMENT_NO_VERIFIED_ARCHIVE',flush=True)
        traceback.print_exc()
    else:
        print('DOCUMENT_ARCHIVE_READY '+status['status'],flush=True)
finally:
    sys.path[:]=previous_path;sys.argv=previous_argv
    for k in tuple(sys.modules):
        if k=='document_trial' or k.startswith('document_trial.'):del sys.modules[k]
    sys.modules.update(old)
    if previous_flag is None:os.environ.pop('NASA_DOCUMENT_USER_RUN',None)
    else:os.environ['NASA_DOCUMENT_USER_RUN']=previous_flag
PY
REMOTE_CODE=$?
set -e
# An absent marker or local timeout is NOT proof that the remote job stopped.
# Read the two known backup artifacts once, with bounded waits; never repeat exec.
echo "Retorno de espera CLI=$REMOTE_CODE. Comprobando artefactos existentes, sin repetir ejecución."
if ! bounded_cli "$RUN_DIR/download-zip.log" "$CALL_TIMEOUT" download -s "$SESSION" /content/nasa-sic12-document-v1.zip "$RUN_DIR/result.zip"; then
  echo "Sin respaldo accesible/verificado. No cerrar ni repetir inferencia; sesión requiere atención manual. Logs: $RUN_DIR" >&2
  exit 1
fi
if ! bounded_cli "$RUN_DIR/download-sha.log" "$CALL_TIMEOUT" download -s "$SESSION" /content/nasa-sic12-document-v1.sha256 "$RUN_DIR/result.sha256"; then
  echo "Falta sidecar verificado. No cerrar; sesión requiere atención manual. Logs: $RUN_DIR" >&2
  exit 1
fi
python3 - "$PACKAGE" "$RUN_DIR" <<'PY'
import sys,json
from pathlib import Path
from document_trial.common import sha,save,verify_terminal
p=Path(sys.argv[1]);d=Path(sys.argv[2]);digest=sha(d/'result.zip')
s=verify_terminal(d/'result.zip',d/'result.sha256',(p/'plan.json').read_bytes(),sha(p/'upload.zip'),json.loads((d/'attempt.json').read_text())['attempt_id'])
save(d/'backup-verified.json',dict(sha256=digest,status=s['status'],backup_verified=True))
print('Respaldo terminal descargado y verificado:',d,s['status'])
PY
if ! bounded_cli "$RUN_DIR/stop.log" "$CALL_TIMEOUT" stop -s "$SESSION"; then
  echo "Respaldo verificado, pero cierre no confirmado. Revisar/cerrar manualmente la sesión; no repetir ejecución. Logs: $RUN_DIR" >&2
  exit 1
fi
echo "Sesión propia cerrada después de verificar respaldo. Resultados: $RUN_DIR"
python3 - "$RUN_DIR/backup-verified.json" <<'PY'
import json,sys
if json.load(open(sys.argv[1]))['status']!='completed':
    raise SystemExit('Ejecución fallida; conservar respaldo y avisar. No reintentar automáticamente.')
print('Inferencias terminadas. La evaluación visual y aceptación quedan pendientes, sin nuevas recuperaciones.')
PY
