# Ensayo de orden Docling en 12.pdf

Se ejecutó una vez el componente de orden basado en reglas de Docling sobre las
unidades conciliadas existentes. No se ejecutó DocumentConverter, OCR, modelos
neuronales, clasificador ni integración nativa/GROBID. Alcance:13páginas de12.pdf.

## Consultar

- [Comparación HTML responsive](../results/sic12_document/docling-order-trial-v1-view/index.html).
- [JSON candidato](../results/sic12_document/docling-order-trial-v1/document.json).
- [Resumen por página y recorrido](../results/sic12_document/docling-order-trial-v1/summary.json).
- [Advertencias](../results/sic12_document/docling-order-trial-v1/review-queue.json).
- [Auditoría](../results/sic12_document/docling-order-trial-v1-audit/verification.json).
- [Plan congelado](../analyses/paper/sic12-docling-order-trial-v1-plan.md) y [código](../../code/document_structure/DOCLING_TRIAL.md).

La vista permite elegir página/ruta, sincronizar selección o mantenerla independiente,
ver ambas versiones o una sola, zoom/cajas/flechas y tabla de diferencias. Comparte
13PNG originales idénticos por hash, sin reducción ni recompresión; CSS ajusta su
presentación al ancho. En móvil los paneles se apilan. No son capas de parsers.

## Resultado descriptivo

293unidades preservadas (251segmentos,36contenedores,6grupos),251apariciones de
contenido y279pasos de recorrido, incluidas estructuras/referencias. Se modificaron
99posiciones de contenido;168pares cambiaron su precedencia respecto del baseline.
El denominador de pares comparados es 2006: pares dentro de la misma página y ruta; no mezcla rutas distintas.

Estos números miden desacuerdo, no errores ni mejora. No hay GT adjudicado de lectura.
Las29combinaciones página/ruta procesadas terminaron sin fallback de ejecución.
Eso solo demuestra funcionamiento del componente, no lectura correcta.

| Página | Contenido | Posiciones distintas | Pares invertidos / comparados |
| --- | ---: | ---: | ---: |
| 1 | 27 | 10 | 14 / 103 |
| 2 | 25 | 20 | 58 / 254 |
| 3 | 19 | 11 | 20 / 137 |
| 4 | 19 | 13 | 20 / 137 |
| 5 | 15 | 7 | 8 / 79 |
| 6 | 14 | 4 | 3 / 67 |
| 7 | 18 | 9 | 13 / 121 |
| 8 | 15 | 4 | 3 / 79 |
| 9 | 16 | 14 | 24 / 92 |
| 10 | 11 | 0 | 0 / 37 |
| 11 | 12 | 3 | 2 / 46 |
| 12 | 14 | 4 | 3 / 67 |
| 13 | 46 | 0 | 0 / 787 |

## Qué cambió y qué quedó fijo

Variable única: orden entre bloques/grupos existentes dentro de cada ruta y página.
Docling2.123.1, docling-core2.92.0, rtree1.4.1, pydantic2.12.5, Python3.13.5; defaults
intactos y módulo predictivo fijado por hash. Inputs neutrales ordenados por geometría
antes de invocar el componente, sin usar secuencia baseline como señal semántica.
Anclas de grupos usan las mismas cajas de cuerpos existentes; sus envolventes son
inputs derivados para ordenar, no cajas conciliadas nuevas.

La adaptación geométrica a BOTTOMLEFT fue necesaria porque la conversión de origen
TOPLEFT de la dependencia devuelve BoundingBox y pierde cid. Se detectó con pruebas,
se resolvió creando correctamente PageElement de entrada y no se modificó Docling.

No se modificaron clasificación, enrutamiento, asociaciones, miembros ni orden
interno de grupos/paneles. Caption primero y contenido compartido sin duplicación
se conservan. Si las referencias compartidas exigen que una cápsula aparezca antes,
se registra esa restricción en la traza. No se corrigieron los problemas conocidos
con autores/afiliaciones/metadatos: siguen influyendo en los recorridos.

Las relaciones originales permanecen en baseline_evidence_relations. Se regeneró
next_in_route. No se reutilizaron continuidades antiguas como nuevas: no se ejecutó
NLP de continuidad. Las advertencias anteriores siguen presentes en cada paso y
unidad, junto a la advertencia de propuesta no validada de este ensayo.

## Verificación y límites

145archivos anteriores protegidos intactos por hash; inventario y contexto de páginas
idénticos. Sin duplicación, pérdida de referencias ni ciclos operativos. Nueve pruebas
Python pasan; una expectedFailure documenta un fallo de calidad del propio componente:
un encabezado ancho seguido de dos columnas en un fixture produce intercalación por
filas. No se ajustaron parámetros para ocultarlo. Revisión técnica independiente
completada; corrigió reinicio de selección del otro panel al desactivar sincronización.
Prueba con texto literal de cierre de script confirma conservación al embebir JSON.

Simulación DOM de los HTML reales:156combinaciones página/ruta entre ambas vistas,
navegación, sincronización sin eco y selección independiente; pruebas parent de
sincronización/altura/mostrar panel pasan. La revisión visual en navegador no pudo
realizarse: su política de seguridad rechaza file://. No se intentó un workaround.
Esta limitación no se presenta como QA visual aprobada.

El ensayo no demuestra superioridad frente al baseline ni sustituye estructura
semántica. Las diferencias están disponibles para inspección; revisión humana formal
sigue after_full_mvp. Parada alcanzada para esta exportación acotada; no tuning,
repetición automática ni extensión a otros papers por esta entrega.
