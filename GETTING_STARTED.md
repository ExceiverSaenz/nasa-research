# Ejecutar new_code desde un clon

Esta rama incorpora las fuentes actuales de `new_code/`, sus manifiestos de
modelos y dependencias, y las pruebas de desarrollo de `tests/`. Las carpetas
`code/`, `analytics/`, `demo/` y `docs/` heredadas de main son material anterior;
el flujo actual no depende de ellas. Guía operativa: [new_code/README.md](new_code/README.md).

## Preparación local

Usar Ubuntu/WSL y Python 3.11.16. Instalar y autenticar Colab CLI por separado.
El controlador usa una sesión nueva A100; ejecutar un comando sin `--plan`
puede consumir recursos de Colab.

```bash
git clone --branch develop https://github.com/ExceiverSaenz/nasa-research.git
cd nasa-research
mkdir -p papers/SiC_papers
```

Colocar en `papers/SiC_papers/` los PDFs originales de referencia, con los mismos
nombres y bytes que los objetos del bucket R2 (por ejemplo, `12.pdf`). No se
publican los PDFs en GitHub. El controlador calcula su identidad local; Colab
descarga los objetos de R2 y comprueba sus hashes.

Crear `~/.config/nasa-research/r2.env` fuera del repositorio, con permisos 600:

```dotenv
R2_ENDPOINT_URL=https://TU_ACCOUNT_ID.r2.cloudflarestorage.com
R2_BUCKET=papers
R2_PREFIX=sic_papers/
AWS_ACCESS_KEY_ID=TU_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=TU_SECRET_ACCESS_KEY
```

No publicar claves ni solicitudes firmadas. Configurar el endpoint real de la
cuenta y el bucket/prefijo correspondientes.

```bash
# Comprueba selección y preparación prevista; no crea una sesión.
python3 -B new_code/colab_run.py --papers 12 --plan

# Ejecución autorizada por el operador: parser o parser + integración.
python3 -B new_code/colab_run.py --mode parser --papers 12
python3 -B new_code/colab_run.py --mode both --papers 12
```

Para integrar resultados existentes, colocar primero una carpeta completa y
verificada en `new_code/results/parse_results/<intento>/` y usar
`--mode integrator --parse-run <intento> --papers 12`. No editar sus JSON para
adaptar rutas. Ver [automatización](new_code/automation/README.md).

## Qué se obtiene aparte

- Pesos: `setup_models.py` descarga las revisiones declaradas en `model_manifests/`.
- Entornos y paquetes: el controlador prepara el perfil elegido; los bundles
  compatibles son opcionales. Sin ellos se prepara un entorno nuevo.
- PDFs y resultados previos: se suministran fuera de Git; los resultados nuevos
  se guardan en `new_code/results/`.
- Credenciales y autenticación: configuración privada de cada operador.

`runtime/`, `results/`, `inputs/`, cachés, pesos y PDFs están excluidos de Git.
Los enlaces del README operativo a ejecuciones y visualizaciones locales
requieren esos artefactos externos; no forman parte de este clon. Se incluyen
el constructor y las plantillas del visor, sin HTML generado ni imágenes.

## Pruebas offline

```bash
python3 -B tests/run.py workflow --list
python3 -B tests/run.py workflow
```

Las pruebas no acreditan exactitud semántica ni QA visual. Sigue documentado el
fallo Windows diferido al mover una carpeta temporal; el controlador operativo
requiere Ubuntu/WSL. Esta publicación no ejecuta Colab ni repite inferencias.
