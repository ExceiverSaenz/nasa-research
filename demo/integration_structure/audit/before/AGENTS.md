# Continuidad vigente del proyecto

## Estado actual y precedencia

El MVP de **parsing operativo de colección** está integrado y ejecutado técnicamente:
15 papers/397 páginas,5.374 unidades y4.512 apariciones. Resultado activo:
`analytics/results/sic_collection/parsing-operational-v1/index.html`; JSON/vista por paper.
Entrada canónica `code/document_pipeline/pipeline.py`, contrato README del paquete.
`analytics/config/study_progress.json` contiene `active_parsing_artifact` con manifest/hash.

Leer primero `INDEX.md`, `docs/continuidad/session-handoff.md` y
`docs/continuidad/13-estado-y-ciclo-experimental.md`, siguiendo resume-protocol.md.
Estado narrativo y fuentes vigentes prevalecen sobre planes/notas históricas.
Instrucción explícita reciente del usuario prevalece sobre esta documentación.
No pedir repetir estado reconstruible de artefactos. No ejecutar para recuperar contexto.

## Alcance vigente

- Conciliación y clasificación funcional v2 son fuentes conservadas. Se clasifican unidades conciliadas, no cada parser por separado; parsers aportan evidencia.
- Readingv1 y Docling original son baselines históricos. El resultado operativo conecta estructura, semántica y recorrido con reglas genéricas; no es un ensemble validado.
- Mismo código/configuración en todos15 papers, sin reglas por título/autor/página/ID. Cachés aprobados de12 reutilizados por identidad; otros14 mismo Docling geométrico/nativo.
- No OCR, nuevos parsers, modelos neuronales, GROBID, Colab ni renders en ese incremento.
- 13 tests/4.764 casos DOM pasan; no QA visual real ni exactitud semántica medida. No repetir esas pruebas/exportaciones por rutina.
- 478 nodos de sección son propuestas;198 niveles desconocidos. Advertencias de todas5.374 unidades por revisión final, no5.374errores. Ver evaluación por paper.

## Decisiones que deben conservarse

1. Preservar originales, ZIP, cajas, texto, clasificaciones y procedencia. Versiones nuevas separadas; sin sobrescritura ni scores imputados. Raíz sin Git: snapshots/manifests, no crear repositorio.
2. 374 hijos MinerU sin bbox continúan diferidos; conservar19 padres y17 páginas abstendidas. No usar la caja del padre para localizar al hijo ni levantar abstención automáticamente. No es urgente resolverlo.
3. Caption primero en asociaciones existentes utilizables. Compartidos por referencia, contenido una vez. No aceptar asociaciones nuevas solo por cercanía.
4. Precedencia, consecutividad, pertenencia y continuidad separadas. Párrafos por referencias, sin concatenación irreversible. Recorrido físico separado de pertenencia temática; flujos independientes sin precedencia inventada.
5. Fuente directa verificable puede bastar por dimensión. Contradicciones conservan alternativas y «Requiere validación humana». No confundir acuerdo de fuentes dependientes con certeza/probabilidad.
6. Revisión humana acumulada after_full_mvp, incluidas decisiones automáticas. No pedir etiquetado caso a caso ni bloquear salidas por ambiguos ahora.
7. Calidad semántica y V&V con referencia independiente siguen pendientes. Ejecutar15 papers técnicamente no prueba generalización universal. DOM no es QA visual; no sortear bloqueos de file:// con alternativas de navegador.

## GROBID pospuesto

Usuario decidió continuar sin GROBID por peso/coste. Adaptador/runner/visor offline
se conservan en `code/document_structure/`; no hay C real ni inferencia GROBID.
Docker Linux llegó a arrancar tras respaldo de sockets; descarga fijada iniciada y
posteriormente detenida1cliente, sin borrar cachés. G0/modelos/configuración no
completados. No reanudar descargas, Docker, servicios o modelos por contexto.
No sustituir motores/versiones para facilitar una futura instalación.

## Consulta selectiva y ejecución

- Buscar con rg antes de leer; usar índices docs/code/analytics según alcance. No cargar toda la documentación ni referencias bibliográficas.
- Leer docs/ORGANIZATION.md antes de mover/crear documentación. Distinguir método, diseño, evidencia, resultados e historia.
- Antes de abrir/ejecutar scripts, consultar code/SCRIPT_INVENTORY.md. code/results, vendor, retry_*, __pycache__ y paquetes históricos no son código vigente por defecto.
- Cambios técnicos: analytics/config/increment_registry.json; cadena pregunta→evidencia→técnica→decisión→criterio de parada, baseline y aceptación/regresión. No tuning por resultados ni ampliaciones automáticas.
- Colab: code/colab/EXECUTION.md y analytics/config/remote_runs.json antes de cualquier operación autorizada. No sesiones/GPU/recuperación automática por contexto. GCE: piloto10 preparado, solo usuario crea/ejecuta según code/document_trial/GCE.md; no inferir estado remoto actual.
- Fuentes Data Mining y Speech and Language Processing son bibliografía, no autorización ni prueba de técnicas implementadas.
- Última petición: consolidación documental. No autoriza nuevo procesamiento, servicios, OCR, modelos ni código de procesamiento. Una nueva solicitud concreta puede autorizar otro incremento; no pedir permiso repetido cuando ya exista autorización suficiente.

## Historia que no debe reabrirse por rutina

Diagnóstico A03–A06/P5 acotada cerrados con límites; no repetir por contexto.
Table1 de12.pdf:página3 continúa advertencia de recuperación detenida; Table2
conserva aceptación específica histórica. No extrapolar a tablas de toda la colección.
Seis asociaciones multipanel revisadas por usuario y Fig5 como contraste, registro
`analytics/results/sic12_document/multipanel-candidates-v1-human-review/human-review.json`;
no regla global validada. Fig6 conserva pendiente de solapamiento.

Los AGENTS anteriores, decisiones/paquetes y cadenas de transformación completos
permanecen en snapshots. Versión anterior exacta:
`docs/history/parsing-operational-documentation-consolidation-v1/before/AGENTS.md`.
Para cifras, fuentes y pendientes completos usar el estado narrativo y los informes;
no reconstruir conclusiones nuevas a partir de instrucciones históricas.
