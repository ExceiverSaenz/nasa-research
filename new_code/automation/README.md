# Tres modos de ejecución de SiC en Colab

Desde Ubuntu/WSL, con Colab CLI autenticada y R2 configurado en
`~/.config/nasa-research/r2.env` (permisos 600):

```bash
python3 -B new_code/colab_run.py
```

El menú ofrece **1. Parser**, **2. Integrador**, **3. Parser + integrador**.
Después acepta un paper (`12`), un grupo (`1 3 12`) o `all`. En modo integrador
primero muestra las carpetas disponibles en `new_code/results/parse_results/` y
solicita la carpeta que se quiere integrar. La selección pertenece a esa carpeta.

## Selección directa y planificación sin ejecutar

```bash
# Solo parser; mantiene los argumentos anteriores.
python3 -B new_code/colab_run.py --papers 12
python3 -B new_code/colab_run.py --mode parser --papers 1 3 12

# Integrar un paper ya parseado.
python3 -B new_code/colab_run.py --mode integrator --parse-run 20261030T021637Z-a2ba8ca7 --papers 12

# Un grupo o todos los papers de una carpeta.
python3 -B new_code/colab_run.py --mode integrator --parse-run NOMBRE_DEL_INTENTO --papers 1 3 12
python3 -B new_code/colab_run.py --mode integrator --parse-run NOMBRE_DEL_INTENTO --all

# Parsear e integrar exactamente esos papers en la misma sesión.
python3 -B new_code/colab_run.py --mode both --papers 1 3 12
python3 -B new_code/colab_run.py --mode both --all

# Añadir --plan a cualquiera: no crea sesiones, instala ni transfiere.
python3 -B new_code/colab_run.py --mode integrator --parse-run 20261030T021637Z-a2ba8ca7 --papers 12 --plan
```

`--parse-run` admite un nombre o ruta a una carpeta inmediata dentro de
`new_code/results/parse_results/`. `--papers` admite número/nombre PDF o identidad
nativa inequívoca de ese intento. Un paper desconocido o repetido se rechaza.
`--workers` limita los papers concurrentes del integrador (predeterminado: 2).

## Dependencias por modo

| Modo | Lista directa | Preparación |
| --- | --- | --- |
| parser | `parse_system/parsing/unified/requirements.in` | Entorno de los tres motores, Detectron2 y pesos fijados. Sin añadir dependencias propias de integración. |
| integrator | `reconciliation_system/requirements.in` | Docling geométrico/PyMuPDF y su cierre de dependencias. Sin preparar pesos, MinerU ni Detectron2; sin compilación CUDA ni su instalación por APT. |
| both | `requirements.in` | Un entorno conjunto, preparado una sola vez para ambas etapas. |

Cada lista incluye sus dependencias transitivas: compartir alguna librería entre
perfiles no significa que se ejecute el otro sistema. Todos usan Python 3.11.16.
La sesión nueva sigue siendo A100; la integración no necesita inferencia GPU.
Docling incorpora Torch y bibliotecas CUDA de forma indirecta. Su presencia en
el entorno del integrador no significa que se usen modelos neuronales en esa etapa.
Ver los recibos concretos de cada perfil antes de interpretar su tamaño o paquetes.

## Reutilización e integridad

Antes de crear una VM se buscan bundles con candidato expandido, hashes, recibos,
pins y build compatibles en `runtime/colab-bundles/` y
`runtime/environment-bundles/`. Un cambio de nombre/firma no impide reutilizar un
bundle que satisface los controles actuales. Cada perfil exige su candidato exacto;
no se instala el bundle conjunto para satisfacer un perfil mínimo.

Si parser no tiene bundle propio, puede reutilizar únicamente el wheel verificado
de Detectron2 de un bundle conjunto compatible. Se resuelve la lista del parser,
sin recompilar Detectron2 ni instalar herramientas de compilación CUDA. Si tampoco
hay build compatible, se realiza la preparación completa. El nuevo bundle del perfil
se conserva para siguientes sesiones. `--plan` distingue `reuse_bundle`, `reuse_build`
e `install_new`. Los bundles anteriores no se borran ni reescriben.
Los bundles entrantes se extraen en `runtime/bundle-inputs/<raíz>/`; la exportación
nueva usa una ubicación separada. Así un bundle cuyo nombre interno sea
`export-bundle` no ocupa el destino de una exportación posterior.

APT consulta las fuentes oficiales Ubuntu existentes para los prerrequisitos
necesarios; conserva las comprobaciones de firmas/hashes. Solo una compilación
nueva que requiera expresamente CUDA añade su preparación correspondiente.
No se alteran controladores ni se desactivan verificaciones para sortear un
repositorio externo inconsistente.

En la VM se validan host/ABI, candidato, imports, recibo y artefactos antes de reutilizar
un entorno. Los pesos existentes se verifican por manifiesto; los PDFs existentes
por hash. Un entorno incompleto/incompatible queda para revisión; no se parchea ni
se reintenta automáticamente. Cambiar código sin cambiar dependencias compatibles
no fuerza una reconstrucción. La VM nueva todavía necesita instalar los paquetes
que no contiene y descargar los pesos/PDFs que falten; no se copia una `.venv`.

## Resultados seleccionados y R2

Para integrator, el controlador verifica los archivos seleccionados contra el
manifest original y envía solo esos archivos de `results/` y `renders/`, más
`inputs.json`, `configuration.json`, `status.json` y `manifest.json` originales.
Un grupo excluye los archivos de los demás papers. No se modifican ni reexportan
los resultados fuente; los metadatos comunes originales conservan la colección.
La selección y el hash del manifest quedan en `selection.json` del controlador.
Se exige el contrato actual `parsing-hybrid-files/2` y un intento completo.

Los PDFs de los modos parser/integrator se descargan desde R2, nunca se sustituyen
por una subida del original local. Los originales de `papers/SiC_papers/` sirven de
referencia de identidad. En integrator se exige coincidencia con los hashes del
intento seleccionado. Las solicitudes se firman después de preparar entorno/pesos,
y las claves permanentes permanecen en WSL. Las solicitudes temporales se eliminan;
los recibos no contienen URLs firmadas ni claves.

El integrador resuelve los PDFs descargados en la VM mediante un directorio
explícito y verifica sus hashes. Registra rutas originales/resueltas sin modificar
los JSON del parser. Su perfil mínimo valida su propio recibo y conserva el hash
del entorno fuente del parser; no afirma que sean la misma instalación. En both
se conserva el control de recibo compartido de la misma sesión.

## Salidas, cierre y errores

Parser descarga su intento nuevo a `results/parse_results/<id>/`; integrator a
`results/reconciliation_results/<id>/`. Both verifica y descarga primero el parser
y después integra esos mismos papers en la misma VM; conserva ambas carpetas.
Los TAR son transporte, con SHA256; cada carpeta conserva su manifest por archivo.
Las vistas que requieren PNG no se generan si el parser guardó solo identidad y geometría.

Logs, selección, código enviado, recibos y transporte quedan en
`runtime/colab-attempts/<id>/`. La sesión se cierra después de verificar **todas**
las salidas solicitadas. `--keep-session` permite conservarla. Si falla integración,
el respaldo ya verificado del parser permanece disponible.

Un fallo o timeout deja estado `manual_review`, sin reintentos ni cierre de una VM
potencialmente activa. Consultar `colab sessions` y `colab status -s NOMBRE` antes
de crear otro intento. Cada fase remota debe emitir la confirmación explícita
`SIC_PHASE_COMPLETED` del intento/fase: una salida cero de Colab CLI sin esa
confirmación se trata como fallo. Los scripts de continuación de las pruebas
conservan la revisión y el estado anterior; no son reintentos automáticos.

## Evidencia real y pendiente

Se completaron los modos parser, integrator y both con `12.pdf` en A100; las
salidas se descargaron y verificaron y las sesiones se cerraron al finalizar.
Los fallos de preparación y sus continuaciones revisadas se conservaron, sin
repetir inferencias. [IDs, resultados y límites](../README.md#pruebas-y-evidencia)
y [registro verificable](../runtime/three-mode-validation-20261030.json).

El fallo intermitente Windows al mover una carpeta en una prueba simulada sigue
pendiente por decisión del usuario. La causa no está determinada; la misma
prueba pasó en WSL. [Detalle y alcance](../README.md#pendientes). Usar WSL/Colab
no garantiza ausencia de otros fallos de infraestructura o entrega local.
