# Parsing híbrido autónomo

`parse_system/` es la distribución mínima del backend híbrido para n PDFs.
Puede copiarse o renombrarse sin code/, history/, notebooks ni helpers del
proyecto. No contiene lanzadores anteriores ni pruebas de desarrollo.

```text
parse_system/
  run.py
  parsing/
    __init__.py
    unified/                 CLI, instalador, scheduler y adaptaciones
    adapters/
      layoutlmv3/inference/   detector, render, tipos y exportación reutilizados
      table_transformer/     detector reutilizado
      mineru/                exportador reutilizado
  vendor/unilm/layoutlmv3/    subconjunto original necesario para detección
```

Entrada desde cualquier directorio:

```bash
python3 /ruta/a/new_code/parse_system/run.py --help
python3 /ruta/a/new_code/parse_system/run.py environment prepare --help
python3 /ruta/a/new_code/parse_system/run.py template --output /ruta/a/runtime.json
```

[Guía de instalación y ejecución](parsing/unified/README.md).
El lanzador llama directamente a la CLI: `run ... --user-run` ejecuta;
`environment prepare` instala en un destino nuevo. No usa `--backend` ni
`--execute`. Esta carpeta no requiere wrappers de `code/` ni entradas de notebooks.

Se necesita instalar el entorno virtual del perfil de parser y aportar los pesos
verificados de los tres motores y las rutas de los PDFs. El flujo de
[preparación conjunto](../README.md) usa `setup_models.py` para descargar las
revisiones fijadas en `../model_manifests/`, verificar sus hashes y guardar los
pesos en `../runtime/model-cache/`. Ese script genera `hybrid-runtime.json`
con las rutas reales; usar ese archivo para `check` y `run`.
La plantilla `template` contiene rutas de ejemplo que deben completarse si se
configura el runtime manualmente. Este paquete no incluye pesos.
La carga e inferencia reales de los tres motores se completaron en A100 sobre
`12.pdf`: 13 páginas y 39 tareas, cero fallidas, tanto en el caso solo parser
como en el caso combinado. [Evidencia y límites](../README.md#pruebas-y-evidencia).
No acredita exactitud semántica, toda la colección ni capacidad en 6 GB.

Para automatización desde Ubuntu/WSL usar `python3 -B new_code/colab_run.py --mode parser --papers 12` desde la raíz del proyecto. El controlador obtiene los PDFs
de R2 y verifica su identidad; instala la lista del parser y sus dependencias,
sin añadir la lista del integrador. [Tres modos y reutilización](../automation/README.md).
Las credenciales R2 y los originales locales de referencia están fuera de este
paquete mínimo; copiar `parse_system` no los instala ni transfiere.

Los originales del vendor se conservan sin cambios, con README de procedencia;
la adaptación se aplica a una copia de ejecución. Recursos, notebooks y motores
auxiliares anteriores quedaron archivados en el proyecto en
los respaldos históricos preservados; no son dependencia del paquete.
Las pruebas mantenidas están fuera de esta carpeta en tests/parsing_hybrid/.

Las ejecuciones guardan por defecto en la carpeta hermana
`../results/parse_results/run-<fechaUTC>-<uuid>/`. `--output intento-001` permite
nombrar el intento dentro de ese mismo destino, sin sobrescribir uno existente.
No se escriben salidas en `reconciliation_system` ni `reconciliation_results`.
