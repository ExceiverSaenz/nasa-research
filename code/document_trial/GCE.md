# Parsing a PDF on Google Compute Engine

Preparation authorized October 26, 2026. Only the user creates resources and runs parsing. First package: **10.pdf, nine pages, three parsers**. Original configurations, weights, Python/Torch/CUDA, and 200 dpi rendering. No automatic reconciliation.

The package is new and declares USER_ONLY_GCE_SSH_T4; it does not pretend to be Colab. It preserves /content to reuse original adapters without editing inference paths. The only original sources modified in the derived ZIP are the guards and attribution in document_trial/remote.py and worker.py; originals remain intact. Manifests and platform-change.json record the baseline and changes.

## 1. Upload a file to Cloud Shell before creating the VM

From Cloud Shell's **Upload file / Subir archivo** menu, upload:

`C:\Users\HP Victus\Desktop\nasa_research\code\packages\sic-gce-v1\sic-gce-v1-paper10.tar.gz`

You can also use gcloud installed in WSL with project access; installation is unnecessary for the Cloud Shell option. Do not paste credentials into chat.

In Cloud Shell, from the folder containing the file:

```bash
tar -xzf sic-gce-v1-paper10.tar.gz
cd sic-gce-v1
export GCE_PROJECT=nasa-512810
export GCE_ZONE=us-central1-a
export GCE_VM=nasa-parsing-t4
```

Extract the TAR once only into a new destination. Its SHA256 is published beside the local file in `.tar.gz.sha256`; compare `sha256sum ../sic-gce-v1-paper10.tar.gz` with that value if you need to verify transfer. Submission rechecks the ZIP, SHA, members, and plan before contacting the VM.

## 2. Create the VM and prepare the system

**This command starts incurring charges**: n1-standard-8 (8 vCPU/30 GB), one T4, 150 GB persistent disk, Ubuntu 22.04, standard instance without automatic restart. It uses neither Spot nor a service account within the VM. It has a maximum duration of 4 hours with a STOP action; this is neither a monetary cap nor a guarantee of completing the paper.

```bash
bash gce.sh create
bash gce.sh bootstrap
```

If you already extracted the first delivery and create reported that `--no-scopes` is missing, correct only the launcher from `~/sic-gce-v1`; do not extract the package again:

```bash
sed -i 's/--no-service-account$/--no-service-account --no-scopes/' gce.sh
bash gce.sh create && bash gce.sh bootstrap
```

The omission prevented VM creation. `&&` avoids attempting bootstrap if create fails.

Do not repeat create if it fails or loses connection: check whether the VM exists. Quota does not guarantee capacity. If RESOURCE_POOL_EXHAUSTED appears, retain the message and decide on a zone; there is no automatic search/retry. The default network/SSH and Compute Engine permissions must be available; IAM and firewall rules are not changed automatically.

Bootstrap installs system libraries and the 570-server driver from Ubuntu, without models or parser environments. If it fails, retain the message and `/content/gce-bootstrap.log`; do not repeat it or update models to work around the failure.

Once bootstrap displays **Bootstrap terminado** (Bootstrap completed), reboot to load the driver:

```bash
gcloud compute ssh "$GCE_VM" --project="$GCE_PROJECT" --zone="$GCE_ZONE" \
  --command='test -f /content/bootstrap-completed && test ! -e /content/gce-claimed && sudo systemctl reboot'
```

The SSH connection may end with code 255 because of the reboot. Wait for the VM to start and check once:

```bash
gcloud compute ssh "$GCE_VM" --project="$GCE_PROJECT" --zone="$GCE_ZONE" \
  --command='nvidia-smi'
```

A single Tesla T4 and driver >=560.28.03 must appear. Before starting, the service rechecks GPU, driver, project/VM/zone/numeric-ID metadata, and at least 60 GiB of free disk space. Original checks for each environment remain intact.

## 3. Submit the attempt once

From `sic-gce-v1` in Cloud Shell:

```bash
bash gce.sh submit package runs/paper10-01
```

Generates a new UUID, verifies the package, copies through SCP, and creates systemd service `nasa-parsing-UUID`, with no Restart and with RemainAfterExit to retain its state when finished. **Submitted does not mean completed**. You can disconnect SSH/Cloud Shell: the service continues inside the VM while it remains powered on. It does not depend on a Colab session.

Do not rerun submit if it takes time, loses connection, or returns an error. The attempt directory and `/content/gce-claimed` prevent reuse. An ambiguous error requires status and review of the same attempt, without new inference.

## 4. Check progress

```bash
bash gce.sh status package runs/paper10-01
```

Displays ActiveState/SubState/ExecMainStatus and the last 35 lines. `active/running` may include installation or download; it does not certify inference. `active/exited` means the process exited and systemd retains the unit. Detailed records are in `/content/nasa-sic12-document-v1/commands/`, and console output is in `/content/gce-console.log`. `failed` retains the failure; it does not launch recovery.

## 5. Download and verify when finished

When the service finishes:

```bash
bash gce.sh collect package runs/paper10-01
bash gce.sh stop package runs/paper10-01
```

collect requires an existing ZIP/sidecar, downloads them once, and verifies SHA/CRC, plan, bundle, UUID, project/VM/zone/numeric ID, and page/parser states; for completed status it requires identity/render and required native files. It saves backup-verified.json. A **failed** backup may be technically verified: this does not mean parsing succeeded. stop revalidates the current bytes and requires an existing, terminated unit (inactive, failed, or active/exited through RemainAfterExit) before stopping the VM. It also checks with Compute Engine that the VM retains the numeric ID bound before submission: recreating it with the same name blocks the action. collect never stops; stop never performs inference again.

Results are in `runs/paper10-01/result.zip`, `result.sha256`, attempt.json, backup-verified.json, and transfer logs. Download the folder to your PC through Cloud Shell before deleting anything. To notify the agent, indicate where the ZIP/sidecar were saved; they are verified offline. Do not run document_trial.offline or the reconciler automatically: comparable result intake remains a separate stage.

If collect fails, **there is no implicit permission to shut down or relaunch**. The first remote-availability failure does not create receipt-started; once download starts, that directory prevents automatic repetition. Retain partial files and request review. The ZIP is published only at completion: a file's presence alone does not establish a verified backup.

## Time limit, persistence, and budget

The VM stops when it reaches its 4-hour limit; this may interrupt installation or parsing. The persistent disk retains files, but an interrupted attempt may lack a terminal ZIP and is not resumed/repeated automatically. We do not enable the service at boot. Rebooting/starting the VM to recover files must not start parsing; nevertheless, check its state before intervening. The duration limit applies to VM execution and does not promise a total budget of USD 50.

Persistent storage and other resources may continue to incur charges while the VM is stopped. After copying and verifying results on your PC, you can delete the VM and disk from Console; first check which resource you are deleting. This guide does not perform deletion. Do not leave a GPU powered on between attempts.

Do not reuse this /content for another PDF: review the first real execution before preparing the next increment. Neither installation nor actual parsing on Compute Engine has yet been validated; offline tests do not establish actual compatibility or execution speed.

## Official sources consulted

- [Create an N1 VM with a T4 GPU](https://docs.cloud.google.com/compute/docs/gpus/create-gpu-vm-general-purpose)
- [VM duration limit](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime)
- [Installing drivers on Compute Engine](https://docs.cloud.google.com/compute/docs/gpus/install-drivers-gpu)
- [NVIDIA drivers on Ubuntu Server](https://ubuntu.com/server/docs/nvidia-drivers-installation/)
- [CUDA 12.6 requirements](https://docs.nvidia.com/cuda/archive/12.6.0/cuda-toolkit-release-notes/index.html)
- [GPU pricing](https://cloud.google.com/products/compute/gpus-pricing)

## Additional local preparation (offline; do not run for the delivered package)

```bash
PYTHONPATH=code python3 -B -m document_trial.gce_package \
  --base code/packages/sic-parsing-v1/10 \
  --output code/packages/DESTINO_NUEVO \
  --release code/packages/ARCHIVO_NUEVO.tar.gz
```

New destinations are required. This neither rebuilds nor touches original ZIPs, downloads weights, nor creates a VM. Use for other PDFs requires a later scope decision.
