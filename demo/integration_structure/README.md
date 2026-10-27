# SiC collection integration · Jupyter / A100

Open `integration_structure_pipeline.ipynb` and run the cells in order in a Linux x86_64 session with an **A100** GPU. In Colab, select A100 as the runtime type. Jupyter on other Linux platforms with an A100 is also supported.

The current integration uses the CPU. The GPU identifies the requested environment; parsing models are not run and CUDA weights are not needed. Installation uses the Internet to download Python 3.13.5 and the pinned packages. Documents, native results, and scientific code are already included in `upload.zip`.

## Files and usage

- `integration_structure_pipeline.ipynb`: complete notebook with separate stages, a diagram, validation, result inspection, and a final backup.
- `upload.zip` and `upload.sha256`: upload these two files from **this folder**. The notebook also checks the expected hash embedded in its cells. In regular Jupyter, place them next to the notebook; in Colab, upload them through the file panel. The ZIP is approximately 1.3 GB: for Colab, storing it in Drive and configuring its path in the first cell may be more convenient.
- `src/`: 28 scientific files copied byte for byte from the current code.
- `integration_demo/`: collection adaptation, stage control, environment, and verification. It does not modify scientific rules.
- `requirements-runtime.lock`, `requirements-docling.txt`: exact versions.
- `source-snapshot.json`, `bundle-manifest.json`, `package-spec.json`, and `package-verification.json`: provenance, hashes, scope, and package review.
- `tests/`, `build_package.py`, `make_notebook.py`, `verify_delivery.py`: tests and local tools for maintaining this delivery.

The package includes the 15 PDFs and the preserved consolidated native ZIP, with 11,467 records from the three parsers across 397 pages. Running the demo does not require Windows paths or the rest of the project.

## Workflow

Native inputs → Linux pointer preparation → reconciliation → functional classification v2 → inventory/capsules → Docling geometric baseline + native evidence → structure and operational integration → JSON, views, index, and review queues.

The capsule step preserves the reading-v1 contract as an intermediate format. Docling provides the operational ordering baseline. Each stage saves its files so that inputs and outputs can be inspected.

The notebook creates an isolated Python 3.13.5 interpreter with PyMuPDF 1.27.2.3, Docling 2.123.1, and docling-core 2.92.0. It installs the exact official Docling and docling-slim distributions with `--no-deps`, together with the pinned docling-core/rtree/PyMuPDF dependency closure. This loads the original geometric postprocessor without installing its neural extras. It checks its hash and runs a real ordering probe before processing the collection. This is not an installation of the complete Docling converter or its models.

## Resources and outputs

Recommended: at least **16 GiB of RAM and 20 GiB of free disk space**, plus backup space in Drive. These are preparation margins, not runtimes or peak usage measured on an A100. The collection is processed with identical configuration and no concurrent models.

The attempt's `run/` folder contains:

| Folder / file | Contents |
| --- | --- |
| `prepared/` | Unchanged native sources, previous renders, and regenerated pointers |
| `reconciliation/` | Units, relations, and evidence from the three parsers |
| `classification-v2/` | Classification of reconciled units |
| `capsules-reading-v1/` | Intermediate inventory and capsules |
| `operational/` | JSON, structure, Docling, native evidence, and final views |
| `operational/index.html` | Entry point for the 15 papers |
| `operational/review-queue.json` | Human review queue after the MVP |
| `stages/`, `logs/`, `status.json` | States, commands, outputs, and failures |
| `source-code/`, `pdfs/` | Executed code and PDFs to preserve provenance |
| `verification.json` | Technical integrity of the new attempt |

In Colab, the final cell creates `result.zip` and `result.sha256`, verifies all members, and copies both to a new Drive folder. ZIP download starts from the notebook with `files.download()`. Regular Jupyter provides local files under the same contract. Verification also allows a failed attempt to be backed up: its status remains `failed`, rather than integration success.

HTML views are static and retain their images through relative paths. Provenance JSON retains the runtime's actual absolute paths; the backup includes the consumed sources and a relative manifest to locate them after download. After relocation, historical absolute paths document origin; they are not rewritten or presented as active local paths.

## Limits and preservation

Outputs are new. The demo recalculates Docling and native evidence for all 15 papers: the historical run reused approved caches for 12.pdf. Because of that provenance difference, binary equality with the canonical artifact is not promised.

Abstentions, contradictions, originals, and the 374 children without bounding boxes are preserved. They are not assigned their parent's box. Sections and continuities remain proposals; all units retain `after_full_mvp` review. Integrity tests do not establish semantic accuracy or real visual QA.

Do not repeat execution cells. A stage that has already started is rejected if launched again. On failure, retain logs and back up the attempt; a separate execution requires a new directory. There is no automatic recovery. If a cell is manually interrupted, check that the subprocess has terminated before using the interrupted-attempt closing cell, then create the backup.

## Local verification of this delivery

From the project root:

```powershell
python -B -m unittest discover -s demo/integration_structure/tests -v
python -B demo/integration_structure/verify_delivery.py
```

Tests use synthetic sources and real APIs (including geometric Docling and native extraction). They do not re-export the canonical collection. Final local evidence is saved in `verification.json`; actual notebook execution on an A100 remains the user's responsibility.
