# A03 Correspondencias y desacuerdos entre predicciones

24 de octubre de 2026. Método aprobado por el usuario mediante selección
«Aprobar A03 tal como está propuesto (recomendado)». Etapa A03 ejecutada sola;
A04/A05/A06 todavía no ejecutadas. Propuesta conservada en sic12_page3-a03-proposal.md.

## Pregunta C01 y alcance

¿Dónde coinciden y difieren los parsers al delimitar y clasificar regiones?
Se organizaron los18casos A02 como asociaciones visuales explícitas y se midieron
las parejas entre modelos dentro de cada caso, sin filtrar por clase, score,
área o intersección. D05 proporciona44segmentos; los4contenedores MinerU se
conservan solo como contexto. TATR se compara en las dos tablas, sin penalizarlo
por categorías no soportadas. No hay matching automático ni objetos de referencia.

## Qué se hizo

Se creó exploration/proximity.py para S01, associations.py para referencias,
papeles, cardinalidades y enumeración de pares, y run_associations.py para
verificación/exportación. Comando analytics/associate_regions.py --output CARPETA_NUEVA.
Roles y ambigüedades se atribuyen al juicio visual A02, no a una decisión de las
medidas. Cardinalidad y ambigüedad quedan separadas; varias candidatas pueden ser
redundancia o mezcla, no necesariamente granularidad uno-a-varios.

La pareja A/B sigue orden LM,TATR,MinerU. Cada pareja se guarda una vez con todos
sus casos relacionados; no se recalcula Q02 dentro de cada modelo. No se alteran
cajas, etiquetas o selección. No se forman cajas-unión para medir grupos.

## Resultados

- 18registros de asociación:16con candidatos entre modelos y2sin pareja cruzada
  (encabezado/página), con disponibilidad explicada.
- 48registros trazados:44seleccionados y4contenedores contextuales.
- 44parejas únicas entre modelos; las132medidas S01 son calculables en estos datos.
  No confundir44parejas con44segmentos seleccionados: son unidades distintas.
- 9casos conservan marca de ambigüedad por alternativas parciales, redundantes
  o de alcance mezclado. No son9errores independientes confirmados.
- 19parejas tienen analysis_label distinto. Eso incluye diferencias legítimas
  de taxonomía y cajas mezcladas: no es un conteo de19errores de clasificación.

| Pareja (A→B) | IoU | Contención A en B | Contención B en A |
| --- | ---: | ---: | ---: |
| LM r20 → TATR q5, tabla superior | 0.899373 | 0.899373 | 1.000000 |
| LM r20 → MinerU p0-b2-c1 | 0.959481 | 0.990824 | 0.968083 |
| TATR q5 → MinerU p0-b2-c1 | 0.878731 | 1.000000 | 0.878731 |
| TATR q7 → MinerU p0-b4-c1 | 0.878187 | 1.000000 | 0.878187 |
| LM r5 → MinerU p0-b7, primer ítem | 0.366384 | 0.368067 | 0.987673 |
| LM r5 → MinerU p0-b8, segundo ítem | 0.624496 | 0.634970 | 0.974265 |
| LM r21 → MinerU p0-b13, ecuación | 0.042074 | 0.042104 | 0.983336 |

Redondeo solo para presentación. Valores analíticos completos e IDs completos
están en associations.json. No se usan umbrales para interpretar estos ejemplos.

## Interpretación y clase de evidencia

Hecho geométrico: las cajas TATR q5/q7 están contenidas en los cuerpos de tabla
MinerU, con área menor. Esto es compatible con la observación visual de bordes
muy ajustados; no prueba cuál recorte es completo o correcto.

Juicio visual A02 conservado: r20 es candidata de tabla superior; no se descarta
por baja confianza. Su coincidencia con la tabla de MinerU no la convierte en GT.
Las cajas LM mezcladas siguen como candidatas de alcance ambiguo aun si contienen
gran parte de otra caja.

La lista presenta cardinalidad1:2, manteniendo clases list frente a text y sin
forzar coincidencia uno-a-uno. En captions, el rótulo y descripción LM se registran
como componentes frente al caption MinerU, sin presumir igual contenido recuperado.

La ecuación queda casi contenida en r21, pero ocupa una pequeña parte de esa
caja. Es un ejemplo de por qué contención alta no implica buena delimitación
ni mismo objeto semántico. r21 se enlaza a varios bloques derechos; no se divide
ni se cuenta como nuevas detecciones por cada caso.

Resultados técnicamente comprobados: integridad, alcance de parejas, procedencia
tipada y aritmética S01. No hay exactitud de detección validada. Complementariedad
y utilidad son hipótesis/casos por evaluar en A04/A05, no consecuencias automáticas
de acuerdo geométrico. Encabezado/página sin candidata cruzada no se declaran
omisiones ni falsos negativos.

## Evidencia y verificación

Derivados en analytics/results/sic12_page3/a03-20261024/: associations.json,
association-manifest.json, association-status.json, local-tests.txt,
inspect_export.py y export-check.json. Se enlazan overlays/crops A02 sin repetir
su revisión histórica. Manifiesto: hashes de A02,P03,P04,S01,propuesta aprobada y
código. Se conserva la distinción entre aprobación del método y validación
humana independiente de cada juicio.

9pruebas nuevas más35previas: geometría idéntica/disjunta/contacto, inclusión,
intercambio de contenciones, marco inválido/diferente, valores no finitos,
cardinalidad/ambigüedad, referencias, categorías ausentes, deduplicación y recorrido
real. Auditoría independiente Decimal de132medidas con tolerancia1e-12 y
enumeración independiente de parejas/casos, cobertura y hashes de entradas.
No nuevas inferencias, E03, selección por confianza, GT, conciliación o GPU.

## Límites y puerta A04

A03 se cierra como comparación descriptiva trazable; la ambigüedad explicada es
resultado y no se fuerza un ganador. La página no representa la colección y los
casos no son réplicas independientes. Los pares sin intersección se mantienen:
pueden corresponder a componentes distintos de un mismo caption descrito.

Para ejecutar A04 hay decisiones metodológicas necesarias: si un caption
utilizable exige rótulo+descripción juntos y si una tabla utilizable debe incluir
las líneas exteriores. Se solicitarán opciones y recomendación antes de evaluar
completitud/utilidad con uno de esos criterios. No se supone silenciosamente
que un crop sin rótulo o sin línea exterior sea correcto o incorrecto.
El objetivo A03–A06 permanece activo; A04 espera esas decisiones, no un mensaje
genérico «continuemos». A05/A06 todavía no se ejecutan.
