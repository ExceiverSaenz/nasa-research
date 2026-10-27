#!/usr/bin/env bash
# USER ONLY. Never invoked by agent, preparation, tests with real gcloud, or Colab.
set -euo pipefail
ACTION=${1:?Uso: bash gce.sh create|bootstrap|submit|status|collect|stop [PAQUETE INTENTO]}
PROJECT=${GCE_PROJECT:-nasa-512810}
ZONE=${GCE_ZONE:-us-central1-a}
VM=${GCE_VM:-nasa-parsing-t4}
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
for value in "$PROJECT" "$ZONE" "$VM"; do
  [[ "$value" =~ ^[a-z][a-z0-9-]{0,62}$ ]] || { echo 'Identidad GCE inválida' >&2; exit 2; }
done
cloud() { gcloud "$@" --project="$PROJECT" --zone="$ZONE"; }
ssh_command() { cloud compute ssh "$VM" --command="$1"; }
case "$ACTION" in
  create)
    cloud compute instances create "$VM" --machine-type=n1-standard-8 \
      --accelerator=type=nvidia-tesla-t4,count=1 --maintenance-policy=TERMINATE \
      --provisioning-model=STANDARD --no-restart-on-failure \
      --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
      --boot-disk-size=150GB --boot-disk-type=pd-balanced \
      --max-run-duration=4h --instance-termination-action=STOP --no-service-account --no-scopes
    ;;
  bootstrap)
    cloud compute scp "$HERE/gce_bootstrap.sh" "$VM:~/sic-gce-bootstrap.sh"
    ssh_command 'bash ~/sic-gce-bootstrap.sh'
    ;;
  submit|status|collect|stop)
    PACKAGE=${2:?Indica paquete GCE}; RUN_DIR=${3:?Indica directorio local del intento}
    PACKAGE=$(cd -- "$PACKAGE" && pwd)
    # Load only inert entry code from the verified derived package.
    export PYTHONPATH="$PACKAGE/upload.zip"
    if [[ "$ACTION" == submit ]]; then
      python3 -B -m document_trial.gce_entry prepare-attempt --package "$PACKAGE" --run "$RUN_DIR" \
        --project "$PROJECT" --instance "$VM" --zone "$ZONE"
      INSTANCE_ID=$(cloud compute instances describe "$VM" --format='value(id)')
      python3 -B -m document_trial.gce_entry bind-instance --package "$PACKAGE" --run "$RUN_DIR" --instance-id "$INSTANCE_ID"
      python3 -B -m document_trial.gce_entry write-launch --package "$PACKAGE" --run "$RUN_DIR"
    fi
    ATTEMPT=$(python3 - "$RUN_DIR/attempt.json" "$PROJECT" "$VM" "$ZONE" <<'PY'
import json,re,sys
a=json.load(open(sys.argv[1]))
if [a.get(k) for k in ('project','instance','zone')]!=sys.argv[2:]:raise ValueError('Attempt/host mismatch')
v=a['attempt_id']
if not re.fullmatch('[0-9a-f]{32}',v):raise ValueError('Invalid attempt')
print(v)
PY
)
    UNIT="nasa-parsing-$ATTEMPT"
    if [[ "$ACTION" != submit ]]; then
      CURRENT_ID=$(cloud compute instances describe "$VM" --format='value(id)')
      python3 - "$RUN_DIR/attempt.json" "$CURRENT_ID" <<'PY'
import json,sys
if json.load(open(sys.argv[1])).get('instance_id')!=sys.argv[2]:raise SystemExit('VM identity changed; no action')
PY
    fi
    case "$ACTION" in
      submit)
        STAGE=".sic-gce-$ATTEMPT"
        # mkdir is exclusive. Failure or ambiguous SSH never retries or removes evidence.
        ssh_command "test -d /content && test -w /content && test ! -e /content/gce-claimed && nvidia-smi && mkdir \"\$HOME/$STAGE\"" > "$RUN_DIR/pre-submit.log" 2>&1
        cloud compute scp "$PACKAGE/upload.zip" "$PACKAGE/upload.sha256" "$RUN_DIR/attempt.json" "$RUN_DIR/launch.sh" "$VM:~/$STAGE/" > "$RUN_DIR/upload.log" 2>&1
        ssh_command "bash \"\$HOME/$STAGE/launch.sh\"" > "$RUN_DIR/submit.log" 2>&1
        echo "Intento enviado: $RUN_DIR. Consulta status; no vuelvas a hacer submit."
        ;;
      status)
        ssh_command "systemctl show '$UNIT' --property=LoadState,ActiveState,SubState,ExecMainStatus; tail -n 35 /content/gce-console.log 2>/dev/null || true"
        ;;
      collect)
        # Terminal files must exist before download. Missing means manual review.
        ssh_command "test -f /content/nasa-sic12-document-v1.zip && test -f /content/nasa-sic12-document-v1.sha256"
        mkdir "$RUN_DIR/receipt-started"
        cloud compute scp "$VM:/content/nasa-sic12-document-v1.zip" "$RUN_DIR/result.zip" > "$RUN_DIR/download-zip.log" 2>&1
        cloud compute scp "$VM:/content/nasa-sic12-document-v1.sha256" "$RUN_DIR/result.sha256" > "$RUN_DIR/download-sha.log" 2>&1
        python3 -B -m document_trial.gce_entry verify --package "$PACKAGE" --run "$RUN_DIR"
        echo "Respaldo verificado. VM no detenida automáticamente; usa stop."
        ;;
      stop)
        # A verified failed terminal backup also permits stopping; no retry follows.
        python3 -B -m document_trial.gce_entry verify --package "$PACKAGE" --run "$RUN_DIR"
        ssh_command "load=\$(systemctl show '$UNIT' --property=LoadState --value) && test \"\$load\" = loaded && state=\$(systemctl show '$UNIT' --property=ActiveState --value) && sub=\$(systemctl show '$UNIT' --property=SubState --value) && { test \"\$state\" = inactive || test \"\$state\" = failed || { test \"\$state\" = active && test \"\$sub\" = exited; }; }"
        cloud compute instances stop "$VM"
        ;;
    esac
    ;;
  *) echo 'Acción desconocida' >&2; exit 2 ;;
esac
