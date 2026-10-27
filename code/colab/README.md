# Prueba mínima con Colab CLI 0.7.4

## Entrada operativa común

Antes de usar cualquier lanzador Colab CLI, seguir
[`EXECUTION.md`](EXECUTION.md) y registrar el run en
[`analytics/config/remote_runs.json`](../../analytics/config/remote_runs.json).
Esta guía contiene contexto histórico de un smoke test; no repetirlo para
recuperar contexto.

## Guía histórica de infraestructura

La etapa descrita aquí ya fue superada por instalación LayoutLMv3 e imports/config
correctos. Ver `docs/continuidad/04-estado-de-la-prueba.md` y evidencia en
`code/results/layoutlmv3-import/20261018T201957Z/`. No repetir este smoke para
iniciar una conversación. Sesión posterior `nasa-layout-env`, detenida según el
usuario; siguiente hito: inferencia de una página. Los saldos y limitaciones
que siguen son históricos, no consultas actuales.

Estado histórico consultado por el usuario: 280.14 unidades, 0.00/h, ninguna sesión activa. Consultar de nuevo antes de ejecutar. El acceso automatizado a WSL está bloqueado; ejecutar estos comandos en Ubuntu como exceiver.

Esta prueba verifica infraestructura, transferencia y recuperación. No instala dependencias ni ejecuta LayoutLMv3. Las operaciones de preparación se hacen localmente. La inferencia futura del detector se ejecutará en GPU; el inventario, validación de cajas y análisis de resultados pueden hacerse localmente.

## Preparación local (sin GPU)

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
python3 -m py_compile code/colab/smoke_remote.py
colab version
colab usage
colab sessions
```

## Ejecutar únicamente después de autorizar el consumo

Solicitar una T4 para esta prueba pequeña; no se necesita una A100 para validar la conexión. Si aparece una sesión existente adecuada, revisar su propietario y estado antes de reutilizarla. No detener sesiones ajenas.

```bash
colab new -s nasa-cli-smoke --gpu T4
colab status -s nasa-cli-smoke
colab usage
colab upload -s nasa-cli-smoke code/colab/smoke_remote.py /content/nasa_smoke_source.py
colab exec -s nasa-cli-smoke --timeout 180 -f code/colab/smoke_remote.py
mkdir -p code/results/smoke
colab download -s nasa-cli-smoke /content/nasa-smoke-result.json code/results/smoke/result.json
python3 - <<'PY'
import hashlib, json
from pathlib import Path
r = json.loads(Path('code/results/smoke/result.json').read_text())
expected = hashlib.sha256(Path('code/colab/smoke_remote.py').read_bytes()).hexdigest()
assert r['uploaded_source_sha256'] == expected, 'El archivo transferido no coincide'
assert r['gpu_ok'] is True, 'La operación CUDA no pasó'
print(json.dumps(r, indent=2))
print('Transferencia, GPU y recuperación verificadas')
PY
```

Ejecutar cada paso por separado; no continuar tras un fallo. Antes de detener, comprobar que result.json existe, es legible y contiene gpu_ok=true. Si la ejecución falla, consultar estado y recuperar los resultados disponibles antes de cerrar. Un timeout del cliente no demuestra que el proceso remoto se haya detenido.

Si la sesión nasa-cli-smoke fue creada por ti exclusivamente para esta prueba y los resultados ya están verificados:

```bash
colab stop -s nasa-cli-smoke
colab sessions
colab usage
```

## Siguiente etapa: el detector

El entorno aislado y la instalación de LayoutLMv3 ya están comprobados en Colab.
Usar `code/layoutlmv3/test_detector.sh` solo al necesitar reconstruir una VM para
un ensayo autorizado. Falta implementar el wrapper de inferencia. No instalar
paquetes históricos en el kernel moderno con `colab install`.

Para ejecutar varios módulos, preparar un archivo de distribución con una lista explícita de scripts, configuración y PDFs seleccionados; subirlo con colab upload y extraerlo en una carpeta remota dedicada. colab exec -f solo transmite el archivo indicado: no sincroniza imports, datos ni checkpoints. No subir todo el repositorio indiscriminadamente.

Registrar versiones, pesos y hashes, PDF/páginas de prueba y parámetros. Guardar salidas y checkpoints en una carpeta de ejecución, empaquetarlos, descargarlos y comparar sus hashes antes de detener la VM. No confiar en el almacenamiento temporal remoto. Mantener credenciales y metadatos del CLI fuera del proyecto.
