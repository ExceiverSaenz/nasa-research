# Ensayo independiente Table Transformer

Diseño aprobado: `docs/analysis/diseno-experimental/11-diseno-ensayo-table-transformer.md`.
Implementación preparada localmente; **todavía no se ha ejecutado el modelo en GPU**.

## Alcance

Solo detección de tablas sobre el render completo original de SiC12.pdf, página3.
No OCR, reconstrucción de celdas, PDF renderizado de nuevo, entrenamiento o fusión
con LayoutLMv3. Salidas separadas en `code/results/table-transformer-page/<fecha>/`.

| Archivo | Responsabilidad |
| --- | --- |
| `detector.py` | Adaptador TableTransformerDetector, carga e inferencia; imports pesados diferidos |
| `outputs.py` | JSON, overlay y recortes sin padding; no ejecuta modelo |
| `run_image.py` | Coordina una imagen, manifiesto, tiempos, estado y errores |
| `prepare.py` | ZIP explícito de PNG, procedencia y código; valida SHA256 y miembros |
| `remote_job.py` | Entorno independiente, descarga verificada y ejecución; protege evidencia previa |
| `test_page.sh` | Transfiere, ejecuta, descarga y verifica sobre sesión existente autorizada |

## Insumo y modelo

PNG exacto de `page/render.png` del ZIP del primer ensayo,1654×2205px,200dpi.
SHA256: `6f46d8ff2d05eee785739ec1c34716db14135411c731e7aa6433e27ca06d00b9`.
No se usan recortes ni cajas previas como entrada. La identidad se verifica antes
de empaquetar, al extraer y al ejecutar.

Modelo `microsoft/table-transformer-detection`, revisión
`2357cbe2b5a5d1c03e54f32764f06058933b65ab`. Descarga solo config, procesador y
model.safetensors desde esa revisión. La API de metadatos debe devolver el mismo
commit; cada descarga se valida con tamaño y digest LFS-SHA256 o Git-blob-SHA1.
Se guarda además SHA256 de cada archivo y se vuelve a verificar antes de cargar.
La red real y los metadatos de descarga aún no se probaron en Colab.

Se usa el DetrImageProcessor del checkpoint, límite800, y normalización propia;
no800/1333 de LayoutLMv3. El adaptador registra forma real del tensor. Las cajas
cxcywh normalizadas de DETR se convierten directamente a píxeles del PNG original.
No se escalan dos veces ni se recortan sus coordenadas.

Clases nativas table/table rotated/no object para las consultas. Umbral0.5
inclusivo, conservado antes de ver resultados. Las consultas cuyo argmax es
no object no se exportan como tabla. No se aplica NMS ni ajuste posterior.
Todas las consultas, sus logits y cajas normalizadas quedan en regions-raw.json.

## Entorno propio

Python3.11.11 mediante uv0.6.14, en `/content/tatr-probe/env`.
torch2.5.1+cu121 y torchvision0.20.1+cu121 del índice oficialCUDA12.1.
Transformers4.49.0, timm1.0.14, NumPy1.26.4, Pillow10.4.0, safetensors0.5.3,
huggingface-hub0.29.3 y tokenizers0.21.0 en requirements.txt.
Se verifican dependencias y CUDA/T4 y se guarda el freeze completo. Las dependencias
transitivas resueltas se registran; no es una restauración offline byte por byte.
El bootstrap descarga paquetes de varios GB: la instalación forma parte del coste
del nuevo ensayo. No instala ni ejecuta LayoutLMv3 ni reemplaza el kernel moderno.
uv se instala con `pip --target` en un directorio propio, sin modificar paquetes
del kernel. Disponibilidad/compatibilidad real de esta combinación pendiente.

## Uso cuando se autorice la sesión

Desde la raíz en WSL, y solo con una sesión T4 ya asignada para este ensayo:

```bash
bash code/table_transformer/test_page.sh NOMBRE_SESION
```

No crea ni detiene sesiones. Empaqueta PNG+metadatos+código (sin PDF/pesos), sube
solo lo necesario y reutiliza cli_job.py/verify_download.py para respaldo. Un
fallo del job conserva registros y estado; el verificador devuelve error si el
trabajo falló aunque la integridad del ZIP sea correcta. Un timeout del CLI no
confirma terminación: no repetir ni cerrar hasta comprobar estado/recuperación.

Una segunda ejecución sobre los mismos directorios remotos se rechaza **antes de
abrir o truncar registros**, con lock exclusivo persistente. No borrar el lock o
forzar un reintento sobre resultados antiguos; recuperar evidencia y decidir
explícitamente una nueva ejecución/VM. El cierre se hace manualmente después de
descargar/verificar y solo para la sesión propia.

## Salidas y errores

- run-manifest.json, page-status.json y load-report.json.
- regions-raw.json con todos los logits y cajas; regions.json con tablas filtradas.
- overlay.png y crops/query-N.png para cada detección que interseca la imagen.
- Las cajas originales fuera de página se conservan; crop_bbox registra el
  recorte real floor/ceil limitado al PNG, crop_clipped avisa y crop_path es null
  si no hay intersección. No padding ni rotación correctiva de tablas.
- JSON de predicciones se guarda **antes** de imágenes derivadas. Si falla una
  imagen, el estado es failed pero no hace falta repetir GPU para recuperar logits.
- Diagnósticos de red omiten URLs de redirección temporales. Si hay claves faltantes,
  inesperadas o tamaños incompatibles en carga, no se permite predict.
- input-manifest.json, source.json, model-manifest.json, constraints.txt,
  requirements-freeze.txt y setup-console.log quedan en el respaldo remoto.

Los resultados table rotated quedan separados como etiqueta nativa; no se altera
la taxonomía del auditor PubLayNet existente para acomodarlos en secreto.

## Validación local

Desde raíz, con dependencias locales NumPy/Pillow del runtime disponible:

```bash
python -m unittest discover -s code/table_transformer -p 'test_*.py' -v
```

Pruebas de decoding, umbral, background, clipping, cero detecciones, fallos,
paquetes y descargas simuladas. Coordinador con dobles: no acredita torch, HF,
modelo real, procesador real o CUDA. El bootstrap y las descargas se prueban en la
VM, no con estos dobles. No pedir repetir las comprobaciones locales al iniciar chats.

La comparación final será visual sobre las dos tablas, conservando ambas salidas
por separado. No asignar porcentajes ni extrapolar a la colección.

## Corrección del primer ensayo real y reintento

El primer intento falló en carga; respaldo íntegro en
`../results/table-transformer-page/20261023T165134Z/`. No produjo detecciones.
Se admiten solo los tres contadores FrozenBatchNorm de layer2/3/4 downsample
registrados en ese intento. Se mantienen completos en load-report.json;
run-manifest.json registra la política de compatibilidad. No se admiten otras
claves adicionales, ausentes, tamaños incompatibles ni errores de carga.
Fuente verificada: https://github.com/huggingface/transformers/blob/v4.49.0/src/transformers/models/table_transformer/modeling_table_transformer.py
(clase TableTransformerFrozenBatchNorm2d, líneas 188–228).

En la VM original todavía activa:

```bash
bash code/table_transformer/retry_page.sh nasa-tatr-env
```

Reutiliza Python/torch/Transformers/timm y pesos de esa VM; solo sube el código
corregido y el mismo PNG. Salidas remotas nuevas `/content/tatr-retry-state/page`,
respaldo `/content/tatr-retry-result.zip`. No borra/reemplaza el respaldo original.
La protección de archivo/lock también impide repetir este reintento.
Si ya se perdió la VM, este flujo no reconstruye el entorno.
17 tests propios y34 anteriores OK; inferencia corregida aún pendiente.
## Estado vigente TATR: inferencia recuperada (23 octubre 2026, ensayo 16:59 UTC)

La misma T4 `nasa-tatr-env` cargó el modelo y ejecutó inferencia: carga4.011s,
predicción0.515s, dos tablas. La exportación remota falló al serializar un
numpy.bool_ en crop_clipped; el estado remoto se conserva como failed/export.
Se corrigió únicamente esa conversión a bool nativo con regresión reproducida.
18 tests TATR +34 LayoutLMv3 aprobados. No se requiere nueva inferencia.

Respaldo local verificado por SHA-256 y CRC:
`code/results/table-transformer-page/20261023T165937Z/result.zip`,
SHA-256 `a29324b855ae95a9e2be227fa13e4b61253e098501abda84a151654d5d820611`.
Incluye queries, cajas, overlay y ambos recortes. Derivados reconstruidos localmente
en `recovered-exports/` desde las queries guardadas y el render original verificado;
cajas, scores e IDs coinciden exactamente con los del ZIP. Provenance conservada,
sin modificar el ZIP ni atribuir éxito al exportador remoto. Script puntual
`recover_exports.py` en el mismo directorio; review/ conserva imágenes e informes remotos.

Observación visual: dos tablas sin figuras ni captions, sin cajas adicionales con
umbral0.5. Confianzas0.999889 y0.999862 no son porcentajes de calidad. Bordes muy
ajustados, líneas horizontales exteriores excluidas; no afirmar recortes perfectos.
Mejora diagnóstica frente a mezcla tabla/figura de LayoutLMv3 en esta página.
Sin OCR, celdas, fusión ni validación de colección. Mantener resultados separados.

**Siguiente paso:** revisar con el usuario las salidas recuperadas; no ejecutar otra
vez retry_page.sh. Respaldo íntegro disponible para detener exclusivamente
`nasa-tatr-env`; cierre aún no confirmado. No crear nueva asignación automáticamente.
Los estados pendientes de inferencia/reintento siguientes son históricos.

