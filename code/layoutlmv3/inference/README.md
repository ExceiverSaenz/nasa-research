# Single-page LayoutLMv3 inference

## 1. Purpose and scope

This folder contains the Python package `inference`, an experimental adapter for detecting the visual layout (*document layout*) of **one page of a scientific paper** using LayoutLMv3. It is part of `nasa_research`, whose document-processing objective is to locate PDF regions and preserve their provenance so that other tools can later extract their contents.

A region is a rectangle on the page associated with a category and detector score. For example, a `table` prediction indicates where a possible table is located; it does not return its rows, cells, values, or scientific units. Results are retained in JSON and shown on a copy of the image as an *overlay* for review.

### Parent project context

The `nasa_research` documentation places this work in the scientific-document *parsing* stage. The described collections concern SiC materials and tensile properties of small specimens. The project's [context and scope](../../../docs/contexto/01-contexto-y-alcance.md) prioritize avoiding omissions and incomplete crops, preserving traceability, and reducing manual corrections.

The documented final objective is local execution at no cost. The historical Colab T4 trial is an experimental exception: demonstrating feasibility on that VM does not establish feasibility, performance, or zero cost on the local computer.

This package implements a small trial to investigate LayoutLMv3 as a candidate before processing a collection. The [overall parsing design](../../../docs/arquitectura/02-arquitectura-del-parsing.md) also considers Table Transformer and MinerU, but their integration is conceptual and is not implemented in this folder.

### System under inspection

| Element | Meaning in this package |
|---|---|
| PDF and page | Source document and physical number of the selected page. |
| Render | RGB image of the entire page, produced before invoking the model. |
| Detector | Five-category visual LayoutLMv3 configuration, executed with Detectron2. |
| Checkpoint | Pretrained weights file; this package loads weights rather than training them. |
| Predictions | Boxes, categories, and scores after detector postprocessing. |
| Execution result | Exported files and execution status; this is not a quality evaluation. |

The configured candidate is `HYPJUDY/layoutlmv3-base-finetuned-publaynet`, revision `1c4d2cf657feafac1f53b6f92afe23b279d4f45b`. Its categories are `text`, `title`, `list`, `table`, and `figure`. The configuration is *image-only*: it receives the image without OCR words or boxes as input. This workflow must not be confused with token labeling, where word boxes are already supplied to the model.

### Responsibility boundary

The package renders one PDF page, constructs/loads the detector, and exports regions, an overlay, and traceability. It does not perform OCR, training, box merging, or extraction of internal table content. It also does not interpret material properties, values, or scientific units, or implement the complete data-curation pipeline.

Model download, environment preparation, packaging, and remote session operation belong to external components. `run_page.py` consumes prepared local files and coordinates a single page; it does not create or close a Colab session. Configurations and weights are not included in this directory.

### Example of the intended workflow

The selected trial uses `SiC_papers/12.pdf`, physical page 3. The renderer produces an RGB image at 200 dpi. The adapter prepares an input resized according to 800/1333, requests predictions, and retains their boxes in the original render's coordinate system. The exporter writes JSON and an image with boxes for human inspection.

This workflow describes the implementation and intended trial. It does not claim that the real detector has completed this workflow: the following section defines the available evidence.

### How to read the documentation

1. To understand the component, read sections 1–4 of this README.
2. To prepare an execution, consult requirements, inputs, and outputs in sections 5–6 and the parent project's status.
3. To evaluate a claim, consult the tests and evidence in section 7; always distinguish inspected code, test doubles, and the real detector.
4. To analyze a specific function, consult its docstring and the [canonical view by symbol](../../documentation/documentation-inference/views/documentation.md).

External JSONL records are the canonical source of contracts and evidence. This README provides introductory context, the package map, and navigation. Docstrings bring the relevant contract close to the code without replacing recorded provenance.

## 2. Status and validation limits

Documentation status as of October 19, 2026:

- **Implemented:** single-page rendering, detector construction and loading, prediction, and export of regions, overlay, and metadata. These operations' presence in the code does not establish complete execution with the real detector.
- **Available evidence:** actual local render and historical local test records, including tests with detector doubles. Installation and import/configuration checks on a Tesla T4 are also documented. Section 7 details evidence scope and paths.
- **Pending verification:** detector construction, actual checkpoint loading, and inference through this adapter with the real model. There is also no verified evaluation of region quality.
- **Version correspondence:** editing docstrings changed source hashes. Historical results correspond to earlier sources, linked through [source-state.json](../../documentation/documentation-inference/data/source-state.json); they are not automatically attributed to the current version. That record documents an AST comparison without docstrings, not a new test or detector execution.

The project was not executed and the historical suite was not repeated during this documentation update.

## 3. Map and navigation

| File | Responsibility, interface, and dependencies |
|---|---|
| __init__.py | Declares the package; importing it does not load the model. |
| types.py | RenderedPage, Predictions, LoadReport, and RunResult; NumPy/dataclasses; data for render, detector, outputs, and coordinator. |
| render.py | render_page: PDF/page/dpi → RenderedPage; pypdf/PDFium; no writes. |
| detector.py | LayoutLMv3Detector, compare_state_dicts, and file_sha256; config/weights/RGB → report/predictions; deferred PyTorch/Detectron2. |
| outputs.py | save_json, render_geometry, save_regions, save_overlay, and save_manifest; data → JSON/PNG; NumPy/Pillow. |
| run_page.py | run_page, parse_args, and main; coordinates inputs and new directory → RunResult/files. |
| __pycache__/ | [Generated cache](__pycache__/README.md); preserved bytecode, not evidence of execution. |

Canonical documentation: [external README](../../documentation/documentation-inference/README.md), [JSONL records](../../documentation/documentation-inference/data/records.jsonl), [view by symbol](../../documentation/documentation-inference/views/documentation.md), and [historical README](../../documentation/documentation-inference/views/historico-inference-20261019.md). This folder contains no configurations, launch scripts, or tests: consult the parent folder for those.

## 4. Workflow and shared contracts

Inputs → render → load → predict → export. Complete contracts appear in the canonical view (INF-002 through INF-008). Physical pages are one-based; dpi must be positive. RGB uint8 with shape (height, width, 3). PDF coordinates are in 1/72-inch points with a bottom-left origin; render coordinates are in pixels with a top-left origin. CropBox and rotation are part of the PDF-render matrices. UserUnit values other than 1 are rejected.

The detector requires 800/1333 input, image-only, RGB, and text/title/list/table/figure classes. It supplies original height/width to the model for postprocessing; it does not apply a second scaling. The manifest retains effective configuration. Strict compatibility compares keys and shapes, not quality or expected values.

## 5. Requirements and execution

The [render requirements](../requirements-page.txt) pin pypdfium2 5.14.0 and pypdf 6.10.0. The detector depends on the isolated environment described in [project status](../../../docs/continuidad/04-estado-de-la-prueba.md), including PyTorch/Detectron2 and vendor/models. Python 3.9 has a historical syntax check, not verified execution of this adapter; historical local tests used Python 3.12.14. Do not install the old stack into the modern kernel to recover context.

From code/layoutlmv3/, with the relevant dependencies available:

```bash
python -m inference.run_page --help
python -m inference.run_page --pdf ../../SiC_papers/12.pdf --page 3 --dpi 200 --output ../results/layoutlmv3-page/primer-ensayo
```

These are interface examples, not executions performed during this edit. --output must be new; --device accepts cuda or cpu, defaulting to cuda. Default config/checkpoint/model-config-dir paths start from code/; they can be overridden explicitly. --pdf and --page are required. --help may exit with 0, invalid arguments with 2; main returns 0 if RunResult.succeeded and 1 for failures it handles. Other errors may propagate.

The [external launcher](../test_page.sh) operates on an existing session; operational documentation is in [continuation](../../../docs/continuidad/05-continuacion-de-la-prueba.md). Do not execute it or allocate paid resources merely because this README was read.

## 6. Inputs and outputs

Inputs: readable PDF, physical page, dpi, cascade YAML alongside ditod, checkpoint, and a local directory containing config.json/download-manifest.json. The selected trial is SiC_papers/12.pdf, physical page 3 (printed page 157), rendered at 200 dpi. The historical local view measures 1654 × 2205 px; these are not universal dimensions.

| Generated file | Contents |
|---|---|
| render.png | Complete RGB render. |
| run-manifest.json | Identities/hashes, versions, geometry, configuration, and timings. |
| load-report.json | Parameter differences when a report is available. |
| regions.json | Identified regions with page, type, score, and XYXY box. |
| regions-raw.json | Arrays after filtering/NMS and postprocessing; not logits or earlier proposals. |
| overlay.png | Copy of the render with boxes, IDs, and labels. |
| page-status.json | completed/failed, stage, count, error, and timings. |
| error.log | Traceback of Exception caught within the stage block. |

Zero regions may be completed; a None count indicates that predict did not complete. A partial export fails. An existing directory is rejected, but save_json does replace files within an execution through .part. Diagnostics are not guaranteed if initial preparation or storage in except/finally fails. Recovery is not guaranteed if the VM is lost.

## 7. Tests and evidence

[test_inference.py](../test_inference.py) covers rendering, CropBox/rotation, matrices, validations, parameter comparison, and coordination with doubles. [verification.json](../../results/inference-local-checks/verification.json) and [tests.log](../../results/inference-local-checks/tests.log) record the historical 20-test suite; continuity documents report expansion to 22. These scopes are not conflated, and the report is not presented as execution of code with new hashes.

[source-state.json](../../documentation/documentation-inference/data/source-state.json) preserves correspondence before/after this edit. Verifying the AST without docstrings preserves executable structure, but does not imply identical __doc__, hashes, or bytecode. It does not replace GPU integration or detection evaluation.

## 8. Glossary

- Render: complete raster image of the page; distinct from the model's resized input.
- XYXY: (x0, y0, x1, y1), in render pixels.
- Checkpoint: weights deserialized by torch.load and compared strictly.
- Postprocessing: detector transformation/filtering before array export.
- Double: explicit substitute for the detector in tests; not the real model.
- Manifest: provenance/configuration record; not a quality evaluation.

## 9. Limitations and references

Five native categories; renaming does not create new captions/footers. Reading order is not guaranteed. Library and GPU failures may propagate. The test factory must provide load, predict, load_report, and metadata; no formal protocol is declared.

The [canonical documentation](../../documentation/documentation-inference/README.md) retains provenance and limits. The [historical record](../../documentation/documentation-inference/views/historico-inference-20261019.md) preserves earlier instructions and parameters, including remote examples. Remote status is not inferred from these files.
