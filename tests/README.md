# Development Tests

These tests verify the code in `new_code/`; they are not an operational dependency.
You do not need to upload them to Colab to run the parser or reconciliation.

From the project root:

```powershell
python -B tests/run.py workflow --list
python -B tests/run.py workflow
python -B tests/run.py compatibility
python -B tests/run.py extended
```

- `workflow`: preparation tools, parsing, the compact contract, and the autonomous reconciliation system. Includes offline process tests and fixtures; does not run inference or remote services.
- `compatibility`: legacy reader with ZIP/sidecar support, required to maintain compatibility with previous attempts.
- `extended`: scientific algorithms, views, and optional adapters, including GROBID and historical comparisons. Some tests require project-specific evidence and dependencies; they are not routinely run with workflow.
- `all`: explicit union of the three Python suites.

The files are kept in place because some share fixtures through imports.
The JavaScript `test_*.js` tests in `integration/` are optional view checks
and are run with Node according to the viewer; the Python selector does not include them.

Local PDFs are stored in `papers/SiC_papers/` and
`papers/Tensile_Properties_of_Sub-sized_Specimens_papers/`.
The paths and names within historical fixtures describe their
transport contracts; they are not paths that must exist in the current root.
Existing results are not rewritten to update paths.
