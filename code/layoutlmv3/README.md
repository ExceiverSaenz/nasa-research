# Isolated environment using Colab CLI 0.7.4

## Status and continuity

Installation, direct weight download, and imports/configuration were completed on a Tesla T4 on October 18, 2026. Verified backup: `code/results/layoutlmv3-import/20261018T201957Z/`. Actual session `nasa-layout-env`, stopped according to the user. Nine tests passed on Windows and WSL.

Do not rerun this guide to recover context. The next milestone is to test the implemented single-page inference MVP; see [inference/README.md](inference/README.md). Packaging/recovery and actual GPU execution of the adapter remain pending. Consult `docs/continuidad/04-estado-de-la-prueba.md` and `docs/continuidad/05-continuacion-de-la-prueba.md`. The commands below are a reconstruction procedure for a new VM with resource-use authorization, not a pending list of manual checks.

## Additional detector installation (second stage)

With the local files already prepared, verify without a GPU:

```bash
python3 -m unittest discover -s code/layoutlmv3 -p 'test_*.py' -v
bash -n code/layoutlmv3/test_detector.sh
```

After resource use is authorized, create a T4 only if no suitable session exists:

```bash
colab sessions
colab new -s nasa-layout-env --gpu T4
bash code/layoutlmv3/test_detector.sh nasa-layout-env
```

test_detector.sh transfers code and the small manifest without uploading the weights TAR. The installer downloads the model directly in Colab from the pinned Hugging Face revision and verifies size and SHA-256 before publishing each file. If the download fails or is corrupt, it deletes the partial file and does not continue installation. Internet access from Colab is required; verified access from WSL does not establish access from the VM. Download errors omit temporary URLs. It then rebuilds the base environment, installs dependencies, checks imports and configuration, and downloads logs with SHA-256 to code/results/layoutlmv3-import/<date>/. It does not create or stop sessions. After checking the backup, stop only the session created for the test with `colab stop -s nasa-layout-env`. If installation fails, the verifier returns an error but retains the downloaded ZIP. On timeout, do not assume that the process has stopped or repeat it concurrently. The backup includes the manifest and, if download completed successfully, `model-download-check.json`. It does not include downloaded weights.

This stage does NOT load weights into a detector or run inference. Additional dependencies were installed and their imports/configuration checked in Colab; local tests alone do not establish those imports. This test does not modify or transfer PDFs.

The base environment section below installs and verifies Python 3.9.25, PyTorch 1.10.0+cu111, torchvision 0.11.1+cu111, and Detectron2 0.6. That base section alone does not install LayoutLMv3; the additional workflow above does install it and download its weights. Neither processes PDFs. The Colab kernel remains intact. The installer retains setuptools 80.9.0 because old PyTorch needs pkg_resources.

## Preparation without a GPU

From Ubuntu WSL:

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
python3 -m unittest discover -s code/layoutlmv3 -p 'test_*.py' -v
colab usage
colab sessions
```

Tests do not install packages, invoke Colab, or require a GPU.

## Execution, only after resource use is authorized

Execute step by step. Review existing sessions before creating one. If nasa-layout-env already exists, check it with colab status and do not create another or stop a session belonging to other work. Rates are checked after resources are allocated. Request a T4 for this initial environment; the minimal operations do not require an A100.

```bash
colab new -s nasa-layout-env --gpu T4
colab status -s nasa-layout-env
colab usage
colab upload -s nasa-layout-env code/layoutlmv3/setup_env.py /content/nasa_setup_env.py
colab upload -s nasa-layout-env code/layoutlmv3/cli_job.py /content/nasa_cli_job.py
```

Launch the transferred file through runpy: this preserves __file__ and avoids relying on colab exec -f to synchronize other files or define that variable.

```bash
printf '%s\n' 'import runpy, sys; sys.argv=["/content/nasa_cli_job.py"]; runpy.run_path(sys.argv[0], run_name="__main__")' \
  | colab exec -s nasa-layout-env --timeout 1800
```

Initial downloads may take time. A timeout does not confirm that the remote process has stopped: check its status before retrying or closing the session. Do not launch two installers concurrently.

## Recover results, including after installer failure

Before executing this block, wait until `Respaldo remoto:` appears in the output. The process packages diagnostics when it finishes, even if the installer returns an error. Recovery is not guaranteed if the VM disconnects or dies. If upload fails, correct it before executing.

```bash
RUN_DIR="code/results/layoutlmv3-env/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"
colab download -s nasa-layout-env /content/nasa-layoutlm-setup.zip "$RUN_DIR/setup.zip"
colab download -s nasa-layout-env /content/nasa-layoutlm-setup.sha256 "$RUN_DIR/setup.sha256"
python3 code/layoutlmv3/verify_download.py "$RUN_DIR/setup.zip"
```

The verifier checks the ZIP's SHA-256 and CRC, then installer status. If it reports failed installation but verified integrity, diagnostics have been recovered: inspect setup-console.log inside the ZIP; do not claim that the environment works. If integrity fails, download again before stopping.

After recovering and checking results, stop only the session created for this work:

```bash
colab stop -s nasa-layout-env
colab sessions
colab usage
```

## What is retained

The ZIP contains configuration, version lists, and logs. It does not contain the virtualenv, Python interpreter, PDFs, models, or results stored outside /content/nasa-layoutlm-state. The environment is rebuilt on each VM; this first adaptation does not promise offline or automatic restoration of all files. Closing the VM deletes /content.

The complete wheel cache is optional: setup_env.py accepts --cache-wheels. The normal launcher does not enable it, to avoid duplicating several GB of downloads. If manually enabled, it is included in the ZIP and must be downloaded before closing. A future restoration requires transferring verified snapshot.json and wheelhouse to the state directory before executing the installer. Transitive versions are recorded after resolution; without a snapshot, two installations may differ.

## Verification scope

Local tests verify file recovery and validation. Base versions and the additional installation were verified in Colab in the documented execution. A new VM must rebuild and check the environment. Wheel availability, downloads, driver compatibility, and Internet access may prevent installation. It does not compile Detectron2 against CUDA 13; it uses the historical PyTorch/CUDA 11.1 wheel within a separate environment.

Sources used for the original configuration:

- https://detectron2.readthedocs.io/en/latest/tutorials/install.html
- https://github.com/microsoft/unilm/tree/master/layoutlmv3
- Installed google-colab-cli 0.7.4 help shared by the user.

Launcher update (October 18, 2026): packaging and recovery are now implemented. `code/layoutlmv3/test_page.sh NOMBRE_SESION` runs the full trial on an existing authorized session, without creating or closing it. It includes automatic reconstruction of the new VM's environment and download/verification of the page backup. Package `code/packages/layoutlmv3-page.zip`, approximately 3.8 MiB; 22 local tests passed and Bash syntax is valid. **Current next step: authorize/allocate a T4 and run that launcher**; actual inference remains unverified. Do not request the local checks again to recover context.

```text
inference/
├── __init__.py
├── render.py
├── detector.py
├── outputs.py
└── run_page.py
test_inference.py
```
