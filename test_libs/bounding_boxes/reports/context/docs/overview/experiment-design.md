# Experiment design

Purpose: compare the usefulness of boxes, labels, native structure and recorded costs from four tools on the same 15 SiC papers and 397 pages. Read [current status](current-status.md) for execution and [conclusions](../findings/conclusions.md) for the provisional decision.

## Configurations and provenance

[experiment.json](../../../../code/config/experiment.json) defines Heron, Heron-101, MinerU Basic and MinerU Standard. Environment A contains both Heron variants and Basic; B contains Standard/vLLM. Heron revisions and model identities are pinned in configuration/manifests; resolved locks and receipts define the actual environment. Native extraction correction retained MinerU 4.0.12 and pinned DocVortex 0.6.7. See the [decision record](../decisions/decision-record.md) and [correction history](../../../../../../history/bounding-boxes-cleanup-20261101T050218/preserved/docs/history/private-ranges-fix.md).

The intended sequence is A/A/A/B with a single measured pass. In the corrected delivery only Basic/Standard were newly executed, while verified Heron outputs were reused. [Tool provenance](../../../../raw_results/code/mineru-nativefix-20261101T034122Z/tool-provenance.json) prevents treating copied projections as independent runs. `assembled`, `download`, `viewer_source` and `viewer` are representations of evidence, not additional experiments.

## Assessment dimensions

The [analysis plan](../methodology/analysis-plan.md) records user priorities P01–P12. Keep coverage, coherent segmentation, granularity, native relationships, label family/subtype and costs separate. Several consecutive paragraphs or a combined figure can be useful when content and boundaries are preserved. Mixing columns or sections and losing title boundaries matter more than uniform box counts. A shared caption may be covered in a group box without its own geometry; do not assign the parent's box to a child.

[Geometry](../methodology/geometry.md) measures overlap and candidate partition differences. [Targets](../methodology/targets.md) distinguishes vocabulary, family, subtype and function on comparable regions. Neither engine agreement nor a schema catalog supplies an independent PDF reference. Dependent model families cannot vote themselves into ground truth.

## Interpretation limits

No overall weighted score, universal winner, representative semantic benchmark or repeated end-to-end resource comparison was established. Detector inference timing and MinerU SDK parsing timing have different scopes. Sampled device memory is not exclusive model memory. Technical tests and hash preservation support integrity, not semantic correctness. Existing feedback is selected preference evidence, with contradictory or ambiguous examples retained.

Original boxes, labels, scores, relationships and provenance are preserved. Missing values remain missing. Analysis does not infer new parentage by proximity, reconstruct reading order, train a classifier or authorize further computation. The [findings catalog](../findings/INDEX.md) links the evidence by dimension.
