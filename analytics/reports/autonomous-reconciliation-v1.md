# Conciliación autónoma v1: implementación y regresión

26oct2026. Diseño aprobado por usuario; ejecución offline completada sobre evidencia
guardada. Reutilizable por identidad de documento/página, sin IDs de casos en reglas.

## Entrega

- Código: `code/reconciliation/`; instrucciones en su README.
- Salida: `analytics/results/sic12_document/autonomous-reconciliation-v1/`.
- Vista: `review.html`; automática/MinerU/TATR/LayoutLMv3 con categorías, grupos,
  contenedores opcionales, inspector y decisiones. La automática es distinta de la
  salida humana anterior y no incorpora Table2 histórica.
- Auditoría: `analytics/results/sic12_document/autonomous-reconciliation-v1-audit/`.

Resultado: 13 páginas procesadas, 536 registros preservados (251 segmentos y 36
contenedores MinerU, 236 LM, 13 TATR), seis grupos automáticos y 128 correspondencias
geométricas. Estas últimas no son 128 identidades semánticas validadas ni una medida
de exactitud. Las ocho categorías están implementadas; Otros puede no aparecer en
un documento y está probado con clase desconocida.

Seis grupos coinciden en miembros y caption con las referencias humanas guardadas.
Fig5 y siete figuras simples en p8/p12 no producen agrupaciones indebidas. Referencias
humanas se consultan únicamente en pruebas, nunca para generar la salida. Fig6
mantiene cajas solapadas y advertencia; no se ha reparado la geometría. TATR se
integra en correspondencias/conflictos tabulares, no reemplaza cuerpos o celdas.

## Verificación

21 pruebas pasan: ontología, capacidades, identidad, preservación, conflictos,
abstención, fuentes fallidas, versión desconocida, página dañada, no finitos,
regresión de grupos, seguridad HTML y exportación determinista/no sobrescritura.
Comparación exacta de cajas MinerU con R y de 536 registros con punteros nativos.
55 fuentes con hash; 367 archivos anteriores verificados sin cambios. JavaScript
del visor pasó comprobación de sintaxis. No se realizó revisión visual real ni
prueba de interacción en navegador: protocolo file: bloqueado previamente para
el agente. No se atribuye a la comprobación de sintaxis validación visual.

Revisión independiente detectó cinco problemas de frontera: uso de parser fallido,
página sin MinerU, versiones externas, fallo local que abortaba documento y NaN no
serializable. Corregidos con pruebas de regresión observadas fallar y luego pasar.
Las fuentes fallidas se conservan sin apoyar decisiones; la página inválida queda
bloqueada, otras continúan. Manifiesto global ilegible/inválido impide cargar el lote.
Valores no finitos se preservan con etiqueta JSON explícita, no se recortan.

## Límites y siguiente decisión

El motor automatiza normalización y relaciones conservadoras; no corrige OCR,
límites de objetos, pérdida de contenido o jerarquía semántica de secciones.
Preserva clasificación nativa y registra conflictos, sin ganador por score.
El adaptador suministrado soporta el formato de evaluación existente y versiones
declaradas; nuevos formatos requieren adaptadores, no heurísticas para adivinar escala.
No se han procesado otros papers ni demostrado generalidad. Sin nuevos OCR,
inferencias, entrenamiento, sesiones remotas o cambios de modelos.

Conviene ahora identificar salidas existentes de otros papers y acordar el conjunto
reservado de evaluación por documento. No ampliar automáticamente el corpus ni
repetir 12.pdf para ajustar umbrales. Si no hay evidencia adecuada, registrar esa
carencia antes de pedir ejecuciones. Un piloto exige positivos nuevos y referencias
por función; dos papers reservados son mínimo de diseño, no prueba universal.

## Ledger de ejecución

Plan: `analytics/analyses/paper/autonomous-reconciliation-plan.md`.
Ruling: T1–T3 se implementaron en un núcleo puro conjunto y se verificaron por suites
funcionales, no como ensayos causales separados; no atribuir diferencias a una única
variable empírica ni afirmar mejora de exactitud. La presentación es una capa separada.
Ruling: temporales de pruebas dentro de tmp/ del workspace, porque el temporal del
sandbox Windows rechazó escritura; no fue necesario ampliar permisos.
Parada alcanzada para implementación/regresión; piloto entre papers pendiente.
