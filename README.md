# Scientific paper parsing research

Research code for integrating document-parser outputs into a traceable representation for future extraction of varied scientific features.

## Current status

The operational Parse MVP was executed on 15 SiC papers / 397 pages with the same code and configuration. It preserves 5,374 structural units and 4,512 content appearances. These are technical execution and integrity results, not measured semantic accuracy. Semantic evaluation, real visual QA and downstream feature-extraction performance remain pending. Extract, Curate and Discover are not implemented by completing Parse.

This repository is a selected source/documentation snapshot for private research review. It is not the complete local research archive. See [scope and external data](docs/REPOSITORY_SCOPE.md).

## Code map

| Directory | Role |
| --- | --- |
| `code/document_pipeline` | Current operational integration, structure, routing and export |
| `code/reconciliation` | Conservative reconciliation of stored parser outputs |
| `code/functional_classification` | Functional classification v2 over reconciled units; v1 retained as historical code |
| `code/reading_order` | Historical reading-v1 baseline and reused inventory/view utilities |
| `code/document_structure` | Native PDF evidence, Docling geometric baseline and deferred offline GROBID support |
| `code/layoutlmv3`, `code/table_transformer`, `code/mineru_probe` | Original parser adapters, with their own runtime requirements |
| `code/document_trial`, `code/page_integration`, `code/colab` | Supporting orchestration and historical experiments |
| `demo/integration_structure` | Jupyter integration demonstration and pinned runtime files |
| `analytics/reports` | Selected stage analyses and evaluations |

## Start here

1. [Architecture](docs/arquitectura/02-arquitectura-del-parsing.md).
2. [Operational JSON contract](docs/arquitectura/parsing-operativo-contrato.md).
3. [Collection evaluation](analytics/reports/sic-parsing-operational-v1-evaluation.md).
4. [Runtime and data requirements](docs/REPRODUCIBILITY.md).
5. [Integration entry point](code/document_pipeline/README.md).

The canonical `pipeline.py` consumes prepared artifacts. It does not rerun the original parsers or automatically rebuild all earlier stages. The Jupyter demo orchestrates those integration stages from preserved inputs, but its external input bundle is excluded here.

## Design principles

Preserve source boxes, text, categories and provenance. Record conflicts and abstentions. Keep precedence, succession, membership and paragraph continuity distinct. Do not impute child coordinates from parent boxes or treat source agreement as confidence. Human semantic review includes automatic decisions.

## Publication and rights

Intended first publication: private repository for PI review. Paper PDFs, rendered pages, model weights, credentials and full output archives are excluded. No open-source license is assigned by this packaging step. Agree ownership, licensing and redistribution with the PI before public release. External dependencies retain their own terms.
