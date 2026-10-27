# A06 Pilot synthesis and review priorities

October 24, 2026. Descriptive/comparative study of physical page3 of
SiC12.pdf, preserving C01 questions. A03,A04,A05 were executed and verified
sequentially with their approved decisions; A06 synthesizes their results.
Future proposals in this report are neither executed nor authorized.

## Answers to the five C01 questions

### 1 What each parser contributes by category

TATR contributes two isolated table candidates, without including figures/captions.
MinerU separates several regions that LM mixes and offers explicit caption,
equation, header and page categories. LM retains useful table,
text and title candidates, list class and separate labels, alongside partial or
mixed boxes. These are contributions observed on this page, not a global winner.

E02 contextualizes the outputs: D05 LM23,TATR2,MinerU19. The 19 MinerU leaves are not
19 GT objects. An unsupported class does not mean the content was lost.
See E02 and A05 reports, and the A05 matrix with recoverable original labels.

### 2 Where they agree or differ

A03 records 18 visual associations, 44 unique cross-model pairs and 132 S01
measures. There are similar-scope cases (title and certain captions/texts), one-to-many
cases in numbered items and LM boxes with multiregion scope. For tables, TATR
boxes are contained within MinerU bodies; this describes geometry, not perfection.

Nine cases retain ambiguity and 19 pairs have different comparable categories;
neither number is a confirmed error count. No one-to-one assignment was forced,
pair discarded by class or box chosen by confidence.
Evidence: A03 report, associations and independent Decimal geometric audit.

### 3 What appears mixed or clipped

The previously documented upper LM mixtures and multiblock r21 from Q02 are retained.
Under the approved criterion, both TATR crops fail structural borders;
upper MinerU cuts part of the lower rule and the strict extent of the lower
border remains indeterminate. MinerU table captions exclude Table1/Table2,
so they do not satisfy label+description in the same crop. Crop p0-b12 includes
a direction. fragment from the preceding paragraph.

The 23 LM records exported no crops: their usefulness is not certified and no new
crops are created as if native. 21 actual crops byte-identical to the ZIPs
were inspected. Visible completeness of a page is not document completeness or
correct OCR transcription. Individual evidence and border samples in A04.

**Interpretive correction:** the commercial FE software / Abaqus... sequence
suggests that the upper-right block continues left item2. The
previous judgment of r12 list as a confirmed error was excessive. It remains a
continuity hypothesis, without validating reading order or changing previous data.
This A04 qualification takes priority when interpreting A02/Q02; A05 preserves it.

No complete omission audit was performed: there is no reviewed geometric
reference. No recall, precision or quality percentages are presented.

### 4 Whether there is evidence for combining tools

There are local diagnostic alternatives on three separate axes: geometry,
explicit category and crop. Better separating a figure or emitting equation contributes
information, but does not demonstrate that an ensemble outperforms a parser alone.
Limitations against the usefulness criterion remain in tables and table
captions. A complete solution has not been obtained merely by combining
counts or through prediction agreement.

No global winner or automatic reconciliation rule is proposed. Nor was
reduction of manual work, cost or comparable latency measured: historical timings
have different scopes and unavailable resource consumption is not imputed. Evidence: A05
matrix and report, Q03 comparability limits.

### 5 What requires human review and more evidence

Priorities consistent with C01, without attributing invented error rates or times:

1. **Omissions:** to assert them, first agree on a reviewed reference;
   neither model agreement nor the visual count19 replaces it.
2. **Crops:** review caption labels and the two tables' borders, and the
   preceding fragment in p0-b12. The lower MinerU border retains uncertainty.
   Exporting or correcting crops would be another agreed increment, not done here.
3. **Mixtures:** preserve and review LM r13/r16/r18/r19/r22 and r21 against the desired
   region scope. Do not remove them through an area, confidence or IoU rule.
4. **Context and classification:** verify cross-column continuity and list
   granularity before labeling r12 or MinerU text as semantic errors.
5. **Generalization:** propose, without executing, a trial on the complete12.pdf and
   then1→2→4→8→14 SiC papers, reviewing diversity, errors and cost at each step.
   More pages require agreement; each new ColabT4 allocation requires authorization.

## What was checked and what remains open

Descriptive facts: exported records, categories, availability and statuses.
Visual judgments: mixtures, visible crop content and compliance with approved
criteria, attributed to the assistant. Hypotheses: list continuity and potential
complementarity. Technically validated results: hashes, typed references,
pair scope and S01 arithmetic; not parser detection accuracy.

The following remain open as scientific limitations, not executed tasks:
systematic omissions, OCR/LaTeX, strictly indeterminate border, absent LM crops,
semantic unit crossing columns, integration benefit and collection
quality. Each uncertainty is preserved instead of inventing thresholds,
GT or a winning box.

## Traceable evidence and closure of authorized stages

Separate reports:

- A03: `analytics/reports/sic12_page3-a03-associations.md`.
- A04: `analytics/reports/sic12_page3-a04-completeness.md`.
- A05: `analytics/reports/sic12_page3-a05-complementarity.md`.
- A06: this report; synthesis and approvals recorded in
  `analytics/results/sic12_page3/a06-20261024/`.

Each A03/A04/A05 folder preserves its own manifest, status and verifier. A03
includes 44 local tests (9 new and 35 previous) and an audit of 132 measures; A04
verifies 48 references/21 crops and border samples; A05 preserves 18 cases with three
axes and exact A04 statuses. A06 links those dependencies and records future
actions as execute_now=false. The final `completion-audit.json` audit and
`synthesis-status.json` establish final status after checking the
objective's full scope.

E03, new inference, automatic reconciliation, expansions,
installations or Colab allocations were not executed in these stages. Predictions,
ZIPs and previous datasets were not modified; interpretive revisions are documented
with new evidence and preserve historical records.

Authorized A03–A06 work closes with substantiated partial answers,
without confusing pilot closure with parser validation. Any subsequent trial,
reference or export change requires its specific agreement.
