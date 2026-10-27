# Clasificación funcional de la versión conciliada — v2

26oct2026. Corrección explícitamente autorizada del alcance del MVP anterior.
[Diseño/plan](../analyses/collection/functional-classification-reconciled-v2-plan.md).

## Problema y decisión

V1 clasificó todos los registros de parsers, en vez de unidades conciliadas.
Sus resultados se conservan como intento histórico, pero no representan el MVP
solicitado. No comparar directamente sus conteos de cobertura con los de v2.
V2 toma exactamente objects/containers/groups declarados en la conciliación guardada.
No rehace conciliación ni determina selección por parser o por score.

La categoría, estado y motivo conservados en conciliación son evidencia inicial
explícita. El análisis geométrico/NLP usa vecinos conciliados; las etiquetas
nativas, detecciones externas comparables y decisiones previas solo aportan
evidencia, soporte grueso o contradicción. Diferencias no se borran ni se resuelven
por mayoría. Relaciones de caption y miembros de grupo aportan contexto funcional;
conservan autoridad y advertencias, sin nueva aceptación humana.

## Salida

`analytics/results/sic_collection/functional-classification-reconciled-v2/`:
summary, manifest, review-queue y document.json por paper.

- 15 papers / 397 páginas.
- **5343 regiones conciliadas:** 4886 segmentos +457 contenedores.
- **31 grupos lógicos**, referidos a miembros existentes, sin nuevas cajas.
- 6124 registros alternativos separados como evidence_records; no reciben
  clasificación funcional ni se convierten en objetos adicionales.
- Todos los 11467 registros fuente originales siguen preservados en su capa
  correspondiente y en las fuentes intactas; IDs y procedencia sin sustitución.
- 4219 funciones propuestas automáticamente y 1155 abstenciones sobre **5374
  unidades estructurales** (regiones+grupos, no objetos semánticos disjuntos).
- 2471 unidades con alguna advertencia, de función/categoría/subtipo/geometría o
  estado heredado. Advertencia «Requiere validación humana», revisión after_full_mvp.
  La cobertura no representa exactitud y no solicita revisión humana inmediata.

Se conservan 374 hijos sin bbox, padres y abstención de página completa en las
17 páginas afectadas. Relaciones, grupos, decisiones, correspondencias y estados
originales preservados; categorías conciliadas no reemplazadas silenciosamente.
Reading order sigue unresolved. Validación semántica al final del MVP completo.

## Website de 12.pdf

[Abrir website local responsive](../results/sic12_document/functional-classification-reconciled-v2-view/index.html).
13 páginas, 251 segmentos +36 contenedores y 6 grupos conciliados. Una sola capa,
sin selector de parser. Color por categoría o función, navegación, zoom y contenedores.
Categoría conservada, propuestas, alternativas y evidencia accesibles en inspector.
Los grupos seleccionan las cajas originales de sus miembros, sin nueva envolvente.

PNG originales copiados por bytes y verificados por hash; no resize/recompresión.
Ajuste inicial al ancho mediante CSS, zoom optativo. Grid de lectura+inspector en
desktop, inspector debajo en móvil; sin altura fija ni scroll interno obligatorio
para la página ajustada. No publicación externa ni subida de papers.

## Verificación y límites

15 pruebas Python offline pasan; 52 combinaciones de página/color/contenedores y
selección de grupos/zoom verificadas con DOM simulado. Node verifica sintaxis JS.
Revisión independiente confirmó elegibilidad, abstenciones y presentación estática.
Se corrigió con regresión rojo→verde que una fuente seleccionada fallida pudiera
influir en otra; también se conserva abstención explícita del grupo.

Baseline: 63 outputs y cuatro módulos históricos verificados antes de exportar.
1164 archivos de entrada protegidos y 25 archivos anteriores de clasificación/vista
intactos. Exportación semántica única; auditoría verifica conjuntos exactos,
original_record/evidence completos, categorías semilla y abstenciones/relaciones.
13 PNG y HTML final verificados por hash.

**QA visual real pendiente:** el navegador de pruebas no alcanzó localhost
(ERR_CONNECTION_TIMED_OUT). No afirmar responsive validado en navegador por pasar
pruebas simuladas. Se entrega el website local y su verificación automatizada.

[Auditoría](../results/sic_collection/functional-classification-reconciled-v2-audit/verification.json).
Sin OCR, modelos, Colab, nuevos renders ni cambios en resultados anteriores.
Reglas geométricas/NLP congeladas, sin tuning sobre los resultados. Pipeline
canónico y V&V pendientes. Parar corrección tras entrega; siguiente etapa: diseño
del orden documental sobre la conciliación, no ejecución automática.


## Métricas descriptivas por paper y categoría (ampliación documental)

Esta sección agrega únicamente datos de la salida v2 guardada. No ejecuta el
clasificador ni modifica etiquetas, estados, advertencias, cajas o vínculos. Los
conteos describen decisiones del sistema; no son precisión, recall, F1 ni tasa de
error. La revisión semántica humana permanece al final del MVP completo.

### Definiciones, denominadores y criterios

Para cada dimensión d (categoría, función y subtipo):

- **Cobertura C_d = unidades con value no nulo / N.** Incluye categorías conservadas;
  no significa corrección nueva, certeza ni validación humana.
- **Abstención A_d = unidades con status=abstained / N.** En esta salida C_d+A_d=1
  en cada estrato. Puede deberse a candidatos múltiples, falta de candidato o bloqueo
  de una propuesta única por restricciones de la página; no siempre es ambigüedad.
- **Advertencias W = unidades únicas con una o más advertencias / N.** No sumar
  motivos: una unidad puede aparecer en varios. Tener propuesta no elimina advertencias.
- **Cobertura conjunta = unidades con categoría y función no nulas / N**; cobertura
  completa exige además subtipo no nulo. Ninguna de ambas certifica exactitud.
- N incluye segmentos, contenedores y grupos declarados. Los grupos referencian
  miembros y los contenedores contienen hijos; no son objetos semánticos disjuntos
  ni muestras independientes. Los 6124 registros externos solo aportan evidencia.
- Se agrupa por **categoría propuesta efectiva**; value=null aparece en Ambigua.
  La categoría retenida original sigue en los JSON de entrada. Ambigua no es GT.
- Un estrato N=0 se muestra como **— (no aplica)**, no 0 % de cobertura/abstención.
  Todos los porcentajes de cada fila usan el N de esa misma fila y se redondean a
  dos decimales; los conteos son exactos. Los motivos no cambian el denominador.

Datos completos reutilizables: [metrics.json](../results/sic_collection/functional-classification-reconciled-v2-metrics/metrics.json).

### Resumen global

| Dimensión (N=5374) | Con propuesta única: n (%) | Abstención: n (%) |
| --- | --- | --- |
| Categoría | 5 165 (96,11 %) | 209 (3,89 %) |
| Función | 4 219 (78,51 %) | 1 155 (21,49 %) |
| Subtipo | 3 680 (68,48 %) | 1 694 (31,52 %) |

Advertencias: **2 471 (45,98 %)**. Cobertura conjunta categoría+función: **4 060 (75,55 %)**. Las tres dimensiones: **2 934 (54,60 %)**.

### Separación por tipo de unidad

| Unidad | N | Categoría C / A | Función C / A | Subtipo C / A | Con advertencia n (%) |
| --- | --- | --- | --- | --- | --- |
| Segmento | 4 886 | 4 677 / 209 | 4 188 / 698 | 3 649 / 1 237 | 1 983 (40,59 %) |
| Contenedor | 457 | 457 / 0 | 0 / 457 | 0 / 457 | 457 (100,00 %) |
| Grupo lógico | 31 | 31 / 0 | 31 / 0 | 31 / 0 | 31 (100,00 %) |

C / A expresa conteos con propuesta única / abstención. Los 31 grupos tienen las tres dimensiones propuestas, pero heredan advertencias de miembros o del grupo. Los 457 contenedores conservan su categoría y no tienen función/subtipo efectivo asignados.

### Desglose por paper

Cada cobertura se acompaña de la abstención correspondiente, con el mismo denominador.

| Paper | N | Cat. C / A | Func. C / A | Func. C % / A % | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| 1.pdf | 331 | 307 / 24 | 252 / 79 | 76,13 % / 23,87 % | 243 / 88 | 144 (43,50 %) |
| 2.pdf | 303 | 302 / 1 | 218 / 85 | 71,95 % / 28,05 % | 227 / 76 | 139 (45,87 %) |
| 3.pdf | 89 | 86 / 3 | 79 / 10 | 88,76 % / 11,24 % | 57 / 32 | 34 (38,20 %) |
| 4.pdf | 94 | 93 / 1 | 86 / 8 | 91,49 % / 8,51 % | 69 / 25 | 25 (26,60 %) |
| 5.pdf | 204 | 203 / 1 | 185 / 19 | 90,69 % / 9,31 % | 144 / 60 | 65 (31,86 %) |
| 6.pdf | 390 | 382 / 8 | 319 / 71 | 81,79 % / 18,21 % | 210 / 180 | 193 (49,49 %) |
| 7.pdf | 299 | 293 / 6 | 264 / 35 | 88,29 % / 11,71 % | 189 / 110 | 122 (40,80 %) |
| 8.pdf | 607 | 557 / 50 | 504 / 103 | 83,03 % / 16,97 % | 521 / 86 | 193 (31,80 %) |
| 9.pdf | 187 | 186 / 1 | 156 / 31 | 83,42 % / 16,58 % | 87 / 100 | 104 (55,62 %) |
| 10.pdf | 69 | 68 / 1 | 62 / 7 | 89,86 % / 10,14 % | 55 / 14 | 16 (23,19 %) |
| 11.pdf | 365 | 356 / 9 | 314 / 51 | 86,03 % / 13,97 % | 223 / 142 | 168 (46,03 %) |
| 12.pdf | 293 | 291 / 2 | 255 / 38 | 87,03 % / 12,97 % | 172 / 121 | 130 (44,37 %) |
| 14.pdf | 740 | 730 / 10 | 571 / 169 | 77,16 % / 22,84 % | 540 / 200 | 328 (44,32 %) |
| 15.pdf | 694 | 663 / 31 | 486 / 208 | 70,03 % / 29,97 % | 467 / 227 | 405 (58,36 %) |
| 17.pdf | 709 | 648 / 61 | 468 / 241 | 66,01 % / 33,99 % | 476 / 233 | 405 (57,12 %) |

Cobertura funcional micro (todas las unidades): **78,51 %**; macro por paper (mismo peso a cada documento): **82,11 %**. Advertencias micro: **45,98 %**; macro: **42,48 %**. Rango funcional observado: **66,01 %–91,49 %**. Son estadísticas de esta colección, sin intervalos de confianza ni generalización poblacional.

### Desglose global por categoría

Como se agrupa por la categoría efectiva, la cobertura de categoría es 100 % en
las categorías resueltas y 0 % en Ambigua por construcción; no es desempeño por
clase ni una matriz de confusión. Las coberturas de función/subtipo sí muestran
qué otras decisiones quedan pendientes dentro de cada categoría propuesta.

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 2 752 | 2 752 / 0 | 2 331 (84,70 %) | 421 (15,30 %) | 2 728 / 24 | 421 (15,30 %) |
| Título | 469 | 469 / 0 | 256 (54,58 %) | 213 (45,42 %) | 469 / 0 | 213 (45,42 %) |
| Figura | 781 | 781 / 0 | 404 (51,73 %) | 377 (48,27 %) | 31 / 750 | 781 (100,00 %) |
| Tabla | 119 | 119 / 0 | 57 (47,90 %) | 62 (52,10 %) | 0 / 119 | 119 (100,00 %) |
| Caption | 337 | 337 / 0 | 337 (100,00 %) | 0 (0,00 %) | 95 / 242 | 242 (71,81 %) |
| Ecuación | 67 | 67 / 0 | 67 (100,00 %) | 0 (0,00 %) | 67 / 0 | 0 (0,00 %) |
| Margen | 640 | 640 / 0 | 608 (95,00 %) | 32 (5,00 %) | 186 / 454 | 486 (75,94 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 209 | 0 / 209 | 159 (76,08 %) | 50 (23,92 %) | 104 / 105 | 209 (100,00 %) |

### Cruce paper × categoría

Las nueve categorías se conservan en cada paper, incluso si N=0. C / A son conteos; las tasas de función y advertencias tienen denominador local. Las tasas de categoría/subtipo también están calculadas en metrics.json.

#### 1.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 151 | 151 / 0 | 128 (84,77 %) | 23 (15,23 %) | 150 / 1 | 23 (15,23 %) |
| Título | 27 | 27 / 0 | 2 (7,41 %) | 25 (92,59 %) | 27 / 0 | 25 (92,59 %) |
| Figura | 44 | 44 / 0 | 22 (50,00 %) | 22 (50,00 %) | 0 / 44 | 44 (100,00 %) |
| Tabla | 8 | 8 / 0 | 4 (50,00 %) | 4 (50,00 %) | 0 / 8 | 8 (100,00 %) |
| Caption | 21 | 21 / 0 | 21 (100,00 %) | 0 (0,00 %) | 6 / 15 | 15 (71,43 %) |
| Ecuación | 0 | — | — | — | — | — |
| Margen | 56 | 56 / 0 | 51 (91,07 %) | 5 (8,93 %) | 56 / 0 | 5 (8,93 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 24 | 0 / 24 | 24 (100,00 %) | 0 (0,00 %) | 4 / 20 | 24 (100,00 %) |

#### 2.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 188 | 188 / 0 | 145 (77,13 %) | 43 (22,87 %) | 186 / 2 | 43 (22,87 %) |
| Título | 24 | 24 / 0 | 15 (62,50 %) | 9 (37,50 %) | 24 / 0 | 9 (37,50 %) |
| Figura | 45 | 45 / 0 | 23 (51,11 %) | 22 (48,89 %) | 3 / 42 | 45 (100,00 %) |
| Tabla | 2 | 2 / 0 | 1 (50,00 %) | 1 (50,00 %) | 0 / 2 | 2 (100,00 %) |
| Caption | 13 | 13 / 0 | 13 (100,00 %) | 0 (0,00 %) | 4 / 9 | 9 (69,23 %) |
| Ecuación | 0 | — | — | — | — | — |
| Margen | 30 | 30 / 0 | 20 (66,67 %) | 10 (33,33 %) | 10 / 20 | 30 (100,00 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 1 | 0 / 1 | 1 (100,00 %) | 0 (0,00 %) | 0 / 1 | 1 (100,00 %) |

#### 3.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 36 | 36 / 0 | 36 (100,00 %) | 0 (0,00 %) | 36 / 0 | 0 (0,00 %) |
| Título | 11 | 11 / 0 | 10 (90,91 %) | 1 (9,09 %) | 11 / 0 | 1 (9,09 %) |
| Figura | 16 | 16 / 0 | 8 (50,00 %) | 8 (50,00 %) | 0 / 16 | 16 (100,00 %) |
| Tabla | 2 | 2 / 0 | 1 (50,00 %) | 1 (50,00 %) | 0 / 2 | 2 (100,00 %) |
| Caption | 10 | 10 / 0 | 10 (100,00 %) | 0 (0,00 %) | 1 / 9 | 9 (90,00 %) |
| Ecuación | 0 | — | — | — | — | — |
| Margen | 11 | 11 / 0 | 11 (100,00 %) | 0 (0,00 %) | 8 / 3 | 3 (27,27 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 3 | 0 / 3 | 3 (100,00 %) | 0 (0,00 %) | 1 / 2 | 3 (100,00 %) |

#### 4.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 46 | 46 / 0 | 46 (100,00 %) | 0 (0,00 %) | 46 / 0 | 0 (0,00 %) |
| Título | 11 | 11 / 0 | 11 (100,00 %) | 0 (0,00 %) | 11 / 0 | 0 (0,00 %) |
| Figura | 16 | 16 / 0 | 8 (50,00 %) | 8 (50,00 %) | 0 / 16 | 16 (100,00 %) |
| Tabla | 0 | — | — | — | — | — |
| Caption | 9 | 9 / 0 | 9 (100,00 %) | 0 (0,00 %) | 4 / 5 | 5 (55,56 %) |
| Ecuación | 0 | — | — | — | — | — |
| Margen | 11 | 11 / 0 | 11 (100,00 %) | 0 (0,00 %) | 8 / 3 | 3 (27,27 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 1 | 0 / 1 | 1 (100,00 %) | 0 (0,00 %) | 0 / 1 | 1 (100,00 %) |

#### 5.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 102 | 102 / 0 | 102 (100,00 %) | 0 (0,00 %) | 102 / 0 | 0 (0,00 %) |
| Título | 19 | 19 / 0 | 17 (89,47 %) | 2 (10,53 %) | 19 / 0 | 2 (10,53 %) |
| Figura | 32 | 32 / 0 | 17 (53,12 %) | 15 (46,88 %) | 2 / 30 | 32 (100,00 %) |
| Tabla | 4 | 4 / 0 | 2 (50,00 %) | 2 (50,00 %) | 0 / 4 | 4 (100,00 %) |
| Caption | 16 | 16 / 0 | 16 (100,00 %) | 0 (0,00 %) | 6 / 10 | 10 (62,50 %) |
| Ecuación | 6 | 6 / 0 | 6 (100,00 %) | 0 (0,00 %) | 6 / 0 | 0 (0,00 %) |
| Margen | 24 | 24 / 0 | 24 (100,00 %) | 0 (0,00 %) | 8 / 16 | 16 (66,67 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 1 | 0 / 1 | 1 (100,00 %) | 0 (0,00 %) | 1 / 0 | 1 (100,00 %) |

#### 6.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 106 | 106 / 0 | 106 (100,00 %) | 0 (0,00 %) | 106 / 0 | 0 (0,00 %) |
| Título | 25 | 25 / 0 | 22 (88,00 %) | 3 (12,00 %) | 25 / 0 | 3 (12,00 %) |
| Figura | 128 | 128 / 0 | 65 (50,78 %) | 63 (49,22 %) | 2 / 126 | 128 (100,00 %) |
| Tabla | 8 | 8 / 0 | 4 (50,00 %) | 4 (50,00 %) | 0 / 8 | 8 (100,00 %) |
| Caption | 59 | 59 / 0 | 59 (100,00 %) | 0 (0,00 %) | 39 / 20 | 20 (33,90 %) |
| Ecuación | 30 | 30 / 0 | 30 (100,00 %) | 0 (0,00 %) | 30 / 0 | 0 (0,00 %) |
| Margen | 26 | 26 / 0 | 26 (100,00 %) | 0 (0,00 %) | 0 / 26 | 26 (100,00 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 8 | 0 / 8 | 7 (87,50 %) | 1 (12,50 %) | 8 / 0 | 8 (100,00 %) |

#### 7.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 140 | 140 / 0 | 140 (100,00 %) | 0 (0,00 %) | 140 / 0 | 0 (0,00 %) |
| Título | 26 | 26 / 0 | 21 (80,77 %) | 5 (19,23 %) | 26 / 0 | 5 (19,23 %) |
| Figura | 53 | 53 / 0 | 27 (50,94 %) | 26 (49,06 %) | 1 / 52 | 53 (100,00 %) |
| Tabla | 6 | 6 / 0 | 3 (50,00 %) | 3 (50,00 %) | 0 / 6 | 6 (100,00 %) |
| Caption | 20 | 20 / 0 | 20 (100,00 %) | 0 (0,00 %) | 7 / 13 | 13 (65,00 %) |
| Ecuación | 1 | 1 / 0 | 1 (100,00 %) | 0 (0,00 %) | 1 / 0 | 0 (0,00 %) |
| Margen | 47 | 47 / 0 | 47 (100,00 %) | 0 (0,00 %) | 8 / 39 | 39 (82,98 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 6 | 0 / 6 | 5 (83,33 %) | 1 (16,67 %) | 6 / 0 | 6 (100,00 %) |

#### 8.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 414 | 414 / 0 | 387 (93,48 %) | 27 (6,52 %) | 411 / 3 | 27 (6,52 %) |
| Título | 65 | 65 / 0 | 20 (30,77 %) | 45 (69,23 %) | 65 / 0 | 45 (69,23 %) |
| Figura | 8 | 8 / 0 | 4 (50,00 %) | 4 (50,00 %) | 0 / 8 | 8 (100,00 %) |
| Tabla | 14 | 14 / 0 | 5 (35,71 %) | 9 (64,29 %) | 0 / 14 | 14 (100,00 %) |
| Caption | 8 | 8 / 0 | 8 (100,00 %) | 0 (0,00 %) | 0 / 8 | 8 (100,00 %) |
| Ecuación | 0 | — | — | — | — | — |
| Margen | 48 | 48 / 0 | 47 (97,92 %) | 1 (2,08 %) | 8 / 40 | 41 (85,42 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 50 | 0 / 50 | 33 (66,00 %) | 17 (34,00 %) | 37 / 13 | 50 (100,00 %) |

#### 9.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 69 | 69 / 0 | 69 (100,00 %) | 0 (0,00 %) | 69 / 0 | 0 (0,00 %) |
| Título | 6 | 6 / 0 | 6 (100,00 %) | 0 (0,00 %) | 6 / 0 | 0 (0,00 %) |
| Figura | 65 | 65 / 0 | 34 (52,31 %) | 31 (47,69 %) | 3 / 62 | 65 (100,00 %) |
| Tabla | 0 | — | — | — | — | — |
| Caption | 17 | 17 / 0 | 17 (100,00 %) | 0 (0,00 %) | 0 / 17 | 17 (100,00 %) |
| Ecuación | 2 | 2 / 0 | 2 (100,00 %) | 0 (0,00 %) | 2 / 0 | 0 (0,00 %) |
| Margen | 27 | 27 / 0 | 27 (100,00 %) | 0 (0,00 %) | 6 / 21 | 21 (77,78 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 1 | 0 / 1 | 1 (100,00 %) | 0 (0,00 %) | 1 / 0 | 1 (100,00 %) |

#### 10.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 47 | 47 / 0 | 47 (100,00 %) | 0 (0,00 %) | 47 / 0 | 0 (0,00 %) |
| Título | 8 | 8 / 0 | 6 (75,00 %) | 2 (25,00 %) | 8 / 0 | 2 (25,00 %) |
| Figura | 7 | 7 / 0 | 3 (42,86 %) | 4 (57,14 %) | 0 / 7 | 7 (100,00 %) |
| Tabla | 2 | 2 / 0 | 1 (50,00 %) | 1 (50,00 %) | 0 / 2 | 2 (100,00 %) |
| Caption | 4 | 4 / 0 | 4 (100,00 %) | 0 (0,00 %) | 0 / 4 | 4 (100,00 %) |
| Ecuación | 0 | — | — | — | — | — |
| Margen | 0 | — | — | — | — | — |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 1 | 0 / 1 | 1 (100,00 %) | 0 (0,00 %) | 0 / 1 | 1 (100,00 %) |

#### 11.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 166 | 166 / 0 | 166 (100,00 %) | 0 (0,00 %) | 166 / 0 | 0 (0,00 %) |
| Título | 29 | 29 / 0 | 5 (17,24 %) | 24 (82,76 %) | 29 / 0 | 24 (82,76 %) |
| Figura | 50 | 50 / 0 | 26 (52,00 %) | 24 (48,00 %) | 2 / 48 | 50 (100,00 %) |
| Tabla | 6 | 6 / 0 | 3 (50,00 %) | 3 (50,00 %) | 0 / 6 | 6 (100,00 %) |
| Caption | 23 | 23 / 0 | 23 (100,00 %) | 0 (0,00 %) | 8 / 15 | 15 (65,22 %) |
| Ecuación | 0 | — | — | — | — | — |
| Margen | 82 | 82 / 0 | 82 (100,00 %) | 0 (0,00 %) | 18 / 64 | 64 (78,05 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 9 | 0 / 9 | 9 (100,00 %) | 0 (0,00 %) | 0 / 9 | 9 (100,00 %) |

#### 12.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 126 | 126 / 0 | 126 (100,00 %) | 0 (0,00 %) | 126 / 0 | 0 (0,00 %) |
| Título | 19 | 19 / 0 | 17 (89,47 %) | 2 (10,53 %) | 19 / 0 | 2 (10,53 %) |
| Figura | 70 | 70 / 0 | 38 (54,29 %) | 32 (45,71 %) | 6 / 64 | 70 (100,00 %) |
| Tabla | 8 | 8 / 0 | 4 (50,00 %) | 4 (50,00 %) | 0 / 8 | 8 (100,00 %) |
| Caption | 28 | 28 / 0 | 28 (100,00 %) | 0 (0,00 %) | 4 / 24 | 24 (85,71 %) |
| Ecuación | 8 | 8 / 0 | 8 (100,00 %) | 0 (0,00 %) | 8 / 0 | 0 (0,00 %) |
| Margen | 32 | 32 / 0 | 32 (100,00 %) | 0 (0,00 %) | 8 / 24 | 24 (75,00 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 2 | 0 / 2 | 2 (100,00 %) | 0 (0,00 %) | 1 / 1 | 2 (100,00 %) |

#### 14.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 446 | 446 / 0 | 343 (76,91 %) | 103 (23,09 %) | 443 / 3 | 103 (23,09 %) |
| Título | 58 | 58 / 0 | 47 (81,03 %) | 11 (18,97 %) | 58 / 0 | 11 (18,97 %) |
| Figura | 93 | 93 / 0 | 49 (52,69 %) | 44 (47,31 %) | 5 / 88 | 93 (100,00 %) |
| Tabla | 16 | 16 / 0 | 8 (50,00 %) | 8 (50,00 %) | 0 / 16 | 16 (100,00 %) |
| Caption | 45 | 45 / 0 | 45 (100,00 %) | 0 (0,00 %) | 6 / 39 | 39 (86,67 %) |
| Ecuación | 6 | 6 / 0 | 6 (100,00 %) | 0 (0,00 %) | 6 / 0 | 0 (0,00 %) |
| Margen | 66 | 66 / 0 | 63 (95,45 %) | 3 (4,55 %) | 13 / 53 | 56 (84,85 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 10 | 0 / 10 | 10 (100,00 %) | 0 (0,00 %) | 9 / 1 | 10 (100,00 %) |

#### 15.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 348 | 348 / 0 | 208 (59,77 %) | 140 (40,23 %) | 343 / 5 | 140 (40,23 %) |
| Título | 66 | 66 / 0 | 52 (78,79 %) | 14 (21,21 %) | 66 / 0 | 14 (21,21 %) |
| Figura | 66 | 66 / 0 | 35 (53,03 %) | 31 (46,97 %) | 5 / 61 | 66 (100,00 %) |
| Tabla | 29 | 29 / 0 | 14 (48,28 %) | 15 (51,72 %) | 0 / 29 | 29 (100,00 %) |
| Caption | 35 | 35 / 0 | 35 (100,00 %) | 0 (0,00 %) | 5 / 30 | 30 (85,71 %) |
| Ecuación | 9 | 9 / 0 | 9 (100,00 %) | 0 (0,00 %) | 9 / 0 | 0 (0,00 %) |
| Margen | 110 | 110 / 0 | 102 (92,73 %) | 8 (7,27 %) | 23 / 87 | 95 (86,36 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 31 | 0 / 31 | 31 (100,00 %) | 0 (0,00 %) | 16 / 15 | 31 (100,00 %) |

#### 17.pdf

| Categoría | N | Cat. C / A | Función C n (%) | Función A n (%) | Subtipo C / A | Advertencias n (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Texto | 367 | 367 / 0 | 282 (76,84 %) | 85 (23,16 %) | 357 / 10 | 85 (23,16 %) |
| Título | 75 | 75 / 0 | 5 (6,67 %) | 70 (93,33 %) | 75 / 0 | 70 (93,33 %) |
| Figura | 88 | 88 / 0 | 45 (51,14 %) | 43 (48,86 %) | 2 / 86 | 88 (100,00 %) |
| Tabla | 14 | 14 / 0 | 7 (50,00 %) | 7 (50,00 %) | 0 / 14 | 14 (100,00 %) |
| Caption | 29 | 29 / 0 | 29 (100,00 %) | 0 (0,00 %) | 5 / 24 | 24 (82,76 %) |
| Ecuación | 5 | 5 / 0 | 5 (100,00 %) | 0 (0,00 %) | 5 / 0 | 0 (0,00 %) |
| Margen | 70 | 70 / 0 | 65 (92,86 %) | 5 (7,14 %) | 12 / 58 | 63 (90,00 %) |
| Otros | 0 | — | — | — | — | — |
| Ambigua | 61 | 0 / 61 | 30 (49,18 %) | 31 (50,82 %) | 20 / 41 | 61 (100,00 %) |

### Pendientes estructurales y decisiones diferidas: no confundir con errores

El ejemplo parent con bbox y child con texto pero bbox=null representa contenido
preservado con geometría pendiente, no pérdida de texto ni error semántico probado.
En la salida actual hay **374 hijos textuales sin caja y 19 contenedores padres index**
con caja conservada. Esta es una decisión explícitamente diferida por el usuario.
No imputar la caja del padre al hijo, borrar registros ni levantar abstenciones.

Se distinguen tres niveles relacionados, que no deben sumarse:

1. **Hijos sin caja: 374.** Pendiente geométrico individual conservado.
2. **Abstención heredada de página: 473 unidades en 17 páginas.** Incluye hijos,
   padres y otros registros afectados por la regla conservadora de página completa.
   No implica que todos esos registros tengan geometría inválida.
3. **Función de contenedor pendiente: 457 contenedores.** Pendiente general del
   diseño actual; solo 19 son los padres index de estos hijos. No atribuir los 457
   completos al incidente de hijos sin coordenadas ni a una nueva decisión humana.

La unión de marcas de contenedor pendiente y abstención geométrica de página tiene
**910 unidades**, todas con función abstendida: 457+473−20=910. Las 374 marcas de
hijos sin caja están incluidas en la abstención de página. El solapamiento de 20
contenedores de páginas abstendidas no equivale a los 19 padres index: también hay
otro contenedor afectado. **910 de las 1155 abstenciones (78,79 %) tienen al menos
una de esas marcas estructurales**; quedan 245 sin ellas. Esta asociación de motivos
no demuestra causalidad exclusiva ni permite declarar correctos los casos pendientes.

No se excluyen esas unidades de los denominadores oficiales ni se recalcula una
cobertura artificialmente más alta. Tampoco se convierten automáticamente en 910
revisiones humanas individuales: hay decisiones de diseño/política que podrían
resolver familias de casos en el futuro, si se acuerda un incremento separado.

| Paper | Páginas abstendidas | Hijos sin caja | Padres index con caja | Contenedores pendientes (todos) | Unidades con abstención de página | Unión estructural |
| --- | --- | --- | --- | --- | --- | --- |
| 1.pdf | 1 | 20 | 1 | 27 | 31 | 57 |
| 2.pdf | 2 | 20 | 2 | 24 | 63 | 84 |
| 3.pdf | 0 | 0 | 0 | 9 | 0 | 9 |
| 4.pdf | 0 | 0 | 0 | 8 | 0 | 8 |
| 5.pdf | 0 | 0 | 0 | 17 | 0 | 17 |
| 6.pdf | 0 | 0 | 0 | 67 | 0 | 67 |
| 7.pdf | 0 | 0 | 0 | 29 | 0 | 29 |
| 8.pdf | 1 | 24 | 3 | 16 | 31 | 44 |
| 9.pdf | 0 | 0 | 0 | 31 | 0 | 31 |
| 10.pdf | 0 | 0 | 0 | 5 | 0 | 5 |
| 11.pdf | 0 | 0 | 0 | 27 | 0 | 27 |
| 12.pdf | 0 | 0 | 0 | 36 | 0 | 36 |
| 14.pdf | 3 | 100 | 3 | 55 | 109 | 161 |
| 15.pdf | 5 | 135 | 5 | 51 | 151 | 197 |
| 17.pdf | 5 | 75 | 5 | 55 | 88 | 138 |

**Forma de las abstenciones funcionales:** 694 sin candidato; 432 con un candidato pero decisión bloqueada; 29 con varios candidatos. Son particiones excluyentes y suman 1155. Esto distingue falta de evidencia, restricciones y competencia de propuestas.

**Subtipos pendientes:** 895 sin candidato y 799 con varios candidatos, total 1694. Varios subtipos pueden ser compatibles (por ejemplo encabezado y margen recurrente); no interpretar esta cuenta como 1694 conflictos semánticos reales. Las reglas no se cambiaron para corregirlo en esta ampliación.

### Límites de interpretación y verificación documental

Las advertencias no son errores confirmados ni una estimación del tiempo humano.
Las decisiones sin advertencias tampoco quedan validadas. Precisión, recall,
macro-F1, matriz de confusión y error entre decisiones emitidas requieren una
referencia humana independiente; se mantienen pendientes hasta el final del MVP.
La revisión futura debe incluir propuestas automáticas y abstenciones, con separación
por paper/formato y sin usar los casos de desarrollo como validación independiente.

Se verificó la suma por paper, categoría y tipo de unidad; C+A=N para cada dimensión
y estrato; la igualdad con summary.json; N=0 como no aplica; hijos/padres/estados
conservados y hashes de las salidas originales antes/después. No se importó ni
invocó el clasificador. No se modificó el visor ni se ejecutaron modelos/OCR/Colab.
[Verificación de esta ampliación](../results/sic_collection/functional-classification-reconciled-v2-metrics/verification.json).
El reporte anterior íntegro se conserva en
`docs/history/20261026-functional-classification-v2-metrics/before/analytics/reports/`.
