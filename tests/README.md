# Pruebas de desarrollo

Estas pruebas verifican el código de `new_code/`; no son una dependencia operativa.
No hace falta enviarlas a Colab para ejecutar el parser o reconciliación.

Desde la raíz del proyecto:

```powershell
python -B tests/run.py workflow --list
python -B tests/run.py workflow
python -B tests/run.py compatibility
python -B tests/run.py extended
```

- `workflow`: herramientas de preparación, parsing, contrato compacto y sistema autónomo de reconciliación. Incluye pruebas offline de procesos y fixtures; no ejecuta inferencia ni servicios remotos.
- `compatibility`: lector histórico con ZIP/sidecar, necesario para conservar compatibilidad con los intentos anteriores.
- `extended`: algoritmos científicos, vistas y adaptadores opcionales, incluidos GROBID y comparaciones históricas. Algunas pruebas requieren evidencia y dependencias específicas del proyecto; no se ejecutan por rutina con workflow.
- `all`: unión explícita de las tres suites Python.

Los archivos no se mueven porque algunos comparten fixtures mediante imports.
Las pruebas JavaScript `test_*.js` de `integration/` son comprobaciones de vistas
opcionales y se ejecutan con Node según el visor; el selector Python no las incluye.

Los PDFs locales viven en `papers/SiC_papers/` y
`papers/Tensile_Properties_of_Sub-sized_Specimens_papers/`.
Las rutas y los nombres presentes dentro de fixtures históricos describen sus
contratos de transporte; no son rutas que deban existir en la raíz actual.
Los resultados existentes no se reescriben para actualizar rutas.
