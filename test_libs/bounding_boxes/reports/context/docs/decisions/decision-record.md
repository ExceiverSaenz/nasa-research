# Decisions for comparing bounding boxes in SiC papers

> **Document role: Decision record.** Original statements retain their stage-specific scope. See [current status](../overview/current-status.md) for current completion and pending validation.

Date: October 31, 2026.

This report consolidates the agreements from the conversation to justify the selection of tools for detecting and delimiting document elements. The experiment will compare direct outputs through visual review, matches between tools, counts, computational cost, and failures. There is no independent reference data or selected winning tool.

## Agreed objective and scope

These four configurations will be compared:

1. Heron.
2. Heron-101.
3. MinerU Basic.
4. MinerU Standard.

The objective is to detect, delimit, and classify the elements in the papers: text, titles, tables, figures, captions, equations, and all other categories returned by each configuration. Particular attention will be paid to boxes that mix elements and to elements that are not correctly identified.

Reading order is a later aim of the project, but **will not be measured in this experiment**. The future intention is to insert figures and tables into the text flow; only boxes, labels, and direct relationships relevant to the multipanel requirement are examined here.

**All pages of all papers in the SiC collection** will be processed and visually reviewed. The specific PDF list, their hashes, and the total page count will be fixed before execution; they will not be inferred from the project's historical figures.

## Execution and preservation of results

| Decision | Agreement |
| --- | --- |
| Environment | Google Colab with an A100 GPU, following the project's operational Colab/R2 configuration. |
| PDFs | SiC papers obtained from R2. |
| Repetitions | One run per configuration on the agreed set. |
| Parameters | Start with official default values, documented and fixed for all papers. |
| Versions and weights | Record and pin their specific identities before execution. The experiment's revisions have not yet been selected. |
| Outputs | Evaluate what each tool returns directly and preserve its original results. |
| Destination | `test_libs/bounding_boxes/`, within the project. |
| Final choice | The user will decide how to weigh visual quality, time, and resources after observing the results. |

Panels, labels, and associations will not be completed through custom rules as part of the evaluated output. Any coordinate transformation used for drawing or comparison must preserve geometry and keep the original output separate.

Heron and Heron-101 are layout detectors; Basic and Standard are levels of a parsing pipeline. Their usefulness for the task will be compared, explicitly stating what work each measured time includes. Full pipeline time will not be presented as detection-only time.

## What will be observed and measured

| Comparison | What it reveals | Limitation |
| --- | --- | --- |
| Overlay boxes on pages | Review apparent omissions, clipping, excess area, and mixing. | Visual review is not a preexisting independent reference. |
| Compare matches between tools | Locate agreements and discrepancies. | Agreement does not demonstrate correctness; they may share errors. |
| Count detections by category | Locate differences that require review. | More boxes do not imply a better result. |
| Examine fragmentation and merging | Record one box versus several in the same region. | Do not automatically penalize a different partition. |
| Compare boxes and labels separately | Distinguish geometric discrepancy from different classification. | Requires defining correspondences and criteria before computing matches. |
| Measure time, memory, and failures | Describe observed cost and operational stability. | One run cannot estimate variability between repetitions. |

Time, RAM, GPU memory, and failures will be recorded. Preparation, downloads, model loading, and inference will be distinguished in the timing record. Memory sampling and the measurement instrument still need to be specified.

Without an independent reference, **accuracy, recall, and mAP will not be reported as quality metrics**. Overlap between predictions measures geometric agreement, not accuracy against reality.

## Agreed visual review and viewer

The viewer must show the four outputs side by side, synchronized by paper and page, and allow boxes from each tool to be enabled or disabled on the same page. Each tool's specific name will be visible; review will not be blind.

The review will combine problem categories and freeform observations:

- Mixing different elements in one box.
- Apparent omission.
- Content clipping.
- Excess included area.
- Duplicate.
- Fragmentation of one element into several boxes.
- Merging several elements into one box.
- Incorrect label.

Information not provided will be distinguished from information provided incorrectly. Anything a tool does not report will be marked as **unknown/not reported**; it will not be silently inferred.

## Labels and dimensionality

All original labels will be preserved, including those beyond text, table, figure, and equation. Dimensionality is reserved for later analysis: for example, a region could be text by content and a title by function. That analysis will not replace or correct the tool's original label.

A single text unit among line, paragraph, and block was not agreed upon. Each tool's output granularity will be preserved, and differences will be recorded. The common category mapping and handling of equivalences remain to be defined.

Equations within paragraphs are part of the objective and need **their own boxes**. An output including a formula as text or as an `equation_inline` span does not establish that it provides a separate box for it.

## Multipanel figure requirement

A box is needed for each panel, for example (a), (b), and (c), preserving its relationship to the complete figure and shared caption. Detecting only the complete figure does not satisfy this objective.

The following will be reviewed separately:

1. Panels separated, omitted, clipped, or merged.
2. Identifiers recognized and linked to their panels. Reading the text `(a)` without linking it does not count as an association.
3. Preservation of the complete figure.
4. Explicit panel–complete figure relationship.
5. Explicit relationship to the shared caption.

Extending this requirement to table cell hierarchies or text line and paragraph hierarchies was not agreed upon.

## Documentary findings about the tools

These findings come from documentation and code consulted during the conversation. They are not inference results on the SiC papers. The consulted branches may change and do not replace the specific revision that will be pinned for execution.

### Categories

Heron and Heron-101 publish the same 17 labels: Caption, Footnote, Formula, List-item, Page-footer, Page-header, Picture, Section-header, Table, Text, Title, Document Index, Code, Checkbox-Selected, Checkbox-Unselected, Form, and Key-Value Region. Their direct output contains boxes, labels, and scores. [Heron](https://huggingface.co/docling-project/docling-layout-heron), [Heron-101](https://huggingface.co/docling-project/docling-layout-heron-101).

In MinerU, Basic corresponds to the internal medium effort and Standard to high. Both use local layout; Standard incorporates VLM extraction. [Tiers](https://github.com/opendatalab/MinerU/blob/master/mineru/parser/tier.py), [PDF stages](https://github.com/opendatalab/MinerU/blob/master/mineru/backend/analysis/pdf/window.py).

The CSV distinguishes the 25 classes of MinerU's internal detector, the 16 main types in the Middle JSON contract, the 13 visual child types, and the inline types. **A catalog supported by the schema does not demonstrate that every tier emits all those types**, or that all appear in the SiC papers. Actual emission by configuration remains to be observed. [Detector](https://github.com/opendatalab/MinerU/blob/master/mineru/model/layout/pp_doclayout_v2_base.py), [schema](https://github.com/myhloli/DocVortex/blob/main/src/docvortex/schema.py), [output contract](https://github.com/opendatalab/MinerU/blob/master/docs/en/reference/output_files.md).

### Multipanel support

| Tool | Separation and identifiers | Complete figure and shared caption |
| --- | --- | --- |
| Heron | May produce separate Picture boxes, but has no panel class. Does not transcribe identifiers. Actual separation remains to be observed. | The direct model returns no hierarchy or Caption associations. |
| Heron-101 | Same interface and explicit support limitations as Heron; this does not imply equal performance. | The direct model returns no hierarchy or Caption associations. |
| MinerU Basic | May produce separate image/chart regions. No structured identifier–panel association was found. | The schema allows a visual's body and captions; no explicit panel hierarchy with the complete figure and shared caption was found. |
| MinerU Standard | Uses local layout and VLM extraction; no specialized panel detector or structured association of panel identifiers was established. | Shares the schema; the complete required structure was not established. |

The Heron rows are based on their model cards. The MinerU rows are based on the PDF stages and schema linked above. The absence of an explicit structure is inferred from the reviewed schema; it does not mean that obtaining a box matching a panel is impossible.

In MinerU, postprocessing filters certain `figure_title` items contained in visual regions, and its comment mentions internal markers (a)/(b). This does not demonstrate that those texts disappear from all textual output. [Official filter](https://github.com/opendatalab/MinerU/blob/master/mineru/model/layout/pp_doclayout_v2_base.py).

`image_body` represents the visual body, not a child subfigure. Image children supported by the schema are the body and annotations. Complete direct support for figure → identified panels → shared caption was not found in any of the four configurations. Docling's additional features are not attributed to the Heron detectors. [Visual schema](https://github.com/myhloli/DocVortex/blob/main/src/docvortex/schema.py).

The MinerU 3.1.15 report about figure parts without their parent is historical evidence of one case, not a measurement of Basic/Standard in the experiment's future version. [Issue 5031](https://github.com/opendatalab/MinerU/issues/5031).

## Produced files and actual status

- Former `tool-categories.csv`: base documentary catalog; its nine columns are retained as the first nine columns of the canonical `tool-multipanel-categories.csv` after verified consolidation.
- `tool-multipanel-categories.csv`: preserves those columns and adds multipanel support, limitations, sources, and review date. It is the most complete CSV from this conversation.
- `categorias_librerias.before-*.csv`: backups preceding the updates.

The multipanel update was saved in a new file because the original CSV was locked by another application. The original did not receive those columns. Both CSVs were reread to check their four rows and the corresponding fields.

In this conversation, the runner and viewer have not been created, no Colab sessions have been started, no models have been downloaded, and no inference has been run for this comparison. Visual review has not been completed, and no tool has been selected either.

## Outstanding items to finalize the protocol

1. Pin exact versions, weights, and defaults, including input resolution, thresholds, and enabled options.
2. Freeze the inventory and hashes of SiC PDFs and confirm the page count.
3. Define each configuration's specific output to evaluate and check what geometry and relationships it preserves.
4. Define coordinate normalization, rotations, and traceability of each box to its original output.
5. Define label equivalences, matching criterion and threshold, and correspondences of one box versus several.
6. Specify time and memory instrumentation, count denominators, and recording of failures or incomplete pages.
7. Define a persistent format for observations and review states per page.
8. Design and implement the runner and viewer before execution. No specific implementation design was approved in this conversation.

No aggregate score, weighting, or automatic rule for choosing a winner was set. The final decision belongs to the user with the available results.

## Dependency investigation and preliminary checks

Expansion requested before drawing up the implementation plan. The four configurations must run sequentially within the same Colab A100 session. A single session does not require a single Python process or a single package installation.

### Identified languages and dependencies

Technical proposal pending selection of an approach: Python 3.11 for preparation, execution, result inspection, and tests; HTML, CSS, and JavaScript for the comparative viewer. The viewer can use already generated page images and SVG boxes, with no mandatory framework or Node.js in production. Its distribution format has not yet been chosen.

| Component | Required or candidate packages | Weights and resources |
| --- | --- | --- |
| Direct Heron | torch, torchvision, transformers, Pillow, safetensors, and huggingface-hub; requests for transport when applicable | docling-project/docling-layout-heron, including config and preprocessor |
| Direct Heron-101 | Same set; does not require another installation of the same libraries | docling-project/docling-layout-heron-101, including config and preprocessor |
| MinerU Basic | mineru[torch] and its transitive dependencies; includes accelerate, OCR, table and formula models, ONNX Runtime, and MinerU utilities | opendatalab/MinerU-4_models_torch: layout, OCR, formulas, and tables |
| MinerU Standard | The Basic installation plus a VLM engine: mineru-llama-cpp or vllm depending on the chosen approach | Additional VLM model; not another independent Basic bundle |
| PDFs and pages | pypdfium2 and Pillow, candidates already present in project receipts | Verified R2 PDFs; local references for identity only |
| Local R2 | S3-compatible signing; the project's transport can be reused after inspection. boto3 is an alternative, not a requirement | Permanent credentials in WSL; temporary requests for Colab |
| Resources and tests | psutil and nvidia-smi/NVML for instrumentation; pytest as a candidate for the automated suite | No additional evaluation models |

Heron uses RTDetrV2ForObjectDetection and RTDetrImageProcessor. Installing the full Docling, Detectron2, LayoutLMv3, or Table Transformer is not necessary for those two direct detectors. MinerU's transitive dependencies must be resolved and locked; the table is not an executable requirements.lock. [Official Heron model card](https://huggingface.co/docling-project/docling-layout-heron).

MinerU 4.0.12, already pinned by the project, was identified as a conservative candidate. Its official manifest requires torch >=2.7,<3 and transformers >=5.10.1,<6 for the torch extra. The full extra adds vllm >=0.19.1,<0.29 on Linux. The complete inventory of direct dependencies is in the official manifest; its transitive closure must also be resolved. [MinerU 4.0.12 packages](https://github.com/opendatalab/MinerU/blob/mineru-4.0.12-released/pyproject.toml).

For Standard with vLLM, that version's registry identifies opendatalab/MinerU2.5-Pro-2605-1.2B. For llama.cpp it identifies jinzhenj/MinerU2.5-Pro-2605-1.2B-GGUF and requires the Q8_0 model plus mmproj. Their revisions have not been downloaded or pinned for this experiment. Both Heron models also require revision and hash pinning before preparing weights. [Official model registry](https://github.com/opendatalab/MinerU/blob/mineru-4.0.12-released/mineru/model/registry.py).

### Reuse and environment alternatives

The preserved a100-v2 receipt declares Python 3.11.16, Torch 2.7.1+cu126, torchvision 0.22.1+cu126, Transformers 5.10.1, MinerU 4.0.12, mineru-llama-cpp 0.2.0, DocVortex 0.6.7, pypdfium2 5.14.0, Pillow 12.3.0, huggingface-hub 1.33.0, accelerate 1.15.0, and safetensors 0.8.0. It does not declare vllm. It is a historical environment receipt, not evidence of an active VM or new compatibility.

A specific conflict was identified: vllm 0.19.1 declares torch==2.10.0 and torchvision==0.25.0, incompatible with the preserved bundle's Torch/torchvision pins. That package must not be added to that sealed environment. This verifies that specific candidate; it does not characterize all vLLM versions. [Metadata published on PyPI](https://pypi.org/pypi/vllm/0.19.1/json).

Alternatives considered before the two-environment decision:

1. Keep a shared candidate environment with the preserved pins and Standard through llama.cpp. Reduces dependency changes; requires verifying GPU acceleration and performance of that build. Installing the package is not presumed to guarantee A100 use.
2. Prepare a new joint environment compatible with vLLM, with its own lock. It can use the recommended engine for NVIDIA, but replaces the candidate base and requires checking both Heron models with the new closure.
3. Use two separate Python environments within the same A100 session and sequential processes. Isolates conflicts, although it duplicates some dependencies and requires more disk space/preparation.

The initial recommendation to investigate a shared environment first was superseded by the user's explicit choice indicated at the end of the report. Do not automatically change engines after observing results. The engine, quantization, and backend are part of the experimental configuration and its cost.

MinerU's auto selection depends on the available modules and device: on Linux with a GPU it may choose vLLM if installed, otherwise another engine. Therefore, the resolved engine must be recorded and fixed for all papers. [Candidate version's VLM selector](https://github.com/opendatalab/MinerU/blob/mineru-4.0.12-released/mineru/model/vlm/selector.py).

### Proposed contract for preliminary tests

Persistent automated tests are not yet implemented. They must distinguish PASS, FAIL, and NOT_RUN; a test that cannot be run does not count as passed.

| Timing | Necessary checks |
| --- | --- |
| Before allocating GPU | Colab CLI and authentication, local PDF inventory, R2 HEAD access per object and a test GET, PDF identity, candidate and dependency metadata review, caches/bundles, and transport space |
| Upon entering the session | Actual A100, RAM/VRAM/disk, system and architecture, Python/ABI, drivers, R2 access through temporary requests, and access to package/model repositories |
| Before installing | Actual versions of the chosen interpreter, pip check, imports in separate processes, lock/host compatibility, and wheel/cache hashes; distinguish reusable, missing, corrupt, and incompatible |
| Before downloading weights/PDFs | Identity and SHA256 of existing files; download only missing/corrupt files through an explicit flow, without deleting preserved caches or accepting presence as integrity |
| After preparation | Real imports, CUDA and torchvision operation, RT-DETRv2 classes, local loading of both Heron models, official MinerU model verification, and effective VLM engine |
| Before running the collection | Explicit minimal test of each configuration on one page, separate from the benchmark; output contract, valid labels and coordinates, preservation of originals, local result writing, and reading by the viewer |
| Between configurations | Process termination, verified GPU release, absence of residual workers, unchanged environment, and preservation of previous results |
| Offline tests | Installer not run if everything is valid; rejection of corrupt cache/incompatible version; R2 error or expired URL stops the phase; timeout does not trigger an automatic new session; viewer preserves geometry and shows unknowns |

A check without inference does not guarantee that a model runs. The minimal inference test and CUDA operation belong to an explicit later phase; they were not performed now. The specific sequential order and warmup rules remain pending. Downloading weights, installing, or testing one page must not be mixed with measured inference time.

Do not reinstall everything by default. First inspect, then validate, and only then prepare what is missing. An incompatible environment is not patched on the fly: it is reported and resolved before the collection. Permanent credentials will not be copied to Colab, the viewer, or receipts; signed URLs will not be recorded either.

### Checks actually performed

Temporal evidence: the R2 response was dated 2026-11-01T00:19:53Z, corresponding to October 31 in the user's timezone.

| Check | Result and scope |
| --- | --- |
| Local inventory | 15 PDFs present in papers/SiC_papers. Pages were not recounted. |
| Existing WSL | Ubuntu-22.04 available. Its system Python is 3.10.12; it is not equivalent to Python 3.11 in the preserved Colab environment. |
| Colab CLI | 0.7.4 available; help works and an authenticated session query succeeded, with no active sessions at that moment. It was not updated and no session was created. |
| R2 configuration | File present in WSL; necessary fields available. No keys were displayed. |
| R2 HEAD | HTTP 200 for all 15 PDFs; sizes match local files. Does not imply a full hash of the other 14 objects. |
| R2 GET of 12.pdf | 4,874,584 bytes downloaded into memory; PDF header and SHA256 match the local original. |
| WSL Python packages | The probed packages were not found in system Python: boto3, botocore, torch, torchvision, transformers, mineru, vllm, huggingface-hub, Pillow, pypdfium2, psutil, and pytest. This is not an audit of all environments or a reason to install them locally. |
| Previous bundle | Its manifest and receipt were read; not all its files/hashes were revalidated, and it was not restored. |
| GPU, inference imports, and models | NOT_RUN; there is no A100 session for this experiment. |
| R2 from Colab | NOT_RUN; the tested access is from WSL. |

The R2 probe used HTTPS and S3 SigV4 signing through the standard library, without installing boto3, writing objects, or saving new PDFs. Objects were verified by name, without requiring bucket listing permission. [R2 S3 compatibility](https://developers.cloudflare.com/r2/api/s3/api/).

A systemd user-session warning appeared during the WSL checks; the subsequent queries indicated above did complete. No services were modified. The Obsidian CLI rejected the script inventory query because Obsidian was unavailable; no vault review was claimed, and operational scripts dependent on that inventory were not opened or run. The investigation continued with README files, manifests, and receipts outside the vault.

There is still no guarantee of a functional joint environment, persistent preflight suite, runner, or viewer. This expansion documents requirements, alternatives, and real infrastructure probes to decide the approach before the plan.

## Current isolation decision for implementation

The user chose **two isolated Python environments within the same Colab A100 session, with vLLM for MinerU Standard**. This choice supersedes the shared-environment and llama.cpp alternatives for Standard. The four configurations will run sequentially, without sharing inference processes between tools.

Distribution proposed by the implementer to make that choice concrete:

- Environment A: Heron, Heron-101, and MinerU Basic, with a candidate Python 3.11 base and the preserved compatible pins.
- Environment B: MinerU Standard with vLLM, with an independent lock and Torch/torchvision compatible with the pinned vLLM. Do not modify environment A to satisfy B.
- Share only input files and artifact caches whose identity is verified; sharing a cache does not mean sharing site-packages or models loaded in memory.
- Proposed order: Heron, Heron-101, MinerU Basic, MinerU Standard. Each stage uses its environment's absolute interpreter and a new process.

Each configuration's official default parameters remain fixed for all papers; the Torch backend and vLLM engine will be recorded explicitly. There will be no silent engine fallback or GPU-to-CPU fallback. Dependency resolution, weight revisions, and remote checks remain pending.

The requested plan is in `implementation-plan.md`, alongside this report. Preparing the plan does not start Colab, install dependencies, or run the collection. The next step is to review the plan before implementing it.

## Local implementation and preliminary tests

After approving the plan, the user authorized implementation and testing, while retaining the prohibition on starting the A100 or running the collection. Contracts, reuse gates, local/R2 preflight, normalization, agreement between predictions, a sequencer with injectable services, lazy adapters, a worker, output aggregation, and a viewer with persistent reviews were implemented. Local entry point: `run.py`; current instructions and limitations: `README.md`.

Verified results from this phase:

- 41 offline tests passed; failures were observed before implementing or correcting the behaviors. They include corrupt hashes, no reinstall when valid, pending gates, geometry errors, native relationships, timeout without retries, persistence, atomic review, and transport/models without implicit effects.
- Fresh local inventory: 15 PDFs and 397 pages. Receipt: `runtime/local-preflight.json`.
- Implemented R2 preflight run from WSL: 15 successful HEAD requests with matching size and GET of 12.pdf with correct PDF/SHA256 identity. Receipt: `runtime/r2-preflight.json`.
- Locks A and B resolved with existing uv, hashes, and target Python 3.11/Linux x86_64/glibc 2.39. Receipt: `runtime/dependency-resolution.json`. Those environments were not installed; resolving dependencies does not validate imports or CUDA.
- Three preserved wheels were verified against the a100-v2 bundle; the jieba wheel with SHA256 85b492b77ca63d22fafb41c71fe019d027de17349620e1ab41d0194803273a87 was reused. The original bundle was kept intact.
- JavaScript syntax verified with existing node and viewer built on an explicitly marked synthetic fixture, without processing papers. There was no browser visual QA or Playwright testing.

Independent code review found issues with gates, reuse, native nesting, and persistence; their corrections were checked with tests. The technical record is in `IMPLEMENTATION_LEDGER.md`.

The complete plan **remains partially implemented**: integrating Colab transport with prepare/smoke/execute in the CLI, completing coverage of auxiliary model files, moving Heron loading into the stage lifecycle, verifying instrumentation per process, and running browser tests are still outstanding. Basic transport already exists with offline tests. Revisions and hashes for both Heron models and the Standard VLM were pinned through official metadata and small JSON files; weights were not downloaded. Real adapters require a later Linux/A100 smoke test; imports, model loading, R2 from Colab, and CUDA remain NOT_RUN. `experiment.json` retains `ready=false` to block premature execution. No session was created, and no inference or collection was run in this phase.

## Continuation of Colab integration and viewer tests

At the user's request, implementation continued while retaining the prohibition on starting A100 or running the collection. This section supersedes the previous phase's inventory of outstanding implementation work; it does not change the experimental agreements.

The `colab plan`, `prepare`, `smoke`, and `execute` phases were integrated. The first is descriptive only. The others require explicit authorization and phase-specific gates: R2 and authentication before allocating a single session, two isolated environments inspected before installation, models verified before downloading missing files, one smoke page per tool, and measured A/A/A/B sequence. A timeout or uncertain phase preserves the attempt in manual_review without automatic retries, closure, or new allocation.

The future flow verifies transfer hashes, locks, inventory, and snapshots; it requires native page and file coverage before closure. It downloads original outputs and environment, preparation, smoke, and execution receipts; builds the viewer, and only then closes the session if delivery is verified. Permanent credentials are not transferred; temporary signed requests are kept separate from code and results.

The pinned VLM's chat_template.jinja and merges.txt auxiliary files were completed, and the Linux uv bootstrap was identified by SHA256 in case a future VM lacks Python 3.11. Those weights were not downloaded, and no inference environment was installed. Heron now reuses one load per process/stage across papers. The snapshot bridge uses MinerU 4.0.12's completeness API without modifying its packages or writing manual markers; that compatibility requires a later remote smoke test.

For the viewer, installed Chrome was reused and Playwright 1.58.0 was prepared in a local development folder. The four views and names, layers, label filter, zoom, navigation, selection, SVG/image geometry, and persistent review with export/import were tested in a real browser. A synthetic screenshot was visually reviewed. No real papers were used, and this does not establish visual QA of their collection.

The complete remote cycle was tested with simulated transport: exactly one creation, phases in order, preservation of attempts on failure, download verification, and closure only after validating results. An independent review identified and enabled corrections to the pinned MinerU's configuration API, prior R2 verification, returned provenance, and page coverage. The final count and receipts are in `runtime/tests-with-browser.xml` and `runtime/integration-validation.json`.

No A100 session has been started, and no real inference, smoke test, or collection has been run. CUDA/vLLM, imports in remote environments, weight loading, R2 from Colab, and operational bootstrap compatibility remain NOT_RUN. `ready=false` records this lack of validation; commands with effects require their explicit flags and phase receipts. Human review of all pages remains pending.

## Real smoke test authorized and completed

The user authorized a single A100 session, preparation of both environments, and running one page with the four tools, without running the collection. When asked about closure, the user chose **to close after downloading and verifying the smoke test**.

Only `bbx-8456b0df1ca4487f9df41dc433ab3544`, attempt `smoke-20261101T011229Z`, was created. The first page of `1.pdf` was used; the complete PDF was downloaded from R2, and its size and SHA256 matched the inventory. A one-page PDF was derived for each worker. The collection's other pages were not processed.

Environments A and B passed isolation, lock, pip check, and imports. A used Torch 2.7.1+cu126/CUDA 12.6; B used Torch 2.10.0+cu128/CUDA 12.8 and vLLM 0.19.1. Both successfully ran matmul and NMS on GPU. Standard initialized a V1 LLM engine on CUDA, loaded the pinned VLM weights, and used FlashAttention. The verified jieba wheel and locks were reused; venvs and weights missing from the new VM were prepared and verified before use.

**Heron, Heron-101, MinerU Basic, and MinerU Standard finished with PASS and native one-page coverage.** The downloaded ZIP has 4,829,399 bytes and 49 evidence files plus a manifest, with verified hashes. Original outputs, logs, metrics, and receipts were preserved. The session was then closed, and Colab confirmed that no active sessions remained.

Preserved incidents: a local PATH check failed before resource allocation, and execution continued with the existing CLI's absolute path. A CUDA probe sent during preparation exceeded the client's wait; afterward, A's result was reused and B was verified. No other VM was created, and model inference was not repeated because of these incidents.

The result supersedes previous NOT_RUN states only for this smoke test. It does not validate box/label accuracy, panels, or captions; it does not establish the complete collection or general capability in 6 GB. Detector and parsing times have different scopes, and Standard includes initialization/compilation; they must not be used as a ranking.

Complete operational source: [smoke report](../../reports/execution/smoke-20261101T011229Z/smoke_report.md), [verification](../../../../raw_results/code/smoke-20261101T011229Z/verification.json), and [final status](../../../../raw_results/code/smoke-20261101T011229Z/final-status.json). The input configuration's `ready=false` state is preserved as part of the attempt's original identity; it does not represent authorization to run the collection. Evidence of real operation is in the attempt's receipts.
