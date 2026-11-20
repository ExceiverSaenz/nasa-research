# Data index

## Parser outputs

The [corrected collection](code/mineru-nativefix-20261101T034122Z/) is the main
completed technical delivery. Its `assembled/` tree holds per-tool/per-paper
normalized and native data; metrics, final status and tool provenance remain
beside it. Heron reuse and new MinerU executions retain their distinct origins.
The earlier [collection attempt](code/collection-20261101T015723Z/) and
[smoke attempt](code/smoke-20261101T011229Z/) preserve their own scope and failures.

Folders historically called `viewer_source` retain page/detection indexes and
backgrounds used by analytical examples; no interactive UI remains. Original
return packages/receipts and extracted native evidence remain preserved.

## Calculated analytical data

| Delivery | Data |
| --- | --- |
| [Automatic analysis](analytics/auto-20261101T080056Z-r2/) | Detection JSONL, overlaps, native relationships, geometry diagnostics, timing/cost CSV and manifests |
| [BBox/geometry](analytics/deep-20261101-v2/) | IoU histograms, pair summaries, coverage/granularity tables, groups, patterns and verification |
| [Targets](analytics/targets-20261101-v1/) | Census, category/subtype tables, correspondence data and labeled agent case assessments |

[Original human feedback](feedback/) is separate from parser predictions and
agent assessments. Analytical snapshots preserve which preferences were consumed.
They are selected examples, not exhaustive human ground truth.

[Provenance](provenance/) contains frozen inventories and selected execution/
dependency receipts. Model and package pins are in [code/config](../code/config/).
[Persisted test receipts](tests/) describe software checks, not extraction accuracy.
Generated test fixture trees and execution environments were archived externally.

The three final narratives and their embedded images are in [reportes](../reportes/).
Use the root [delivery index](../README.md) to follow the data-generation and
analytical source code.
