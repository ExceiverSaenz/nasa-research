# Coverage Audit · tensile_papers (2026-11-13)

> Closes **OQ-01** of [01-specification.md](01-specification.md). Read-only measurement of what MinerU left in the sealed collection, per paper and page; it decides which layers the interface can promise. Evidence, not interpretation: where a number is not explained, it says so.

**Reference** · [01-specification.md](01-specification.md) (BR-02, BR-13, BR-14, BR-15, OQ-01, OQ-11), [04-architecture-decision-record.md](04-architecture-decision-record.md) (ADR-004)

## Method and guarantees

- **Scope** · All 23 papers of `src/raw_results/code_results/tensile_papers` (237 pages, 3,291 final blocks), read through `CollectionRepository` and the project's own spatial and capture readers, following the same page-join rules as `test_libs/visualizations/build_viewer.py`.
- **Read-only** · A stat inventory (path, size, modified time) of the collection (19,716 files) and of the PDF folder (25 files) was taken before and after each run: identical. Nothing was written inside the repository except the files listed under *Reproduction*.
- **Verification** · `CollectionRepository.bindings(n)` verified seal, run identity and PDF identity for every paper before it was read. Result: 23 of 23 passed; every PDF's SHA-256 equals the sealed `pdf_sha256`, and every PDF's page count equals the native document's.
- **Limit** · Coverage is measured in the sealed evidence. It does not say whether the detections are correct; that is what the tool's users will judge.

## Per-paper table

| Paper | Pages | Blocks | Text origin | Title in metadata | Tables | Table pages | Table pages with cell boxes | Tables with merged cells | Blocks with control characters |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 11 | 208 | txt | yes | 5 | 5 | 4 | 4 | 22 |
| 2 | 5 | 66 | txt | yes | 2 | 2 | 0 | 0 | 13 |
| 3 | 20 | 214 | txt | no | 2 | 2 | 1 | 0 | 0 |
| 4 | 4 | 73 | ocr | yes | 0 | 0 | 0 | 0 | 0 |
| 5 | 6 | 64 | txt | yes | 1 | 1 | 1 | 1 | 0 |
| 7 | 9 | 142 | txt | yes | 2 | 2 | 1 | 0 | 3 |
| 8 | 11 | 165 | ocr | no | 2 | 2 | 2 | 1 | 0 |
| 9 | 9 | 103 | txt | no | 3 | 3 | 1 | 2 | 0 |
| 10 | 14 | 208 | txt | yes | 4 | 3 | 1 | 2 | 6 |
| 11 | 11 | 118 | txt | yes | 3 | 3 | 0 | 0 | 1 |
| 12 | 9 | 129 | txt | no | 4 | 2 | 2 | 1 | 0 |
| 13 | 7 | 101 | txt | yes | 1 | 1 | 0 | 0 | 0 |
| 14 | 7 | 99 | txt | yes | 0 | 0 | 0 | 0 | 0 |
| 15 | 10 | 122 | txt | yes | 3 | 2 | 0 | 0 | 0 |
| 16 | 12 | 216 | txt | yes | 2 | 2 | 0 | 0 | 0 |
| 17 | 10 | 114 | ocr | yes | 6 | 4 | 4 | 6 | 0 |
| 18 | 11 | 93 | ocr | no | 1 | 1 | 1 | 0 | 0 |
| 19 | 18 | 178 | ocr | yes | 4 | 3 | 3 | 2 | 0 |
| 20 | 5 | 60 | ocr | yes | 2 | 1 | 1 | 0 | 0 |
| 21 | 11 | 228 | txt | yes | 2 | 2 | 1 | 0 | 3 |
| 22 | 10 | 205 | txt | yes | 4 | 3 | 2 | 3 | 5 |
| 23 | 14 | 186 | txt | yes | 5 | 5 | 1 | 0 | 0 |
| 24 | 13 | 199 | txt | no | 3 | 3 | 0 | 0 | 3 |
| **Total** | **237** | **3291** |  | **17 yes** | **61** | **52** | **26** | **22** | **56** |

"Table pages with cell boxes" counts pages that have a table block and at least one cell with placed geometry. "Blocks with control characters" counts final blocks whose text contains characters below U+0020 other than line breaks.

## Findings

**Integrity and structure**

1. All 23 papers verify. Every PDF matches its sealed identity and page count (237 pages in total).
2. The native document is complete: 3,291 blocks of 13 types, every block and every one of the 905 inner parts has a bounding box. There are no deferred children (unlike the SiC collection described in `AGENTS.md`).
3. The 13 final block types are exactly the tag catalog of the interface: `text` 1,102, `ref_text` 616, `header` 325, `paragraph_title` 293, `chart` 239, `page_number` 213, `image` 193, `footer` 81, `equation` 77, `table` 61, `aside_text` 34, `page_footnote` 33, `doc_title` 24. No other type appears.
4. Inner parts: `image_body` 193, `image_caption` 144, `chart_body` 239, `chart_caption` 197, `table_body` 61, `table_caption` 64, `table_footnote` 7. There are more table captions than tables (64 for 61), so a table can carry more than one caption part; the interface must not assume at most one.
5. 148 blocks continue a paragraph from the previous page (`continues_prev`).

**Document-level facts**

6. Text origin is per paper, not per page: 17 papers use the PDF text layer (`parse_mode: txt`) and 6 use OCR (`ocr`: papers 4, 8, 17, 18, 19, 20). This closes **OQ-11**.
7. Only 17 papers carry a title in the metadata; papers 3, 8, 9, 12, 18 and 24 do not, so the file-name fallback of BR-15 is required, not optional.

**Layers**

8. *Layout detections* exist on all 237 pages. In all 23 papers the render window and the layout results join unambiguously (one render, one batch, matching image sizes), so layout can be promised everywhere.
9. *Layout and final blocks agree*: 3,237 of 3,291 blocks (98.4%) overlap a layout detection with IoU of at least 0.5; 14 are between 0.3 and 0.5 and 40 below 0.3. The interface must show "no matching detection" for roughly 1.6% of blocks.
10. *OCR line boxes* exist on all 237 pages (up to 175 on one page). They are geometry only; recognized text with polygons exists only on the 26 table pages below.
11. *Table cell boxes* exist on **26 of the 52 pages that have a table**; every page with cells has a table. Per paper: all table pages covered in 7 papers (5, 8, 12, 17, 18, 19, 20), none in 6 papers (2, 11, 13, 15, 16, 24), partial in the other 8, and no tables in papers 4 and 14. A "not captured" cells layer is therefore the normal case for half the tables, and the missing-evidence report will be used often.
12. Coordinates are consistent: every frame is available (`pixel_edges` 3,441; `unit_top_left`, `pdf_visual_space` and `pdf_user_space` 237 each) and none carries `unknown_coordinate_convention`. The 287 unknown locations quoted earlier belong to the `delivery14` runs, not to this collection.
13. *Unexplained*: 3,140 regions and 6 fragments in the spatial graphs have no geometry, all with reason `not_exposed`. They are not final blocks, layout, OCR lines or cells, and the ingestion should ignore any entity without geometry. What they represent is not determined here.

**Content**

14. 61 tables, all with HTML (3,432 cells in total); 22 of them (36%) use `rowspan` or `colspan`. Merged-cell editing is a requirement, not an extra.
15. 56 final blocks (1.7%) in 8 papers (1, 2, 7, 10, 11, 21, 22, 24) contain control characters (U+0001, U+0003, U+0004, U+0006, U+0007), typically where a bullet or symbol was extracted as a control code. They are invisible in ordinary text views. No block contains U+FFFD.
16. A correction to the earlier design notes: dashes and quotation marks in the text (for example the en dash in "302–310") are correct Unicode. The "�" seen while inspecting the data came from the console's encoding, not from MinerU; the real defect is the control characters of finding 15.

**Sizes for performance** · Largest page by blocks: 60 (paper 1, page index 9, a references page). Largest by OCR lines: 175 (paper 16, page index 10). Largest by layout detections: 70. Largest by cells: 279 (paper 8, page index 6). Interface and API must stay responsive at these sizes.

## Consequences for the design and the backend

| Decision | Consequence |
|---|---|
| Layers the interface promises | Final blocks, layout detections and OCR line boxes on every page; cell boxes only where present, otherwise a visible "not captured" state with a flaggable report |
| `original.json` layer fields | `layers.<name>.available` plus the reason (`not_captured`); counts per page; computed once at ingestion (ADR-004) |
| Tag catalog | The 13 final types are complete; the catalog needs no additions from this collection |
| Titles | File-name fallback implemented and tested (papers 3, 8, 9, 12, 18, 24) |
| Text label | Show "PDF text layer" or "OCR" per paper from `parse_mode` |
| Table editor | Merged cells are mandatory; plan for tables with many cells (finding 14, 279 cells on one page) |
| Control characters | Decided (OQ-12): shown as visible glyphs; the original keeps the raw character; a ready-made "Wrong characters" case |

## New open questions

- **OQ-12 · Control characters.** *Closed 2026-11-13, decision: visible glyphs.* Every control character below U+0020 other than tab, line feed and carriage return is shown as the symbol U+2400 plus its code (U+0001 as U+2401, and so on) in every text view, the preview and the summary exports. The original is never changed. See BR-21 in [01-specification.md](01-specification.md).
- **OQ-13 · Weakly matched blocks.** *Closed 2026-11-13, decision: show the nearest detection with its overlap.* For a block whose best layout IoU is below 0.5, the Layout layer draws the detection with the highest overlap, labelled with its IoU (for example "IoU 0.21") and marked as a weak match; when no detection overlaps at all it shows "No matching detection". The original stores `layout_match: { "item_id", "iou", "weak" }` per block, computed once at generation, so the client does no matching. There is no filter or list for these blocks (1.6%): the indicator on the block is enough.
- **OQ-14 · Entities without geometry.** *Closed 2026-11-13, decision: ignore and count.* Ingestion omits every spatial-graph entity without geometry (3,140 regions and 6 fragments, all `not_exposed`); their meaning stays undetermined and the interface needs none of them, since it only shows final blocks, layout detections, OCR lines and cells. Each page of the original stores `ignored_without_geometry` (a count) so the omission is visible and auditable. A test asserts that every final block, layout detection, OCR line and cell that is shown does have geometry, which is what guarantees nothing visible is lost.

## Reproduction

From the repository root (read-only; each takes tens of seconds to a few minutes):

```
python -B -I parsing_validator/audit/audit_collection.py <out.json>
python -B -I parsing_validator/audit/audit_blocks.py <audit.json> <out.json>
python -B -I parsing_validator/audit/audit_text.py
```

The results of 2026-11-13 are kept next to the scripts (`audit/results-collection-2026-11-13.json`, `audit/results-blocks-2026-11-13.json`). The scripts are measurement tools, not service code, and call project-private functions on purpose; they are expected to be replaced by the ingestion's audit command (ADR-004).
