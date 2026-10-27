# Current contract: parsing-operational/1

Describes the files already exported; does not propose changes. Source:
[README](../../code/document_pipeline/README.md), [technical report](../../analytics/reports/sic-parsing-operational-v1.md)
and [canonical manifest](../../analytics/results/sic_collection/parsing-operational-v1/manifest.json).
Technically operational status, with semantic accuracy/visual QA pending.

## File organization

Root `analytics/results/sic_collection/parsing-operational-v1/`:
`index.html`, `summary.json`, `manifest.json`, `review-queue.json`, `papers/{id}/`.
Each paper contains `document.json`, `baseline-docling.json`, `native-evidence.json`,
`native-analysis.json`, `review-queue.json`, `verification.json`, `manifest.json`
and `view/index.html` with original `images/`. The index links all 15 papers.

| Field / file | What it represents |
| --- | --- |
| inventory | Complete original reconciled units and groups; original_unit preserves text/bbox/classification and origin |
| classification_source / reconciliation_source | Original source refs and hashes |
| canonical_sources | Baselinev1, Docling and native files; caches reused by identity where appropriate |
| operational_semantics | Function, role, flow, effective route, decisions, alternatives and warnings per unit; no editing of original_unit |
| native-analysis.json | Native classification/evidence proposals before the operational connection |
| native_links / native-evidence.json | Span alignment, source, comparison text and transformation; no replaced OCR text |
| structure | Sections, candidate roots, memberships, fragments and candidate continuities |
| steps / routes | Capsules and operational presentation route; shared references without duplicating content |
| relations | Precedence, consecutiveness and continuity with explicit scopes |
| operational_connection | Routing, zones, proposed and suspended precedence constraints, baseline alternative |
| original_page_context | Preserved page identities and statuses/incidents; no lifting of abstentions |
| operational_config / metrics / validation | Frozen configuration, accounting and technical validation; semantic_accuracy=null |
| manifest.json | Hashes of inputs, outputs, new/reused code and runtime; does not replace semantic evaluation |

## Identities and references

Unit IDs are not regenerated per parser/page/visualization. The paper is the
documentary unit; its route crosses pages. Inventory, occurrences and visits
are not the same denominator. Resolve `unit_ref` against inventory, `step` against
steps and section refs against structure.sections. Shared references point to
the first occurrence, not a copy of the text.

Native claims `baseline:/...` are interpreted relative to baseline-docling.json.
Refs `native:...` and span pointers resolve in native-evidence.json.
Normalized/aligned text is used for comparison and does not replace the original.
Without its own bbox, no invented position is drawn; a preserved parent does not locate the child.

## Semantics and partial hierarchy

`operational_semantics.role` may incorporate section_heading_candidate from the
structural layer; `decisions.document_role` preserves the native layer's decision.
These are not two confirmed labels and must not be overwritten to suggest agreement.
An unknown auxiliary role does not erase the previous category/function.

Sections are proposals. `heading_ref` may be null; heading_candidates and
parent_candidates preserve nonoperational alternatives. `parent_ref` forms an
acyclic operational hierarchy. Absence of a parent may mean a valid root or lack of knowledge.
`level` preserves the level declared by the PDF if present; numbering_level_candidate
is the marker depth and may exclude the article root. Do not equate
both scales; interpret basis and parent_ref. Encoding differences may
retain distinct aliases/hypotheses for the same heading without asserting identity.

Physical membership uses route context; thematic_section_candidates may
be empty even with a located figure and linked caption. This does not imply loss.
Each paragraph fragment preserves its unit refs and text_concatenated=false.

## Statuses and warnings

| Status or measure | Interpretation |
| --- | --- |
| aligned_unique | Unique native alignment; not human validation |
| heading_proposal / unresolved_heading_candidate | Proposal based on classification/style; not a confirmed section |
| ambiguous_numbering / unlocated | Explicit ambiguity or lack of location, without discarding the node |
| inferred_from_operational_order / physical_context_only | Proposed context, not demonstrated thematic membership |
| deferred / geometry abstention | Preserved decision; do not infer coordinates or child order |
| candidate_supported | Continuity with heuristic support; not an accepted paragraph |
| candidate_ambiguous / blocked_deferred | Uncertain continuity/blocked by abstention or unusable alignment; do not equate with the child count |
| Suspended constraint | Conflict preserved as an alternative; not used to produce a cycle |
| after_full_mvp | Nonblocking final review queue, including unique automatic decisions |

All 5,374 units require review by policy, not 5,374 errors. Do not add
nodes/relations/units or overlapping warnings. Reordered pairs and changed
positions do not measure corrected errors; route changes may shift indices.

## Preservation and use

Do not modify originals or frozen results. Do not introduce manual overrides
per paper to suggest quality. A new correction requires a separate increment and
destination. The viewer switches between Docling/operational without recalculating, preserves renders
byte for byte and fits width with CSS. DOM is neither visual QA nor proof of accuracy.
