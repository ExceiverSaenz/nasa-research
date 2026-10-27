# Clasificación funcional offline MVP v1

## Uso en la integración canónica

La clasificación conciliada v2 sigue como fuente original inmutable; su semántica
operativa complementaria y recorrido están en [document_pipeline](../document_pipeline/README.md),
ejecutado en15 papers. El inventario no vuelve a clasificarse por parser. Roles nuevos
no sustituyen silenciosamente la categoría/función original; ambiguos y advertencias
permanecen. No reexportar el clasificador para actualizar documentación.

## Versión vigente: conciliación v2

La v1 inferior clasifica registros de fuentes y queda como intento histórico de
alcance incorrecto. No repetirla ni usar sus cifras como clasificación conciliada.
La entrada vigente v2 son objects/containers/groups de la reconciliación: categoría
conservada como semilla, etiquetas nativas y otros parsers como evidencia, sin
reemplazos silenciosos. Fuente de diseño:
[reconciled-v2-plan](../../analytics/analyses/collection/functional-classification-reconciled-v2-plan.md).

Módulos nuevos: `reconciled.py`, `export_reconciled.py`, `view.py` y viewer HTML/JS/CSS.
Los módulos v1 originales permanecen intactos. Pruebas offline v2:

```powershell
$env:PYTHONPATH='code'
python -B -m unittest functional_classification.test_reconciled functional_classification.test_view -v
node code/functional_classification/test_view.js analytics/results/sic12_document/functional-classification-reconciled-v2-view/index.html
```

Salida vigente `analytics/results/sic_collection/functional-classification-reconciled-v2`;
website local `analytics/results/sic12_document/functional-classification-reconciled-v2-view/index.html`.
HTML sin red externa; abrir index.html en navegador conservando images/ a su lado.
Las imágenes PNG originales se copian por bytes; el ajuste inicial es solo CSS.
La clasificación no ejecuta OCR/modelos/Colab ni calcula orden. No repetir exportación.
Grupos referencian miembros y captions; no reciben una caja envolvente inventada.

## Referencia histórica v1

Diseño/plan canónico:
[`functional-classification-mvp-v1-plan.md`](../../analytics/analyses/collection/functional-classification-mvp-v1-plan.md).
API pura `classifier.classify_document(document)`; entrada: un document.json de
reconciliación vigente, con todos sus registros/páginas. Salida: sidecar por paper,
registros originales íntegros, propuestas por categoría/subtipo/función, metadatos
por referencia, geometría relativa auxiliar y cola de revisión al final del MVP.
Relaciones/grupos/estados originales se conservan. No determina orden de lectura.

Solo biblioteca estándar. No modelos/OCR/red, entrenamiento ni scores inventados.
No importa ni ejecuta reconciliador. No cambia el esquema ni normalización originales.
Valores/reglas congelados en el plan y `classifier.CONFIG`; cobertura no es exactitud.
Los textos normalizados solo sirven para comparar: original_record conserva el literal.

Pruebas offline desde raíz:

```powershell
$env:PYTHONPATH='code'
python -B -m unittest functional_classification.test_classifier -v
```

Exportación **solo dentro del incremento autorizado**, a destino nuevo:

```powershell
$env:PYTHONPATH='code'
python -B -m functional_classification.export analytics/results/sic_collection/autonomous-reconciliation-v1 analytics/results/sic_collection/functional-classification-mvp-v1
```

No repetir por contexto. El exportador rechaza sobrescritura; verifica SHA256 de
fuentes nativas y protege todos los archivos de la colección de entrada. Guarda
manifest, summary, review-queue y papers/*/document.json; al fallar conserva parcial.
Las advertencias dicen «Requiere validación humana», `review_stage=after_full_mvp`.
Ninguna advertencia solicita intervención durante esta etapa. Decisiones automáticas
también quedan semánticamente sin validar. No se alteran abstenciones de página ni
se imputan cajas a hijos MinerU; clasificación y lectura son decisiones separadas.
