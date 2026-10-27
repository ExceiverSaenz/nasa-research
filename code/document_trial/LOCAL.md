# Local parsing in WSL2

Status as of October 26, 2026: all three environments and all weights are installed and verified. Seven offline tests pass; parsing was not run. The computer is already prepared: the next operational command is `run`; do not repeat `prepare`. Evidence: [preparation report](../../analytics/reports/sic-local-wsl-v1.md).

Preparation was authorized on October 26, 2026 after GPU capacity was unavailable in GCE. Baseline: immutable package `code/packages/sic-parsing-v1/10` (9 pages). Variable: local WSL2 / RTX 3050 Laptop 6 GB platform; Python, packages, weights, resolution, precision, and options for all three parsers are preserved. The GPU differs from a T4; this does not demonstrate numerical equivalence or that inference fits in 6 GB. Do not install an NVIDIA Linux driver inside WSL.

Environments and weights reside in `~/.local/share/nasa-parsing/local-v1-ready`. `ready.json` appears only after packages, CUDA, GPU, and weights have been verified. Preparation does not render or call models. The derivation records hashes of path and guard changes; historical ZIPs remain intact.

From WSL at the project root, prepare once only:

```bash
PYTHONPATH=code python3 -B -u -m document_trial.local prepare --repo "$PWD"
```

Only after verified preparation does the user start paper 10:

```bash
PYTHONPATH=code python3 -B -u -m document_trial.local run --repo "$PWD" --user-run
```

The paper is fixed by preparation, not by the execution command. Parsers run sequentially in separate processes. A failure stops subsequent branches; it does not change configuration or repeat inference automatically. The historical worker may finish accounting for pages in its branch before returning the failure. The new output directory has a UUID under `code/results/local-parsing-v1/`; it retains logs, page accounting, terminal status, ZIP, and SHA256 even after handled failures. Forced interruptions or shutdown may prevent that terminal backup: retain the directory. Reconciliation is not started and results are not evaluated automatically.

Do not rerun `prepare` to repair a failure: first inspect the stage log; existing directories are rejected and preserved. `run` rechecks inputs, inventories, and weights before inference. Do not declare success from an existing ZIP: inspect execution-status.json. The `pilot-started.json` marker prevents concurrent executions and repetition of this pilot without reviewing its result first. Do not delete it automatically.

For new installations, transport uses two simultaneous downloads and a 600-second read timeout; it does not modify pinned dependencies. Reference: [uv variables](https://docs.astral.sh/uv/configuration/environment/). Large downloads may be retained in `wheels/*.part`; `local_download.py` checks the resume range and requires the official SHA256 before installation. `wheels/receipts.json` records provenance. Explicit `repair-install` is used only after diagnosing an interrupted installation; it never resumes or repeats parsing. Previous logs are retained.

Offline test: `PYTHONPATH=code python3 -B -m unittest document_trial.test_local -v`.
