# Integración GROBID: implementación offline

## Decisión vigente

**GROBID pospuesto por peso/coste.** Sin inferencia, variante C ni comparación real.
Docker Linux llegó a arrancar posteriormente; la descarga fijada se inició y después
se detuvo. El antiguo bloqueo de motor de la sección histórica no es el último
estado conocido, pero G0 sigue incompleto. No reanudar servicios/descargas/modelos.
El parsing vigente funciona sin GROBID en los15 papers:
[document_pipeline](../document_pipeline/README.md).
Las verificaciones/cifras de implementación que siguen son históricas de ese incremento.

Plan: `analytics/analyses/paper/sic12-grobid-trial-v1-plan.md`.
Estado: código/adaptación/visor verificados con fixtures; **GROBID no ejecutado**.
No existe C real de12.pdf ni HTML comparativo real. No se presenta fixture como resultado.

## Componentes y contratos

- `grobid_adapter.parse_tei(raw,run)`: UTF-8 TEI con namespace; DTD/entities
  rechazados. Texto/attrs/coords/XML IDs/XPath y padres íntegros; contabilidad de
  todos los nodos, incluidos no mapeados. Identidad por hashTEI+posición XML.

- `grobid_align.align_tei(evidence,B)`: anclas nativas existentes, coincidencia
  exacta única por texto/geometría, offsets de la vista normalizada→spans fuente.
  Mantiene varias cajas y fragmentos, sin bbox nuevas. Texto parcial no cambia una
  región completa. Repeticiones/fuzzy quedan candidatos; rotación/crop incompatible
  se abstienen. No usa padres para localizar hijos diferidos.

- `grobid_mapping.json`: reglas genéricas versionadas. Distingue descripción
  bibliográfica del artículo en teiHeader frente a bibliografía citada; title,
  authors, affiliations, abstract, paragraphs, headings, captions/figDesc, notes,
  formulas, references y visual objects. Labels desconocidos se conservan.

- `grobid_reconcile.integrate_grobid(B,evidence,links,mapping)`: copia B íntegro,
  agrega `grobid_proposals` por unidad/dimensión y `grobid_structure` candidato.
  Cada decisión guarda B_decision, claims y C_decision. Solo completa desconocidos
  desde claims únicos de región completa bien alineados. Desacuerdos retienen B,
  alternativas y advertencias. Acuerdo no equivale a independencia/validación.
  Ningún claim de modelo se convierte en evidencia directa. No concatena párrafos.

- `grobid_evaluation.compare_B_C`: valida inventario, orden, fuentes, refs de spans,
  jerarquía y relaciones; cuenta cambios/abstenciones/conflictos por página,
  categoría y dimensión. Calidad semántica `not_evaluated/null`. Scoring con GT
  requiere un contrato de anotación independiente futuro; rechaza referencias
  pasadas informalmente para evitar presentar B/C como verdad.

- `grobid_export.export_saved_tei(B,raw,lock,destination)`: sin red/modelos; verifica
  respuesta200 completa, hashes/run/lock/PDF/fuentes y manifest B. Destino exclusivo;
  raw intacto, evidencia, links, mapping, C, comparación, cola y manifest.

- `grobid_view.build_view(B,C,render_catalog,destination)`: comparación B/C, filtros
  y flujos independientes. Catálogo de renders es la conciliación original,
  identificada por hash en manifest B. PNG copiados byte a byte; zoom CSS, sin
  recompresión. El HTML solo se genera después de recibir C real válido.

## Runner y puerta de ejecución

`runners/grobid_trial.py` no inicia Docker ni descarga modelos. Import es inerte.
`verify_lock` exige imagen0.9.1 por digest/plataforma, config/modelos completos,
hashes, parámetros de consolidación verificados y recursos4CPU/8GiB/heap4GiB.
La lista de componentes mínima no reemplaza el inventario de toda la cascada:
se exige inventariar/configurar todos los componentes efectivos y recursos
transitivos antes de marcar el lock como listo. El archivo pending de auditoría
es deliberadamente inválido para ejecutar; no editar booleanos sin verificación.

Antes del POST real, el runner attesta un servicio ya autorizado: contenedor,
imagen, CPU/memoria, ausencia de GPU/mounts de modelos, entrypoint/entorno oficiales,
loopback exclusivo, red Docker interna y versión. No sigue redirects al enviar PDF.
Consolidaciones0, una solicitud, timeout900s, cero retries. Reserva persistente
antes de envío; destino existente bloquea repetición. HTTP/headers antes de cuerpo,
chunks raw persistidos/flush; errores de lectura/timeout conservan parciales y estado
desconocido. No mata procesos ni reenvía tras timeout. Medición de tiempo incluida;
perfil de memoria/recursos efectivos aún depende del runtime real pendiente.

Comandos disponibles **para una futura ejecución autorizada**, no ejecutados ahora:

```text
PYTHONPATH=code python -B -m document_structure.runners.grobid_trial PDF B_JSON LOCK ATTEMPT_NEW --authorized-execution
PYTHONPATH=code python -B -m document_structure.grobid_export B_JSON ATTEMPT_NEW/raw/response.tei.xml LOCK C_DEST_NEW
PYTHONPATH=code python -B -m document_structure.grobid_view B_JSON C_DEST_NEW/document.json RECONCILIATION_JSON VIEW_DEST_NEW
```

El flag no es autorización por sí mismo; requiere la decisión real del usuario.
No incluirlo en imports/tests/exportadores. No automatizar arranque mientras siga
vigente la restricción de no ejecutar modelos. Ningún contenedor creado ahora.

## Pruebas y límites

```text
PYTHONPATH=code python -B -m unittest discover -s code/document_structure -t code -p 'test_grobid_*.py'
node code/document_structure/test_grobid_view.js
```

Fixtures comprueban contratos sin inferencia ni llamadas de red; PDFs/PNGs de
fixtures no son resultados del estudio. DOM comprueba interacciones, no QA visual.
No se ha comprobado aún compatibilidad efectiva/velocidad/cobertura sobre12.pdf.
El matching conservador puede abstenerse ante codificación, líneas partidas,
coordenadas omitidas o regiones mixtas; se conservan evidencias y candidatos.
GROBID no reconstruye niveles fiables por sí solo. Orden Docling y padres/hijos
sin coordenadas intactos; visualizaciones nuevas solo como relaciones candidatas.

Comprobación read-only realizada26oct2026: cliente Docker existe, motor
`dockerDesktopLinuxEngine` no disponible. No se intentó arrancarlo ni descargar
imagen. G0, inferencia, C y comparación real permanecen pendientes. Revisar auditoría
`analytics/results/sic12_document/grobid-trial-v1-audit/` antes de continuar.
