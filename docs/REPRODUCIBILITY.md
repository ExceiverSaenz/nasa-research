# Runtime and data requirements

## Integration

The frozen demo targets Python 3.13.5 on Linux x86_64. It pins PyMuPDF 1.27.2.3, Docling 2.123.1 and docling-core 2.92.0. See the existing `demo/integration_structure/requirements-runtime.lock`, `requirements-docling.txt` and README. The original parser adapters require separate environments; do not combine all requirements files into one environment.

The integration itself uses CPU. A100 is the requested demo environment, not a requirement for GPU inference in this integration. Its actual A100 execution remains pending.

## Data availability

The notebook requires the original `upload.zip` and matching `upload.sha256` from the research archive. That approximately 1.3 GB bundle includes third-party PDFs and parser outputs and is deliberately excluded. Obtain it through the approved private data channel. Keep its embedded expected hash unchanged. Without the bundle, the notebook documents the workflow but cannot reproduce the collection run.

The canonical pipeline consumes reading-v1 artifacts, reconciled/classified inventory, PDFs, and optionally approved caches. See `code/document_pipeline/README.md` for its input contract. A clean checkout alone does not contain those artifacts.

## Verification status

This snapshot checks source-copy integrity, Python syntax and notebook structure without processing papers. Historical test results in the research reports describe their original runs; they are not claimed as fresh tests of this checkout. Some integration/remote tests depend on omitted archives, configurations, external tools or data. Read each module guide before executing tests or launchers.

## Example data

Tests such as `code/reading_order/test_engine.py` and `code/document_pipeline/test_structure.py` contain synthetic fixtures illustrating the inventory and structure contracts. They are not real paper results. The JSON contract documents the full output format.
