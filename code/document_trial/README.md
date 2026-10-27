# Coordinated SiC PDF parsing: execution exclusively by the user

## Prepared Compute Engine alternative (October 26, 2026)

GCE adaptation authorized by the user; first new package for 10.pdf, without agent execution of infrastructure or models. Guide: [GCE.md](GCE.md). Separate entry point `gce.sh`; do not use `run_document.sh` inside the VM. Package `code/packages/sic-gce-v1/10`, with Colab originals preserved. Offline verification does not establish actual installation/parsing in GCE.

## Current workflow: paper by paper, complete ZIP

By user decision, each paper is rerun individually, in order: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, and 17. Each individual package is uploaded in full in a single call, regardless of size. Its SHA and attempt identity are then transferred. Individual packages are not split and do not run assembly. Three parsers per paper, original configuration, individual outputs, and no reconciliation.

The batch and its packages are retained as historical artifacts; they are outside the current workflow. The chunked-transport branch is retained only if a batch package is explicitly selected. Previous instructions are preserved at `docs/history/20261026-paper-direct-upload/before/code/document_trial/README.md`. Direct upload reduces calls; it does not guarantee resolution of TLS interruptions.

October 26, 2026: parameterized coordination, with no changes to models/weights/configuration. New packages for the 15 current PDFs: `code/packages/sic-parsing-v1/index.json`. Each package contains one complete PDF and runs LM, TATR, and MinerU as before. Parsing of 12.pdf can be repeated in a new folder; it does not overwrite results.

From WSL, with your own exclusive, clean T4 session in IDLE state:

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
bash code/document_trial/run_document.sh NOMBRE_DE_TU_SESION_T4 --own-session code/packages/sic-parsing-v1/1
```

After verifying the backup of 1.pdf, continue with 2.pdf and the remainder in order. Each execution closes the owned session only after verified backup; create a clean session for the next paper. The package is now a required argument to avoid executing another document by default. An individual package runs only its paper. Closing the owned session after a verified terminal backup is retained, even if parsing fails. Do not retry after timeout: retain the attempt and inspect its status/backup.

New results: `code/results/document-parsing/<SHA256-PDF>/<date>-<pid>/`. The ZIP stores renders/identities, native outputs from the three parsers, configuration, weight verification, environments, logs, and page/parser states. ZIP/SHA/CRC, plan, and attempt identity are checked; this does not establish validated semantic quality. The workflow ends here. **Do not automatically run `document_trial.offline`, finalize, or reconciliation.export**: subsequent reconciliation/evaluation is separate.

200 dpi, T4, and original environments are retained. PDF identity comes from the plan; the p3 render regression is required only when the hash belongs to 12.pdf. Other PDFs do not receive its Table2 or historical references. Remote temporary destinations retain inherited names to avoid changing transport; they are exclusive to the clean session and do not determine the document, which is verified through the plan hash.

Prepare another package (local preparation only, without models; new destination):

```bash
PYTHONPATH=code python3 -B -m document_trial.prepare --pdf SiC_papers/3.pdf --output code/packages/OTRO_DESTINO_NUEVO
```

Preparation requires a local PDF reader (`pypdf` or PyMuPDF already installed). It does not install libraries or change inference environments. Delivered packages are already prepared: rebuilding them is unnecessary for execution.

## Historical reference for the original 12.pdf trial

The following documentation preserves v5 context. Its two-argument command is superseded by the current command above; v5 packages/results remain immutable. Its subsequent evaluation is outside current parsing.

Package for **13 physical pages** of the SiC PDF, SHA256 `9cea2fa5ad94c6a31031c72a9c3f698d571c85c810af644304c3b9f0d306f660`. The agent has not run OCR, inference, or Colab. Actual compatibility in Colab remains pending your execution; offline tests do not demonstrate it.

## Run once from WSL

When you have **your own exclusive, clean T4 session in IDLE state**:

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
bash code/document_trial/run_document.sh NOMBRE_DE_TU_SESION_T4 --own-session
```

Does not create or allocate sessions. Verifies, uploads, executes, and downloads. `--own-session` authorizes closing that session after verifying ZIP/SHA256/plan/terminal status, package hash, and unique attempt identity, including on failure. Current package: `code/packages/sic12-document-v5`; v1 and the failed backup remain intact. The 20261025T012230Z-5535 attempt backup identifies pinned certifi being blocked by uv's first-index policy on the PyTorch index. v3 adds only `--index-strategy unsafe-best-match` to LM/TATR requirements installation; MinerU already used it. No version or requirement changes. Availability and actual download from subsequent indexes remain pending your trial. v1/v2 packages and both failed backups are retained.

Bounded local wait: 600 seconds per helper call and 10,800 seconds for exec; not a cost estimate. Logs go directly into the attempt directory, without a console pipe. No live streaming: inspect `cli-console.log` while waiting. Return codes and timeouts: `*.status.json`. At the deadline, only the local CLI process tree is terminated; this does not demonstrate that remote work has ended. Each known artifact is downloaded once, without repeating exec. Only a terminal backup of the current attempt permits closure. Without a valid backup, or if stop fails/blocks: error, closure unconfirmed, and manual attention required. There is no automatic retry.

In the ZIP, `commands/NNNN-stdout-stderr.log` retains both streams combined as bytes; `commands/NNNN.json` retains the command, stage, timings, and return code. The combined stream does not distinguish stdout from stderr. The cell normally returns control to the kernel; failures are retained in the backup and returned as a local error after downloading/verifying/closing.

The original LM editable path `/content/nasa-layoutlm/layoutlmv3` must be available. If it exists, execution fails without deleting that environment. Do not rebuild the package, update versions, or retry to resolve a failure: retain the backup and report it.

## Configuration and execution

Three separate environments; freezes, sources, YAML, and revisions from the originals:

| Branch | Python | Torch / CUDA |
|---|---|---|
| LayoutLMv3 | 3.9.25 | 1.10.0+cu111 / 11.1 |
| TATR | 3.11.11 | 2.5.1+cu121 / 12.1 |
| MinerU | 3.11.16 | 2.7.1+cu126 / 12.6 |

Tesla T4 is required in each branch. 70/39/135 runtime dependencies are validated, respectively. pip/setuptools/wheel omitted by freeze are identified as bootstrap; LM retains historical pins pip 25.1.1/setuptools 80.9.0. Original uv installers: 0.12.21 for LM/MinerU and 0.6.14 for TATR, kept separate. MinerU 4.0.12/DocVortex 0.6.0, Basic/Torch, OCR, image_analysis=True, CPU tables; revision `2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d`. TATR revision `2357cbe2b5a5d1c03e54f32764f06058933b65ab`, processor 800, and threshold 0.5. LM retains original YAML/vendor/checkpoint, RGB, and 800/1333. All weights are verified by revision, bytes, and SHA256.

All three probes precede any inference. Rendering uses the original adapter in the LM environment, RGB 200 dpi, CropBox/rotation, and each page's own dimensions. The page 3 PNG hash must match before models are processed. One call per parser/page, 39 combinations. LM/TATR are loaded once per branch; MinerU retains its original internal cycle. No ROI, padding, second pass, recovery, retry, or alternative OCR. Native outputs precede derived outputs; errors and 39 states are accounted for even if installation/loading/inference fails.

The new coordinator serializes NumPy values without imputing scores. It avoids the historical TATR `bool_` export error; it does not change its previous failed/export/1 state.

## Backup and subsequent local evaluation

Destination `code/results/sic12-document-v1/<date>-<pid>/`: ZIP, sidecar, verification, and logs. The ZIP retains the plan, execution, runtimes, renders, states, and native outputs per page/parser.

After reporting completion, local inspection can prepare results and views without models; you do not need to run this step now:

```bash
PYTHONPATH=code python3 -B -m document_trial.offline \
  --package code/packages/sic12-document-v5 \
  --result code/results/sic12-document-v1/FECHA-PID/result.zip \
  --sidecar code/results/sic12-document-v1/FECHA-PID/result.sha256 \
  --output analytics/results/sic12_document/EVALUACION_NUEVA
```

A new destination is required. Produces an HTML index, native M0, M1 enrichment, reconciled R, manifests/pointers, label search, and visual templates. MinerU supplies structure; TATR/LM remain pending evidence. **This is not a validated general matcher**: it does not associate by proximity/IoU/score or invent improvements from more boxes. Adjudications are recorded separately. Native indices are preserved; the array is not treated as verified reading order.

### Page 3 regression

Table1 remains pending; Table2 always retains its historical acceptance. That enrichment transfers to the new M1/R only if the render and all native segments/containers match the original exactly. If they differ, regression review remains pending, without transplanting labels/boxes or revoking historical acceptance. Tolerances: IoU >=0.50, reference coverage expanded by 2 px >=0.90, error <=1 px; these are not duplicate thresholds.

### Review and recurrence

Visually inventory every page: omissions, duplicates, classes, separation, cropping, links, reading/continuity, and transcription/table content where they differ. The agent's reference awaits human review and is not independent GT. Searches cover JSON/Markdown, including blocks/lines/spans and Table1/Table 1 variants, spaces, line breaks, and capitalization. Hits do not establish correct recognition or association. Only the visual inventory establishes the denominator of visible labels and permits reporting “not located in the inspected files and fields” without claiming permanent loss.

After the templates are completed, the offline aggregator retains counts/denominators, uncertainties, and changes attributed to recovery, reconciliation, manual adjudication, or representation. It does not accept document quality by itself:

```bash
PYTHONPATH=code python3 -B -m document_trial.finalize \
  --reviews analytics/results/sic12_document/EVALUACION_NUEVA \
  --output analytics/results/sic12_document/RESUMEN_NUEVO
```

Rejects pages/reviews missing without explanation. Separate M0→M1 from M1→R. A failed parser is not equivalent to an empty page or a confirmed omission. The conclusion requires a case-based report; no test, ZIP, or box count replaces it. No new recoveries are executed; any correction is another increment.

## Clean inventory v4

The installed inventory is obtained with the same Python in a new process before importing Torch. No dependency is installed or updated. `inventory-MODELO-ETAPA-clean.json` and `inventory-MODELO-ETAPA-after-torch.json` are retained, with all entries, names, versions, metadata and root paths, sys.path, PID, executable, and prefix. Duplicates are not overwritten.

Strict plan verification uses only the clean inventory; the capture after Torch is diagnostic. Same-version copies are retained at all their paths; conflicting versions in the clean inventory or missing provenance block execution. Versions differing from the plan, extra/missing packages, and different GPU/Python/CUDA continue to block execution. The historical bootstrap-tool policy remains in effect. Subprocess logs and both inventories remain in the backup, even if a later check fails. A failed clean capture is also archived. This package has not been tested in Colab; that execution belongs to the user.

## Separation by stage v5

ETAPA is `preflight` or `before-infer`. Both checks remain, and each retains its captures and `runtime-MODELO-ETAPA.json` report, with the stage and exact references to its inventories. The second does not overwrite the first. Repeating the same stage still raises an error because evidence already exists.

The v4 attempt passed all three probes and generated 13 renders (page 3 with the original hash), but stopped before loading models when repeating a probe with the same name. This collision is the corrected defect. The regression test reproduces probe -> infer inputs for all three branches with inert models and one synthetic page; it checks export, file preservation, and blocking before model loading if a version changes in the second check. It does not validate actual loading or prediction: those remain pending execution exclusively by the user.
