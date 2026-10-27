# Document reconciliation through human decisions

Approved increment `final-reconciliation-v1`, offline. API: `build(root)` validates and composes; `export(root, destination)` exports the document, HTML view, manifest, and prior hashes. Standard libraries only, with no models, subprocesses, OCR, inference, or candidate regeneration.

Reads all thirteen R outputs using evaluation-manifest hashes. Checks each human decision against the candidate, baseline, manifest, M0 pointers, and LM evidence. Six accepted groups and single Fig5; explicit Fig6 is deduplicated if it matches. Acceptance resides in the human record, not in generator status. Original sources, geometry, text, and alternatives are preserved by reference.

The `test_final_reconciliation.py` tests are offline. Run with PYTHONPATH=code: `python -m unittest document_trial.test_final_reconciliation -v`. Do not repeat export to recover context. An incompatible destination is rejected. The view uses original renders through local paths; the project structure must be retained. Fig6 geometry and P7 remain pending.
