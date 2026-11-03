# Instructions for reading_order

These rules apply to this directory and its subdirectories in every chat. They supplement the project root instructions; they do not expand authorization to execute operations or modify other directories.

## Structure and existing sources

- `code/`: implementation.
- `test/`: tests.
- `analytics/`: analysis.
- `raw_results/`: results, with `code_results/`, `tests_results/`, and `analytics_results/`.
- `docs/lecture_order_report.md`: existing context and background. Consult only the necessary sections; distinguish decisions, proposals, and evidence of execution.

Respect this structure. Do not create parallel directories or copy resources from other parts of the project when references are sufficient.

## Keep files and documentation minimal

1. Every file must serve a concrete purpose, and each piece of information must have a single source of truth. Before creating a file, check whether updating or referencing an existing one is sufficient.
2. Update existing documentation. Create another document only when it serves a distinct need that cannot reasonably be addressed there. Do not routinely generate READMEs, indexes, plans, handoffs, summaries, journals, or reports for each session or change.
3. Keep plans, progress updates, and explanations in the chat when they do not need to persist. Incorporate lasting decisions into the relevant document without duplicating content or accumulating a transcript of every session.
4. Reference existing code, data, configurations, results, and documentation using paths, links, or identifiers. Do not copy them to provide context or make a self-contained delivery unless there is an explicit portability or reproducibility need.
5. Do not routinely create or retain `legacy` files, `old`, `new`, or `v2` variants, duplicate implementations, or compatibility wrappers. Maintain compatibility only when a verified dependency requires it, and explain why. Experimental versions with a verifiable comparison purpose may require separate artifacts.
6. If duplicates or obsolete files are found, identify their references and dependencies and propose consolidation. This rule alone does not authorize deleting originals, evidence, historical results, or files outside the requested change.
7. Create only the backups required by applicable rules or a concrete recovery need, limited to the affected files. Do not routinely generate successive precautionary copies, full snapshots, or delivery bundles. Preserve provenance and artifacts that must be retained.
8. Store results in the appropriate destination and reference them from analyses; do not repeat the same result across directories or documents. Do not recreate existing artifacts merely to reconstruct context.

For a task limited to these instructions, modify only this `AGENTS.md`: do not add supplementary documentation or reorganize existing files.
