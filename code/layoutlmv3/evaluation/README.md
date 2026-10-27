# Auditoría sin referencia: MVP

`audit.py` consume el `regions.json` de una sola página, sin importar `inference`,
PyTorch o Detectron2. Usa solo biblioteca estándar y sintaxis compatible con Python3.9.
La función no lee/escribe archivos, no muta la entrada y no elimina predicciones.

```python
from evaluation.audit import audit_regions

report = audit_regions(
    regions_document,
    iou_threshold=0.90,
    containment_threshold=0.95,
)
```

Los parámetros son obligatorios y deben ser finitos en (0,1]. Los valores0.90 y0.95
son **heurísticos exploratorios**, no calibrados ni umbrales de exactitud.

## Controles

1. **Validez técnica:** dimensiones, unidades, origen y formato del documento;
   IDs, categorías nativas, correspondencia class_id/type/native_label, score y
   cajas finitas, positivas y dentro del render.
2. **Posible duplicado:** misma clase e IoU mayor o igual al umbral.
3. **Conflicto de clase:** clases distintas e IoU mayor o igual al umbral.
4. **Posible anidamiento:** IoU por debajo del umbral de similitud e
   intersección/área de caja menor mayor o igual al umbral de contención.

Se compara cada par no ordenado una vez. Cada par produce como máximo una alerta;
similitud alta tiene prioridad sobre anidamiento para evitar doble conteo del mismo
par. Una región puede aparecer en varios pares: alert_count no es número de objetos
erróneos. Se informan IoU, coberturas de ambas cajas, IDs, índices, clases y scores.

El esquema global inválido lanza ValueError, porque no hay un marco fiable para
comparar coordenadas. Las regiones inválidas generan validation_errors y no
participan en pares; se conservan índices de entrada desde0 e IDs disponibles.
Para IDs duplicados se marcan todas sus apariciones. No hay filtrado por confianza.

El contrato es el formato actual de PubLayNet: text/title/list/table/figure.
Una categoría futura distinta requiere acordar un esquema nuevo, no se interpreta
silenciosamente como compatible. Cero regiones es entrada válida con cero pares;
no se convierte en100% de calidad. quality_score siempre es null.

## Ejecutar sobre el respaldo existente

Desde `code/layoutlmv3/`, ejemplo de lectura/escritura externa a la función:

```python
import json
import zipfile
from pathlib import Path
from evaluation.audit import audit_regions

archive = Path('../results/layoutlmv3-page/20261023T153938Z/result.zip')
with zipfile.ZipFile(archive) as source:
    regions = json.loads(source.read('page/regions.json'))
report = audit_regions(regions, iou_threshold=0.90, containment_threshold=0.95)
# Guardar report en una ruta de evaluación propia; nunca sobre regions.json.
```

El informe de esta ejecución ya existe en
`code/results/layoutlmv3-page/20261023T153938Z/audit/iou-0.90-containment-0.95/`.
No repetirlo para recuperar contexto. Incluye audit.json y provenance.json
(hash del archivo de código y del ZIP/miembro de entrada). No hace falta GPU.

## Límites

- Alertas geométricas no son errores confirmados, precisión ni recall.
- Un anidamiento puede ser legítimo y una mezcla puede no activar ninguna alerta.
- No identifica objetos nunca detectados ni sabe dónde terminan científicamente.
- No evalúa cobertura textual, outliers de tamaño, consistencia entre inferencias,
  ni usa referencias manuales. Son incrementos posteriores que debe decidir el usuario.
- O(N²) para pares: adecuado para las23 regiones y el límite actual de100 por página.

Pruebas nuevas: `test_audit.py`. Cubren geometría, umbrales, clases/IDs inválidos,
contención, ausencia de mutación, reproducibilidad y el resultado real guardado.
