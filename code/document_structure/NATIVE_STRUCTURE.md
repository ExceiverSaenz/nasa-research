# Additive native layer B-native

## Current integration

B-native for 12.pdf is preserved historical evidence/cache. The current canonical
integration is in [document_pipeline](../document_pipeline/README.md), run on 15 papers
with the same method and without GROBID. Do not repeat this export for context. Its
proposals are neither GT nor semantic validation. The remainder describes the original B layer.

Authorization and scope: `analytics/analyses/paper/sic12-native-structure-implementation-scope.md`.
Input: original PDF, reconciliation/classification v2 and approved Docling traversal.
Does not run Docling, OCR, GROBID or models. Does not change original classification, boxes, groups,
text or traversal. Independent output with provisional operational
proposals: these do not automatically replace the canonical pipeline.

## Components

- `native.py`: PyMuPDF1.27.2.3, Python3.13.5. Text/spans/styles, XMP/metadata,
  outlines, annotations, image resources, structure and article threads.
  No image rendering or decoding. Preserves xref/pointer and PDF hash.

- `align.py`: transforms reconciled extents to crop-relative points;
  links spans whose centers fall inside the box. This is a many-to-many correspondence,
  not identity or new segmentation. Aligned text is a comparison view,
  not a replacement for the transcription. Nonzero rotation and invalid geometry trigger abstention;
  children without bbox receive no boxes and their parent is preserved.

- `claims.py`: reconciliation by dimension. A verifiable direct claim
  may suffice; incompatible direct values leave the proposal unresolved.
  Differences from retained or inferred evidence preserve conflicts and alternatives.
  It does not vote across correlated sources or fabricate scores/probabilities.

- `structure.py`: contextualized front-matter roles, hierarchy declared by outlines,
  exact Unicode-normalized links to located headings. Without a declared
  hierarchy, preserves existing titles as candidates of unknown level.
  Metadata can be identified without outlines. Partial author mention ≠ authorship.
  Section membership inferred from provisional traversal; thematic membership of
  visualizations remains separate. Paragraphs use references, with candidate continuities
  at column/page transitions; text is not concatenated and candidates are not accepted as GT.

- `native_export.py`: verifies hashes and contracts, rejects overwriting and exports
  `native-evidence.json`, `document.json`, `summary.json`, `review-queue.json`, manifest.

- `native_view.py`/`native_view.*`: responsive inspection with original boxes,
  hierarchy, previous/proposed classification, contradictions and evidence.
  Copies original PNGs byte for byte; optional CSS zoom, no recompression.

## Contract

`inventory`, `approved_routes` and `approved_steps` are complete baseline copies.
`classification_proposals` contains decisions by category, function, document role
and flow. Each decision preserves claims, alternatives, provenance, status and the warning
“Requires human validation”. `operational_proposal` belongs to the new layer;
`applied_to_baseline=false`. A supported proposal is not equivalent to human validation.
`contradictions` allows grouped inspection. The after_full_mvp queue is preserved without blocking.

`document_structure` separates sections, contextual/thematic membership, fragments
and candidate continuities. It does not infer global order from links, resources, Figure tags
or article threads. Shared geometric StructTree attributes do not locate
individual figures. Missing data and multiple matches remain explicit.

## Verification and operation

Tests: `PYTHONPATH=code python -B -m unittest document_structure.test_native_structure`.
DOM: `node code/document_structure/test_native_view.js [HTML_exportado]`.
These are neither semantic validation nor actual browser visual QA.
The completed export remains frozen; do not repeat or tune rules on 12.pdf.
Export-module commands require new destinations and scope authorization.
Library freeze in `native-requirements.txt`; do not install or run models.

Limitations: center-based matching may associate spans from overlapping regions; exact
heading matching does not automatically resolve every title split across boxes.
Authors with variants/mixed affiliations retain unapplied candidates. Unknown
roles are not forced. Hierarchy depends on outline quality;
membership/continuity inherit traversal errors. Without GT, accuracy is not reported.
