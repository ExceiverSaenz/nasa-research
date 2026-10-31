# Paper Processing: Colab, Parsing, and Reconciliation

`new_code` brings together environment setup, weight and PDF downloads, the
hybrid parser, and reconciliation. Its operational source code runs without `code/`,
notebooks, or legacy packages. Originals and previous results are preserved.

## Structure

```text
new_code/
  colab_run.py                     local Ubuntu/WSL controller
  automation/
    colab_worker.py                remote phases and explicit success confirmation
    selection.py                   selection and transfer of original evidence
    integrator_bundle.py           local validation of integrator bundles
    README.md                      automation details
  setup_environment.py             install, check, export, or reuse the environment
  setup_models.py                  download pinned weights and generate runtime JSON/YAML
  prepare_papers.py                sign R2 requests and download verified PDFs
  requirements.in                  combined candidate; not a lock file
  model_manifests/                 revisions, sizes, and SHA256 for the three models
  parse_system/                    hybrid parser; entry point: run.py
  reconciliation_system/           integration; entry point: run.py
  inputs/                          PDFs downloaded on the execution machine
  runtime/
    environment/                   example environment installed on the VM
    bundle-inputs/                 input bundles extracted on the VM
    environment-bundles/           preserved bundles, including a100-v2
    colab-bundles/                  bundles exported by the automation
    colab-attempts/<id>/            controller state, logs, receipts, and local transport
    model-cache/                   verified weights by model and revision
    models-config/                 configuration generated on the VM
    pip-cache/                     package cache
    setup-<date>-<id>/              installer logs and state
  results/
    parse_results/<attempt>/       parser results
    reconciliation_results/<attempt>/ integration results
  visualization/
    build.py                       local build from verified results
    viewer.html                    responsive template for the four views
    index.html                     parser comparison and integration for 12.pdf
    verification.json              hashes, checks, and viewer limitations
    README.md                      visualizer usage, rebuilding, and tests
```

The local original PDFs are outside `new_code`, in
`../papers/SiC_papers/` and `../papers/Tensile_Properties_of_Sub-sized_Specimens_papers/`.
The automated controller selects only the SiC collection.

[Automation](automation/README.md) · [Parser](parse_system/parsing/unified/README.md) ·
[Reconciliation](reconciliation_system/README.md).

## Run from Ubuntu/WSL: Parser, Integrator, or Both

Local requirements: Python 3 compatible with the scripts, an authenticated Colab CLI,
the reference SiC PDFs, and configured R2 credentials. From the project root:

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"

# Menu: 1 parser, 2 integrator, 3 both; then 12, 1 3 12, or all.
python3 -B new_code/colab_run.py

# Direct selection.
python3 -B new_code/colab_run.py --papers 12
python3 -B new_code/colab_run.py --papers 1 3 12
python3 -B new_code/colab_run.py --all

# Integrator: one paper, a group (--papers 1 3 12), or the entire folder (--all).
python3 -B new_code/colab_run.py --mode integrator --parse-run 20261030T021637Z-a2ba8ca7 --papers 12

# Parser and integrator in the same session.
python3 -B new_code/colab_run.py --mode both --papers 12

# Check the selection and bundle before creating a VM.
python3 -B new_code/colab_run.py --papers 12 --plan
```

`12` selects `12.pdf`. In `parser`/`both`, `--all` selects the local reference
SiC PDFs; in `integrator`, it selects all papers in the chosen folder.
Each run creates a **new A100 session** with a unique name and transfers a snapshot
of the current code with hashes. It excludes runtime files, results, inputs, and Python caches.
The controller installs or restores the environment for the selected profile. Only `parser` and
`both` prepare weights and run the three engines; `integrator` consumes saved
evidence. PDFs are retrieved from R2, and outputs are downloaded and verified.
In integrator mode, only the selected papers' files and the original metadata
are transferred; PDFs are downloaded from R2 and verified using SHA256.
The source attempt's JSON files are not modified. [Options and controls](automation/README.md).

Parser results are saved in `results/parse_results/<id>/`; integrator results
are saved in `results/reconciliation_results/<id>/`. In `both` mode, both outputs
share the same ID and are verified before the session is closed.
The controller's supporting files remain in `runtime/colab-attempts/<id>/`;
no `results/colab_runs` folder is created.

The session is closed after all requested outputs and their downloads have been verified.
To keep it open, add `--keep-session`. For both stages, use `--mode both`.
On errors or timeouts, the controller neither retries nor closes a potentially active VM.
Check the local state and `colab sessions` before starting another attempt:
a client timeout does not prove that the remote process has ended.

## Environment Setup and Reuse Without Unnecessary Rebuilds

The controller selects a profile: `parser` uses the parser requirements;
`integrator` uses the reconciliation requirements; `both` uses `new_code/requirements.in`.
Each profile installs its dependency closure, not the other profiles' lists.
The integrator does not prepare weights or compile Detectron2/CUDA. The commands above
without `--mode` and with `--papers`/`--all` continue to use parser mode.

Before allocating the A100, the controller searches for bundles in `runtime/colab-bundles/`
and `runtime/environment-bundles/`, including `a100-v2`. It checks SHA256, contents,
expanded requirements, receipts, current pins, and Detectron2 build identity.
The current signature takes priority, but a different bundle name does not prevent reuse
if it passes the selected profile's checks. In Colab, compatibility with
Python, Ubuntu, glibc, and the architecture is also validated before installation;
profiles that run the parser also check GPU/ABI compatibility and the Detectron2 build.

A complete, compatible bundle avoids dependency resolution. For parser/both, it avoids
recompiling Detectron2 and installing CUDA build tools. It uses the lock file with hashes
and `--no-deps`; large packages are downloaded directly in Colab.
A `.venv` is not copied between machines.
Without a dedicated parser bundle, a compatible combined build can supply only the
verified Detectron2 wheel while the parser's minimal requirements list is resolved.
If no compatible artifacts are available, a new environment is installed and a bundle
is exported for subsequent sessions. Previous bundles are preserved.

Adding, removing, or changing libraries in `requirements.in` is detected before
the environment is reused. New libraries must be declared there; they are not inferred
from imports. Changes to the rest of the code update the transferred snapshot without
requiring compatible dependencies to be rebuilt. Current validations still apply.

On the VM, the controller checks for an existing valid extracted bundle, a complete
environment, and valid weights/configuration before repeating their preparation.
An incomplete or incompatible environment requires review; it is not silently modified.
Do not add packages to an environment after publishing its fingerprint.

Parser profiles use Python 3.11.16, Torch 2.7.1+cu126, and the pinned Detectron2
build; they require Ubuntu 22.04/24.04 x86_64 and NVIDIA access. If compilation is needed,
the installer installs CUDA Toolkit 12.6 without requesting an NVIDIA driver.
`MAX_JOBS=2` is the default build setting. The installer preserves logs and emits
periodic status updates.
The `integrator` profile uses Python 3.11.16 with the Docling/PyMuPDF pins, validates
its own receipt, and does not prepare models or build Detectron2. The pinned
Docling distribution includes Torch and CUDA packages as transitive dependencies;
this does not mean running models or performing the APT step that installs CUDA Toolkit 12.6.

System prerequisites are obtained from the already configured official Ubuntu
sources, preserving signature and hash verification. Input bundles are extracted into
`runtime/bundle-inputs/`, separately from new exports. Each remote phase
must emit explicit success confirmation: Colab CLI may return exit code
zero even when Python has displayed an exception. A failure is left for review,
without automatic retries or overwriting its evidence.

Closing Colab loses `/content`: the installed environment, weights, and caches
on that VM. The local bundle preserves reusable lock files and wheels, not the entire
installation or the weights. A new VM still needs to download and install anything missing.

## Frozen Weights and PDFs from R2

`setup_models.py` downloads the pinned revisions of LayoutLMv3, Table Transformer,
and MinerU directly from Hugging Face. `model_manifests/` declares files, sizes,
and SHA256 hashes. Weights are stored in `runtime/model-cache/`; valid files are reused,
and partial downloads are preserved for resumption. The generated configuration points
to those paths. `parse_system` does not include a local `models/` weights folder.

On Ubuntu/WSL, `~/.config/nasa-research/r2.env`, with permissions set to 600, contains:

```dotenv
R2_ENDPOINT_URL=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
R2_BUCKET=papers
R2_PREFIX=sic_papers/
AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_SECRET_ACCESS_KEY
```

Use the exact Cloudflare endpoint, including its jurisdiction if applicable,
without appending the bucket to the endpoint. Permanent keys remain in WSL.

The automation signs requests after preparing the environment and weights to
make full use of their one-hour validity period. Colab downloads from R2 and verifies
size, SHA256, and the PDF header. Temporary requests are deleted, and receipts retain
provenance without signed URLs or keys. Local originals serve as integrity
references; they are not transferred as a substitute for R2.

## Compact Parser Results

```text
results/parse_results/<attempt>/
  inputs.json
  configuration.json
  status.json
  manifest.json
  renders/<paper-id>/<page>/identity.json
  results/<paper-id>/<page>/
    layoutlmv3/                    detection JSON and metadata
    table_transformer/             detection JSON and metadata
    mineru/                        middle-native, regions, and model-native if available
```

Pages are rendered once at 200 DPI in temporary staging, and the three engines
share the image. The PNG is deleted once all three finish processing that page.
The following are preserved: PDF identity, physical page, dimensions, DPI, crop box,
rotation, PDF/pixel transformations, renderer, and the hash of the image used by the models.
No overlays, crops, or duplicate `native/` folder are generated.
A stalled renderer may leave temporary staging identified in the state
for review; it is not deleted while the renderer is still writing.

`manifest.json` (`parsing-hybrid-files/2`) records the inventory and SHA256 of every
persistent file, including configuration and state; it does not include itself.
`status.json` retains tasks, events, fingerprints, metrics, and errors. Each model's
outputs remain separate, without modifying the original text, boxes, or scores.

New attempts do not require a ZIP or sidecar. The TAR with SHA256 used by
the controller is only a downloadable transport artifact; reconciliation consumes the
folder and its manifest. Previous attempts using ZIP remain readable.

## Reconcile a Complete Attempt

For automated integration, use `--mode integrator` or `--mode both`.
On a VM with a combined environment kept open using `--mode both --keep-session`,
the manual entry point remains available from `/content/new_code`:

```bash
PYTHON="$PWD/runtime/environment/.venv/bin/python"

"$PYTHON" -B reconciliation_system/run.py preflight
"$PYTHON" -B reconciliation_system/run.py run \
  --parse-run "$PWD/results/parse_results/COMPLETE_ATTEMPT_NAME" \
  --output integration-attempt --workers 2
```

This requires a complete attempt, its valid manifest, and the original PDF accessible
with the declared hash. Paths in `inputs.json` refer to the execution machine;
a local download does not automatically convert `/content/...` paths into
Windows/WSL paths. Do not edit protected JSON files to change those paths.

Integration preserves provenance, verifies files, and writes a separate attempt
to `results/reconciliation_results/`. It supports geometry without persistent PNGs;
in that case, it produces data and an index without generating views that require images.
It does not automatically generate a ZIP and retains support for reading the legacy ZIP contract.
With the default manual entry point and in `both` mode, the receipt must match
the one used by the parser. Automated `integrator` mode validates its own receipt
for the minimal profile and separately records the source environment's hash.

## On-Demand HTML Visualization

The current viewer corresponds to attempt `20261030T021637Z-a2ba8ca7`:
[open HTML](visualization/index.html) · [verification](visualization/index.verification.json).
It includes 13 pages and 536 detections, model and category selection, search,
zoom, box details, available text, and provenance.

To build it explicitly from the project root, with PDFium/Pillow
installed in the local Python environment being used:

```bash
python -B new_code/visualization/build.py \
  --run new_code/results/parse_results/20261030T021637Z-a2ba8ca7 \
  --pdf papers/SiC_papers/12.pdf \
  --output new_code/visualization/index.html
```

Images are regenerated from the PDF and embedded in the HTML; no PNGs are added
to the parser attempt. The hashes of the 13 regenerated PNGs differ from those recorded
in Colab, although their dimensions match. Pixel equivalence and actual visual QA
have not been established. The viewer reports this difference; the source JSON files
were verified against the manifest and preserved unchanged.

## Tests and Evidence

`../tests/` is a development dependency, not a runtime dependency. It does not need
to be uploaded to Colab. From the project root:

```bash
python -B tests/run.py workflow --list
python -B tests/run.py workflow
python -B tests/run.py compatibility
python -B tests/run.py extended
```

[Testing guide](../tests/README.md). The suites distinguish the current workflow,
legacy compatibility, and optional algorithms/views. JavaScript tests
are run separately according to the viewer.

On October 29, 2026, local time, three real tests of `12.pdf`
were completed on an A100. The following identifiers use UTC:

| Mode | Attempt | Evidence |
| --- | --- | --- |
| Parser | `20261030T032958Z-ba150cdc` | [13 pages, 39 completed tasks, zero failures](results/parse_results/20261030T032958Z-ba150cdc/status.json) |
| Integrator | `20261030T035016Z-f35fc63e` | [Complete integration of the previous attempt](results/reconciliation_results/20261030T035016Z-f35fc63e/summary.json) |
| Both | `20261030T040105Z-4215756a` | [Complete parsing: 13 pages/39 tasks](results/parse_results/20261030T040105Z-4215756a/status.json) and [complete integration](results/reconciliation_results/20261030T040105Z-4215756a/summary.json) |

[Three-mode validation record](runtime/three-mode-validation-20261030.json):
transport artifacts, manifests, and hashes verified; sessions closed after
the tests finished. The actual receipts show MinerU/Detectron2 without Docling/PyMuPDF
in `parser`, and Docling/PyMuPDF without MinerU/Detectron2 in `integrator`.

The tests detected a collision between the input bundle and the new export,
and an inconsistent index in an NVIDIA repository that was not needed to restore
the environment. Bundle paths, remote success confirmation, and the scope of APT
were corrected. Failures and reviewed continuation runs were preserved within
the same sessions; inference was not repeated.
The preserved continuation scripts are evidence of those attempts, not an
automatic resume entry point for future sessions.

The recorded offline Windows run examined 151 tests, with one error and one
skipped test; it was not a fully passing suite. The affected test passed on
WSL. Fixtures and real tests have different scopes; consult the specific
receipts instead of replacing them with a generic claim of success.

## Pending Items

**Deferred by user decision:** investigate the `PermissionError: [WinError 5]`
when moving the downloaded temporary folder to its final destination in
`test_full_controller_then_reuse_without_real_colab`, a simulated Windows test.
The specific cause has not been determined: do not attribute it to antivirus software,
specific permissions, or open files without evidence. The same test passed on WSL,
and all three real cases completed; this does not prove that the Windows error
has been fixed. System permissions were not modified to resolve it.

The current controller requires Ubuntu/WSL and Colab CLI. Although computation takes
place in Colab, local transfers and storage are still involved and remain susceptible
to errors. If a delivery fails, preserve the state and review the backup
before starting another attempt; do not automatically repeat parsing/integration.
There is no guarantee that future sessions will not fail because of connectivity,
resources, or external repositories.

Semantic accuracy, human review, independent V&V, and actual visual QA
remain pending. These cases do not demonstrate generalization to all 15 papers or
capability on a 6 GB GPU. The historical collection artifact remains intact.
