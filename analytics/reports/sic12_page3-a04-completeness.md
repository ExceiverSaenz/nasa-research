# A04 Completitud visible de regiones y recortes

24 de octubre de 2026. Etapa ejecutada después de cerrar A03 y recibir dos
decisiones explícitas del usuario: caption con rótulo y descripción en el mismo
recorte, y tabla con contenido y bordes estructurales completos. A05/A06 aún no
ejecutadas. No nueva inferencia, E03, GT ni conciliación.

## Pregunta C01 y método

¿Qué contenido aparece mezclado o recortado y qué requiere revisión? Se
inspeccionaron los21crops originales existentes (2TATR,19MinerU), extraídos sin
modificación de sus ZIP verificados. Se contrastaron con el render y evidencia
A02/A03. Los23registros LM no exportaron crops: su alcance visible previo se
conserva, pero utilidad de un recorte inexistente queda indeterminada. No se
generaron crops sintéticos para presentarlos como exportaciones del modelo.
Los4contenedores MinerU permanecen solo como contexto, sin doble conteo.

Las observaciones se refieren a contenido visible de esta página, no a exactitud
OCR, LaTeX, contenido científico o completitud de un párrafo en todo el documento.
No se deciden omisiones sin referencia revisada. La revisión es del asistente,
no una anotación humana independiente. Se registra indeterminación sin suponer
tolerancias de píxel ni umbrales de calidad.

## Resultados relevantes

| Evidencia | Observación | Resultado frente al criterio acordado |
| --- | --- | --- |
| TATR q5/q7 | Contenido tabular visible; líneas exteriores fuera de los crops | No satisface bordes estructurales completos |
| MinerU p0-b2-c1, tabla superior | Contenido presente; parte del trazo de regla inferior queda fuera | No satisface borde completo |
| MinerU p0-b4-c1, tabla inferior | Trazo oscuro inferior visible; una fila gris antialiasada de borde queda fuera | Extensión estricta del borde indeterminada, sin tolerancia inventada |
| MinerU p0-b2-c0/p0-b4-c0 | Descripción visible sin Table1/Table2 | No satisface caption completo en mismo crop |
| MinerU p0-b3-c1/p0-b9-c1 | Fig1/Fig2 y descripción en mismo crop | Aparentemente satisface al nivel visual inspeccionado |
| MinerU p0-b3-c0/p0-b9-c0 | Figuras con ejes o Fuel rod/Cladding, sin tabla/caption ajenos | Contenido visible aparentemente conservado; no certificado píxel a píxel |
| MinerU p0-b12 | Párrafo sobre presión con fragmento direction. previo en borde superior | Contenido ajeno observado; requiere revisión |
| MinerU p0-b8/p0-b10 | Fin izquierdo commercial FE software y comienzo derecho Abaqus... | Posible continuidad del ítem2 entre columnas; unidad semántica completa no certificada en crop p0-b8 |
| LM23registros | No crops exportados; mezclas/parciales A02 conservados | Utilidad del crop indeterminada; no cero ni fallo de inferencia |

Título, encabezado, página, introducción, texto visible y ecuación tienen registro
individual en review.json, incluidos los aparentemente conservados y los límites
por fragmentos de página. Aparente cumplimiento visual no equivale a exactitud
de transcripción ni a aprobación humana individual. No se calcula porcentaje de
calidad a partir de estos estados o del conteo de crops.

## Evidencia fina de bordes y crop_clipped

El crop MinerU superior tiene bbox entero [114,231,1564,428], con extremo inferior
exclusivo428. En el render, la regla inferior tiene muestrasRGB(189,189,189)
en y427, (15,15,15) en428 y (0,0,0) en429, verificadas en x300/700/1200. El crop
conserva solo la primera de esas filas: parte del trazo oscuro queda fuera.

El inferior termina en y1526 exclusivo; conserva trazo oscuro en1524/1525,
pero queda fuera fila1526 grisRGB(203,203,203), verificada en x300/500/700.
Esto no se resuelve con una tolerancia no acordada: se conserva indeterminación
para el borde estricto. Los valores son muestras de imagen, no anotaciónGT o
una regla automática para decidir calidad de otras tablas.

crop_clipped=false de MinerU no garantiza contenido completo: indica ausencia
de clipping al marco, no preservación de rótulos, reglas o texto ajeno. La caja
predicha flotante y el crop entero se conservan separados.

## Revisión de una interpretación anterior

La lectura conjunta del ítem2 izquierdo y el texto Abaqus... derecho sugiere una
continuación entre columnas. Por ello el juicio previo A02/Q02 que calificaba
LM r12 list como prosa incorrectamente clasificada era demasiado fuerte. A04 lo
deja como posible continuación de lista, sin validar el orden de lectura ni
modificar la etiqueta original. La diferencia list/text sigue siendo descriptiva;
no se considera error de clase confirmado. A03 no necesita recalcular geometría.

Los registros A02/A03 se conservan como evidencia histórica; esta revisión tiene
prioridad interpretativa al sintetizar C01. Se conservó una primera pasada A04
como archivos draft-first-pass; la salida vigente es review.json con su manifiesto.

## Evidencia, verificación y límites

Directorio analytics/results/sic12_page3/a04-20261024/: review.json,
review-manifest.json, review-status.json, crop-inventory.json,21crops originales,
boundary-pixels.json, receta y verificador, export-check.json.
Se comprobaron48referencias exactas,21crops byte a byte contra ZIP, hashes de
entradas/registro/receta y muestras de píxeles contra render. Es comprobación
técnica de evidencia; no prueba automáticamente los juicios visuales.
No cambió código de producción: no se repiten suites de inferencia/analytics
históricas para esta revisión documental. La verificación es puntual al incremento.

A04 se cierra con estos límites explícitos: crops LM no disponibles, borde
inferior MinerU estrictamente indeterminado, continuidad entre columnas como
hipótesis, sin auditoría completa de omisiones ni referencia geométrica.
El objetivo persistente continúa. A05 necesita acordar qué cuenta como aporte
útil: ventaja diagnóstica de separación/categoría frente a utilidad estricta
del recorte. No se elegirá silenciosamente ni se seleccionará por score/IoU.
