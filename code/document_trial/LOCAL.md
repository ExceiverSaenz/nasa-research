# Parsing local en WSL2

Estado 26oct2026: los tres entornos y todos los pesos están instalados y
verificados. Siete pruebas offline pasan; no se ejecutó parsing. El equipo ya
está preparado: el siguiente comando operativo es `run`, no repetir `prepare`.
Evidencia: [informe de preparación](../../analytics/reports/sic-local-wsl-v1.md).

Preparación autorizada el 26oct2026 tras falta de capacidad de GPU en GCE.
Baseline: paquete inmutable `code/packages/sic-parsing-v1/10` (9 páginas).
Variable: plataforma local WSL2 / RTX 3050 Laptop 6 GB; se conservan Python,
paquetes, pesos, resolución, precisión y opciones de los tres parsers. La GPU
es diferente de T4; esto no demuestra equivalencia numérica ni que la inferencia
quepa en 6 GB. No instalar un driver NVIDIA Linux dentro de WSL.

Entornos y pesos residen en `~/.local/share/nasa-parsing/local-v1-ready`.
`ready.json` solo aparece después de verificar paquetes, CUDA, GPU y pesos.
La preparación no renderiza ni llama a los modelos. La derivación guarda hashes
de los cambios de rutas y guardas; los ZIP históricos permanecen intactos.

Desde WSL, en la raíz del proyecto, preparar una única vez:

```bash
PYTHONPATH=code python3 -B -u -m document_trial.local prepare --repo "$PWD"
```

Solo después de una preparación verificada, el usuario inicia paper 10:

```bash
PYTHONPATH=code python3 -B -u -m document_trial.local run --repo "$PWD" --user-run
```

El paper está fijado por la preparación, no por el comando de ejecución.
Los parsers corren secuencialmente en procesos separados. Un fallo detiene
las siguientes ramas; no cambia configuración ni repite inferencia automáticamente.
El worker histórico puede terminar de contabilizar las páginas de su rama antes
de devolver el fallo. El directorio de salida nuevo lleva UUID bajo
`code/results/local-parsing-v1/`; conserva logs, contabilidad de páginas,
estado terminal, ZIP y SHA256 incluso tras fallos controlados. Interrupciones
forzadas o apagado pueden impedir ese respaldo terminal: conservar el directorio.
No se inicia reconciliación ni se evalúan resultados automáticamente.

No volver a ejecutar `prepare` para reparar un fallo: primero inspeccionar
el log de la etapa; los directorios existentes se rechazan y se conservan.
`run` vuelve a comprobar entradas, inventarios y pesos antes de inferir.
No declarar éxito a partir de un ZIP existente: revisar execution-status.json.
El marcador `pilot-started.json` impide ejecuciones concurrentes y repetir este
piloto sin revisar primero su resultado. No borrarlo automáticamente.

Para instalaciones nuevas, el transporte usa dos descargas simultáneas y timeout
de lectura de 600 segundos; no modifica las dependencias fijadas. Referencia:
[variables de uv](https://docs.astral.sh/uv/configuration/environment/).
Las descargas grandes pueden conservarse en `wheels/*.part`; `local_download.py`
comprueba el rango de reanudación y exige el SHA256 oficial antes de instalar.
`wheels/receipts.json` registra la procedencia. La reparación explícita
`repair-install` se usa únicamente después de diagnosticar una instalación
interrumpida; nunca reanuda ni repite un parsing. Se conservan logs anteriores.

Prueba offline: `PYTHONPATH=code python3 -B -m unittest document_trial.test_local -v`.
