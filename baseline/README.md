# Baseline: Parsing MVP

Code, pinned configuration, approved results, and tests for the Docling baseline. The original parsing of 23 PDFs is technically complete: 237 pages and 3,047 elements. LLM integration and independent semantic evaluation remain pending.

```text
baseline/
├── __init__.py
├── .gitignore
├── README.md
├── requirements.in
├── requirements.lock
├── bootstrap.lock
├── lock-verification.json
├── code_parsing/
│   ├── __init__.py
│   ├── colab_run.py
│   ├── worker.py
│   ├── parsing.py
│   ├── r2.py
│   ├── common.py
│   ├── contracts.py
│   └── tests/
├── catalog/
│   └── collection.json
├── results/
│   ├── 20261101T023303Z-c8235a43-portable-v1/
│   └── 20261101T041027Z-a3424b13-local-verified/
└── runtime/
    └── colab-attempts/<attempt>/status.json
```

## Usage

From the project root:

```powershell
python -B -m baseline.code_parsing.colab_run --source-dir "papers/Tensile_Properties_of_Sub-sized_Specimens_papers" --all --plan
python -B -m unittest discover -s baseline/code_parsing/tests -v
```

`--plan` selects local references and verifies lock files without credentials, network access, installations, or Colab. Actual execution requires an explicit `--execute`, Ubuntu/WSL, an authenticated Colab CLI, an A100, and `~/.config/nasa-research/r2.env`. The PDFs processed are downloaded from R2, bucket `papers`, prefix `tensile_papers/`, and verified against the local references. This cleanup does not authorize new remote runs.

## Code and configuration

The code uses classes with single responsibilities and dependency injection. The controller coordinates operations; the worker prepares the environment and batch; `parsing.py` converts and exports; `r2.py` handles selection, credentials, and transport; `common.py` verifies integrity; and `contracts.py` defines interfaces.

Parsing options are in `parsing.py`, the R2 prefix is in `r2.py`, and platform requirements are in the controller and worker. The four dependency and integrity files at the root are required by the current implementation. Their hashes were not changed. The Python lock file alone does not cover the interpreter, driver, or model weights; those layers are recorded for each run.

Historical `colab-attempts` state files are preserved in full and unchanged: the controller checks them before creating a session. An unconfirmed previous closure blocks another creation. Every owned session must attempt to close even if recovery fails or is interrupted. Previous logs, uploaded source files, and transport archives are in the external archive; they were not discarded. New attempts will write their usual receipts and results.

## Results

The [JSON catalog](catalog/collection.json) identifies the two approved sets by name and hash; `result_directory` is relative to `baseline/`. Paper directories retain `document.json`, `document.md`, `elements.jsonl`, `assets/`, `manifest.json`, `run.json`, `files.json`, and `storage-derivation.json`.

JSON, Markdown, and JSONL may share an image. `files.json` records file hashes, and the batch manifest includes child manifests. Derivation records link to the preserved originals. Do not remove files from a result without reviewing its contract and manifests. Colab is not required to consume these existing results.

## Tests and archive

All 37 tests are retained in `code_parsing/tests`. Their fixtures are written to `history/baseline-tests/`, outside the MVP. `tests/catalog_export.py` preserves the CSV regression helper; it is not a pipeline tool. The optional exporter and R2 inventory CLI were archived along with documentation, CSV files, caches, source files, and historical evidence.

- [Archive and recovery guide](../history/baseline-mvp-20261102T010523Z/archive-readme.md).
- [Complete pre-cleanup backup](../history/baseline-mvp-20261102T010523Z/before.tar.gz) and [SHA256 manifest](../history/baseline-mvp-20261102T010523Z/before-manifest.json).
- [Location of every previous file](../history/baseline-mvp-20261102T010523Z/accounting.json).
- [MVP verification](../history/baseline-mvp-20261102T010523Z/verification.json).

MVP checks are offline: integrity, planning, imports, and simulated behavior. They do not establish a new A100 run, scientific accuracy, or exhaustive visual QA. Historical closures are preserved records, not a query of the current remote state.
