# Reference-free audit: MVP

`audit.py` consumes `regions.json` for a single page without importing `inference`, PyTorch, or Detectron2. It uses only the standard library and Python 3.9-compatible syntax. The function does not read/write files, mutate the input, or remove predictions.

```python
from evaluation.audit import audit_regions

report = audit_regions(
    regions_document,
    iou_threshold=0.90,
    containment_threshold=0.95,
)
```

Parameters are required and must be finite within (0,1]. The values 0.90 and 0.95 are **exploratory heuristics**, neither calibrated nor accuracy thresholds.

## Checks

1. **Technical validity:** document dimensions, units, origin, and format; IDs, native categories, class_id/type/native_label correspondence, score, and finite, positive boxes within the render.
2. **Possible duplicate:** same class and IoU greater than or equal to the threshold.
3. **Class conflict:** different classes and IoU greater than or equal to the threshold.
4. **Possible nesting:** IoU below the similarity threshold and intersection/smaller-box area greater than or equal to the containment threshold.

Each unordered pair is compared once. Each pair produces at most one alert; high similarity takes priority over nesting to avoid counting the same pair twice. A region may appear in multiple pairs: alert_count is not a count of erroneous objects. IoU, coverage of both boxes, IDs, indices, classes, and scores are reported.

An invalid global schema raises ValueError because there is no reliable frame for comparing coordinates. Invalid regions produce validation_errors and do not participate in pairs; zero-based input indices and available IDs are retained. For duplicate IDs, all occurrences are flagged. There is no confidence filtering.

The contract is the current PubLayNet format: text/title/list/table/figure. A different future category requires agreement on a new schema; it is not silently interpreted as compatible. Zero regions is a valid input with zero pairs; it is not converted into 100% quality. quality_score is always null.

## Run against the existing backup

From `code/layoutlmv3/`, an example of file I/O outside the function:

```python
import json
import zipfile
from pathlib import Path
from evaluation.audit import audit_regions

archive = Path('../results/layoutlmv3-page/20261023T153938Z/result.zip')
with zipfile.ZipFile(archive) as source:
    regions = json.loads(source.read('page/regions.json'))
report = audit_regions(regions, iou_threshold=0.90, containment_threshold=0.95)
# Save report to a separate evaluation path; never overwrite regions.json.
```

The report from this execution already exists at `code/results/layoutlmv3-page/20261023T153938Z/audit/iou-0.90-containment-0.95/`. Do not repeat it to recover context. It includes audit.json and provenance.json (hashes of the code file and input ZIP/member). No GPU is needed.

## Limits

- Geometric alerts are not confirmed errors, precision, or recall.
- Nesting may be legitimate, and a merged region may trigger no alert.
- It does not identify objects that were never detected or know their scientific boundaries.
- It does not evaluate text coverage, size outliers, or consistency across inferences, and does not use manual references. These are later increments for the user to decide.
- O(N²) for pairs: suitable for the 23 regions and the current limit of 100 per page.

New tests: `test_audit.py`. They cover geometry, thresholds, invalid classes/IDs, containment, absence of mutation, reproducibility, and the saved real result.
