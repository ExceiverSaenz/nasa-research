# Table 1: encabezado cuadrado y trazas — solo el usuario ejecuta OCR

El paquete esta preparado; no se ha ejecutado OCR nuevo. ROI original `[112,154,943,230]`,831x76. Se conserva cada pixel y se agrega blanco arriba377/abajo378, sin resize ni mejora de imagen: lienzo831x831. Referencia manual excluida del upload. Configuracion, versiones, pesos, thresholds del parser y tolerancias de aceptacion originales intactos.

## Ejecutar desde Ubuntu/WSL

Si necesitas una sesion nueva propia:

```bash
colab new -s nasa-table1-square-env --gpu T4
```

Cuando este READY (o usando el nombre de una T4 propia existente):

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
bash code/page_integration/test_square.sh nasa-table1-square-env --own-session
```

No ejecutar los lanzadores header/v1 anteriores. No volver a preparar el paquete.
`--own-session` declara sesion propia exclusiva. El lanzador no crea sesiones: verifica T4, sube el ZIP/sidecar, ejecuta una sola ROI con el parser original, descarga y verifica hash/CRC/plan/estado terminal y despues cierra esa sesion. Un fallo terminal con respaldo tambien se descarga/verifica antes del cierre. Ante timeout sin confirmacion terminal no reintenta ni cierra un proceso posiblemente activo: revisar el log y gestionar manualmente la sesion para no dejarla sin seguimiento. Ante descarga/integridad fallida no cerrar antes de asegurar el respaldo.

Avisar al terminar con la carpeta `code/results/table1-square-v1/<fecha>-<pid>/` y cualquier error. Toda evaluacion posterior es local, sin OCR/GPU. No afirmar reconocimiento ni vinculo por el mero estado completed.

## Entorno y observadores

Mismo `parse_native`: MinerU4.0.12, DocVortex0.6.0, Python3.11.16, Torch2.7.1+cu126, Basic/Torch/CUDA12.6/Tesla T4, OCR, image_analysis=True y tablasCPU. Se reutilizan config.yaml, requirements.lock/freeze y revision de pesos `2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d`. El runtime verifica paquetes/config/pesos antes de parsear. Directorios nuevos `/content/nasa-table1-square-v1*`, sin sobrescribir experimentos previos.

`trace_observer.py` verifica hashes de tres fuentes instaladas contra el wheel oficial4.0.12 (SHA256 `a3ff8582a4608eb1f4dde55800ac156d59b01ceabd2ab4002bdf8e86306b1eab`). Incompatibilidad implica fallo, no cambio de version/filtros. Los wrappers temporales observan llamadas originales y se restauran; no se modifica el paquete instalado en disco ni se invoca ninguna inferencia adicional.

En `rois/p0-b2/traces/`:

- Preprocesamiento: tamano/hash de imagen y forma del tensor, sin volcar millones de pixeles.
- Layout antes del filtrado: pred_boxes y logits completos, umbrales de clase; indice de lote/consulta conservado por posicion de tensor. No se imputa ningun score ni se guarda completo el tensor de orden innecesario.
- Antes/despues de conversion de predicciones, filtro PaddleX, deduplicacion, formulas, margenes/cabeceras y captions internos: argumentos y resultados literales.
- Antes/despues de crops/deteccion OCR, descarte por confianza y reconocimiento: cajas, textos y scores conservados. Imagenes internas como dimensiones/hash; valores numericos no finitos quedan explicitamente tipados, nunca sustituidos por scores.
- Normalizacion textual: argumentos antes/despues para detectar vaciado posterior.

Cada invocacion tiene archivos `NNNNN-before.json`, `NNNNN-after.json` o `NNNNN-error.json`; `summary.json` contiene contadores y hashes. Los contadores cero distinguen etapas no alcanzadas. Las trazas describen la nueva ejecucion, no prueban retrospectivamente cual filtro causo el vacio del encabezado anterior. Fallos de observacion se archivan, no autorizan reintentos automaticos.

## Transformacion y aceptacion

Convertir cajas normalizadas del parser a pixeles del lienzo y restar padding antes de trasladar:

`x_original=112+831*x_normalizada`

`y_original=154+831*y_normalizada-377`

Funcion pura `square_original_box` conserva la caja candidata sin clipping y marca si pertenece integramente al contenido. Una caja en blanco o cruzando el padding no se vincula como rotulo valido. No usar `original_box` del recorte simple directamente para estas salidas; el marco ahora es un lienzo con padding.

Se mantienen IoU>=0.50, cobertura>=0.90 de referencia ampliada2px y error inverso<=1px, referencia manual previa y parentage p0-b2/p0-b2-c0/p0-b2-c1. No se deduce numeracion por orden ni se asocia solo por cercania. Candidatos ambiguos se conservan. Si las lineas no tienen texto individual, exigir revision visual registrada antes de verificar el vinculo. Table2 aceptada y experimentos anteriores intactos.

Pruebas offline: padding/pixeles/inversa, wrappers de descriptores y aliases, identidad de retorno y llamada unica, mutacion nativa observada sin alterar, excepciones originales, raw logits/no finitos, paquete/config/tolerancias, bootstrap Jupyter y lanzador con CLI ficticio (exito/fallo/timeout/respaldo corrupto). No cargan Torch/MinerU ni ejecutan OCR. La compatibilidad remota y recuperacion real estan pendientes de tu ejecucion.
