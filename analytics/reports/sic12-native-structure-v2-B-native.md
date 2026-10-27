# Native evidence and structural reconciliation in 12.pdf

26oct2026. Additive implementation authorized by the user. Operational baseline:
approved Docling, reconciled functional classification v2 and original PDF. The complete
inventory is preserved and the route is unchanged. No OCR, models, GROBID or
repetition of Docling. The other 14 papers were not processed.

## Results and files

- [Responsive view](../results/sic12_document/native-structure-v2-view/index.html):
  13 pages with original PNGs without recompression, reconciled boxes, hierarchy and
  per-region comparison of previous classification/proposal/evidence.
- [Integrated JSON](../results/sic12_document/native-structure-v2/B-native/document.json).
- [PDF evidence](../results/sic12_document/native-structure-v2/B-native/native-evidence.json).
- [Metrics](../results/sic12_document/native-structure-v2/B-native/summary.json) and
  [final queue](../results/sic12_document/native-structure-v2/B-native/review-queue.json).
- [Manifest](../results/sic12_document/native-structure-v2/B-native/manifest.json) and
  [audit](../results/sic12_document/native-structure-v2-audit/verification.json).
- [Methods and contract](../../code/document_structure/NATIVE_STRUCTURE.md).

| Measure | Result | Interpretation |
| --- | ---: | --- |
| Preserved reconciled units | 293/293 | Includes regions, containers and groups; none discarded |
| Native evidence items | 525 | 131 blocks, 242 links, 25 image resources, 18 outlines, 37 XMP, 8 metadata, 25 tags, 39 thread areas |
| Units with aligned spans | 220/293 (75.09%) | Geometric center-based correspondence, not validated identity |
| Without associated spans | 67 | May include figures/tables; does not equal lost text |
| Without their own geometry | 6 | Groups preserved; no invented boxes assigned |
| Proposed document roles | 22/293 (7.51%) | Limited refinement; other categories/functions are preserved or abstained |
| Directly supported / inferred roles | 17 / 5 | Not human labels or calibrated scores |
| Units with contradiction | 5/293 (1.71%) | 10 dimensions in total: function and flow; alternatives intact |
| Aligned / unlocated outline nodes | 14 / 4 | 18 declared nodes; includes truncated article root, not 18 confirmed body sections |
| Membership inferred from provisional order | 87 | Includes uncertainty inherited from the route |
| Physical context of visualizations | 64 | Separate thematic membership, without automatic assignment |
| Paragraph fragments / candidate continuities | 77 / 20 | References only; no concatenation or accepted continuity |
| Units retained for final review | 293 | after_full_mvp policy; not 293 detected errors |

The roles are 14 section headings, 1 article title, 1 keywords, 1 copyright,
1 abstract heading, 1 candidate abstract body and 3 candidate affiliations.
271 units receive no new document role; this does not mean they lose their
previous classification. Category: 291 retained values and 2 preserved abstentions.
Function: 234 retained, 15 supported, 2 inferred, 5 conflicting and 37 unresolved.
Coverage, direct evidence and warnings **do not measure semantic accuracy**.

## Techniques and conflicts

PyMuPDF1.27.2.3, Python3.13.5; no neural dependencies. Text/spans,
styles, XMP, bookmarks, annotations and structural objects are read without rendering.
Unicode NFKC normalization for comparison; source text remains intact.
Geometry links spans to reconciled boxes; exact titles and bookmarks support
headings/hierarchy. Located XMP fields and front-matter context support metadata.
Auxiliary lexical signals generate abstract/affiliation proposals, explicitly
inferred. No fixed section schema or names/pages from 12.pdf are used.

One direct verifiable source may suffice. Reconciliation operates per dimension:
it preserves previous classification, all claims and alternatives. If direct
sources disagree, the proposal remains unresolved; no majority vote decides it. If a
direct source contradicts the previous one, it may propose a provisional value without
rewriting the previous one or hiding the conflict. Five units on page 1 propose
metadata function/front-matter flow versus the previous body. The approved route does not change.

An author's name within text is insufficient for authorship: a partial match
remains an unapplied candidate. Additional characters remain in the real author
line; it is preserved as a pending candidate without forcing classification. Front-matter
metadata may be recognized without outlines; absence of hierarchy does not invent levels.

## Explicit limitations

The four unlocated nodes include the root with a truncated title and three
subsections that do not satisfy normalized text equality. There are encoding
discrepancies, for example `e` in native text versus a separator in the bookmark;
rules were not corrected to match 12.pdf. Partial matches are not asserted
as identities. Titles split across several boxes remain a limitation.

Center-based matching may include spans shared by overlapping boxes and does not
guarantee a one-to-one correspondence. Semantic validation of roles, section
and paragraphs is pending. Memberships and continuities inherit Docling errors. Original figures,
tables, captions and groups remain linked according to existing evidence;
this layer accepts no new associations. Thematic membership remains unresolved.
Figure tags with shared attributes do not locate individual figures. Article
threads and links are preserved as candidate evidence, not accepted order.

The collection's 374 children without bbox and their parents fall outside this increment;
12.pdf does not contain those incidents. Fixtures check that the layer does not impute boxes,
lift abstentions or remove parents. It has not been generalized to the other 14 papers.

## Technical acceptance and review

17 offline tests pass: PDF without metadata, Unicode, missing/rotated geometry,
deferred children, contradictions, authorship versus mention, metadata without outlines,
front page before body, hierarchy, IDs/pointers, hashes, no-overwrite and PNG bytes.
Independent review detected two P2 issues; both had RED→GREEN reproduction and
specific reviewer closure. This does not certify general semantic quality.

Exported HTML DOM: 156 page/filter/zoom combinations, 1773 region selections,
18 hierarchy links and keyboard selection checked. **This is not real visual QA**.
Browser access to file:// blocked by policy; no alternatives were attempted
to bypass it. The view is delivered for the user to open locally.

Contract and hashes verified in the audit: inventory, original classifications,
approved route, sources and renders intact; resolved pointers and acyclic
hierarchy. Human review accumulated at the end of the MVP, without blocking continuation.
One frozen export; do not repeat, refine rules or run GROBID/models.
Canonical integration, generalization and route improvement remain pending.
