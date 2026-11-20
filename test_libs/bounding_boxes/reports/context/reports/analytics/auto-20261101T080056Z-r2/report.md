# Automatic SiC bounding box analysis

Data, tables and original assets: [data directory](../../../../../raw_results/analytics/auto-20261101T080056Z-r2). Artifact filenames in the report refer to that directory.


**Status: automatic analysis completed; visual review and semantic assessment pending.**

Input: `mineru-nativefix-20261101T034122Z`; 15 papers, 397 pages, 1588 tool/page outputs.

Predictions and provenance were preserved. The following results describe the outputs; they do not measure accuracy, recall, actual omissions, or relationship correctness.

## Technical coverage and records

| Tool | Records | Valid bbox | No bbox | Invalid geometry |
| --- | ---: | ---: | ---: | ---: |
| heron | 4889 | 4889 | 0 | 0 |
| heron101 | 4777 | 4777 | 0 | 0 |
| basic | 12769 | 4966 | 7803 | 0 |
| standard | 12805 | 4965 | 7840 | 0 |

Records without a bbox may be children or spans of content covered by a group. They are not counted as omissions and were not assigned their parents' boxes.

## Agreement and granularity

There were 35778 positive overlaps between tools and 24878 candidate correspondence components per page/tool pair.
Matches below IoU 0,5 and many-to-many relationships were preserved. Union areas were calculated as unions of rectangles, not as enclosing rectangles.
A component may chain independent regions together: it needs review before being treated as a semantic unit.

## Available native structure

| Tool | Parent–child edges | Visual parents with caption child | Explicit panel nodes | List items | List groups with items |
| --- | ---: | ---: | ---: | ---: | ---: |
| heron | 0 | 0 | 0 | 952 | 0 |
| heron101 | 0 | 0 | 0 | 928 | 0 |
| basic | 8601 | 251 | 0 | 0 | 0 |
| standard | 8637 | 251 | 0 | 0 | 0 |

These counts come from the native membership projection in the preserved JSON files. They do not establish actual panels, caption suitability, or a universal absence of engine capabilities. `image_body` was not treated as a panel. Opaque relationships or unexpressed semantic relationships remain pending.

G1 records the visual→caption structural pattern when directly declared; G2/G3 require explicit panel nodes. G4 requires a PDF inventory and identifier review. G5 distinguishes items from a list group. No pattern was created based on proximity.

## Geometry and signals to review

There are 2494 attribute signals outside the proposed IQR bands. The same record may produce several signals; this is not a count of errors or unique boxes.
Strata: tool, native label, and level. Linear percentiles, unscaled MAD, 1,5 IQR bands only with n≥20 and positive IQR. Small groups and zero dispersion were preserved without imputing scores.
Character clipping, column/section intrusions, and mixing of text and visualizations were not confirmed. These checks still await comparison against the PDF.

## Recorded costs

| Tool | Timing scope | Sum of available times (s) | Sampled peak RAM (MiB) | Peak device GPU (MiB) |
| --- | --- | ---: | ---: | ---: |
| heron | detector_page_inference_sum | 12.598 | 1669.70703125 | 920.0 |
| heron101 | detector_page_inference_sum | 16.685 | 1681.21875 | 1054.0 |
| basic | sdk_parse_excluding_export | 301.352 | 5853.03515625 | 2862.0 |
| standard | sdk_parse_excluding_export | 321.891 | 9706.5234375 | 12473.0 |

Heron/Heron-101 were reused from the previous attempt and measure the detector; Basic/Standard come from the corrected attempt and measure SDK parsing excluding export. These totals do not form a comparable speed ranking. Loading and unexposed subtasks remain unknown.
RAM/GPU are sampled by stage, not attributed by paper or exclusively to the model. Total stage duration was not estimated from the last sample. One pass does not estimate variability across runs.
Timing distributions are in timing_distributions.csv; detector_page_timings.csv preserves Heron's per-page observations. MinerU page observations are not fabricated from averages.

## Failures by collection attempt

| Attempt | Tool | Attempted | Failed | Not attempted | DocVortex |
| --- | --- | ---: | ---: | ---: | --- |
| collection-20261101T015723Z | heron | 15 | 0 | 0 | N/A |
| collection-20261101T015723Z | heron101 | 15 | 0 | 0 | N/A |
| mineru-nativefix-20261101T034122Z | basic | 15 | 0 | 0 | 0.6.7 |
| mineru-nativefix-20261101T034122Z | standard | 15 | 0 | 0 | 0.6.7 |
| collection-20261101T015723Z | basic | 15 | 11 | 0 | 0.6.9 |
| collection-20261101T015723Z | standard | 15 | 11 | 0 | 0.6.9 |

failures.csv preserves available causes, versions, receipts, and denominators. Failures from the previous collection remain separate from the corrected completion; reused Heron is not counted as another run. This table covers collection attempts: smoke, preparation, and native validation are distinct phases and are not averaged as repetitions.

## Pending visual review

[Open review batches](review/index.md). All pages are included, including those without signals. The PDF case inventory and assessments are deliberately empty.
Priorities: all content, especially headings/captions/body; respect columns and headings; accept several paragraphs or a combined figure when they maintain coverage; assess relationships and tagging by capability and consistency.
There are no omission percentages, true confusion matrix, validated semantic consistency, or winner. A combined box may be a useful basis even if it requires subsequent uniform separation.

## Artifacts and verification

- [Protocol and provenance](../../../../../raw_results/analytics/auto-20261101T080056Z-r2/analysis_manifest.json).
- [Input identity](../../../../../raw_results/analytics/auto-20261101T080056Z-r2/input_manifest.json).
- [Technical verification](../../../../../raw_results/analytics/auto-20261101T080056Z-r2/analysis_verification.json).
- [Automatic summary](../../../../../raw_results/analytics/auto-20261101T080056Z-r2/automatic_summary.json).
- [Review status](../../../../../raw_results/analytics/auto-20261101T080056Z-r2/review_status.json).
- Adjacent CSV and JSONL tables contain counts, overlaps, geometry, native relationships, and costs with original references.

Technical verification checks hashes and output consistency; it does not constitute scientific validation. No parsing, Colab, OCR, rendering, or visual review was performed.
