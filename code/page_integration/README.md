# Recuperación localizada: dos rótulos, ejecución exclusiva del usuario

## Experimento vigente preparado: Table1 square-v1 con trazas

El encabezado sin padding produjo salida nativa vacia. El nuevo incremento aprobado
conserva831x76 pixeles y agrega blanco377arriba/378abajo para lienzo831x831, mismo
parser/configuracion/tolerancias. Paquete separado `code/packages/table1-square-v1/`.
Solo usuario: `bash code/page_integration/test_square.sh SESION_T4 --own-session`.
Instrucciones vigentes en [SQUARE.md](SQUARE.md). No se ha ejecutado OCR nuevo;
Table2 aceptada y experimentos anteriores intactos. Las secciones siguientes son historia.

## Siguiente experimento listo: encabezado de Table 1

Paquete independiente `code/packages/table1-header-v1/`; instrucciones vigentes en
[HEADER.md](HEADER.md). El usuario ejecuta `bash code/page_integration/test_header.sh SESION_T4 --own-session`.
Solo una ROI `[112,154,943,230]`, mismo parser/configuracion/tolerancias; no hay OCR nuevo
ejecutado por el agente. El lanzador cierra la sesion propia despues de verificar respaldo.
Table2 aceptada, paquetes y resultados anteriores intactos. Las instrucciones v1 siguientes
se conservan como historia; no ejecutarlas para esta nueva ROI.

## Actualización: Table 2 mediante líneas nativas (24oct2026)

Incremento posterior aprobado y realizado exclusivamente sin OCR. Resultado vigente:
`analytics/results/sic12_page3/table2-lines-v1/accepted/table2-lines.json`.
Primera línea del caption nativo = candidato de rótulo; segunda = candidato de descripción.
La asignación no es transcripción individual del parser: requiere registro visual separado,
con hash de fuente y punteros. `visual-review.json` registra la inspección de Codex;
no equivale a aprobación humana del resultado ni valida otros documentos.

Solo se aplica la equivalencia explícita `\mathrm{UO}_{2}` → `UO2` para comparar;
se conservan literales y regla aplicada. No se eliminan comandos LaTeX genéricamente.
Se preservan el candidato combinado original y todas las alternativas rechazadas.
Más de dos líneas, solapamientos, inversiones, contenido interpuesto, columnas distintas
o varios candidatos elegibles impiden cerrar automáticamente el vínculo.

Table 2 pasa IoU=0.6637845569 y cobertura=0.99 con las tolerancias originales.
Vínculo `p0-b4`/`p0-b4-c0`/`p0-b4-c1` verificado con revisión visual explícita del agente.
Table 1 no se recupera ni modifica; sus resultados v1 se conservan sin cambios.
24 pruebas offline pasan. ZIP, referencia, paquete original y 85 archivos protegidos intactos.

Comando reproducible offline (salida nueva obligatoria):

```bash
PYTHONPATH=code python3 -B -m page_integration.workflow evaluate-table2-lines \
  --preparation code/packages/localized-labels-v1 \
  --result code/results/localized-labels-v1/20261024T221741Z/result.zip \
  --output CARPETA_NUEVA \
  --review analytics/results/sic12_page3/table2-lines-v1/visual-review.json
```

Sin `--review`, el vínculo permanece pendiente aunque pase la geometría.
El esquema específico está en `label_recovery.schema.json#/$defs/table2_lines`.
El upload v1 queda congelado como evidencia de lo ejecutado; no se reconstruye ni se
repite OCR para este incremento. Las instrucciones remotas siguientes son históricas.

Estado 24oct2026: código y paquete preparados; pruebas offline, sin OCR. La recuperación real y los vínculos siguen pendientes. El diagnóstico A03–A06 no se repite.

## Qué se ejecutará

Dos PNG recortados del render original, sin resize/padding: p0-b2 `[112,154,1564,428]`, p0-b4 `[112,1106,818,1526]`. Incluyen rótulo, descripción y cuerpo según cajas originales; no corrigen los bordes tabulares históricos. Se verificaron visualmente antes del OCR. La referencia manual NO se sube ni entra en el algoritmo.

La entrada nueva llama al `parse_native` original sin modificarlo: MinerU4.0.12/DocVortex0.6.0, Python3.11.16, Basic/Torch, OCR, image_analysis=True, CUDA12.6/Tesla T4, tablas CPU; funciones LLM desactivadas. Se reproduce el config.yaml original y se instala el requirements.lock archivado, con hashes. Se compara el conjunto completo de paquetes instalado con el freeze original. Pesos locales de la revisión `2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d`, verificados contra recibo original. Si ya hay pesos en la ruta original, se verifican sin sobrescribirlos. Cualquier incompatibilidad detiene el proceso antes del OCR.

No hay API OCR alternativa, reintentos, ampliación de documentos, asignación/cierre de sesiones ni ejecución automática de comandos CLI. El bootstrap se prepara para que lo ejecute únicamente el usuario desde su Colab CLI sobre una sesión T4 elegida por él. Crea un venv dedicado, puede instalar dependencias y descargar solo los pesos originales si no existen.

## Ejecutar en Ubuntu/WSL mediante Colab CLI

Flujo recomendado, equivalente al lanzador anterior (solo lo ejecuta el usuario):

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
bash code/page_integration/test_labels.sh NOMBRE_DE_TU_SESION_T4
```

Gestiona verificación del paquete, subida, ejecución, descarga y hash en una sesión existente. No crea/cierra sesiones ni repite OCR. Ante error/timeout conserva el log y se detiene; revisar antes de descargar o reintentar. 

El lanzador usa un bootstrap que aísla los argumentos del kernel Jupyter y exige `LOCALIZED_LABELS_COMPLETED` antes de descargar. No ejecutar directamente `remote_labels.py` con `colab exec -f`: el kernel puede pasar sus propios argumentos a argparse. Ante error o timeout, no repetir automáticamente; revisar el log y confirmar si terminó. Esta corrección no cambia el paquete OCR, sus versiones ni configuración.

## Evaluación posterior, sin OCR

Cuando el usuario notifique el final, verificar y evaluar el ZIP descargado. El comando no carga modelos:

```bash
PYTHONPATH=code python3 -B -m page_integration.workflow evaluate \
  --preparation code/packages/localized-labels-v1 \
  --result "$RUN_DIR/result.zip" \
  --output analytics/results/sic12_page3/localized-labels-v1-evaluation
```

La carpeta de salida debe ser nueva. `unified-page.json` conserva candidatos, motivos, textos literales, fragmentos, cajas nativas/originales, hashes, punteros y referencias a cuerpos/captions originales. La asociación usa parentesco, alineación, orden, descripción coincidente y ausencia de texto interpuesto; no usa la referencia manual ni proximidad sola. Un candidato con varios destinos elegibles sigue ambiguo aunque otro destino ya sea ambiguo. Bloques combinados no reciben una caja de rótulo inventada: se conserva la caja del bloque y puede fallar la aceptación geométrica.

La evaluación compara la referencia manual independiente. Mantiene literalmente los umbrales aprobados: IoU>=0.50; intersección candidato/referencia ampliada 2px dividida por área de esa referencia ampliada >=0.90; error inverso <=1px. **Una caja exacta ajustada a los glifos puede fallar esa cobertura estricta**; el sistema lo informa, no relaja el umbral. La comparación textual admite Table1/Table 1 y diferencias de espacios/mayúsculas; no corrige automáticamente caracteres dudosos.

`registry_implemented`, `labels_recovered` y `links_verified` son estados distintos. `links_verified` representa aceptación automatizada contra la referencia; `human_review` permanece `pending` hasta revisión humana. Ninguna prueba sintética demuestra OCR real o generalización.

## Comprobaciones offline realizadas

```bash
python -B -m unittest discover -s code/page_integration -p 'test_*.py' -v
```

Pruebas acotadas de ROI, unidades/inversa, tolerancia, ambigüedad, intercambios, falsos captions, referencia en cuerpo, deriva de runtime, ZIP/allowlist/integridad y evaluación de salidas sintéticas. No importan ni ejecutan torch/MinerU. No se reejecutan los análisis históricos.

Archivos originales intactos. El manifiesto `code/packages/localized-labels-v1/integrity.json` protege los ZIP de los tres modelos, preparados, render, exportaciones originales pertinentes, código MinerU y resultados A03–A06 usados; la evaluación verifica sus hashes antes de producir un nuevo derivado.


## Reconciliación de página implementada offline (24oct2026)
Prioridad aprobada: MinerU estructura, TATR contraste tablas, LayoutLMv3 apoyo.
Salida vigente analytics/results/sic12_page3/reconciliation-v1/verified-output/;
reconciled-page.json, review.html, selected-overlay.png y manifest.json.
Código code/page_integration/reconciliation.py: receta específica de esta página,
no matching general. 48fuentes preservadas,19segmentos+4contenedores,8relaciones,
35vínculos candidatos pendientes. No convertir A03 en identidades; sin unión/promedio
ni ranking de scores. Texto nativo con procedencia, sin nueva validación OCR.
32tests offline pasan (10nuevos);151archivos protegidos intactos. Informe y auditoría
reconciliation-v1/report.md y verification.json; copias de continuidad en before/.
Table1 sigue advertencia pendiente; Table2 aceptación con revisión visual de agente
intacta y rótulo derivado separado. Bordes tablas, continuidad lista/r12 y p0-b12
direction siguen explícitos. No orden de lectura validado ni ensemble superior.
Implementación y aceptación técnica con pendientes verificadas; no exactitud GT.
No OCR/inferencia/Colab ejecutados. Esta autorización no amplía a12.pdf completo.
