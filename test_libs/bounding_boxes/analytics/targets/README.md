# Block targets

Result: [report](../../reports/final-target-analysis.md). Continues the already agreed labeling method, with a complete census and59 unique objects reviewed by the agent in65 ROIs. It is neither a human reference nor a random sample. Specification and decisions: [PROTOCOL.md](../../reports/context/docs/methodology/targets-protocol.md).

Original inputs, previous analysis, feedback, and viewer remain unchanged. No parser, OCR, model, Colab, or PDF rendering is run. Sheets use existing PNG backgrounds.

Scripts executed in order: prepare.py,review_figures.py, visual review and references.json, audit.py,profiles.py,caption_text.py,subtypes.py,report.py,verify.py. Paths for this delivery are fixed in scripts; do not run on the same destination to overwrite. `report.py` is a narrative specific to this collection; its interpretations require review with other inputs. Figures require already installed Matplotlib; calculations use stdlib.

Tests:

```powershell
python -B -m unittest discover -s test_libs/bounding_boxes/tests/analytics/targets -p 'test_*.py' -v
```

Ten checks: families, directional costs, multilabels, affiliation compatibility, separate absences, and caption/heading/number subtypes. Independent review detected an ARTICLE INFO duplicate, affiliation/footnote/list compatibility, and table_caption subtype on a figure caption. Counts and interpretation were corrected; an appropriate caption family remains separate from an incorrect subtype.

Initial audit results and the first report are preserved as diagnostics, outside the current output. Code snapshots fix changes to assess after case preparation; the family function did not change, checked in verify.py. Human feedback with ambiguous direction is neither edited nor reversed.

The targeted sample includes12 of19 headings in8.pdf. Do not turn its rates into an overall accuracy ranking. Comparison of all targets is in target_census.csv/target_patterns.csv; reviewed cases and their evidence in agent_reference_cases.jsonl/agent_assessments.jsonl. Subtype accuracy is additionally analyzed in agent_subtype_assessments.csv.
