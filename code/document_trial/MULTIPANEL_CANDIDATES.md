# Offline multipanel candidate API v1

`generate(R, expected_identity)` returns candidates/diagnostics; no accepted links.
`export(source_R, source_manifest, destination_json)` records hashes and protects
incompatible existing destinations. Coverage frozen at 0.90. Same-parent captions
with native Fig/Figure-number text only; no nearest-caption search. All external
TATR/LM evidence retained; no score ranking or model calls.

Authorized evaluation: pages 5,6,10,11 only. No CLI/remote execution.
Tests classified offline: with PYTHONPATH=code, run
`python -m unittest document_trial.test_multipanel_candidates document_trial.test_explicit_association -v`.
Inputs immutable; new sidecars only. See approved design/results in
analytics/analyses/paper/sic12-multipanel-candidates-*.md.
