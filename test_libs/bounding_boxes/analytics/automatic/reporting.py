"""Human-readable automatic report; semantic conclusions deliberately pending."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path, write_authored_report
from pathlib import Path


def write_report(output, source, summary, paper_cost, stage_cost, attempt_rates):
    rows = ['# Análisis automático de bounding boxes SiC', '',
            '**Estado: automático completado; revisión visual y valoración semántica pendientes.**', '',
            f"Entrada: `{Path(source).name}`; {summary['papers']} papers, {summary['pages']} páginas, {summary['tool_page_outputs']} salidas de herramienta/página.", '',
            'Se conservaron predicciones y procedencia. Los resultados siguientes describen las salidas; no miden exactitud, recall, omisiones reales ni corrección de relaciones.', '',
            '## Cobertura técnica y registros', '',
            '| Herramienta | Registros | Bbox válida | Sin bbox | Geometría inválida |',
            '| --- | ---: | ---: | ---: | ---: |']
    for tool, counts in summary['tools'].items():
        rows.append(f"| {tool} | {counts['rows']} | {counts['valid']} | {counts['missing']} | {counts['invalid']} |")
    rows += ['', 'Los registros sin bbox pueden ser hijos o spans de contenido cubierto por un grupo. No se cuentan como omisiones y no recibieron cajas de sus padres.', '',
             '## Acuerdos y granularidad', '',
             f"Se registraron {summary['positive_overlap_edges']} solapamientos positivos entre herramientas y {summary['candidate_components']} componentes candidatos de correspondencia por página/par de herramientas.",
             'Se conservaron coincidencias por debajo de IoU 0,5 y relaciones muchos a muchos. Las áreas de unión se calcularon como unión de rectángulos, no como rectángulo envolvente.',
             'Un componente puede encadenar regiones independientes: necesita revisión antes de tratarlo como unidad semántica.', '',
             '## Estructura nativa disponible', '',
             '| Herramienta | Aristas padre–hijo | Padres visuales con caption hijo | Nodos explícitos panel | Ítems de lista | Grupos de lista con ítems |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for t, p in summary['native_pattern_totals'].items():
        rows.append(f"| {t} | {p['parent_edges']} | {p['visual_caption_parents']} | {p['explicit_panel_nodes']} | {p['list_item_nodes']} | {p['list_groups_with_items']} |")
    rows += ['', 'Estos conteos proceden de la proyección de pertenencia nativa en los JSON preservados. No acreditan paneles reales, adecuación del caption ni ausencia universal de capacidades del motor. `image_body` no fue tratado como panel. Relaciones opacas o semánticas no expresadas quedan pendientes.', '',
             'G1 registra el patrón estructural visual→caption cuando se declara directamente; G2/G3 requieren nodos explícitos de panel. G4 requiere inventario del PDF y revisión de identificadores. G5 diferencia ítems y grupo de lista. Ningún patrón fue creado por proximidad.', '',
             '## Geometría y señales para revisar', '',
             f"Hay {summary['geometry_candidate_rows']} señales por atributo fuera de las bandas IQR propuestas. Un mismo registro puede producir varias señales; no es un conteo de errores ni de cajas únicas.",
             'Estratos: herramienta, etiqueta nativa y nivel. Percentiles lineales, MAD sin escalar, bandas 1,5 IQR solo con n≥20 e IQR positivo. Se preservaron grupos pequeños y dispersión cero sin imputar puntuaciones.',
             'No se confirmaron recortes de caracteres, invasiones de columnas/secciones ni mezclas de texto y visualizaciones. Estas comprobaciones siguen pendientes de contraste con el PDF.', '',
             '## Costes registrados', '',
             '| Herramienta | Alcance temporal | Suma de tiempos disponibles (s) | RAM pico muestreado (MiB) | GPU pico de dispositivo (MiB) |',
             '| --- | --- | ---: | ---: | ---: |']
    for stage in stage_cost:
        t = stage['tool']; pc = [p for p in paper_cost if p['tool'] == t]
        values = [p['recorded_s'] for p in pc if p['recorded_s'] is not None]
        total = f'{sum(values):.3f}' if len(values) == len(pc) else 'N/A (incompleto)'
        ram = stage['ram_peak_bytes']; gpu = stage['gpu_peak_mib']
        rows.append(f"| {t} | {pc[0]['recorded_scope']} | {total} | {ram/1048576 if ram is not None else 'N/A'} | {gpu if gpu is not None else 'N/A'} |")
    rows += ['', 'Heron/Heron-101 se reutilizaron del intento previo y miden detector; Basic/Standard provienen del intento corregido y miden parsing SDK excluyendo exportación. Estos totales no forman un ranking de velocidad comparable. Carga y subtareas no expuestas permanecen desconocidas.',
             'RAM/GPU están muestreadas por etapa, no atribuidas por paper ni exclusivamente al modelo. No se estimó duración total de etapa a partir del último muestreo. Una pasada no estima variabilidad entre ejecuciones.',
             'Las distribuciones temporales están en timing_distributions.csv; detector_page_timings.csv conserva las observaciones por página de Heron. No se fabrican observaciones de página de MinerU a partir de promedios.', '',
             '## Fallos por intento de colección', '',
             '| Intento | Herramienta | Intentados | Fallidos | No intentados | DocVortex |',
             '| --- | --- | ---: | ---: | ---: | --- |']
    for rate in attempt_rates:
        rows.append(f"| {rate['source_run_id']} | {rate['tool']} | {rate['attempted']} | {rate['failed']} | {rate['not_attempted']} | {rate.get('docvortex') or 'N/A'} |")
    rows += ['', 'failures.csv conserva causas disponibles, versiones, recibos y denominadores. Los fallos de la colección anterior se mantienen separados del cierre corregido; Heron reutilizado no se cuenta como otra ejecución. El alcance de esta tabla son intentos de colección: smoke, preparación y validación nativa son fases distintas y no se promedian como repeticiones.', '',
             '## Revisión visual pendiente', '',
             '[Abrir los lotes de revisión](review/index.md). Todas las páginas están incluidas, también las que no tienen señales. El inventario de casos del PDF y las evaluaciones están vacíos deliberadamente.',
             'Prioridades: todo el contenido, especialmente títulos/captions/cuerpo; respetar columnas y títulos; aceptar varios párrafos o una figura conjunta cuando mantienen cobertura; valorar relaciones y tagging por capacidad y consistencia.',
             'No hay porcentajes de omisión, matriz de confusión verdadera, consistencia semántica validada ni ganador. Una caja conjunta puede ser base útil aunque requiera separación uniforme posterior.', '',
             '## Artefactos y verificación', '',
             '- [Protocolo y procedencia](analysis_manifest.json).',
             '- [Identidad de entradas](input_manifest.json).',
             '- [Verificación técnica](analysis_verification.json).',
             '- [Resumen automático](automatic_summary.json).',
             '- [Estado de revisión](review_status.json).',
             '- Tablas CSV y JSONL adyacentes contienen conteos, solapamientos, geometría, relaciones nativas y costes con referencias originales.', '',
             'La verificación técnica comprueba hashes y coherencia de salida; no constituye validación científica. No se ejecutó parsing, Colab, OCR, render ni revisión visual.']
    write_authored_report(output,'\n'.join(rows)+'\n')
