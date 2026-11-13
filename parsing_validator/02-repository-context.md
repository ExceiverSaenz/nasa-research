# Repository Context · Parsing Validator backend

> Repository-relative paths, from the repository root `nasa_research/`. Verified on 2026-11-13 against the working tree; `parsing_validator/` is untracked in git.

**Reference** · [01-specification.md](01-specification.md); front-end design [Parsing Validator UI](https://claude.ai/artifact/Vknjv4LhjP3d72yvxH1mys); behavior specification [Parsing Validator: especificación de implementación](https://claude.ai/artifact/Mok8XQhpiiJcWX5w4ThkHt).

## Entry point and relevant files

There is no service code yet. The entry point of the future flow is "open a verified paper and project its geometry onto a page", which already exists in pieces.

| Path or symbol | What the LLM should review |
|---|---|
| `src/code/mineru_collection.py` · `CollectionRepository` | `papers()`, `entry(n)`, `verify(n)`, `bindings(n)`, `.store`. Only access path to a paper's sealed run; `verify` checks seal, run id and PDF identity (`pdf_sha256`). Paper ids are strings of digits. |
| `src/code/mineru_contracts.py` · `ObjectPointer`, `ReferenceResolver`, `ContractError` | How a `{sha256, pointer}` reference resolves to a JSON value. `ContractError` is the error type the readers raise; map it to a service error, never leak its text raw. |
| `src/code/mineru_persistence.py` · `ContentAddressedStore`, `RunRepository` | Store layout (`objects/sha256/xx/<hash>`), run verification, and the read helpers. Writing methods exist for sealing; the service must never call them. |
| `src/code/mineru_spatial.py` · `SpatialGraph`, `Matrix3`, `_points` | Entity graph (document, page, region, fragment, cell), frames and transforms. `SpatialGraph.load(reader, ref)`, `.record()`, `.locate(entity)`, `.source(entity)`. `Matrix3`, `_points` and `_matrix` are used by the reference viewer and are partly underscore-private. |
| `src/code/mineru_observed_geometry.py` · `_EvidenceCache` | Caching reader the reference viewer wraps around the store. Private name. |
| `src/code/mineru_pdf_coordinates.py` · `find_evidence`, `matrix_from_evidence`, `_facts` | Render-to-PDF matrices, and the sampled display matrix (`_facts` plus `raw_to_device`). Private `_facts`. |
| `src/code/mineru_geometry_capture.py` · `read_geometry_links` | Links between captured detector/OCR results, regions and pages (`batch_detection`, `ocr`, `wireless`, `wired`). |
| `test_libs/visualizations/build_viewer.py` (257 lines) | The only existing end-to-end projection of every layer onto display pixels: `raw_to_device`, `layout_page_join`, `frame_to_pdf`, native blocks, detector/OCR polygons, cells. It is hard-wired to one sealed run (`RUN`, `ANCHOR`) and to `papers/SiC_papers/12.pdf`, uses `RunRepository.verify`, and asserts exact mark counts. Treat it as a reference to generalize, not a module to import. |
| `src/raw_results/code_results/tensile_papers/` | The data. `README.md` explains the layout: `<n>/run/{result.json,manifest.json}`, `<n>/receipt.json`, shared `objects/sha256/`, `collection.json`, `collection-receipt.json`, `verification.json`. 23 papers, 19,594 unique objects. |
| `papers/Tensile_Properties_of_Sub-sized_Specimens_papers/<n>.pdf` | The source PDFs; their SHA-256 must equal the sealed `pdf_sha256`. |
| `src/test/test_acceptance/test_collection_repository.py` | How the collection reader is exercised with synthetic organized collections; the pattern to copy for fixtures. |
| `src/test/test_acceptance/test_spatial_references.py`, `test_original_pdf_coordinates.py`, `test_geometry_capture_integrity.py` | Existing coverage of graph and coordinate behavior; do not duplicate, call into the same contracts. |
| `src/test/test_acceptance/test_persistence_windows_concurrency.py`, `test_persistence_commit_protocol.py` | Existing Windows-specific write and rename behavior; review before designing the service's atomic writes. |
| `test_libs/visualizations/test_viewer.py` | Offline regression tests of projection (`raw_to_device`, layout/page join); shows the expected style. |

## Conventions and constraints

- **Project rules** · Read `AGENTS.md`. Relevant points: preserve originals and provenance; new versions are separate files, never overwrites; do not infer or invent scores; a one-paper test does not validate the collection; do not "fix" sealed JSON to adapt paths; the Obsidian vault under `entregas/boveda-obsidian-v1` is not part of this change and is not to be touched.
- **Sealed data** · Nothing under `src/raw_results/code_results/` or `papers/` may be written. Tests assert this with a before/after hash inventory (the viewer builder already does the same).
- **Offline** · No network, no model, no `mineru`/`torch` import. The reference viewer checks `sys.modules` for both; the service should keep that check in its tests.
- **Import path** · Project modules are imported by inserting `src/code` into `sys.path` (`sys.path.insert(0, str(ROOT/'src/code'))`, as in the existing tests and the viewer builder).
- **Style** · Existing code is compact (short lines of logic, `ContractError` for contract violations). New code should follow the repository's tests (`unittest`), keep dependencies to what is installed, and put every call into private project functions behind one adapter module.
- **Runtime** · Python 3.13.5, Windows 11, Node v24.14.1. Installed: FastAPI 0.135.2, Starlette 1.0.0, uvicorn 0.42.0, pydantic 2.12.5, jsonschema 4.26.0, orjson 3.11.8, pypdfium2 5.1.0, Pillow 12.0.0, beautifulsoup4 4.15.0, lxml 6.1.2, latex2mathml 3.81.0, httpx 0.28.1, pytest 9.0.2. There is no requirements file for the service; the project's own pins live under `src/config/requirements/`. Adding a dependency needs a decision (see ADR-001).
- **Known Windows pitfall** · `test_full_controller_then_reuse_without_real_colab` raises `PermissionError: [WinError 5]` when moving a temporary folder on Windows; cause not determined, and it passes on WSL. Do not assume POSIX rename semantics in the service's atomic writes.
- **Coverage** · Measured over all 23 papers in [05-coverage-audit.md](05-coverage-audit.md); cell boxes exist for only half of the table pages, so do not assume them.

## Verification

| Command | What it verifies |
|---|---|
| `python -B -m unittest discover -s src/test/test_acceptance -p "test_*.py"` (repository root) | The existing readers, persistence and spatial contracts the service depends on; must stay green. This is the command documented in `src/README.md`. |
| `python -B -m unittest discover -s test_libs/visualizations -p "test_*.py"` (repository root) | The reference projection logic. |
| `python -B -m unittest discover -s parsing_validator/tests -p "test_*.py"` (repository root) | Proposed location and command for the service's own tests (does not exist yet). |
| `git status --short src/raw_results papers` | Quick check that nothing sealed was touched; expected output: empty. |

## Environment setup (optional)

- Working directory: the repository root. No services to start for tests; a test server runs in-process.
- Test data: prefer synthetic organized collections built in a temporary directory (the pattern in `test_collection_repository.py`) for unit tests, and the real `tensile_papers/` for read-only integration checks. Never write the service's own files into the real annotations folder from a test; use a temporary directory.
- Configuration (proposed names, not yet implemented): the collection folder, PDF folder and annotations folder come from the settings file in the annotations folder's parent (`parsing_validator/settings.json`); the port defaults to a fixed local value and can be overridden by `PV_PORT`.
