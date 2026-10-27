# Native evidence and structural trials

The package no longer contains only T0. Its offline modules are reused in the
[canonical integration of 15 papers](../document_pipeline/README.md), which is current and frozen.
The existence of code does not authorize relaunching models or exports.

| Component | Guide / status |
| --- | --- |
| T0/LayoutReader | Historical static validation; incompatibilities are not routinely repaired |
| Docling ReadingOrderPredictor | [DOCLING_TRIAL.md](DOCLING_TRIAL.md); approved geometric baseline for 12, same component used for the other 14 |
| Native evidence/B-native | [NATIVE_STRUCTURE.md](NATIVE_STRUCTURE.md); implemented offline layer, sources preserved |
| GROBID adapter/client/evaluation/viewer | [GROBID_TRIAL.md](GROBID_TRIAL.md); tested with fixtures, no trial or real C; postponed by the user |
| Active operational structure and order | [document_pipeline](../document_pipeline/README.md); canonical JSON/view per paper |

Neither LayoutReader nor GROBID is used for the active result. Do not run a full
neural Docling pipeline: the current integration uses its geometric component.
Source/metadata/T0 are not equivalent to verified model runtime. See the
[narrative state](../../docs/continuidad/13-estado-y-ciclo-experimental.md).
