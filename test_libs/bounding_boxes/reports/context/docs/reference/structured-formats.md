# Structured formats and retained identifiers



The English [integrated report](../../../final-integrated-report.md) explains the findings. JSON and JSONL descriptive fields (including observations, interpretations, limitations, notes and reference explanations) use English. Keys, identities, numeric results, geometry, scientific classifications and review states retain their existing contracts.



## Review issue codes



`issue_type` is a machine value shared by saved reviews, findings, the viewer and its validation API. `bbx/viewer.py` defines `ISSUES` and rejects unrecognized codes in `save_reviews`; `viewer/app.js` creates these option values and tests `revisada` when counting reviewed pages. Replacing saved values with translated strings would break that contract. Read the retained values with this English glossary:



| Stored value | English meaning |

| --- | --- |

| `mezcla` | Mixed content |

| `omision_aparente` | Apparent omission |

| `recorte` | Clipping |

| `exceso` | Excess coverage |

| `duplicado` | Duplicate |

| `fragmentacion` | Fragmentation |

| `union` | Merge |

| `etiqueta_incorrecta` | Incorrect label |

| `panel` | Panel |

| `identificador` | Identifier |

| `relacion` | Relationship |

| `revisada` | Reviewed |



These values occur in `results/smoke-20261101T011229Z/visual-review/findings.json`, `results/smoke-20261101T011229Z/viewer/reviews.json` and generated runtime test fixtures. Their accompanying review prose is English. A code records the original review category; it does not establish independent semantic validation.



## Exact source records



The following JSON files preserve original gateway queries, returned source metadata, excerpts, paths and hashes. Their Spanish source text and property names are retained as evidence; they are not current English report prose:



- `runtime/deep-analysis-context-query.json`: query for existing bounding-box geometry and category analysis, continuity and inventory, with originals preserved. `Vigente` means Current.

- `runtime/deep-analysis-book-query.json`: bibliographic foundation query covering histograms, spatial normalization, complete linkage versus chaining, evaluation without a reference, support/confidence and cross-page patterns, using existing results.

- `runtime/targets-book-query.json`: authorized target analysis query covering block labels, precision conditional on a reference, asymmetric heading/text costs and tool-specific error patterns. `Referencia` means Reference.



In source metadata, `Nota` means Note, `Carpeta` means Folder, `Tipo` means Type, `Funcion` means Function, `Revision documental` means Document review `estado_documental` means Document status and `fuentes` means Sources. `revisado_documentalmente` means Documentarily reviewed; `revision_documental_pendiente` means Document review pending. A gateway status of `awaiting_review` remains pending; preserving a record does not claim that gateway review accepted it.



Scientific parser outputs, extracted paper text, raw labels, bibliographic names and citation quotations remain source material. Their language, spelling and accents are part of the preserved evidence. Dependency caches, third-party package fixtures, exact query records and original external backups retain their original contents. First-party document filenames are now English; navigation references were updated, and the original names and bytes are preserved in the external migration backup. The two DOCX and two PPTX files in the recursive inventory are dependency default templates, not project reports; there are no XLSX or XLS workbooks in the inventory.



## Audit evidence



The complete recursive extension inventory, decoded JSON/JSONL candidate list and exception classification are recorded outside this directory in `history/bounding-boxes-root-report-and-formats-20261101T043323/`. The scan includes hidden and ignored files and parses escaped Unicode before inspecting string values and keys. Candidate matching is a screening aid; accents in author names and English words such as `union` do not by themselves identify untranslated prose.

