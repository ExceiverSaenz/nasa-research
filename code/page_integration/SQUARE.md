# Table 1: square header and traces — only the user runs OCR

The package is prepared; no new OCR has been run. Original ROI `[112,154,943,230]`,831x76. Every pixel is preserved and white is added above377/below378, without resize or image enhancement: canvas831x831. Manual reference excluded from upload. Original configuration, versions, weights, parser thresholds and acceptance tolerances remain intact.

## Run from Ubuntu/WSL

If you need a new session of your own:

```bash
colab new -s nasa-table1-square-env --gpu T4
```

When READY (or using the name of an existing T4 of your own):

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
bash code/page_integration/test_square.sh nasa-table1-square-env --own-session
```

Do not run the previous header/v1 launchers. Do not prepare the package again.
`--own-session` declares an exclusive session of your own. The launcher does not create sessions: it verifies T4, uploads the ZIP/sidecar, runs one ROI with the original parser, downloads and verifies hash/CRC/plan/terminal state and then closes that session. A terminal failure with backup is also downloaded/verified before closure. On timeout without terminal confirmation it does not retry or close a potentially active process: review the log and manage the session manually to avoid leaving it unattended. On download/integrity failure, do not close before securing the backup.

Report completion with the folder `code/results/table1-square-v1/<fecha>-<pid>/` and any errors. All subsequent evaluation is local, without OCR/GPU. Do not claim recognition or a link merely from completed status.

## Environment and observers

Same `parse_native`: MinerU4.0.12, DocVortex0.6.0, Python3.11.16, Torch2.7.1+cu126, Basic/Torch/CUDA12.6/Tesla T4, OCR, image_analysis=True and CPU tables. Reuses config.yaml, requirements.lock/freeze and weight revision `2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d`. Runtime verifies packages/config/weights before parsing. New directories `/content/nasa-table1-square-v1*`, without overwriting prior experiments.

`trace_observer.py` verifies hashes of three installed sources against the official4.0.12 wheel (SHA256 `a3ff8582a4608eb1f4dde55800ac156d59b01ceabd2ab4002bdf8e86306b1eab`). Incompatibility means failure, not a version/filter change. Temporary wrappers observe original calls and are restored; the installed package on disk is not modified and no additional inference is invoked.

In `rois/p0-b2/traces/`:

- Preprocessing: image size/hash and tensor shape, without dumping millions of pixels.
- Layout before filtering: complete pred_boxes and logits, class thresholds; batch/query index preserved by tensor position. No score is imputed and the unnecessary full order tensor is not saved.
- Before/after prediction conversion, PaddleX filter, deduplication, formulas, margins/headers and internal captions: literal arguments and results.
- Before/after crops/OCR detection, confidence rejection and recognition: boxes, text and scores preserved. Internal images as dimensions/hash; nonfinite numeric values remain explicitly typed, never replaced by scores.
- Text normalization: before/after arguments to detect subsequent emptying.

Each invocation has `NNNNN-before.json`, `NNNNN-after.json` or `NNNNN-error.json` files; `summary.json` contains counters and hashes. Zero counters distinguish stages not reached. Traces describe the new run; they do not retrospectively prove which filter caused the previous empty header. Observation failures are archived and do not authorize automatic retries.

## Transformation and acceptance

Convert the parser's normalized boxes to canvas pixels and subtract padding before translating:

`x_original=112+831*x_normalizada`

`y_original=154+831*y_normalizada-377`

Pure function `square_original_box` preserves the candidate box without clipping and marks whether it lies entirely within the content. A box in white space or crossing padding is not linked as a valid label. Do not use `original_box` from the simple crop directly for these outputs; the frame is now a padded canvas.

IoU>=0.50, coverage>=0.90 of the2px-expanded reference and inverse error<=1px, previous manual reference and parentage p0-b2/p0-b2-c0/p0-b2-c1 are preserved. Numbering is not inferred from order and associations are not based solely on proximity. Ambiguous candidates are preserved. If lines lack individual text, require recorded visual review before verifying the link. Accepted Table2 and previous experiments remain intact.

Offline tests: padding/pixels/inverse, descriptor and alias wrappers, return identity and single call, native mutation observed without alteration, original exceptions, raw logits/nonfinites, package/config/tolerances, Jupyter bootstrap and launcher with fake CLI (success/failure/timeout/corrupt backup). They do not load Torch/MinerU or run OCR. Remote compatibility and actual recovery await your run.
