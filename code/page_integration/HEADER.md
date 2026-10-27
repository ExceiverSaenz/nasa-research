# Table 1: header ROI — user-only execution

Status: code and package prepared, no new OCR. Table 1 is NOT declared recovered.

## Run

From Ubuntu/WSL, on your own T4 dedicated to this trial:

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
bash code/page_integration/test_header.sh NOMBRE_DE_TU_SESION_T4 --own-session
```

If you do not have an active T4 session of your own, you can create one yourself:

```bash
colab new -s nasa-table1-header-env --gpu T4
bash code/page_integration/test_header.sh nasa-table1-header-env --own-session
```

`--own-session` confirms that the session is yours and exclusive: it will close after downloading and verifying a terminal-state backup. The script does not allocate sessions or change hardware. The parser does not run locally: all models run through Colab CLI on T4.

The launcher verifies the package and hardware, uploads a ZIP and its sidecar, installs/verifies the original environment and processes **one ROI once only**. It isolates Jupyter arguments and modules from previous experiments. Downloads the ZIP and sidecar; checks hash, CRC, exact plan and terminal state before closing the session. It also preserves and downloads a terminal failure with backup before closing it. There are no automatic retries.

On timeout or missing terminal confirmation, it cannot guarantee that the process ended: it does not restart OCR or close a potentially active job. It reports the log for manual review; do not leave that session unattended. If download/integrity fails, it does not close before securing the backup. Do not automatically clean or reuse remote paths.

Local results: `code/results/table1-header-v1/<fecha>-<pid>/`. Report completion with that path and any errors. Evaluation will be local, without GPU or OCR. Do not also run `test_labels.sh` (previous experiment).

## What changes and what is preserved

Only the input content changes: ROI `[112,154,943,230]`, 831x76 pixels, from the original1654x2205 render. X=description envelope; upper Y=previous boundary and lower Y=end of description; outward rounding. No padding, resize or image enhancement. The table body is excluded; document/page/hash, parentage and original boxes remain references.

Same `parse_native` call: MinerU4.0.12/DocVortex0.6.0, Python3.11.16, Basic/Torch, OCR, image_analysis=True, CUDA12.6/Tesla T4 and CPU tables; same requirements.lock/freeze, config.yaml, weights and revision `2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d`. The environment is validated before OCR. No new recognition option.

State and venv paths are new (`/content/nasa-table1-header-v1*`) to avoid overwriting the previous trial. Original weights are verified and reused if present; otherwise, the same revisions are downloaded through the original workflow. An incompatibility is reported and stops execution; version/configuration is not changed.

The Table1 reference and expectation remain only in `acceptance-local.json`; they are not uploaded to OCR. Package: `code/packages/table1-header-v1/upload.zip`; plan and inspection crop beside it. History and integrity verification in `analytics/results/sic12_page3/table1-header-v1-preparation/`.

## Agreed acceptance, still awaiting results

- Complete label visible in ROI and recognized in native text as Table1/Table 1 (spaces/case tolerated); do not infer numbering from order.
- Candidate box in original render: `x=x0+xn*831`, `y=y0+yn*76`; IoU>=0.50, coverage of 2px-expanded reference>=0.90, inverse error<=1px. No second scaling.
- Matching description and parentage `p0-b2`/`p0-b2-c0`/`p0-b2-c1`; proximity alone is insufficient. Body references, multiple targets or contradictory candidates remain rejected/ambiguous and preserved.
- If label and description are combined, do not invent a glyph box: evaluate native lines and visually review if they lack individual transcription, as in the previous increment. Do not accept the combined box if it fails geometry.
- Keep previous ZIPs/packages/results, reference and accepted Table2 intact. A failure does not authorize a new region, engine or retry.

Current tests verify preparation and launcher without OCR (fake CLI); they do not demonstrate real recognition or established compatibility of the new remote environment until your run.
