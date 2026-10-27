# MinerU Basic: ensayo de una página en Colab T4

Configuración aprobada: MinerU4.0.12, Basic, backendTorch, CUDA/T4; sin VLM.
Python3.11.16, Torch2.7.1+cu126, torchvision0.22.1+cu126, Transformers5.10.1,
DocVortex0.6.0. requirements.lock fija135 paquetes y hashes para Linux x86_64.
Resolución y disponibilidad binaria comprobadas, salvo jieba0.42.1 (Python puro,
sdist explícitamente permitido). No hay instalación/inferencia GPU acreditada aún.

## Ejecutar solo sobre una sesión existente autorizada

Desde la raíz en WSL:

```bash
bash code/mineru_probe/test_page.sh NOMBRE_SESION
```

No crea ni cierra sesiones. No ejecutar dos veces en la misma VM con estas rutas:
lock y archivos existentes impiden sobrescribir evidencia. Un timeout del CLI no
demuestra que el proceso haya terminado; comprobar antes de cualquier reintento.
El script imprime estado/saldo cerca de la ejecución, no para recuperar contexto.

Se sube únicamente el PNG original verificado de12.pdf,página3 y código/lock/
manifiesto propios. Paquete `code/packages/mineru-page.zip`. MinerU convierte el
PNG internamente en PDF y puede redimensionarlo para sus modelos; registramos esa
transformación y devolvemos cajas normalizadas al marco1654×2205 original.
No se usa texto nativo del PDF fuente ni regiones de los modelos anteriores.

Entorno `/content/mineru-probe/env`, separado del kernel y de LayoutLMv3/TATR.
Bundle `opendatalab/MinerU-4_models_torch`, revisión fija
`2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d`:12archivos,894881298bytes.
Cada descarga se verifica con tamaño y digest Git/LFS del manifiesto fijo,
y se conserva un reciboSHA256. Los modelos ya verificados se activan mediante el
flujo oficial de MinerU con proveedor local en lugar de descargar desde main:
se revalidanSHA256 y luego el flujo oficial comprueba rutas y marca completitud.
Este adaptador depende explícitamente del código4.0.12; no actualizarlo sin revisar.

Layout/OCR/fórmulas usan el backendTorch solicitado en CUDA. Los modelos ONNX de
tablas se mantienen explícitamente enCPU: no afirmar que todo el pipeline utiliza
GPU. Los chequeos iniciales validan T4/versiones/backend/configuración; el runtime
real completo solo se acredita tras ejecución. La dependencia obligatoria
mineru-llama-cpp se instala por el paquete, pero Basic no carga ni descarga un VLM.
Las funciones auxiliares LLM están desactivadas y no se requieren claves API.

## Salidas y recuperación

Resultados locales `code/results/mineru-page/<fecha>/` con ZIP, sidecar y log CLI.
El ZIP incluye configuración, input-manifest, lock/freeze, manifiesto de pesos y
recibo de descarga, estado/log incluso si falla instalación o parsing.
Dentro de `page/`:

- `middle-native.json` y `model-native.json` (si disponible): guardados antes de
  materializar imágenes/Markdown, con el contrato nativo sin reducir.
- `native/`: exportación oficial de recursos, MiddleJson, ModelJson y Markdown.
- `regions.json`: etiquetas nativas, índices, punteros JSON y relación padre/hijo;
  bbox normalizada y XYXY en elPNG original. Score null si no existe.
- `overlay.png` y `crops/`: derivados para revisión, sin padding. Verde para padres,
  azul para hijos. Padre y cuerpo pueden compartir exactamente la misma caja:
  no contarlos como detecciones independientes.
- `run-manifest.json`, `page-status.json`, `error.log` ante fallo.

Las cajas faltantes se registran con bbox null y geometry_warnings, sin inventarlas.
Un fallo de derivados permite reexportar localmente desde middle-native.json y
elPNG original, sin volver a cargar modelos. Mantener el estado remoto original.
Recuperar/verificar ZIP antes de detener exclusivamente la sesión propia.

## Verificación local

```bash
python3 -m unittest discover -s code/mineru_probe -p 'test_*.py' -v
bash -n code/mineru_probe/test_page.sh
```

Pruebas con fixtures/dobles: geometría y jerarquía reales del contrato0.6.0,
tiposJSON, entrada fija, conservación nativa ante fallo, seguridad del paquete,
integridad de descarga y protección de evidencia. No prueban carga/inferencia real.
No repetirlas al iniciar otro chat; consultar `code/results/mineru-local-checks/`.

Comparar visualmente título3.1, párrafos/lista, captions, dos figuras, ecuación,
encabezado/página y tablas. Sin CER/WER, exactitudLaTeX, fusión o porcentaje de calidad.
