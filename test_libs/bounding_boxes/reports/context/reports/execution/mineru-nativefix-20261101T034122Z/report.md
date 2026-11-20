# SiC collection with corrected MinerU

Data, tables and original assets: [data directory](../../../../../raw_results/code/mineru-nativefix-20261101T034122Z). Artifact filenames in the report refer to that directory.


Attempt `mineru-nativefix-20261101T034122Z`. One A100, two isolated environments; session closed after verifying the download.

## Prior validation

The complete original PDF `10.pdf` was processed: 9 pages with Basic and 9 with Standard. The first page contains 2,327 native characters according to PDFium. Parsing defaults were retained, without converting input to images or forcing OCR.

In A and B, the actual native contract, imports, locks, pip check and CUDA matrix multiplication and torchvision NMS operations passed. DocVortex 0.6.7 and MinerU 4.0.12 remained pinned. Standard logs, in both validation and collection, confirm vLLM 0.19.1 with an asynchronous engine and CUDA. R2 was verified with HEAD for all 15 PDFs and a prior GET/hash; on Colab, the identities of downloaded inputs were verified.

## Coverage and provenance

| Tool | Papers | Pages | Boxes with geometry | Rows without a box | Provenance |
| --- | ---: | ---: | ---: | ---: | --- |
| Heron | 15/15 | 397/397 | 4889 | 0 | Reused from collection-20261101T015723Z |
| Heron-101 | 15/15 | 397/397 | 4777 | 0 | Reused from collection-20261101T015723Z |
| MinerU Basic | 15/15 | 397/397 | 4966 | 7803 | Run in this attempt |
| MinerU Standard | 15/15 | 397/397 | 4965 | 7840 | Run in this attempt |

All four tools cover the same 397 pages: 1,588 tool/page outputs. Basic and Standard completed all 15 papers without recorded failures, including the 11 that previously failed because of private_ranges. The Heron variants were not run again. Their receipts and all original native files were verified by size and SHA256 before copying. Previous failed results remain separate and intact.

Only the DocVortex pin changed, 0.6.9 → 0.6.7. The experiment.json hash matches the previous attempt; models, thresholds and revisions were not changed. Verified compatible wheels and artifacts were reused, and the 397 previous PNG backgrounds were copied with hash verification, without rendering them again. new_code was not modified.

## Download and closure

The new results archive contains 1,270 files plus the manifest, occupies 157,463,708 bytes and was downloaded in 19 verified chunks. ZIP SHA256:

`41626b5653343a117ca60cd6afec154dacbea5b5bc20c90ce19b6d8bc3e30744`

The ZIP, each file's manifest, PDF identities, native page coverage and combination of all four tools were verified before closing the A100. The subsequent listing confirmed that this session was no longer active. Another session unrelated to the attempt remained untouched.

Transport incident: the first packaging client became unresponsive. It was remotely confirmed that no ZIP, manifest or packaging process existed; only that local client was stopped and packaging was recovered with a subprocess on the same VM. No inference was repeated. Diagnostic scripts and records were retained in the attempt.

Session: `bbx-71a6437c7ffa438bb5549482d1ebcd22`. Closure confirmed: `2026-11-01T04:30:42.099375+00:00`.

## Viewer and limits

Updated viewer: http://127.0.0.1:8767/ . Shows all four tools on all pages, with original boxes and labels, and the existing combinable layers. Provenance per tool is retained; no human reviews were transferred from another attempt and pages were not automatically marked reviewed.

Functional check in existing Chrome: all four views, overlay, layer disabling, navigation and background/SVG alignment passed on three pages (first of 1.pdf, first of 10.pdf and last of 9.pdf), without JavaScript errors or written reviews. [Browser receipt](../../../../../raw_results/code/mineru-nativefix-20261101T034122Z/browser-verification.json) and [screenshot](../../../../../raw_results/code/mineru-nativefix-20261101T034122Z/browser-qa.png). This sample checks the viewer, not the semantic quality of its detections.

Rows without a box remain without geometry; they do not by themselves equal omissions and were not assigned their parent's box.

This validates execution and compatibility, not semantic accuracy of boxes/labels or correct panel separation. Visual review of the collection and human validation remain pending. Counts are not precision or recall. Heron and MinerU timings come from different sessions and stages, and are not directly equivalent; GPU memory is sampled at device level.

Evidence: [verification](../../../../../raw_results/code/mineru-nativefix-20261101T034122Z/verification.json), [provenance](../../../../../raw_results/code/mineru-nativefix-20261101T034122Z/tool-provenance.json), [metrics](../../../../../raw_results/code/mineru-nativefix-20261101T034122Z/metrics.json), [viewer verification](../../../../../raw_results/code/mineru-nativefix-20261101T034122Z/viewer-verification.json), [final status](../../../../../raw_results/code/mineru-nativefix-20261101T034122Z/final-status.json), [downloaded manifest](../../../../../raw_results/code/mineru-nativefix-20261101T034122Z/download/manifest.json).

