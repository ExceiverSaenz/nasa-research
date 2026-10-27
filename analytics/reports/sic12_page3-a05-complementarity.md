# A05 Aportes y complementariedad diagnóstica por caso

24 de octubre de 2026. Ejecutado después de A04 y de la aprobación explícita del
usuario: tres ejes separados —separación geométrica, categoría explícita y
cumplimiento del recorte— sin ganador global. Se mantuvieron los criterios
estrictos de captions/tablas y todos los estados indeterminados A04.

## Pregunta C01 y qué se hizo

¿Hay evidencia que justifique combinar herramientas? Se construyó una matriz
de18casos con miembros y disponibilidad A03, geometría interpretada desde A02,
clases exportadas, y resultados de crops A04. Cada eje se conserva independiente:
una caja bien separada puede carecer de crop utilizable y una clase específica
no garantiza recuperar todo el contenido. No se asignan pesos ni una puntuación.

Las asociaciones y medidas A03 se reutilizaron, sin ejecutar otra vez matching,
clustering, S01 o revisión histórica completa. Los juicios son del asistente,
con evidencia referida y límites, sin validación humana independiente ni GT.

## Resultados por grupos de casos

| Casos | Separación geométrica | Categoría explícita | Recorte y conclusión diagnóstica |
| --- | --- | --- | --- |
| Tablas01–02 | TATR/MinerU aíslan cuerpos frente a candidatas LM mezcladas/parciales; LM r20/r15 también son candidatas útiles | Table disponible en tres modelos | TATR no conserva bordes completos; MinerU superior falla borde e inferior indeterminada; LM no exportó crops. Ningún crop comparado queda certificado como solución estricta completa |
| Figuras03–04 | MinerU separa figuras de tabla, LM mantiene mezclas | MinerU chart/image frente a figure LM | Crops MinerU aparentemente conservados: alternativa diagnóstica concreta, no prueba de ventaja de un ensemble |
| Captions tablas05–06 | LM divide rótulo/descripción; MinerU delimita descripción | Caption explícito MinerU; title/text LM | MinerU falla rótulo+descripción mismo crop; LM sin crop conjunto exportado. Información complementaria candidata no es un caption completo ya obtenido |
| Captions figuras07–08 | Alcance visual semejante | Caption específico MinerU frente a text LM | Crop MinerU aparentemente cumple; la clase específica no prueba mejora geométrica ni necesidad de combinar |
| Título09 | Delimitaciones visualmente semejantes | Title frente a paragraph_title, mapping preservado | No complementariedad geométrica demostrada; disponibilidad de crop no convierte LM en mala detección |
| Introducción10 | Candidatas completas y parcial LM r23 | Ambos text | Crop MinerU aparentemente conserva bloque; no borrar r23 ni premiar menos cajas |
| Lista/continuación11–12 | Grupo LM frente a segmentos MinerU; posible continuidad entre columnas | LM list explícita frente a text | Unidad semántica del ítem2 indeterminada. La hipótesis A04 invalida tratar r12 como error de clase confirmado |
| Texto13–14,16 | MinerU separa bloques; LM tiene candidatas semejantes más r21 multibloque | Ambos text | Bloques13/16 aparentemente conservados en MinerU;14 tiene fragmento previo. Separación no implica crop limpio |
| Ecuación15 | MinerU aísla ecuación+número5 | Equation explícita MinerU; LM sin esa clase | Aporte concreto de salida separada y crop aparente; no exactitud LaTeX ni omisión LM certificada |
| Encabezado/página17–18 | Salidas MinerU sin candidata cruzada LM registrada | Clases explícitas MinerU | Aporte de disponibilidad en esta página, no falsos negativos o recall validado |

## Interpretación

Se observan alternativas útiles para diagnóstico, particularmente separación de
figuras/ecuación y categorías explícitas en MinerU, y detección tabular TATR.
Pero no se ha demostrado que una combinación supere a un solo parser: podrían
existir errores compartidos, diferencias de objetivo y costes de integración.
Los crops tabulares y captions de tablas siguen necesitando revisión bajo los
criterios elegidos. No se propone una regla que elija cajas automáticamente.

LM conserva información de lista y rótulos separados, candidatos útiles de tabla
y varias regiones de texto. No se descartan por score, errores coexistentes o
ausencia de exportación de crops. Tampoco se declara útil una suma artificial de
registros por tener más contenido aparente: no se ha creado ni validado esa unión.

La corrección A04 sobre r12 se propaga explícitamente: parece continuación del
ítem2, no prosa necesariamente ajena a la lista. Esto es hipótesis de lectura
contextual; no se sustituyen etiquetas ni se valida orden de lectura.

## Evidencia, verificación y límites

Matriz completa: analytics/results/sic12_page3/a05-20261024/matrix.json;
manifiesto/estado, receta y verificador/export-check.json en la misma carpeta.
18casos conservan los tres ejes,48referencias y los estados exactos A04.
Verificados hashes de dependencias y derivados, miembros A03, vínculos A04,
ausencia de selección automática y propagación de la corrección interpretativa.
Se verificó trazabilidad técnica, no la verdad independiente de cada juicio.

No código de producción nuevo ni suites históricas repetidas por contexto.
Sin inferencias, fusión, ampliación, GT, porcentajes de calidad o ganador global.
La complementariedad observada es potencial y local; no una política de integración
validada ni un resultado generalizable a los14papers SiC.

A05 se cierra con esos límites. A06 continúa con la síntesis de las cinco
preguntas y prioridades C01 ya acordadas: omisiones/recortes antes de mezclas
y clasificación, sin declarar omisiones que la evidencia no confirme.
