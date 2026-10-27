# Localized recovery: two labels, user-only execution

## Current prepared experiment: Table1 square-v1 with traces

The unpadded header produced empty native output. The new approved increment
preserves831x76 pixels and adds white377above/378below for an831x831 canvas, same
parser/configuration/tolerances. Separate package `code/packages/table1-square-v1/`.
User only: `bash code/page_integration/test_square.sh SESION_T4 --own-session`.
Current instructions in [SQUARE.md](SQUARE.md). No new OCR has been run;
accepted Table2 and previous experiments remain intact. The following sections are historical.

## Next experiment ready: Table 1 header

Independent package `code/packages/table1-header-v1/`; current instructions in
[HEADER.md](HEADER.md). The user runs `bash code/page_integration/test_header.sh SESION_T4 --own-session`.
Only one ROI `[112,154,943,230]`, same parser/configuration/tolerances; no new OCR
has been run by the agent. The launcher closes the user's own session after verifying the backup.
Accepted Table2, packages and previous results remain intact. The following v1 instructions
are preserved as history; do not run them for this new ROI.

## Update: Table 2 through native lines (24Oct2026)

Later increment approved and performed exclusively without OCR. Current result:
`analytics/results/sic12_page3/table2-lines-v1/accepted/table2-lines.json`.
First native caption line = label candidate; second = description candidate.
The assignment is not the parser's individual transcription: it requires a separate visual record,
with source hash and pointers. `visual-review.json` records Codex inspection;
it is not equivalent to human approval of the result and does not validate other documents.

Only the explicit equivalence `\mathrm{UO}_{2}` → `UO2` is applied for comparison;
literals and the applied rule are preserved. LaTeX commands are not generically removed.
The original combined candidate and all rejected alternatives are preserved.
More than two lines, overlaps, inversions, intervening content, different columns
or several eligible candidates prevent automatically closing the link.

Table 2 passes IoU=0.6637845569 and coverage=0.99 with the original tolerances.
Link `p0-b4`/`p0-b4-c0`/`p0-b4-c1` verified with explicit agent visual review.
Table 1 is not recovered or modified; its v1 results remain unchanged.
24 offline tests pass. ZIP, reference, original package and 85 protected files remain intact.

Reproducible offline command (new output required):

```bash
PYTHONPATH=code python3 -B -m page_integration.workflow evaluate-table2-lines \
  --preparation code/packages/localized-labels-v1 \
  --result code/results/localized-labels-v1/20261024T221741Z/result.zip \
  --output CARPETA_NUEVA \
  --review analytics/results/sic12_page3/table2-lines-v1/visual-review.json
```

Without `--review`, the link remains pending even if geometry passes.
The specific schema is in `label_recovery.schema.json#/$defs/table2_lines`.
The v1 upload remains frozen as evidence of what ran; it is not rebuilt and
OCR is not repeated for this increment. The following remote instructions are historical.

Status 24Oct2026: code and package prepared; offline tests, no OCR. Actual recovery and links remain pending. The A03–A06 diagnosis is not repeated.

## What will run

Two PNGs cropped from the original render, without resize/padding: p0-b2 `[112,154,1564,428]`, p0-b4 `[112,1106,818,1526]`. They include label, description and body according to original boxes; they do not correct historical table boundaries. They were visually verified before OCR. The manual reference is NOT uploaded or fed into the algorithm.

The new input calls the original `parse_native` without modifying it: MinerU4.0.12/DocVortex0.6.0, Python3.11.16, Basic/Torch, OCR, image_analysis=True, CUDA12.6/Tesla T4, CPU tables; LLM functions disabled. The original config.yaml is reproduced and archived requirements.lock installed with hashes. The complete installed package set is compared against the original freeze. Local weights from revision `2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d`, verified against the original receipt. If weights already exist at the original path, they are verified without overwriting. Any incompatibility stops the process before OCR.

There is no alternative OCR API, retry, document expansion, session allocation/closure or automatic CLI-command execution. The bootstrap is prepared for execution only by the user through their Colab CLI on a T4 session they choose. It creates a dedicated venv, may install dependencies and download only the original weights if absent.

## Run in Ubuntu/WSL through Colab CLI

Recommended workflow, equivalent to the previous launcher (user execution only):

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
bash code/page_integration/test_labels.sh NOMBRE_DE_TU_SESION_T4
```

Manages package verification, upload, execution, download and hash in an existing session. Does not create/close sessions or repeat OCR. On error/timeout it preserves the log and stops; review before downloading or retrying.

The launcher uses a bootstrap that isolates Jupyter kernel arguments and requires `LOCALIZED_LABELS_COMPLETED` before downloading. Do not run `remote_labels.py` directly with `colab exec -f`: the kernel may pass its own arguments to argparse. On error or timeout, do not repeat automatically; review the log and confirm whether it finished. This correction does not change the OCR package, its versions or configuration.

## Subsequent evaluation, without OCR

When the user reports completion, verify and evaluate the downloaded ZIP. The command does not load models:

```bash
PYTHONPATH=code python3 -B -m page_integration.workflow evaluate \
  --preparation code/packages/localized-labels-v1 \
  --result "$RUN_DIR/result.zip" \
  --output analytics/results/sic12_page3/localized-labels-v1-evaluation
```

The output folder must be new. `unified-page.json` preserves candidates, reasons, literal text, fragments, native/original boxes, hashes, pointers and references to original bodies/captions. Association uses parentage, alignment, order, matching description and absence of intervening text; it does not use the manual reference or proximity alone. A candidate with several eligible targets remains ambiguous even if another target is already ambiguous. Combined blocks receive no invented label box: the block box is preserved and may fail geometric acceptance.

Evaluation compares against the independent manual reference. It preserves the approved thresholds literally: IoU>=0.50; candidate/2px-expanded-reference intersection divided by the area of that expanded reference >=0.90; inverse error <=1px. **An exact box fitted to glyphs may fail that strict coverage**; the system reports this rather than relaxing the threshold. Text comparison allows Table1/Table 1 and space/case differences; it does not automatically correct uncertain characters.

`registry_implemented`, `labels_recovered` and `links_verified` are distinct states. `links_verified` represents automated acceptance against the reference; `human_review` remains `pending` until human review. No synthetic test demonstrates real OCR or generalization.

## Offline checks performed

```bash
python -B -m unittest discover -s code/page_integration -p 'test_*.py' -v
```

Bounded tests of ROI, units/inverse, tolerance, ambiguity, swaps, false captions, body references, runtime drift, ZIP/allowlist/integrity and synthetic-output evaluation. They do not import or run torch/MinerU. Historical analyses are not rerun.

Original files remain intact. The manifest `code/packages/localized-labels-v1/integrity.json` protects the three models' ZIPs, prepared inputs, render, relevant original exports, MinerU code and A03–A06 results used; evaluation verifies their hashes before producing a new derivative.


## Page reconciliation implemented offline (24Oct2026)
Approved priority: MinerU structure, TATR table comparison, LayoutLMv3 support.
Current output analytics/results/sic12_page3/reconciliation-v1/verified-output/;
reconciled-page.json, review.html, selected-overlay.png and manifest.json.
Code code/page_integration/reconciliation.py: recipe specific to this page,
not general matching. 48sources preserved,19segments+4containers,8relationships,
35candidate links pending. Do not turn A03 into identities; no union/averaging
or score ranking. Native text with provenance, without new OCR validation.
32offline tests pass (10new);151protected files intact. Report and audit
reconciliation-v1/report.md and verification.json; continuity copies in before/.
Table1 remains a pending warning; Table2 acceptance with agent visual review
is intact and its derived label separate. Table boundaries, list/r12 continuity and p0-b12
direction remain explicit. No validated reading order or superior ensemble.
Implementation and technical acceptance with verified pending items; no GT accuracy.
No OCR/inference/Colab run. This authorization does not extend to all of12.pdf.
