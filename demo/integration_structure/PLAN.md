# Full integration: implementation plan

> Inline execution with `superpowers:executing-plans`. User-approved design:
> `analytics/analyses/collection/demo-integration-structure-v1-design.md`.

**Objective:** a notebook and standalone package to run integration of the 15 papers on Linux/A100 from their saved parsing outputs.

**Architecture:** exact copies of current modules and a collection helper. Verified inputs → portable preparation → reconciliation → classification v2 → inventory/capsules → Docling/native/structure/integration → outputs and backup.

**Technology:** Jupyter, standard library, isolated Python 3.13.5, frozen Docling versions and hash, PyMuPDF. The A100 is recorded; computation uses the CPU.

## Global constraints

The same code/configuration for all papers. Canonical sources and results remain intact. New destinations; no retries, OCR, models, or services. Abstentions, children without bounding boxes, and after_full_mvp review are preserved. No Git in this root.

## Review priorities

- Windows pointers: regenerate them from sources at the Linux destination.
- Different kernel: every stage runs with isolated Python 3.13.5.
- Altered ZIP/unsafe paths: reject before executing packaged code.
- Stage or backup failure: record failed/partial status, never fictitious completion.
- Result relocation: portable static views; absolute provenance reflects the execution environment, and sources also travel in the backup.

## Tasks

- [x] 1. New contract tests (RED): safe package, reconciled export, new destinations, failures, and verifiable backup.
- [x] 2. Helpers and environment: `integration_demo/`, locks, and `src/` snapshot; demonstrate GREEN with fixtures and real APIs.
- [x] 3. Notebook, documentation, package builder, and intact inputs; verify syntax, manifests, hashes, and file dependency closure.
- [x] 4. Final independent review, corrections, and delivery; record local evidence and distinguish actual A100 execution pending by the user.

## Decision and progress log

- Design approved by the user on October 27, 2026.
- Preflight: the new exporter produces the contract required by classification v2; reading export produces the contract required by the canonical pipeline.
- Decision: preserve scientific code unchanged; the minimal environment installs exact Docling/docling-slim versions without model extras, and the complete docling-core/rtree/PyMuPDF closure with pinned versions. The probe tests the geometric component by hash and import; it is not presented as a full OCR installation.
- Decision: do not run another local export of the 15 papers to prepare the demo; synthetic tests exercise all stages with real APIs.

- RED observed: missing helper imports; subsequently 8 GREEN contracts.
- Test environment adjustment: temporary files inside the demo because of Windows sandbox restrictions; scientific logic was unchanged.
- Hardware corrected by explicit user instruction: A100.

- 9 GREEN local tests, including the controller in a subprocess with synthetic sources.
- Initial package verified: 60 members, 28 identical scientific source files.
- Final independent review: no critical/major findings.
- Minor documentation clarification: Colab downloads use files.download(); corrected together with residual references to the initial hardware in this plan.
- The final delivery is rebuilt after these clarifications and verified by SHA256.
