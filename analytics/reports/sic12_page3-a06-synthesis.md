# A06 Síntesis del piloto y prioridades de revisión

24 de octubre de 2026. Estudio descriptivo/comparativo de la página física3 de
SiC12.pdf, con preguntas C01 conservadas. A03,A04,A05 se ejecutaron y verificaron
secuencialmente con sus decisiones aprobadas; A06 sintetiza sus resultados.
Las propuestas futuras de este informe no se ejecutan ni quedan autorizadas.

## Respuestas a las cinco preguntas C01

### 1 Qué aporta cada parser por categoría

TATR aporta dos candidatas tabulares aisladas, sin incorporar figuras/captions.
MinerU separa varias regiones que LM mezcla y ofrece categorías explícitas de
caption, ecuación, encabezado y página. LM conserva candidatas útiles de tabla,
texto y título, clase list y rótulos separados, junto con cajas parciales o
mezcladas. Son aportes observados en esta página, no un ganador global.

E02 contextualiza las salidas: D05 LM23,TATR2,MinerU19. Las19hojas MinerU no son
19objetosGT. Una clase no soportada no significa que el contenido se haya perdido.
Véanse informes E02 y A05, y matriz A05 con etiquetas originales recuperables.

### 2 Dónde coinciden o difieren

A03 registra18asociaciones visuales,44parejas únicas entre modelos y132medidas
S01. Hay casos de alcance semejante (título y ciertos pies/textos), uno-a-varios
en los ítems numerados y cajas LM de alcance multirregión. En tablas, las cajas
TATR se contienen en los cuerpos MinerU; esto describe geometría, no perfección.

Nueve casos conservan ambigüedad y19parejas tienen distinta categoría comparable;
ningún número es un conteo de errores confirmados. No se forzó asignación
uno-a-uno, se descartó una pareja por clase o se eligió una caja por confianza.
Evidencia: informe A03, asociaciones y auditoría geométrica Decimal independiente.

### 3 Qué aparece mezclado o recortado

Se conservan las mezclas superiores LM y r21 multibloque ya documentadas en Q02.
Bajo el criterio aprobado, ambos crops TATR incumplen bordes estructurales;
MinerU superior corta parte de regla inferior y la extensión estricta del borde
inferior queda indeterminada. Los captions de tablas MinerU excluyen Table1/Table2,
por lo que no cumplen rótulo+descripción en el mismo crop. El crop p0-b12 incorpora
un fragmento direction. del párrafo anterior.

Los23registros LM no exportaron crops: no se certifica su utilidad ni se crean
crops nuevos como si fueran nativos. Se inspeccionaron21crops reales byte-idénticos
a los ZIP. Completitud visible de una página no es completitud del documento ni
transcripción OCR correcta. Evidencia individual y muestras de bordes en A04.

**Corrección interpretativa:** la secuencia commercial FE software / Abaqus...
sugiere que el bloque superior derecho continúa el ítem2 de la izquierda. El
juicio anterior de r12 list como error confirmado era excesivo. Permanece como
hipótesis de continuidad, sin validar orden de lectura o cambiar datos previos.
Esta matización A04 tiene prioridad al interpretar A02/Q02; A05 la conserva.

No se realizó una auditoría completa de omisiones: no hay referencia geométrica
revisada. No se presentan recall, precisión ni porcentajes de calidad.

### 4 Si hay evidencia para combinar herramientas

Hay alternativas diagnósticas locales en tres ejes separados: geometría,
categoría explícita y crop. Separar mejor una figura o emitir equation aporta
información, pero no demuestra que un ensemble supere al parser por separado.
En tablas y captions de tablas subsisten limitaciones frente al criterio de
utilidad. No se ha obtenido una solución completa simplemente por combinar
conteos o por acuerdo de las predicciones.

No se propone ganador global ni regla automática de conciliación. Tampoco se
midió reducción de trabajo manual, coste o latencia comparable: tiempos históricos
tienen alcances distintos y consumo no disponible no se imputa. Evidencia: matriz
y reporte A05, límites de comparabilidad Q03.

### 5 Qué necesita revisión humana y más evidencia

Prioridades acordes a C01, sin atribuir tasas de error ni tiempos inventados:

1. **Omisiones:** si se quieren afirmar, acordar primero referencia revisada;
   ni la coincidencia de modelos ni el conteo visual19 la sustituyen.
2. **Recortes:** revisar rótulos de captions y bordes de las dos tablas, y el
   fragmento previo en p0-b12. El borde inferior MinerU conserva incertidumbre.
   Exportar o corregir crops sería otro incremento acordado, no hecho aquí.
3. **Mezclas:** conservar y revisar LM r13/r16/r18/r19/r22 y r21 frente al alcance
   de región deseado. No eliminarlas por una regla de área, confianza o IoU.
4. **Contexto y clasificación:** verificar continuidad entre columnas y granularidad
   de lista antes de calificar r12 o los text MinerU como errores semánticos.
5. **Generalización:** proponer, sin ejecutar, un ensayo sobre12.pdf completo y
   después1→2→4→8→14papersSiC, revisando diversidad, errores y coste en cada paso.
   Más páginas requerirán acuerdo; cada nueva asignaciónColabT4 autorización.

## Qué se comprobó y qué permanece abierto

Hechos descriptivos: registros, categorías, disponibilidad y estados exportados.
Juicios visuales: mezclas, contenido visible de crops y cumplimiento de criterios
aprobados, atribuidos al asistente. Hipótesis: continuidad de lista y potencial
complementariedad. Resultados técnicamente validados: hashes, referencias tipadas,
alcance de parejas y aritmética S01; no exactitud de detección de los parsers.

Continúan abiertos, como límites científicos y no como tareas ejecutadas:
omisiones sistemáticas, OCR/LaTeX, borde estrictamente indeterminado, crops LM
ausentes, unidad semántica que cruza columnas, beneficio de integración y calidad
de la colección. Se conserva cada incertidumbre en lugar de inventar umbrales,
GT o una caja ganadora.

## Evidencia trazable y cierre de las etapas autorizadas

Informes separados:

- A03: `analytics/reports/sic12_page3-a03-associations.md`.
- A04: `analytics/reports/sic12_page3-a04-completeness.md`.
- A05: `analytics/reports/sic12_page3-a05-complementarity.md`.
- A06: este informe; síntesis y aprobaciones registradas en
  `analytics/results/sic12_page3/a06-20261024/`.

Cada carpeta A03/A04/A05 conserva manifiesto, estado y verificador propio. A03
incluye44pruebas locales (9nuevas y35previas) y auditoría de132medidas; A04
verifica48referencias/21crops y muestras de bordes; A05 conserva18casos con tres
ejes y estados A04 exactos. A06 enlaza esas dependencias y registra acciones
futuras como execute_now=false. La auditoría final `completion-audit.json` y
`synthesis-status.json` establecen el estado final, después de comprobar el
alcance completo del objetivo.

No se ejecutaron E03, nuevas inferencias, conciliación automática, ampliaciones,
instalaciones o asignacionesColab en estas etapas. No se modificaron predicciones,
ZIP ni datasets anteriores; las revisiones interpretativas quedan documentadas
con evidencia nueva y mantienen los registros históricos.

Se cierra el trabajo autorizado A03–A06 con respuestas parciales fundamentadas,
sin confundir cierre del piloto con validación de los parsers. Cualquier ensayo,
referencia o cambio de exportación posterior necesita su acuerdo específico.
