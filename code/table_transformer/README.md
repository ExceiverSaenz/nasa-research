# Independent Table Transformer trial

Approved design: `docs/analysis/diseno-experimental/11-diseno-ensayo-table-transformer.md`.
Implementation prepared locally; **the model has not yet run on GPU**.

## Scope

Table detection only on the original full render of SiC12.pdf, page3.
No OCR, cell reconstruction, PDF rerendering, training or fusion
with LayoutLMv3. Separate outputs in `code/results/table-transformer-page/<fecha>/`.

| File | Responsibility |
| --- | --- |
| `detector.py` | TableTransformerDetector adapter, loading and inference; deferred heavy imports |
| `outputs.py` | JSON, overlay and crops without padding; does not run the model |
| `run_image.py` | Coordinates one image, manifest, timings, status and errors |
| `prepare.py` | Explicit ZIP of PNG, provenance and code; validates SHA256 and members |
| `remote_job.py` | Independent environment, verified download and execution; protects prior evidence |
| `test_page.sh` | Transfers, runs, downloads and verifies on an existing authorized session |

## Input and model

Exact PNG from `page/render.png` in the first trial's ZIP,1654×2205px,200dpi.
SHA256: `6f46d8ff2d05eee785739ec1c34716db14135411c731e7aa6433e27ca06d00b9`.
No crops or previous boxes are used as input. Identity is verified before
packaging, during extraction and during execution.

Model `microsoft/table-transformer-detection`, revision
`2357cbe2b5a5d1c03e54f32764f06058933b65ab`. Downloads only config, processor and
model.safetensors from that revision. The metadata API must return the same
commit; each download is validated using size and LFS-SHA256 or Git-blob-SHA1 digest.
SHA256 of each file is also saved and reverified before loading.
Actual network access and download metadata have not yet been tested in Colab.

Uses the checkpoint's DetrImageProcessor, limit800, and its own normalization;
not LayoutLMv3's800/1333. The adapter records the actual tensor shape. DETR's
normalized cxcywh boxes are converted directly to original-PNG pixels.
They are not scaled twice and their coordinates are not clipped.

Native query classes table/table rotated/no object. Inclusive threshold0.5,
preserved before seeing results. Queries whose argmax is
no object are not exported as tables. No NMS or subsequent adjustment is applied.
All queries, their logits and normalized boxes remain in regions-raw.json.

## Separate environment

Python3.11.11 through uv0.6.14, in `/content/tatr-probe/env`.
torch2.5.1+cu121 and torchvision0.20.1+cu121 from the officialCUDA12.1 index.
Transformers4.49.0, timm1.0.14, NumPy1.26.4, Pillow10.4.0, safetensors0.5.3,
huggingface-hub0.29.3 and tokenizers0.21.0 in requirements.txt.
Dependencies and CUDA/T4 are verified and the complete freeze saved. Resolved
transitive dependencies are recorded; this is not byte-for-byte offline restoration.
The bootstrap downloads several GB of packages: installation is part of the cost
of the new trial. It does not install or run LayoutLMv3 or replace the modern kernel.
uv is installed with `pip --target` in its own directory, without modifying kernel
packages. Actual availability/compatibility of this combination remains pending.

## Usage once the session is authorized

From the root in WSL, and only with a T4 session already allocated for this trial:

```bash
bash code/table_transformer/test_page.sh NOMBRE_SESION
```

Does not create or stop sessions. Packages PNG+metadata+code (no PDF/weights), uploads
only what is necessary and reuses cli_job.py/verify_download.py for backup. A
job failure preserves logs and status; the verifier returns an error if the
job failed even when ZIP integrity is correct. A CLI timeout does not
confirm termination: do not repeat or close until checking status/recovery.

A second run on the same remote directories is rejected **before
opening or truncating logs**, with a persistent exclusive lock. Do not delete the lock or
force a retry over old results; recover evidence and explicitly
decide on a new run/VM. Closure is manual after
downloading/verifying and only for your own session.

## Outputs and errors

- run-manifest.json, page-status.json and load-report.json.
- regions-raw.json with all logits and boxes; regions.json with filtered tables.
- overlay.png and crops/query-N.png for each detection intersecting the image.
- Original boxes outside the page are preserved; crop_bbox records the
  actual floor/ceil crop limited to the PNG, crop_clipped warns and crop_path is null
  if there is no intersection. No padding or corrective table rotation.
- Prediction JSON is saved **before** derived images. If an
  image fails, status is failed but GPU need not be repeated to recover logits.
- Network diagnostics omit temporary redirect URLs. If loading has missing,
  unexpected keys or incompatible sizes, predict is not allowed.
- input-manifest.json, source.json, model-manifest.json, constraints.txt,
  requirements-freeze.txt and setup-console.log remain in the remote backup.

Table rotated results remain separate as a native label; the existing
PubLayNet auditor taxonomy is not silently altered to accommodate them.

## Local validation

From the root, with local NumPy/Pillow dependencies from the available runtime:

```bash
python -m unittest discover -s code/table_transformer -p 'test_*.py' -v
```

Tests of decoding, threshold, background, clipping, zero detections, failures,
packages and simulated downloads. Coordinator with test doubles: does not establish torch, HF,
real model, real processor or CUDA operation. Bootstrap and downloads are tested in the
VM, not with these doubles. Do not request repeated local checks when starting chats.

The final comparison will be visual on the two tables, preserving both outputs
separately. Do not assign percentages or extrapolate to the collection.

## Correction of the first real trial and retry

The first attempt failed during loading; intact backup in
`../results/table-transformer-page/20261023T165134Z/`. It produced no detections.
Only the three FrozenBatchNorm layer2/3/4 downsample counters
recorded in that attempt are allowed. They remain complete in load-report.json;
run-manifest.json records the compatibility policy. No other additional
or missing keys, incompatible sizes or loading errors are allowed.
Verified source: https://github.com/huggingface/transformers/blob/v4.49.0/src/transformers/models/table_transformer/modeling_table_transformer.py
(class TableTransformerFrozenBatchNorm2d, lines 188–228).

In the original VM, still active:

```bash
bash code/table_transformer/retry_page.sh nasa-tatr-env
```

Reuses Python/torch/Transformers/timm and weights from that VM; uploads only corrected
code and the same PNG. New remote outputs `/content/tatr-retry-state/page`,
backup `/content/tatr-retry-result.zip`. Does not delete/replace the original backup.
File/lock protection also prevents repeating this retry.
If the VM has already been lost, this workflow does not rebuild the environment.
17 own tests and34 previous tests OK; corrected inference still pending.
## Current TATR status: inference recovered (23 October 2026, trial 16:59 UTC)

The same T4 `nasa-tatr-env` loaded the model and ran inference: loading4.011s,
prediction0.515s, two tables. Remote export failed when serializing a
numpy.bool_ in crop_clipped; remote status is preserved as failed/export.
Only that conversion to native bool was corrected, with a reproduced regression.
18 TATR tests +34 LayoutLMv3 tests passed. No new inference is required.

Local backup verified by SHA-256 and CRC:
`code/results/table-transformer-page/20261023T165937Z/result.zip`,
SHA-256 `a29324b855ae95a9e2be227fa13e4b61253e098501abda84a151654d5d820611`.
Includes queries, boxes, overlay and both crops. Derivatives rebuilt locally
in `recovered-exports/` from saved queries and the verified original render;
boxes, scores and IDs match the ZIP exactly. Provenance preserved,
without modifying the ZIP or attributing success to the remote exporter. One-off script
`recover_exports.py` in the same directory; review/ preserves remote images and reports.

Visual observation: two tables without figures or captions, no additional boxes with
threshold0.5. Confidences0.999889 and0.999862 are not quality percentages. Very tight
boundaries, outer horizontal lines excluded; do not claim perfect crops.
Diagnostic improvement over LayoutLMv3's table/figure mixture on this page.
No OCR, cells, fusion or collection validation. Keep results separate.

**Next step:** review recovered outputs with the user; do not run
retry_page.sh again. Intact backup available to stop only
`nasa-tatr-env`; closure not yet confirmed. Do not create a new allocation automatically.
The following pending inference/retry states are historical.
