# Technical extension: geometry, granularity, categories, and recurrence

Authorization: user's request to run an in-depth analysis on existing results. Continues docs/methodology/analysis-plan.md, P01–P12. No parsers, OCR, Colab, models, renders, or changes to originals/vault/feedback. Separate code and results are created. “Cells” is interpreted as regions/boxes, not reconstruction of table cells.

## Decisions frozen before computation

1. Six pairs, 397 pages. Histograms [0,.1), …, [.9,1], IoU=1 separately. All positive overlaps are a different population from reciprocal maximum-IoU pairs and groups. Without assigning IoU=0 to an absence of reference.
2. Strong edges: IoU>=.5 OR containment of either box>=.9. Bipartite components including isolated nodes; exact union, never an enclosing rectangle. Types1:1/1:n/n:1/n:m/no strong correspondence. Sensitivity is preserved with containment .85/.9/.95 and union IoU .85/.9/.95, without choosing the most favorable result.
3. One box versus several is marked geometrically compatible with granularity if union IoU>=threshold, all small boxes are smaller than .98 of the large box's area, and redundancy among small boxes<=1%. Equivalence of content/boundaries/caption remains pending: geometry does not validate semantics. n:m remains complex, not forced into 1:n. Declared parents/children are preserved; geometry is not attributed to children without bbox.
4. Spatial clusters of nearly equivalent boxes: deterministic complete-link agglomeration over IoU>=.9, at most one box per tool and without using labels. Sensitivity .8/.9/.95. Avoids chaining regions through a bridge. Does not remove duplicate boxes; leaves them in other clusters. It is not a document hierarchy or truth.
5. Categories: use the existing partial analytical map and preserve native labels. Add explicit schema descriptors (margins, number, index, reference, note) separate from actual function. An unmapped category remains unmapped. Contingency tables, entropy, and diversity indicate disagreement/availability, not accuracy. Basic/Standard and Heron/101 are considered dependent families: no voting as a reference.
6. Geometric atoms: exact sweep through rectangle boundaries, tool signatures, and category sets; integrates area without double counting and separates geometric agreement from category agreement. Area is a page percentage, not true content. Top/middle/bottom band (.2/.8), narrow/medium/wide width (.35/.7): fixed exploratory descriptors, not actual columns.
7. Patterns: label/category signatures in equivalent clusters, vertical region, and width; support by cases/pages/papers; macro by paper, concentration in the dominant paper, stability leaving one paper out. Associations of page events (declared present categories and discrepancies), support/confidence/lift with explicit denominators. These are exploratory; no classifier is trained or tuned.
8. Human feedback: hashed snapshot of real active records, separate from fixtures; intersection with their regions to contextualize preferences. No example becomes an exhaustive inventory, exact box, or truth label invented from a free-text note. If it changes during execution, the snapshot is preserved and this is reported.
9. Quality according to P01–P12: no aggregate ranking. Distinguish relative coverage, pending structural boundaries, available native relationships, categories, pending clipping, and historical costs. Costs preserve scope differences, without a false timing ranking.

## Consulted foundation

Data Mining book in the vault, query8efd92ca022a433096fe643338bce152: chapter2 (discretization/proximity),3 (histograms/OLAP),4 (evaluation reference),6 (support/confidence/Simpson),8 (complete-link and internal/external evaluation),9 (clustering limitations). Geometric rules are adaptations for this experiment, not thresholds prescribed by the book.

## Execution and verification

- [ ] Tests with controls: equivalent split, gap, duplication, chaining, categories not used in grouping, histograms, and atoms.
- [ ] Local code with stdlib; new destination and before/after hashes of all inputs used; comparison against previous manifest.
- [ ] Tables by pair, page, paper, category, and sensitivity; patterns with references and examples.
- [ ] Technical report, readable summary, and standalone SVG figures; independent review of method/code and necessary corrections.

Ruling: execution follows the already defined specification and current explicit request; the definition of accuracy is not reopened, nor is another approval requested. Cost: exploratory thresholds must remain visible and not become user acceptance. No worktree or commit: .git is read-only and all additions are isolated in deep_analysis and a new delivery.
