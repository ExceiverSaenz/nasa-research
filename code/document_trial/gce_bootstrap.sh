#!/usr/bin/env bash
# User runs once on a clean Ubuntu22.04 GCE VM. No parsers or model installs here.
set -euo pipefail
python3 - <<'PY'
from urllib.request import Request,urlopen
r=Request('http://metadata.google.internal/computeMetadata/v1/instance/name',headers={'Metadata-Flavor':'Google'})
with urlopen(r,timeout=5) as f:
    if f.headers.get('Metadata-Flavor')!='Google':raise SystemExit('GCE required')
    print('GCE VM:',f.read(4096).decode())
PY
if [[ -e /content ]]; then echo '/content ya existe; revisar manualmente, no repetir bootstrap.' >&2; exit 1; fi
sudo mkdir -m 700 /content
sudo chown "$(id -u):$(id -g)" /content
exec > >(tee /content/gce-bootstrap.log) 2>&1
touch /content/bootstrap-started
sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3-pip python3-venv build-essential git ca-certificates \
  libgl1 libglib2.0-0 libgomp1 libsm6 libxext6 poppler-utils \
  nvidia-driver-570-server nvidia-utils-570-server
touch /content/bootstrap-completed
echo 'Bootstrap terminado. Reinicia la VM antes de submit para cargar el driver.'
echo 'No se instalaron entornos de parsers ni se ejecutaron inferencias.'
