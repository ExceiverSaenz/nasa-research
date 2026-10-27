# Integración de la colección SiC · Jupyter / A100

Abre `integration_structure_pipeline.ipynb` y ejecuta las celdas en orden en una
sesión Linux x86_64 con una GPU **A100**. En Colab selecciona A100 en el tipo de
entorno. También funciona en Jupyter Linux de otra plataforma con A100.

La integración actual usa CPU. La GPU identifica el entorno solicitado; no se
ejecutan los modelos de parsing ni se necesitan pesos CUDA. La instalación usa
Internet para descargar Python 3.13.5 y los paquetes fijados. Los documentos,
resultados nativos y código científico ya están incluidos en `upload.zip`.

## Archivos y uso

- `integration_structure_pipeline.ipynb`: notebook completo, con etapas separadas,
  diagrama, validación, inspección de resultados y respaldo final.
- `upload.zip` y `upload.sha256`: subir estos dos archivos de **esta carpeta**.
  El notebook comprueba también el hash esperado incorporado en sus celdas.
  En Jupyter normal, dejarlos junto al notebook; en Colab se pueden cargar desde
  el panel de archivos. El ZIP ocupa aproximadamente 1,3 GB: para Colab puede
  ser más cómodo guardarlo en Drive y configurar su ruta en la primera celda.
- `src/`: 28 archivos científicos copiados byte a byte del código vigente.
- `integration_demo/`: adaptación de colección, control de etapas, entorno y
  verificación. No modifica las reglas científicas.
- `requirements-runtime.lock`, `requirements-docling.txt`: versiones exactas.
- `source-snapshot.json`, `bundle-manifest.json`, `package-spec.json` y
  `package-verification.json`: procedencia, hashes, alcance y revisión del paquete.
- `tests/`, `build_package.py`, `make_notebook.py`, `verify_delivery.py`:
  pruebas y herramientas locales para mantener esta entrega.

El paquete incluye los 15 PDFs y el ZIP nativo consolidado conservado, con
11.467 registros de los tres parsers sobre 397 páginas. No se requieren rutas
de Windows ni el resto del proyecto para ejecutar la demo.

## Flujo

Entradas nativas → preparación de punteros Linux → conciliación → clasificación
funcional v2 → inventario/cápsulas → baseline geométrico Docling + evidencia nativa
→ estructura y conexión operativa → JSON, vistas, índice y colas de revisión.

El paso de cápsulas conserva el contrato reading-v1 como intermedio. El ordenador
que se usa como baseline operativo es Docling. Cada etapa guarda sus archivos
para que se pueda inspeccionar qué entra y qué sale.

El notebook crea un intérprete aislado Python 3.13.5 con PyMuPDF 1.27.2.3,
Docling 2.123.1 y docling-core 2.92.0. Instala las distribuciones oficiales exactas
de Docling y docling-slim con `--no-deps`, junto a la clausura fijada de
docling-core/rtree/PyMuPDF. Así se carga el postprocesador geométrico original
sin instalar sus extras neuronales. Comprueba su hash y ejecuta un probe real
del ordenador antes de procesar la colección. No es una instalación del
conversor completo de Docling ni de sus modelos.

## Recursos y salidas

Recomendado: al menos **16 GiB de RAM y 20 GiB libres en disco**, además del
espacio de respaldo en Drive. Son márgenes de preparación, no tiempos o picos
medidos en A100. Se procesa una colección con configuración idéntica y sin
concurrencia de modelos.

La carpeta `run/` del intento contiene:

| Carpeta / archivo | Contenido |
| --- | --- |
| `prepared/` | Fuentes nativas intactas, renders previos y punteros regenerados |
| `reconciliation/` | Unidades, relaciones y evidencia de los tres parsers |
| `classification-v2/` | Clasificación sobre unidades conciliadas |
| `capsules-reading-v1/` | Inventario y cápsulas intermedias |
| `operational/` | JSON, estructura, Docling, evidencia nativa y vistas finales |
| `operational/index.html` | Entrada a los 15 papers |
| `operational/review-queue.json` | Cola de revisión humana posterior al MVP |
| `stages/`, `logs/`, `status.json` | Estados, comandos, salidas y fallos |
| `source-code/`, `pdfs/` | Código ejecutado y PDFs para conservar procedencia |
| `verification.json` | Integridad técnica del nuevo intento |

En Colab, la celda final crea `result.zip` y `result.sha256`, verifica todos los
miembros y copia ambos a una carpeta nueva de Drive. La descarga del ZIP se inicia desde el notebook con `files.download()`. En Jupyter normal, se entregan archivos
locales con el mismo contrato. La verificación también permite respaldar un
intento fallido: su estado sigue siendo `failed`, no éxito de la integración.

Las vistas HTML son estáticas y conservan sus imágenes mediante rutas relativas.
Los JSON de procedencia mantienen las rutas absolutas reales del runtime; el
respaldo incluye las fuentes consumidas y un manifest relativo para localizarlas
tras descargarlo. Tras moverlo, las rutas absolutas históricas documentan origen;
no se reescriben ni se presentan como rutas locales activas.

## Límites y conservación

Las salidas son nuevas. La demo recalcula Docling y evidencia nativa en los 15
papers: el run histórico reutilizó cachés aprobados de 12.pdf. Por esa diferencia
de procedencia no se promete igualdad binaria con el artefacto canónico.

Se conservan abstenciones, contradicciones, originales y los 374 hijos sin bbox.
No se les asigna caja del padre. Las secciones y continuidades siguen siendo
propuestas; todas las unidades conservan revisión `after_full_mvp`. Las pruebas
de integridad no acreditan exactitud semántica ni QA visual real.

No repetir celdas de ejecución. Una etapa ya iniciada se rechaza si se vuelve a
lanzar. Ante fallo, conservar logs y respaldar el intento; una ejecución distinta
requiere un directorio nuevo. No hay recuperación automática. Si se interrumpe
manualmente una celda, comprobar que el subproceso ha terminado antes de usar la
celda de cierre de intento interrumpido y después generar el respaldo.

## Verificación local de esta entrega

Desde la raíz del proyecto:

```powershell
python -B -m unittest discover -s demo/integration_structure/tests -v
python -B demo/integration_structure/verify_delivery.py
```

Las pruebas usan fuentes sintéticas y APIs reales (incluido Docling geométrico y
extracción nativa). No vuelven a exportar la colección canónica. La evidencia
local final se guarda en `verification.json`; la ejecución real del notebook en
A100 queda a cargo del usuario.
