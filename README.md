# NASA Research — new_code

Paper processing with parsing, reconciliation, and Colab/R2 automation.

- [Prepare a clone and run](GETTING_STARTED.md)
- [new_code guide](new_code/README.md)
- [Automation](new_code/automation/README.md)
- [Tests](tests/README.md)

The operational source code is in `new_code/`. Running it requires Ubuntu/WSL,
an authenticated Colab CLI, private R2 configuration, and the original reference PDFs.
Model weights are downloaded according to the manifests; data, results, and credentials
are kept out of Git.
