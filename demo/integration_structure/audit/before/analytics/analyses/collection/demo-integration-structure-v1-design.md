# Demo de integración completa en Jupyter / A100

Estado: diseño aprobado por el usuario; implementación en curso.
Hardware corregido explícitamente por el usuario a A100 durante la implementación.

## Solicitud y objetivo

Crear `demo/integration_structure`, similar a `demo/parsing_structure`, con un
notebook y todos los archivos necesarios para ejecutar la integración completa
del diagrama del usuario sobre los 15 papers / 397 páginas existentes.
El usuario ejecutará el notebook en un entorno Linux con A100. La preparación
local no crea sesiones remotas ni ejecuta los parsers.

## Enfoque propuesto

Hay una vía que reproduce el flujo solicitado: empaquetar las entradas nativas
conservadas y ejecutar las etapas existentes en destinos nuevos. Una demo que
solo cargue resultados finales no demostraría la conciliación; volver a ejecutar
los tres parsers ampliaría el alcance a la demo de parsing ya existente.

Decisión propuesta del implementador: usar el ZIP consolidado nativo vigente
(`sic-15-papers-3-parsers-native-v1.zip`, aproximadamente 1,17 GB), con su hash,
los PDFs originales verificados por identidad y una copia trazable del código
necesario. La demo será autónoma respecto a las rutas locales de Windows.

## Entrega

- `integration_structure_pipeline.ipynb`: instrucciones y celdas secuenciales
  para cargar/verificar el paquete, preparar entorno, ejecutar, inspeccionar y
  respaldar resultados.
- `upload.zip` y `upload.sha256`: código, contratos, dependencias, PDFs y entradas
  nativas existentes; manifest por archivo y procedencia de las copias.
- `README.md`: uso, recursos, salidas y límites.
- Código auxiliar de preparación/orquestación, pruebas pertinentes y registro
  de verificación de la entrega; todo bajo `demo/integration_structure`.

## Etapas

1. Preflight de Linux/A100, espacio disponible y directorio de intento nuevo.
2. Verificación SHA256 y miembros del paquete antes de extraer; rechazo de rutas
   inseguras y entradas alteradas.
3. Entorno aislado con Python 3.13.5, PyMuPDF 1.27.2.3, Docling 2.123.1 y
   docling-core 2.92.0, además de sus dependencias reproducibles. Se conserva
   la guarda de hash del componente geométrico Docling. El kernel de Jupyter
   puede ser distinto: los comandos se ejecutan con el intérprete aislado.
4. Preparación nueva del archivo consolidado mediante el adaptador vigente:
   genera punteros absolutos válidos dentro del entorno de ejecución.
5. Conciliación de cada página con `reconciliation.engine.reconcile`; colección
   exportada con el contrato consumido por la clasificación funcional v2.
   Un auxiliar nuevo conectará `prepare` → `load_document` → `reconcile` y
   escribirá documentos, summary y manifests, con PDF absoluto e identidad
   verificada. El CLI histórico `reconciliation.export` no acepta este ZIP.
6. Clasificación funcional v2 sobre unidades conciliadas.
7. Construcción de inventario/cápsulas con las APIs existentes. El orden reading
   v1 se documenta como preparación histórica/intermedia del contrato; el baseline
   operativo posterior es el ordenador geométrico Docling.
8. Orden Docling, evidencia nativa, estructura, conexión y ensamblado mediante
   el pipeline canónico existente. Se registrará explícitamente la política de
   cachés: los resultados de la demo se calculan de nuevo desde sus entradas y
   no se declaran idénticos byte a byte al run histórico con cachés de 12.pdf.
9. JSON, vistas por paper, índice, colas de revisión y manifests. Registro de
   ejecución y comprobación de integridad/referencias/conservación.
10. Respaldo verificable en Drive si se usa Colab y descarga de una entrega ZIP.
    En Jupyter Linux fuera de Colab, entrega local equivalente.

## Conservación y fallos

Mismo código/configuración para todos los papers. Se conservan fuentes, cajas,
textos, scores originales, clasificaciones, alternativas y abstenciones. Los
374 hijos sin bbox permanecen diferidos y no heredan las cajas de sus padres.
Caption primero en asociaciones utilizables; contenido compartido por referencias.
No se crean asociaciones solo por proximidad ni se concatenan párrafos.

Cada intento usa un destino nuevo. Los fallos dejan logs y resultados parciales;
no hay reintentos ni recuperación automática. El estado técnico distingue fallo,
parcial y completado; la validación semántica sigue pendiente incluso al completar.
La A100 es compatible como entorno solicitado, aunque las etapas de integración
actuales se ejecutan principalmente en CPU y no requieren inferencia CUDA.

## Validación y criterio de parada

Verificar sintaxis/estructura del notebook, integridad del paquete y dependencias
de archivos; probar con fixtures los contratos nuevos de orquestación, protección
de destinos, rutas portables, conservación de fallos y respaldos. No repetir las
exportaciones canónicas para preparar la demo. Si se realiza un ensayo real de
integración, será una ejecución nueva explícita, acotada y registrada, sin modificar
el baseline. No afirmar ejecución real en A100 si solo hubo verificaciones locales.

Registrar el incremento de empaquetado/orquestación en `increment_registry.json`
con baseline, aceptación, pruebas y decisión; el artefacto operativo activo continúa
siendo la versión congelada existente.

Parar cuando notebook y paquete estén completos y sus comprobaciones pasen;
informar con precisión qué ejecución remota queda por realizar por el usuario.

## Revisión del diseño

Revisión independiente completada: suficiente para aprobación. Precisiones
incorporadas: intérprete aislado con versión exacta, exportador de conciliación
de colección explícito y diferencia de procedencia al recalcular sin cachés.
