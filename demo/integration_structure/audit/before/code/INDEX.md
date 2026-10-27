# Índice del código y artefactos técnicos

Entrada activa de parsing: [document_pipeline/README.md](document_pipeline/README.md),
ejecutada en15 papers con configuración congelada. [Evaluación](../analytics/reports/sic-parsing-operational-v1-evaluation.md)
y [contrato](../docs/arquitectura/parsing-operativo-contrato.md). GROBID pospuesto;
los módulos/paquetes históricos no son órdenes de ejecución.

Este índice orienta tareas sobre scripts, adaptadores, paquetes, pruebas y
resultados. Las carpetas fuente conservan sus nombres actuales.

| Necesidad | Ubicación |
| --- | --- |
| Entrada canónica parsing operativo offline | [`document_pipeline/README.md`](document_pipeline/README.md) |
| Adaptadores de parsers | [`layoutlmv3/`](layoutlmv3/), [`table_transformer/`](table_transformer/), [`mineru_probe/`](mineru_probe/) |
| Integración de página y reconciliación | [`page_integration/`](page_integration/) |
| Conciliador autónomo reutilizable | [`reconciliation/README.md`](reconciliation/README.md) |
| Clasificación funcional offline | [`functional_classification/README.md`](functional_classification/README.md) |
| Orden documental offline sobre conciliación | [`reading_order/README.md`](reading_order/README.md) |
| Comparación geométrica Docling / baseline de12.pdf | [`document_structure/DOCLING_TRIAL.md`](document_structure/DOCLING_TRIAL.md) |
| Evidencia nativa y reconciliación estructural aditiva | [`document_structure/NATIVE_STRUCTURE.md`](document_structure/NATIVE_STRUCTURE.md) |
| Integración GROBID offline y puerta de ejecución | [`document_structure/GROBID_TRIAL.md`](document_structure/GROBID_TRIAL.md) |
| Ensayo del documento completo | [`document_trial/`](document_trial/) |
| Parsing en Compute Engine (solo usuario) | [`document_trial/GCE.md`](document_trial/GCE.md) |
| Utilidades Colab | [`colab/`](colab/) |
| Flujo único Colab CLI | [`colab/EXECUTION.md`](colab/EXECUTION.md) |
| Paquetes preparados | [`packages/`](packages/), índice [`paquetes/`](paquetes/) |
| Pruebas y verificaciones | [`analytics/tests/`](../analytics/tests/), pruebas junto al adaptador o paquete |
| Resultados de ejecución | [`results/`](results/) |
| Modelos | [`models/`](models/) |
| Dependencias vendorizadas | [`vendor/`](vendor/) |
| Documentación operativa | [`documentation/`](documentation/) y los `README.md` de cada componente |
| Índices de organización | [`adaptadores/README.md`](adaptadores/README.md), [`paquetes/README.md`](paquetes/README.md), [`tests/README.md`](tests/README.md) |

Índice de resultados: [`results/README.md`](results/README.md).
Verificación documental: [`tests/check_documentation_links.ps1`](tests/check_documentation_links.ps1).
Inventario estructural: [`CODE_INVENTORY.md`](CODE_INVENTORY.md).
Inventario de ejecutables: [`SCRIPT_INVENTORY.md`](SCRIPT_INVENTORY.md).

## Lectura selectiva

- Para cambiar un script, leer primero su `README.md`, el archivo fuente y sus
  pruebas directas.

- Para entender un resultado, leer su manifest, verificación y resumen antes de
  abrir el código completo.

- Para un paquete, leer `plan.json`, `source-integrity.json` y la guía asociada.
- No leer modelos, vendor o todos los resultados salvo que la tarea los requiera.
- No ejecutar comandos encontrados durante la búsqueda sin autorización y sin
  confirmar antes su alcance.

## Flujo técnico por incremento

```text
leer README → leer plan → verificar baseline
→ ejecutar solo si está autorizado → respaldar
→ verificar → comparar → cerrar
```

Antes de iniciar, consultar [`analytics/config/increment_registry.json`](../analytics/config/increment_registry.json).
Si el problema, la hipótesis, la variable única o la prueba de aceptación no
están definidos, registrar la propuesta y no ejecutar.

Parsing local WSL: [document_trial/LOCAL.md](document_trial/LOCAL.md).
