# Parsing coordinado de PDFs SiC: ejecución exclusiva del usuario

## Alternativa Compute Engine preparada (26oct2026)

Adaptación GCE autorizada por el usuario; primer paquete nuevo para 10.pdf,
sin ejecutar infraestructura ni modelos por agente. Guía: [GCE.md](GCE.md).
Entrada separada `gce.sh`; no usar `run_document.sh` dentro de la VM.
Paquete `code/packages/sic-gce-v1/10`, originales de Colab conservados.
Verificación offline no acredita instalación/parsing real en GCE.

## Flujo vigente: paper por paper, ZIP completo

Por decisión del usuario se vuelve a ejecutar cada paper individualmente, en orden:
1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15 y 17.
Cada paquete individual se sube completo en una sola llamada, independientemente
 de su tamaño. Luego se transfieren su SHA y la identidad del intento.
No se fragmenta ni se ejecuta ensamblaje para paquetes individuales.
Tres parsers por paper, configuración original, salidas individuales y sin conciliación.

El lote y sus paquetes se conservan como históricos; no forman parte del flujo
actual. Su rama de transporte fragmentado se conserva solo si se selecciona
explícitamente un paquete de lote. Instrucciones anteriores preservadas en
`docs/history/20261026-paper-direct-upload/before/code/document_trial/README.md`.
Subida directa reduce llamadas; no garantiza resolver interrupciones TLS.

26oct2026: coordinación parametrizada, sin cambios en modelos/pesos/configuración.
Paquetes nuevos para los 15 PDFs actuales: `code/packages/sic-parsing-v1/index.json`.
Cada paquete contiene un solo PDF completo y ejecuta LM, TATR y MinerU como antes.
El parsing de 12.pdf se puede repetir en carpeta nueva; no sobrescribe resultados.

Desde WSL, con una sesión T4 propia, exclusiva, limpia e IDLE:

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
bash code/document_trial/run_document.sh NOMBRE_DE_TU_SESION_T4 --own-session code/packages/sic-parsing-v1/1
```

Después de verificar el respaldo de 1.pdf, continuar por 2.pdf y el resto en orden.
Cada ejecución cierra la sesión propia solo después del respaldo verificado;
crear una sesión limpia para el siguiente paper.
El paquete es ahora un argumento obligatorio para evitar ejecutar otro documento
por defecto. Un paquete individual ejecuta solo su paper. Se conserva cierre
de la sesión propia tras respaldo terminal verificado, incluso si el parsing falla.
No reintentar tras timeout: conservar intento y revisar su estado/respaldo.

Resultados nuevos: `code/results/document-parsing/<SHA256-PDF>/<fecha>-<pid>/`.
El ZIP guarda renders/identidades, salidas nativas de los tres parsers, configuración,
verificación de pesos, entornos, logs y estados por página/parser. Se comprueba
ZIP/SHA/CRC, plan e identidad de intento; no equivale a calidad semántica validada.
Aquí termina el flujo. **No ejecutar automáticamente `document_trial.offline`,
finalize ni reconciliation.export**: la conciliación/evaluación posterior es aparte.

Se conservan 200dpi, T4 y entornos originales. Identidad del PDF desde el plan;
la regresión del render p3 se exige únicamente cuando el hash es el de 12.pdf.
Otros PDFs no reciben su Table2 ni referencias históricas. Los destinos temporales
remotos conservan nombres heredados para no modificar el transporte; son exclusivos
de la sesión limpia, no determinan el documento, que se verifica por hash del plan.

Preparar otro paquete (solo preparación local, sin modelos; destino nuevo):

```bash
PYTHONPATH=code python3 -B -m document_trial.prepare --pdf SiC_papers/3.pdf --output code/packages/OTRO_DESTINO_NUEVO
```

La preparación requiere lector PDF local (`pypdf` o PyMuPDF ya instalado). No
instala librerías ni cambia entornos de inferencia. Los paquetes entregados ya
están preparados: no hace falta reconstruirlos para ejecutar.

## Referencia histórica del ensayo original de 12.pdf

La documentación siguiente conserva el contexto de v5. Su comando de dos argumentos
queda sustituido por el comando vigente de arriba; los paquetes/resultados v5
permanecen inmutables. Su evaluación posterior no forma parte del parsing actual.

Paquete para **13 páginas físicas** del PDF SiC, SHA256
`9cea2fa5ad94c6a31031c72a9c3f698d571c85c810af644304c3b9f0d306f660`.
El agente no ha ejecutado OCR, inferencias ni Colab. La compatibilidad efectiva
en Colab sigue pendiente de tu ejecución; los tests offline no la demuestran.

## Ejecutar una vez desde WSL

Cuando tengas una sesión **propia, exclusiva, limpia, T4 y en estado IDLE**:

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
bash code/document_trial/run_document.sh NOMBRE_DE_TU_SESION_T4 --own-session
```

No crea ni asigna sesiones. Verifica, sube, ejecuta y descarga.
`--own-session` autoriza cerrar esa sesion tras verificar ZIP/SHA256/plan/estado
terminal, hash del paquete e identidad unica del intento, incluso en fallo.
Paquete vigente: `code/packages/sic12-document-v5`; v1 y respaldo fallido intactos.
El respaldo del intento 20261025T012230Z-5535 identifica bloqueo de certifi fijado
por la politica first-index de uv en el indice PyTorch. v3 agrega exclusivamente
`--index-strategy unsafe-best-match` a la instalacion de requisitos LM/TATR;
MinerU ya la utilizaba. Ninguna version o requisito cambia. La existencia y
descarga efectiva desde los indices posteriores quedan pendientes de tu prueba.
Los paquetes v1/v2 y ambos respaldos fallidos se conservan.

Espera local acotada: 600s por llamada auxiliar y 10800s para exec; no estimacion
de coste. Logs directos en el directorio del intento, sin tuberia de consola.
Sin retransmision en vivo: consultar `cli-console.log` durante la espera.
Retornos y timeout: `*.status.json`. Al vencer el plazo termina solo el arbol
local CLI; esto no demuestra que el trabajo remoto haya terminado. Descarga una
vez cada artefacto conocido, sin repetir exec. Solo respaldo terminal del intento
actual permite cerrar. Sin respaldo valido o si stop falla/se bloquea: error,
cierre no confirmado y atencion manual. No hay reintento automatico.

En el ZIP, `commands/NNNN-stdout-stderr.log` conserva ambos flujos combinados en
bytes; `commands/NNNN.json` conserva comando, etapa, tiempos y retorno. El flujo
combinado no identifica por separado stdout y stderr. La celda devuelve control
normalmente al kernel; los fallos quedan en respaldo y se devuelven como error
local despues de descargar/verificar/cerrar.

La ruta editable original LM `/content/nasa-layoutlm/layoutlmv3` debe estar libre.
Si existe, falla sin borrar ese entorno. No reconstruir paquete, actualizar versiones
ni reintentar para resolver un fallo: conservar respaldo y avisar.

## Configuración y ejecución

Tres entornos separados; freezes, fuentes, YAML y revisiones de los originales:

| Rama | Python | Torch / CUDA |
|---|---|---|
| LayoutLMv3 |3.9.25 |1.10.0+cu111 /11.1 |
| TATR |3.11.11 |2.5.1+cu121 /12.1 |
| MinerU |3.11.16 |2.7.1+cu126 /12.6 |

TeslaT4 obligatoria en cada rama. Se validan70/39/135dependencias runtime,
respectivamente. pip/setuptools/wheel omitidos por freeze se distinguen como
bootstrap; LM conserva los pins históricos pip25.1.1/setuptools80.9.0.
Instaladores uv originales:0.12.21 para LM/MinerU y0.6.14 para TATR, separados.
MinerU4.0.12/DocVortex0.6.0, Basic/Torch, OCR,image_analysis=True, tablasCPU;
revisión `2b3afb86f4d23fa623f6b2f4b2279ed4ef93a89d`.
TATR revisión `2357cbe2b5a5d1c03e54f32764f06058933b65ab`, procesador800 y threshold0.5.
LM conserva YAML/vendor/checkpoint original, RGB y800/1333. Todos los pesos se
verifican por revisión, bytes y SHA256.

Los tres probes preceden a cualquier inferencia. Render con adaptador original
en entornoLM,RGB200dpi,CropBox/rotación y dimensiones propias de cada página.
El hashPNG de página3 debe coincidir antes de procesar modelos. Una llamada por
parser/página,39combinaciones. LM/TATR se cargan una vez por rama; MinerU conserva
su ciclo interno original. Sin ROI,padding,
segunda pasada,recuperación,reintento ni OCR alternativo. Nativos antes de derivados;
errores y39estados contabilizados aunque falle instalación/carga/inferencia.

El coordinador nuevo serializa valores NumPy sin imputar scores. Evita el error
`bool_` de exportación histórico TATR; no cambia su estado anterior failed/export/1.

## Respaldo y evaluación posterior local

Destino `code/results/sic12-document-v1/<fecha>-<pid>/`: ZIP,sidecar,verificación y logs.
El ZIP conserva plan, ejecución, runtimes, renders, estados y nativos por página/parser.

Después de avisar que terminó, la inspección local puede preparar los resultados
y las vistas, sin modelos; no necesitas ejecutar este paso ahora:

```bash
PYTHONPATH=code python3 -B -m document_trial.offline \
  --package code/packages/sic12-document-v5 \
  --result code/results/sic12-document-v1/FECHA-PID/result.zip \
  --sidecar code/results/sic12-document-v1/FECHA-PID/result.sha256 \
  --output analytics/results/sic12_document/EVALUACION_NUEVA
```

Destino nuevo obligatorio. Produce índice HTML, M0nativo, M1enriquecimiento,
Rreconciliado, manifiestos/punteros, búsqueda de rótulos y plantillas visuales.
MinerU es la estructura; TATR/LM quedan como evidencia pendiente. **No es un matcher
general validado**: no asocia por cercanía/IoU/score ni inventa mejoras por más cajas.
Las adjudicaciones se registran aparte. Índices nativos preservados; no se considera
el array un orden de lectura verificado.

### Regresión página3

Table1 permanece pendiente;Table2 conserva siempre su aceptación histórica.
Ese enriquecimiento solo pasa a la nueva M1/R si render y todos los segmentos/
contenedores nativos coinciden exactamente con el original. Si difieren, revisión
de regresión pendiente, sin trasplantar etiquetas/cajas ni revocar la aceptación
histórica. Tolerancias:IoU>=0.50,cobertura referencia ampliada2px>=0.90,error<=1px;
no se usan como umbral de duplicados.

### Revisión y recurrencia

Inventariar visualmente toda página: omisiones,duplicados,clases,separación,cortes,
vínculos,lectura/continuidad y transcripción/tabla donde difieran. Referencia del
agente pendiente de revisión humana, no GT independiente. Las búsquedas recorren
JSON/Markdown, incluidos bloques/líneas/spans y variantes Table1/Table 1, espacios,
saltos y mayúsculas. Los hits no prueban reconocimiento correcto ni asociación.
Solo el inventario visual fija el denominador de rótulos visibles y permite informar
«no localizado en los archivos y campos inspeccionados» sin afirmar pérdida definitiva.

Tras completar las plantillas, el agregador offline conserva conteos/denominadores,
incertidumbres y cambios atribuidos a recuperación,reconciliación,adjudicación manual
o representación. No acepta por sí solo la calidad del documento:

```bash
PYTHONPATH=code python3 -B -m document_trial.finalize \
  --reviews analytics/results/sic12_document/EVALUACION_NUEVA \
  --output analytics/results/sic12_document/RESUMEN_NUEVO
```

Rechaza páginas/revisiones ausentes sin explicación. Separar M0→M1 de M1→R.
Un parser fallido no equivale a página vacía ni omisión confirmada. La conclusión
requiere un informe con casos; ningún test, ZIP o conteo de cajas lo sustituye.
No se ejecutan nuevas recuperaciones; cualquier corrección es otro incremento.


## Inventario limpio v4
El inventario instalado se obtiene con el mismo Python en un proceso nuevo,
antes de importar Torch. No se instala ni actualiza ninguna dependencia.
Se conservan `inventory-MODELO-ETAPA-clean.json` e `inventory-MODELO-ETAPA-after-torch.json`,
con todas las entradas, nombres, versiones, rutas de metadata y raiz, sys.path,
PID, ejecutable y prefijo. Los duplicados no se sobrescriben.
La comprobacion estricta del plan usa solo el inventario limpio; la captura tras
Torch es diagnostica. Copias de igual version se conservan en todas sus rutas;
versiones contradictorias en el inventario limpio o procedencia ausente bloquean.
Versiones distintas del plan, paquetes extra/faltantes y GPU/Python/CUDA distintos
siguen bloqueando. Se mantiene la politica historica de herramientas bootstrap.
Los logs del subproceso y ambos inventarios quedan en el respaldo, incluso si
falla una comprobacion posterior. Una captura limpia fallida tambien se archiva.
No se ha probado este paquete en Colab; esa ejecucion corresponde al usuario.


## Separacion por etapa v5
ETAPA es `preflight` o `before-infer`. Ambas comprobaciones se mantienen y cada
una conserva sus capturas e informe `runtime-MODELO-ETAPA.json`, con etapa y
referencias exactas a sus inventarios. La segunda no sobrescribe la primera.
Repetir la misma etapa sigue produciendo error por evidencia existente.
El intento v4 paso los tres probes y genero13renders (pagina3 con hash original),
pero se detuvo antes de cargar modelos al repetir probe con el mismo nombre.
Esta colision es el defecto corregido. La prueba de regresion reproduce las
entradas probe -> infer para las tres ramas con modelos inertes y una pagina
sintetica; comprueba exportacion, conservacion de archivos y bloqueo antes de
cargar modelos si cambia una version en la segunda comprobacion. No valida
carga ni prediccion reales: quedan pendientes de ejecucion exclusiva del usuario.
