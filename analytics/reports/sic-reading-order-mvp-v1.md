# Orden de lectura MVP v1: resultados

Implementación autorizada sobre la clasificación de la versión conciliada, sin reclasificar ni ejecutar OCR, modelos o Colab. Exportación única de 15 papers / 397 páginas. Las propuestas quedan pendientes de validación semántica después del MVP de todas las etapas.

## Dónde consultar

- [Vista responsive de 12.pdf](../results/sic12_document/reading-order-mvp-v1-view/index.html): 13 páginas, PNG originales íntegros, cajas/lista/flechas sincronizadas, cambio de recorrido y zoom.
- [JSON de 12.pdf](../results/sic_collection/reading-order-mvp-v1/papers/12/document.json).
- [Resumen y enlaces a cada paper](../results/sic_collection/reading-order-mvp-v1/summary.json), [cola de advertencias](../results/sic_collection/reading-order-mvp-v1/review-queue.json).
- [Diseño](../analyses/collection/reading-order-reconciled-mvp-v1-design.md), [plan con parámetros](../analyses/collection/reading-order-reconciled-mvp-v1-plan.md), [código y técnicas](../../code/reading_order/README.md).
- [Auditoría](../results/sic_collection/reading-order-mvp-v1-audit/verification.json).

## Contrato y técnicas

`inventory` conserva cada unidad original y su clasificación sin cambios; `steps` contiene visitas por referencia; `routes` separa cuerpo, notas, bibliografía, metadatos y navegación editorial. Los fragmentos no se concatenan. `original_page_context`, `layouts`, `decisions` y `suspended_constraints` conservan evidencia, alternativas y procedencia. El visor presenta texto/advertencias y el JSON conserva el detalle completo de las alternativas.

XY-cut recursivo propone zonas/columnas desde las cajas existentes (gap vertical .025 ancho; horizontal .012 alto). Un grafo de precedencias conserva restricciones utilizables; los conflictos se suspenden con advertencia. Sin corte claro se ofrece fallback y,x y alternativa x,y. Dirección LTR es hipótesis explícita. El orden atraviesa páginas dentro de cada paper.

Caption primero se aplica únicamente dentro de asociaciones existentes utilizables: native_preserved, automatic_rule, human_accepted o accepted. Automatic_rule no significa aceptación humana. Los vínculos candidatos no se aceptan por cercanía. Captions y cuerpos compartidos tienen una aparición de contenido y visitas posteriores por referencia. La posición del conjunto usa sus cuerpos como anclas, sin exportar cajas nuevas.

`precedes` expresa restricciones; `next_in_route` la visita consecutiva; `paragraph_continues` una hipótesis de pertenencia al mismo párrafo. Geometría de transición de página/columna, guion final o cláusula abierta/inicio minúsculo apoyan candidatos de continuidad. No se fusiona texto ni se considera esa relación validada.

## Cobertura, abstención y advertencias

5 374 unidades contabilizadas = 5 343 regiones + 31 grupos: cobertura de inventario 100 %. Esto no equivale a ordenar individualmente todo el texto. Hay 4 512 apariciones de contenido: 1 835 posiciones propuestas por reglas (40.67 %) y 2 677 fallback (59.33 %). Las 79 apariciones de contenido con evidencia geométrica abstendida están incluidas en fallback, no se suman aparte.

Hay 4 158 pasos con alguna advertencia y 2 838 pasos fallback, incluyendo estructuras/referencias además del contenido. Estos conteos pueden solaparse y su denominador es pasos, diferente del inventario. Las advertencias originales de clasificación siguen en cada unidad; la cola adicional corresponde a esta etapa. Ninguna cifra mide exactitud, precision, recall ni F1: no existe GT de orden validado.

Los 374 hijos sin coordenadas siguen diferidos en 19 placeholders de padres, con referencias sin secuencia individual; 17 páginas conservan abstención. Se preservan todas las cajas y textos originales. La revisión humana no bloquea la exportación y queda al final, también para decisiones automáticas.

Continuidad: 108 candidatos apoyados por reglas, 374 ambiguos y 14 bloqueados por geometría/diferidos. Todos requieren validación humana final. No hay contenido duplicado ni ciclos operativos. Las heurísticas conservadoras producen muchos fallback ante geometría sin separación clara; no se ajustaron umbrales para mejorar estas cifras.

| Paper | Inventario | Apariciones contenido | Posición propuesta | Fallback contenido | Hijos diferidos |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 331 | 284 | 133 | 151 | 20 |
| 2 | 303 | 256 | 50 | 206 | 20 |
| 3 | 89 | 80 | 45 | 35 | 0 |
| 4 | 94 | 86 | 38 | 48 | 0 |
| 5 | 204 | 185 | 59 | 126 | 0 |
| 6 | 390 | 321 | 76 | 245 | 0 |
| 7 | 299 | 269 | 97 | 172 | 0 |
| 8 | 607 | 567 | 82 | 485 | 24 |
| 9 | 187 | 153 | 75 | 78 | 0 |
| 10 | 69 | 64 | 23 | 41 | 0 |
| 11 | 365 | 336 | 129 | 207 | 0 |
| 12 | 293 | 251 | 87 | 164 | 0 |
| 14 | 740 | 580 | 375 | 205 | 100 |
| 15 | 694 | 503 | 196 | 307 | 135 |
| 17 | 709 | 577 | 370 | 207 | 75 |

## Aceptación técnica y límites

23 pruebas offline pasan: columnas/bloques anchos, caption primero, relaciones compartidas, rutas, ciclos, escala, RTL, páginas abstendidas, hijos diferidos, hashes y referencias inválidas. Simulación DOM: 78 combinaciones página×ruta y 199 transiciones de navegación de 12.pdf, sin errores. Las 13 imágenes copiadas mantienen sus hashes, sin reducción ni recompresión. Auditoría independiente de exportación confirma igualdad exacta de unidades y contexto original, referencias únicas y captions antes de cuerpos en las cápsulas aplicables.

111 archivos anteriores protegidos permanecen idénticos por hash, además de las comprobaciones del manifiesto de entrada. La revisión técnica independiente encontró y permitió corregir conflictos de serialización, propagación de fallback, falsas evidencias de continuidad y validación insuficiente de referencias antes de la exportación definitiva. No valida el orden semántico de los papers.

No se completó inspección visual en navegador en esta sesión; la verificación de interfaz es simulación DOM y revisión de código. Abrir el HTML local permite revisar el recorrido. La integración canónica y V&V permanecen pendientes; no repetir exportación ni afinar reglas automáticamente.
