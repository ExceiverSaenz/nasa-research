# Comparative visual review of the smoke test

Data, tables and original assets: [data directory](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review). Artifact filenames in the report refer to that directory.


All four outputs of **the first page of `1.pdf`**, printed folio **641**, chapter **17**, from attempt `smoke-20261101T011229Z` were inspected. The review uses only the existing local outputs. No other A100 was started, no inference was run and the collection was not processed.

**Reviewer: Codex. Status: pending human validation.** These are traceable visual observations, not an independent reference or a precision or recall measurement. Original boxes, labels and outputs were not modified.

## Result per tool

| Tool | Visible boxes | Observed omissions | Problematic labels | Groupings and duplicates |
| --- | ---: | --- | --- | --- |
| Heron | 14, with 13 distinct geometries | Affiliation, `e-mail:` prefix and book reference | Author as `section_header` | Author duplicated with the same box: `text` and `section_header` |
| Heron-101 | 9 | Complete contact block and complete editorial block; retains folio 641 | Author as `section_header`; chapter 17 as `picture` | No duplication observed |
| MinerU Basic | 11 | No relevant text without coverage observed on this page | Chapter 17 as `page_number` | One box for contact and another for editorial information; granularity pending assessment |
| MinerU Standard | 11 | No relevant text without coverage observed on this page | Chapter 17 as `page_number` | The same groupings as Basic |

**Basic and Standard return exactly the same 11 normalized geometries and block labels in this smoke test.** This was checked by comparing their data, in addition to visual inspection. This does not mean that all their OCR contents or full results are identical.

In all four outputs, the chapter title, author, Contents heading, contents body, Abstract heading and abstract paragraph have separate boxes. No box mixing those main elements is observed. **No glyph clipping is confirmed in the inspected boxes.** The absence of a complete line is recorded as an omission, without turning it into clipping of another box.

## Locatable findings

Box numbers are local to each tool and correspond to the annotated images and [box-catalog.json](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/box-catalog.json). [findings.json](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/findings.json) retains detection identifiers, labels, native references and review regions in pixels of the 1700 × 2200 background. Those regions serve to locate the observation: they are not boxes imputed to the detector or validated reference annotations.

| ID | Tool / box | Observation |
| --- | --- | --- |
| H-01 | Heron / no box | The affiliation “National Institute for Materials Science, Tsukuba, Japan” lies outside all boxes. |
| H-02 | Heron / 14 | The email address is covered; the `e-mail:` prefix lies outside. The address itself is not clipped. |
| H-03 | Heron / no box | The line with editors and book title has no box. Copyright and DOI are separately localized. |
| H-04 | Heron / 9 and 12 | The two Tetsuji Noda boxes have exactly the same geometry, with different labels. The duplication already exists in the native JSON. |
| H-05 | Heron / 12 | The author is labeled `section_header`; the `text` alternative also exists in box 9. |
| H101-01 | Heron-101 / no box | The entire lower contact block is not localized: T. Noda, affiliation and email. |
| H101-02 | Heron-101 / no box | Copyright, editorial reference and DOI are not localized. Folio 641 does have a box, number 8. |
| H101-03 | Heron-101 / 5 | The author is labeled `section_header`. |
| H101-04 | Heron-101 / 9 | Chapter number 17 is labeled `picture`. |
| B-01 | MinerU Basic / 8 | Chapter number 17 is labeled `page_number`; this page's folio is 641. |
| S-01 | MinerU Standard / 8 | The same confusion of chapter 17 with page number. |
| B-02, S-02 | Both MinerU variants / 9 | One `footer` box contains contact name, affiliation and email, without individual boxes for each component. |
| B-03, S-03 | Both MinerU variants / 10 | One `footer` box contains copyright, book reference and DOI. It does not include the abstract or folio 641. |

The last four observations are **visible groupings whose assessment is pending**: they may be valid footer blocks. They limit the goal of obtaining independent components, but this page does not demonstrate that they are incorrect geometric mixtures. The 15 observations are not 15 independent errors: for example, H-04 and H-05 describe aspects of the same duplicated author.

## Differences that must not automatically count as errors

- Heron labels 17 as `text`: it is a generic label that does not express its chapter function, but the content is indeed text. It is retained without declaring it false.
- The Heron variants call the chapter title `section_header`; MinerU uses `doc_title`. This is a difference in taxonomy and document scope, not sufficient evidence of error.
- The small “Check for updates” emblem is covered by all four: `picture` in both Heron variants and `header` in both MinerU variants. Visual form and editorial function may be compatible descriptions; it does not count as a scientific figure or a confirmed false positive.
- All delineate the contents body with a single box. Geometric separation of each entry or hierarchy is not established. In MinerU, content entries without geometry do not receive the parent's box.
- Normalized outputs include 49 rows without a box in Basic and 50 in Standard, in addition to their 11 block boxes. They are native content records without their own localization; they do not equal 99 omissions or 99 additional boxes. Their own geometry remains unknown.
- The abstract continues on another page. Ending the box at the last visible line of this page does not clip its continuation absent from the smoke test.

## Visual evidence

The full page, all four overlays and all four enlarged lower details were reviewed. Red labels are review annotations and may obscure small parts of text in these copies; the [original background](../../../../../../raw_results/code/smoke-20261101T011229Z/viewer/pages/smoke-page-1.png) preserves the page without annotations.

| Tool | Page with numbered boxes | Lower detail |
| --- | --- | --- |
| Heron | [Page](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/heron-boxes.png) | [Detail](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/heron-lower-detail.png) |
| Heron-101 | [Page](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/heron101-boxes.png) | [Detail](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/heron101-lower-detail.png) |
| MinerU Basic | [Page](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/basic-boxes.png) | [Detail](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/basic-lower-detail.png) |
| MinerU Standard | [Page](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/standard-boxes.png) | [Detail](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/standard-lower-detail.png) |

The 15 observations were also added to [the viewer's reviews.json](../../../../../../raw_results/code/smoke-20261101T011229Z/viewer/reviews.json), preserving its previous contents in [viewer-reviews.before.json](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/viewer-reviews.before.json). They include agent authorship and pending human validation status. No `revisada` mark was added, as it is reserved for explicit human review. The viewer allows exporting them; its human review counter must not interpret them as approval.

## Scope and limits

This page contains no tables, equations, scientific figures, panels (a)/(b)/(c) or scientific captions. **Their detection, separation and relationships remain unevaluated**, neither passed nor failed. Reading order and global hierarchy were also not evaluated.

This review shows better footer coverage by both MinerU variants on this page and specific classification problems in all four outputs. It is insufficient to choose a winning tool for the SiC papers. Parameters were not adjusted, results were not corrected and the collection was neither authorized nor run as part of this review.

The PDFs derived by each tool have different file hashes, but the background has already been verified as identical pixel by pixel. Original identities and coordinates are preserved. [verification.json](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/verification.json) records the scope and [findings.json](../../../../../../raw_results/code/smoke-20261101T011229Z/visual-review/findings.json) retains hashes of protected files; it was checked that derived PDFs, normalized JSON, background, viewer data and original ZIP did not change during this review.

