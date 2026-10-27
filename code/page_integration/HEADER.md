# Table 1: ROI de encabezado — ejecucion exclusiva del usuario

Estado: codigo y paquete preparados, sin OCR nuevo. Table 1 NO se declara recuperada.

## Ejecutar

Desde Ubuntu/WSL, sobre una T4 propia dedicada a esta prueba:

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
bash code/page_integration/test_header.sh NOMBRE_DE_TU_SESION_T4 --own-session
```

Si no tienes una sesion propia T4 activa, puedes crearla tu mismo:

```bash
colab new -s nasa-table1-header-env --gpu T4
bash code/page_integration/test_header.sh nasa-table1-header-env --own-session
```

`--own-session` confirma que la sesion es tuya y exclusiva: se cerrara despues de descargar y verificar un respaldo terminal. El script no asigna sesiones ni cambia hardware. No se ejecuta localmente el parser: todos los modelos se ejecutan por Colab CLI en T4.

El lanzador verifica el paquete y hardware, sube un ZIP y su sidecar, instala/verifica el entorno original y procesa **una sola ROI una vez**. Aisla argumentos Jupyter y modulos de experimentos anteriores. Descarga el ZIP y sidecar; comprueba hash, CRC, plan exacto y estado terminal antes de cerrar la sesion. Tambien conserva y descarga un fallo terminal con respaldo antes de cerrarla. No hay reintentos automaticos.

Si hay timeout o falta confirmacion terminal, no puede garantizar que termino el proceso: no reinicia OCR ni cierra un trabajo posiblemente activo. Avisa con el log para revisar manualmente; no dejes esa sesion sin seguimiento. Si falla la descarga/integridad, no la cierra antes de asegurar el respaldo. No limpiar ni reutilizar rutas remotas automaticamente.

Resultados locales: `code/results/table1-header-v1/<fecha>-<pid>/`. Avisar al terminar con esa ruta y cualquier error. La evaluacion sera local, sin GPU ni OCR. No ejecutar tambien `test_labels.sh` (experimento anterior).

## Que cambia y que se conserva

Solo cambia el contenido de entrada: ROI `[112,154,943,230]`, 831x76 pixeles, del render original1654x2205. X=envolvente de descripcion; Y superior=barrera previa y Y inferior=fin de descripcion; redondeo hacia fuera. Sin padding, resize ni mejora de imagen. El cuerpo tabular queda fuera; documento/pagina/hash, parentage y cajas originales permanecen como referencias.

Misma llamada `parse_native`: MinerU4.0.12/DocVortex0.6.0, Python3.11.16, Basic/Torch, OCR, image_analysis=True, CUDA12.6/Tesla T4 y tablas CPU; mismo requirements.lock/freeze, config.yaml, pesos y revision `2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d`. Se valida el entorno antes del OCR. Ninguna opcion nueva de reconocimiento.

Las rutas de estado y venv son nuevas (`/content/nasa-table1-header-v1*`) para no sobrescribir la prueba anterior. Se verifican y reutilizan pesos originales si existen; si no, se descargan las mismas revisiones mediante el flujo original. Una incompatibilidad se informa y detiene; no se cambia version/configuracion.

Referencia y expectativa Table1 quedan solo en `acceptance-local.json`; no se suben al OCR. Paquete: `code/packages/table1-header-v1/upload.zip`; plan y crop de inspeccion al lado. Historial y verificacion de integridad en `analytics/results/sic12_page3/table1-header-v1-preparation/`.

## Aceptacion acordada, aun pendiente de resultados

- Rótulo visible completo en ROI y reconocido en texto nativo como Table1/Table 1 (espacios/case tolerados); no deducir numeracion por orden.
- Caja del candidato en render original: `x=x0+xn*831`, `y=y0+yn*76`; IoU>=0.50, cobertura de referencia ampliada 2px>=0.90, error inverso<=1px. Sin segundo escalado.
- Descripcion coincidente y parentesco `p0-b2`/`p0-b2-c0`/`p0-b2-c1`; cercania sola no basta. Referencias del cuerpo, varios destinos o candidatos contradictorios quedan rechazados/ambiguos y conservados.
- Si se combinan rotulo y descripcion, no se inventa una caja de glifos: evaluar lineas nativas y revisar visualmente si no tienen transcripcion individual, conforme al incremento anterior. No aceptar la caja combinada si falla geometria.
- Mantener intactos ZIP/paquetes/resultados anteriores, referencia y Table2 aceptada. Un fallo no autoriza nueva zona, motor o reintento.

Las pruebas actuales verifican preparacion y lanzador sin OCR (CLI ficticio); no demuestran reconocimiento real ni compatibilidad acreditada del nuevo entorno remoto hasta tu ejecucion.
