# Evaluación documental de los 15 papers

Síntesis del resultado guardado, sin nuevo procesamiento, tuning ni adjudicación.
[Informe técnico](sic-parsing-operational-v1.md), [métricas consolidadas](../analyses/collection/parsing-operational-v1-evaluation.json),
[comparación de órdenes](../results/sic_collection/parsing-operational-v1-audit/comparison.json)
y [vistas/JSON](../results/sic_collection/parsing-operational-v1/index.html).

## Dictamen

MVP técnico automatizado útil y más integrado que el componente geométrico Docling
utilizado como baseline. Calidad semántica desigual y aún sin exactitud global.
No se comparó con todo el pipeline neuronal de Docling, que no fue ejecutado.
Misma configuración en 15 papers / 397 páginas; originales, 5.374 unidades y 4.512
apariciones preservadas. Sin ajustes manuales por documento ni GROBID.

## Aportes frente al baseline

- Estructura y recorrido conectados con IDs, fuentes, estados y alternativas: 478 nodos propuestos, 185 con parent y 3.298 unidades con contexto de sección.
- 24 cápsulas pasan al flujo de metadata como propuestas trazables, sin duplicar captions ni contenido.
- 174 de 23.563 pares comparables cambian de sentido (0,74%). No son 174 errores corregidos. Las 1.139 posiciones distintas incluyen corrimientos al separar metadata.
- En la revisión previa del agente de 12.pdf se conservan las 129 relaciones consideradas mejoras de Docling; cuatro de seis regresiones invierten su sentido y otras dos quedan en flujos separados. Solo abarca casos ya revisados, no GT humano ni exactitud global.
- Todas las salidas tienen JSON/visor comparativo y procedencia verificable. La automatización técnica en 15 documentos no demuestra precisión universal.

## Por paper

Función pendiente solo cuenta apariciones de contenido, excluyendo contenedores e
hijos diferidos. Pares cambiados excluyen elementos que pasan a otro flujo; no son
errores confirmados. Nodos de sección pueden contener hipótesis no reconciliadas.

| Paper | Pares cambiados vs Docling | Función pendiente / contenido | Nivel desconocido / nodos | Hijos diferidos |
| --- | ---: | ---: | ---: | ---: |
| 1 | 0 | 32 / 284 | 27 / 27 | 20 |
| 2 | 7 | 40 / 256 | 1 / 21 | 20 |
| 3 | 0 | 1 / 80 | 4 / 11 | 0 |
| 4 | 9 | 0 / 86 | 4 / 12 | 0 |
| 5 | 22 | 1 / 185 | 1 / 17 | 0 |
| 6 | 84 | 4 / 321 | 5 / 29 | 0 |
| 7 | 27 | 3 / 269 | 3 / 25 | 0 |
| 8 | 0 | 41 / 567 | 30 / 66 | 24 |
| 9 | 4 | 0 / 153 | 0 / 9 | 0 |
| 10 | 0 | 2 / 64 | 1 / 8 | 0 |
| 11 | 1 | 24 / 336 | 25 / 29 | 0 |
| 12 | 8 | 1 / 251 | 4 / 21 | 0 |
| 14 | 2 | 14 / 580 | 12 / 61 | 100 |
| 15 | 1 | 22 / 503 | 9 / 68 | 135 |
| 17 | 9 | 111 / 577 | 72 / 74 | 75 |

La jerarquía es especialmente incompleta en 1, 11 y 17. Los papers 6, 7 y 5 concentran
133 de 174 cambios de pares: prioridad de verificación, no errores adjudicados.
Paper 17 concentra 111 de 296 funciones pendientes de contenido. Paper 9 no tiene
subsecciones propuestas; cero parent no implica por sí solo fallo en un paper plano.

## Incertidumbre y revisión: denominadores distintos

| Medida | Casos | Interpretación |
| --- | ---: | --- |
| Revisión final por política | 5.374 unidades | No todas son errores ni ambiguas |
| Alguna advertencia heredada | 2.471 unidades | Avisos anteriores conservados |
| Categoría o función desconocida, unión sin duplicar | 1.292 unidades | 24,0% del inventario; incluye estructuras diferidas |
| Categoría desconocida | 209 unidades | No equivale a texto perdido |
| Función desconocida | 1.127 unidades | 374 hijos + 457 contenedores + 296 apariciones de contenido |
| Función desconocida en contenido | 296 / 4.512 | 6,6%; categoría previa puede estar resuelta |
| Contradicción semántica explícita | 25 unidades | Alternativas por dimensión conservadas |
| Nivel de sección desconocido | 198 / 478 nodos | 41,4%; no usar parent ausente como sinónimo de error |
| Numeración ambigua | 10 nodos | Hipótesis conservadas |
| Encabezado sin localizar | 10 nodos | No forzar identidad por proximidad |
| Sin contexto de sección en flujo principal | 123 unidades | Los 1.536 fuera del flujo principal no se cuentan como ese fallo |
| Continuidad ambigua | 102 relaciones | No aceptar por consecutividad o tema |
| Continuidad bloqueada | 16 relaciones | Abstención/alineación nativa insuficiente; no todos son hijos sin bbox |
| Continuidad con soporte | 127 relaciones | Sigue siendo candidata, no validada |
| Precedencia suspendida | 4 relaciones | Contradicción jerarquía/geometría; cero ciclos operativos |

No sumar filas: unidades, nodos y relaciones tienen granularidades y solapamientos
diferentes. 4.878 unidades no reciben un rol documental más específico; conservan
su categoría/función anterior. Ese campo auxiliar desconocido no significa 4.878
unidades completamente sin clasificar.

## Limitaciones que siguen abiertas

103 nodos tienen alineación nativa única; 235 son candidatos de título no resueltos,
120 propuestas de encabezado, 10 numeraciones ambiguas y 10 no localizados. Outlines
y títulos con diferencias de codificación pueden representar hipótesis duplicadas.
Niveles nativos y profundidad de marcador tienen distinto origen; el contrato explica
cómo interpretarlos. Pertenencia física depende del recorrido; no demuestra pertenencia
temática de figuras/tablas. Metadatos mixtos y columnas/flujos independientes siguen
pudiendo quedar provisionales. Los 374 hijos sin caja y sus 19 padres se mantienen;
las 17 páginas abstendidas no se fuerzan a lectura individual.

13 pruebas offline y 4.764 casos DOM respaldan integridad/interacción, no comprensión.
QA visual real y referencia semántica independiente pendientes. No se calculan
precision/recall/F1 ni se afirma mejora global sin adjudicación al final del MVP.
GROBID permanece pospuesto. Este informe no autoriza correcciones ni otra exportación.
