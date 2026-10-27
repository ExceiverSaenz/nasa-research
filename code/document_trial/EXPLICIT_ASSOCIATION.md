# Explicit Fig6 association

Offline API: `explicit_association.export(source_R, declaration, new_destination)`.
Reads R and sibling M0-native; validates baseline SHA256, identity, two distinct
figure references, caption role and native pointers/content. Writes group,
declaration and manifest separately. No source edits, model or Colab imports.
Conflicting destinations are protected; identical input is idempotent.
Only Fig6 is authorized. Explicit selection is not automatic discovery and
retains pending human validation. Schemas: explicit-figure-group/1 and
explicit-group-manifest/1. Group has references, no new bbox or duplicated text.

Tests: with PYTHONPATH=code at workspace root, run
`python -m unittest document_trial.test_explicit_association -v`.
Tests use existing p5 and temporary workspace folders, no subprocess/inference.
