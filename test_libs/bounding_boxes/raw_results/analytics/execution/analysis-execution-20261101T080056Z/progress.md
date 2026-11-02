# Execution ledger — plan: test_libs/bounding_boxes/plan_analisis.md

User scope: execute automatic analysis of existing outputs; no reparsing, Colab, OCR, renders or visual review. Prepare the latter for later.

Ruling: work in the authorized folder with new analysis-only modules and a new output directory; do not create worktrees or commits — the plan explicitly preserves the workspace and .git is read-only. Cost if wrong: integration remains an uncommitted local change, not an isolated branch.

Ruling: use this persistent ledger instead of git-dependent skill helper scripts — no commits/worktree changes are authorized. Keep test and verification evidence here. Cost if wrong: helper tooling cannot reconstruct task commits; source/output hashes provide execution identity instead.

Pre-flight interfaces: F0 freezes protocol consumed by F1/F2; F1 verifies originals consumed by F2; F2 produces candidates consumed by F3 preparation; F4 remains pending; F5 extracts only recorded costs; F6 verifies automatic deliverables only. No human cases or semantic verdicts will be synthesized.

Status: implementing controls before the offline runner. Plan SHA256: 13b762a29fc2223a7390e7e1847656a71a360843101e20050b46e5a3d1975a79.

Core controls: 12 failures observed with the module absent, then 12/12 passed. One fixture initially hit Windows sandbox Temp access/cleanup restrictions; its root was moved to unique directories under runtime/analysis-test-artifacts without changing permissions or removing evidence. This does not resolve the historical new_code Windows issue.

Runner integration: fixture test failed with runner absent, then passed on real JSON/PDF-identity/background-identity fixture files. A separate missing-label test exposed false agreement from two null labels; RED→GREEN changed such pairs to unevaluable rather than agreement.

Implementation checks: `python -B -m unittest discover -s test_libs/bounding_boxes/analysis_tools/tests -v` — 14/14 PASS, including source immutability, no parent-bbox inheritance, exact union, retained low-IoU 1:n overlaps, null timing preservation, remote-ref hashing and output overwrite refusal.

Ruling: preserve the plan file unchanged and record phase completion in the analysis manifest — avoids rewriting the frozen protocol and conflating automatic completion with the deferred visual phases. Cost if wrong: readers must follow the manifest to see execution state.

Ruling: add an ordinal occurrence suffix to analysis UIDs — native duplicate detections can share identifiers; preserving every row prevents collisions from silently deduplicating content. Cost if wrong: analytical IDs are specific to this normalized input ordering; original IDs/references remain present.

Ruling: native patterns are availability descriptors of direct projected parentage, not verified semantic groups; opaque relation fields and PDF-dependent templates remain pending. Cost if wrong: potential capabilities outside that projection are not quantified, and must be examined visually/natively later.

Ready to execute F0–F2, prepare F3, extract the available F5 costs and verify technical F6. F4 and all visual/semantic conclusions remain deferred.

Final code review (fresh reviewer): no Critical findings; Important finding that failure extraction could only see final complete receipts. Two additional observations concerned temporal distributions and review evidence/date fields.

Final fix pass: historical attempt extraction now reads canonical assembled prior receipts with archive-manifest hashes, publishes versions and denominators per attempt, and skips reused Heron as a new execution. New historical-failure and detector-page-timing controls were observed RED before implementation; 16/16 controls now PASS, including an integration fixture containing both a failed prior configuration and corrected selected outputs. Review templates include evidence references and dates. No deferred review findings remain.

Ruling: stop the first automatic analysis before completion and preserve it as `analysis/auto-20261101T080056Z`, explicitly interrupted; execute the corrected program in `analysis/auto-20261101T080056Z-r2`. Cost if wrong: extra local processing of a partial subset, with no parser inference or remote cost. The partial run is not a completed result.

Performance correction: cache verified native file paths by remote file reference plus expected hash, while still resolving each JSON pointer and retaining all input SHA checks. This removes repeated Windows path resolution per detection without dropping evidence or pairs. The full input manifest is written after F1 as well as checked again at the end.

Ruling: per-attempt failure summaries cover collection attempts, with smoke/preparation/native-validation phases explicitly excluded from pooled denominators. Cost if wrong: phase-specific preparation reliability needs a separate analysis; collection failure frequencies remain scoped to observed attempts.

Clean verification command: `python -B -W error::ResourceWarning -m unittest discover -s test_libs/bounding_boxes/analysis_tools/tests -v` — 16/16 PASS. No parser, GPU, network or browser tests were run. Existing unrelated suites were not repeated because only the isolated analysis modules changed and the project forbids routine scientific reruns.

Completed execution: `python -B test_libs/bounding_boxes/analysis_tools/run_analysis.py --output test_libs/bounding_boxes/analysis/auto-20261101T080056Z-r2` — exit 0. F0/F1 complete; F2 automatic descriptors complete; F3 all review batches prepared with inventory/review pending; F4 not executed; F5 observed costs and separate collection failures extracted, semantic tradeoff valuation pending; F6 technical verification complete only.

Actual output: 15 papers, 397 pages, 1,588 tool/page outputs; 35,240 native rows; 35,778 positive overlap edges; 24,878 candidate components. There are 2,494 per-attribute geometry signals, not confirmed errors or unique affected boxes. All 397 review pages are explicitly not reviewed and all case inventories/assessments remain empty.

Technical verification: 2,452 input files hashed and unchanged, preserved metric counts reconciled, no dangling projected parent references, no source geometry_error values. Automatic run elapsed 114.464 s; OS peak analysis-process RSS 224,997,376 bytes (not parser/GPU memory).

Independent artifact audit: `python -B test_libs/bounding_boxes/runtime/analysis-execution-20261101T080056Z/verify_outputs.py` — PASS. It parsed output rows, checked all 397 unique pending review pages and background links, 794 recorded detector page timings, six separate attempt/tool summary rows, 22 preserved historical failure records, empty reviewed metrics, and current hashes of the frozen implementation and plan. No semantic validation was performed.

Deliverables: analysis/README.md routes to the completed r2 report, technical verification, datasets and review/index.md. The interrupted predecessor remains labeled partial, without a completion claim. Original result directories, new_code and the vault were not modified.
