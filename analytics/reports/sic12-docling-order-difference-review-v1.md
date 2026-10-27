# Diferencias de orden Docling frente al baseline: 12.pdf

La observación del usuario —Docling resulta mucho mejor visualmente— está respaldada
por varias correcciones de continuidad entre columnas en la salida guardada. También
hay regresiones puntuales y relaciones que siguen sin adjudicación suficiente.
No se ajustaron reglas, ejecutó Docling otra vez, OCR ni modelos neuronales.

## Alcance y evidencia

Se revisaron los168pares de contenido cuya precedencia difiere entre las dos salidas,
en13páginas y sus rutas. Se contrastaron cajas conciliadas, texto extraído directamente
del PDF con PyMuPDF y renders originales. Inspección visual de originales: páginas
1,2,3,4,9; para las demás, cajas y texto nativo de las regiones. No se hizo nueva
inspección de interfaz en navegador ni se crearon renders/crops/boxes.

Esta es adjudicación documental del agente, pendiente de revisión humana final;
no un GT humano ni una evaluación de toda la secuencia. Las relaciones entre pares
se solapan: una continuidad recuperada puede corregir varios pares simultáneamente.
No interpretar129/168 como accuracy, precision ni tasa general de éxito.

| Dictamen sobre precedencia cambiada | Pares |
| --- | ---: |
| Corrección respaldada | 129 |
| Regresión respaldada | 6 |
| Indeterminado | 33 |
| Total revisado | 168 |

## Correcciones respaldadas

| Página física | Evidencia de orden correcto | Qué cambia |
| --- | --- | --- |
| 1 | Introducción: encabezado y fragmento izquierdo antes de la continuación derecha que empieza severe degradation | Corrige dos precedencias locales; no arregla toda la página |
| 2 | La sección2/2.1 y el final izquierdo magnitude of the swelling preceden a strain has inverse temperature dependence en derecha | Evita leer constitutivas/ecuaciones antes del comienzo de su sección |
| 3 | El ítem2 izquierdo termina commercial FE software y continúa en derecha Abaqus, while BISON... | La tabla2,3.1 y lista quedan antes de esa continuación; recupera el flujo de columnas |
| 4 | El texto izquierdo termina axial void y continúa en derecha distribution..., antes de4.Results | Mejora la precedencia entre columnas; conserva una inversión local descrita abajo |
| 5 | El final izquierdo dice ...the y derecha comienza fuel rod-cladding gap decreases... | Coloca las conclusiones y desarrollo izquierdo antes de4.1.2/4.1.3 de la derecha |
| 6 | At al final izquierdo continúa this time en derecha | Corrige transición de columna en4.1.4 |
| 7 | El final izquierdo relation continúa of hoop stress en derecha, antes de ecuaciones6–8 | Evita adelantar ecuaciones y explicación derecha |
| 8 | El final izquierdo decreases continúa with increasing temperature en derecha | Restituye continuidad de la explicación de hinchamiento |
| 9 | El final izquierdo was not continúa considered for the stress evaluation en derecha | Corrige el orden del cuerpo antes de4.1.5 y4.2 |
| 11 | azimuthal al final izquierdo continúa power variation en derecha | Recupera la frase que introduce Fig.22 |
| 12 | possible al final izquierdo continúa impacts from such... en derecha, antes de Summary | Evita adelantar conclusiones antes del cierre del desarrollo |

Las continuidades se describen como evidencia del análisis; no se añadieron vínculos
paragraph_continues ni se fusionó texto en resultados. El signo de guion, salto de
línea o ligadura puede diferir entre texto nativo y texto conciliado; no se corrigió OCR.

## Regresiones concretas introducidas

Son cinco casos que explican seis relaciones invertidas:

1. **Página1, abstract frente a introducción —2pares.** Baseline: cuerpo del abstract
   antes de1.Introduction y su primer párrafo. Docling adelanta el encabezado y ese
   párrafo al cuerpo del abstract. La caja del abstract está aproximadamente en
   [564,904,1570,1360] y la introducción en [112,1521,296,1550] y
   [109,1579,822,1669], XYXY píxeles del render1654×2205. El original muestra una
   banda horizontal divisoria: el abstract termina antes de la introducción.
2. **Página1, notas —1par.** Invierte Corresponding author y E-mail address. El original
   y las cajas muestran el rótulo primero y el correo debajo. No es un fallo de OCR.
3. **Página2, columna izquierda —1par.** Docling coloca The current work focuses...
   antes de Recent studies[19–21]..., aunque Recent studies ocupa y≈556–1400 y
   The current work y≈1398–1810. Baseline conservaba este orden local correctamente.
4. **Página2, definiciones de resistividad —1par.** Cambia el orden K0 y Krd. El original
   muestra Kirr, K0, Krd verticalmente; baseline lo respetaba y Docling intercambia
   los dos últimos. Son bloques independientes con cajas ligeramente solapadas.
5. **Página4, columna izquierda —1par.** Coloca A section of the3D FE model...
   antes de Fig.4 shows the axial power profile..., aunque el texto de Fig.4 está
   arriba (y≈514–747) y el del modelo3D debajo (y≈745–953). Baseline lo hacía bien.

En los cuatro casos locales de notas/párrafos/definiciones las cajas se tocan o
solapan aproximadamente2–4px. Eso es una pista compatible con sensibilidad geométrica,
no una causalidad aislada demostrada: no se cambió ninguna caja, tolerancia o regla.
La regresión del abstract afecta un cambio de composición más amplio.

## Indeterminados y pendientes heredados

33pares:9 de página1 (Crossmark/metadatos/copyright y flujos paralelos),14 de página4
(posición relativa de Table3/Fig4 y texto),10 de página9 (figuras frente al cuerpo).
No hay precedencia única adjudicada para esas relaciones entre contenidos flotantes
con la evidencia revisada. Tener caption vinculado no fija su precedencia respecto
a todos los bloques vecinos. Esta decisión conservadora no declara correctos esos
órdenes ni convierte automáticamente todos los elementos en flujos independientes.

Los problemas de clasificación de autores/afiliaciones/editorial en main son heredados:
Docling no los creó ni los corrigió. Tampoco cambió orden interno de paneles, asociaciones,
caption primero o jerarquía. La imagen Crossmark de página1 sigue como figura sin
función documental adecuada. No atribuir estas limitaciones a un nuevo error del parser.

Páginas10 y13: sin cambios de orden de contenido; eso no valida su orden. Las rutas
bibliography,metadata y editorial_navigation no cambian; en notes solo cambia el par
señalado de página1. No se revisaron como correctos todos los pares no modificados.

## Desglose de los168pares cambiados

| Página | Correcciones | Regresiones | Indeterminados |
| --- | ---: | ---: | ---: |
| 1 | 2 | 3 | 9 |
| 2 | 56 | 2 | 0 |
| 3 | 20 | 0 | 0 |
| 4 | 5 | 1 | 14 |
| 5 | 8 | 0 | 0 |
| 6 | 3 | 0 | 0 |
| 7 | 13 | 0 | 0 |
| 8 | 3 | 0 | 0 |
| 9 | 14 | 0 | 10 |
| 11 | 2 | 0 | 0 |
| 12 | 3 | 0 | 0 |

## Trazabilidad y parada

- [168dictámenes por par con IDs y posiciones de ambas rutas](../results/sic12_document/docling-order-difference-review-v1/changed-pairs-review.json).
- [Cajas y texto nativo por región](../results/sic12_document/docling-order-difference-review-v1/native-region-evidence.json).
- [Resumen](../results/sic12_document/docling-order-difference-review-v1/review-summary.json).
- [Verificación](../results/sic12_document/docling-order-difference-review-v1/verification.json).
- [Comparación HTML original sin cambios](../results/sic12_document/docling-order-trial-v1-view/index.html).

Índices baseline_indices/docling_indices son posiciones locales de contenido por
página/ruta; route_step_positions son las posiciones globales con estructuras que
muestra el visor. Extracción de texto usa el ROI de las cajas existentes y puede
incluir partes de líneas vecinas cuando estas se solapan; las páginas originales
respaldan los casos de definiciones/notas descritos. No es OCR ni transcripción validada.

Conclusión acotada: Docling aporta mejoras comprobables de precedencia en los casos
revisados y merece mantenerse como candidato; todavía no como autoridad única del
orden. Las regresiones justifican reconciliación con anclas nativas y estructura,
no tuning automático en esta ronda. Parar aquí: resultados/código intactos, sin nueva
exportación ni extensión de alcance. Revisión humana semántica formal after_full_mvp.
