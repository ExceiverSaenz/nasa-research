#!/usr/bin/env bash
# USER ONLY. One inference, existing own T4, no allocation/retries.
set -euo pipefail
cd "$(dirname "$0")/../.."
SESSION="${1:?Uso: bash code/page_integration/test_square.sh SESION_T4 --own-session}"
if [ "${2:-}" != "--own-session" ]; then
    echo "Confirma que es tu sesion exclusiva con --own-session; se cerrara tras verificar el respaldo."
    exit 2
fi
PACKAGE="code/packages/table1-square-v1"
python3 - "$PACKAGE" <<'PY'
import hashlib,json,sys,zipfile
from pathlib import Path
p=Path(sys.argv[1]);bundle=p/'upload.zip'
if hashlib.sha256(bundle.read_bytes()).hexdigest()!=(p/'upload.sha256').read_text().strip():
    raise ValueError('Paquete modificado; no ejecutar')
with zipfile.ZipFile(bundle) as z:
    manifest=json.loads(z.read('bundle-manifest.json'))
    for n,spec in manifest['files'].items():
        raw=z.read(n)
        if len(raw)!=spec['bytes'] or hashlib.sha256(raw).hexdigest()!=spec['sha256']:
            raise ValueError('Miembro modificado: '+n)
        if n.startswith(('page_integration/','mineru_probe/')) and raw!=(Path('code')/n).read_bytes():
            raise ValueError('Codigo distinto del paquete: '+n)
print('Paquete de una ROI cuadrada con trazas verificado sin OCR.')
PY
mkdir -p code/results/table1-square-v1
RUN_DIR="code/results/table1-square-v1/$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir "$RUN_DIR"
colab status -s "$SESSION" | tee "$RUN_DIR/session-status.log"
if ! grep -q 'Hardware: T4' "$RUN_DIR/session-status.log"; then
    echo "No se confirmo hardware T4. No se inicia OCR ni se cierra una sesion sin respaldo."
    exit 1
fi
colab upload -s "$SESSION" "$PACKAGE/upload.zip" /content/nasa-table1-square-v1-upload.zip
colab upload -s "$SESSION" "$PACKAGE/upload.sha256" /content/nasa-table1-square-v1-upload.sha256
set +e
colab exec -s "$SESSION" --timeout 1800 2>&1 <<'PY' | tee "$RUN_DIR/cli-console.log"
import runpy
import sys
previous_argv=sys.argv[:]
previous_path=sys.path[:]
prefixes=('page_integration','mineru_probe')
def owned(name):
    return any(name==p or name.startswith(p+'.') for p in prefixes)
previous_modules={name:module for name,module in sys.modules.copy().items() if owned(name)}
try:
    for name in previous_modules:
        del sys.modules[name]
    sys.argv=['table1-square-user-run']
    sys.path.insert(0,'/content/nasa-table1-square-v1-upload.zip')
    runpy.run_module('page_integration.remote_square',run_name='__main__')
finally:
    sys.argv=previous_argv
    sys.path[:]=previous_path
    for name in tuple(sys.modules):
        if owned(name):
            del sys.modules[name]
    sys.modules.update(previous_modules)
PY
REMOTE_CODE=${PIPESTATUS[0]}
set -e
if ! grep -Eq '^SQUARE_ARCHIVE_READY (completed|failed)[[:space:]]*$' "$RUN_DIR/cli-console.log"; then
    echo "Sin confirmacion de respaldo terminal (CLI=$REMOTE_CODE). No repetir ni cerrar un proceso posiblemente activo."
    echo "Revisa $RUN_DIR/cli-console.log y avisa; la sesion requiere revision manual."
    exit 1
fi
colab download -s "$SESSION" /content/nasa-table1-square-v1.zip "$RUN_DIR/result.zip"
colab download -s "$SESSION" /content/nasa-table1-square-v1.sha256 "$RUN_DIR/result.sha256"
python3 - "$PACKAGE" "$RUN_DIR" <<'PY'
import hashlib,json,sys,zipfile
from pathlib import Path
p=Path(sys.argv[1]);out=Path(sys.argv[2]);archive=out/'result.zip'
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
if sha!=(out/'result.sha256').read_text().strip():raise ValueError('Hash de respaldo incorrecto; no cerrar')
with zipfile.ZipFile(archive) as z:
    if len(z.namelist())!=len(set(z.namelist())) or z.testzip() is not None:raise ValueError('ZIP invalido; no cerrar')
    if z.read('plan.json')!=(p/'plan.json').read_bytes():raise ValueError('Plan devuelto distinto; no cerrar')
    status=json.loads(z.read('execution-status.json'))
    if status.get('status') not in ('completed','failed'):raise ValueError('Estado no terminal; no cerrar')
(out/'backup-verified.json').write_text(json.dumps({'sha256':sha,'status':status['status'],'backup_verified':True},indent=2)+'\n')
print('Respaldo terminal descargado y verificado:',out,'estado:',status['status'])
PY
colab stop -s "$SESSION"
echo "Sesion propia cerrada tras verificar el respaldo. Resultados: $RUN_DIR"
python3 - "$RUN_DIR/backup-verified.json" <<'PY'
import json,sys
status=json.load(open(sys.argv[1]))['status']
if status!='completed':
    print('La ejecucion fallo; conserva el respaldo y avisa. No reintentar.')
    raise SystemExit(1)
print('Ejecucion finalizada; reconocimiento y vinculo pendientes de evaluar sin GPU.')
PY
