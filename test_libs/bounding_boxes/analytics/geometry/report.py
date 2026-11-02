"""Generate publication/export figures and technical narrative from frozen tables."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path, authored_report_path, write_authored_report
import csv
import json
import sys
import itertools
from collections import Counter,defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from analytics.geometry.run import SOURCE,BASE,TOOLS,PAIRS,readlines,csvout,jsonout,sha,mean
from analytics.geometry.metrics import category,area,overlap,box_state

NAMES={'heron':'Heron','heron101':'Heron-101','basic':'MinerU Basic','standard':'MinerU Standard'}
def readcsv(p):
    with p.open(encoding='utf-8') as f:return list(csv.DictReader(f))
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def pct(v):return f'{100*float(v):.3f} %' if v is not None and v!='' else 'N/A'
def num(v):return f'{float(v):.4f}' if v is not None and v!='' else 'N/A'
def pair(a,b):return NAMES[a]+' / '+NAMES[b]

def main(out):
    if authored_report_path(out).exists() or (out/'report.md').exists():raise RuntimeError('Report exists')
    source_tables=[p for p in out.iterdir() if p.suffix in ('.csv','.json','.jsonl')]
    hashes={str(p.resolve()):sha(p) for p in source_tables}
    s=json.loads((out/'summary.json').read_text(encoding='utf-8'));ss=json.loads((out/'supplement_summary.json').read_text(encoding='utf-8'))
    h=readcsv(out/'iou_histograms.csv');rpatterns=readlines(out/'recurring_patterns.jsonl');blockcats=readcsv(out/'block_label_contingency.csv')
    groups=readlines(out/'block_granularity_groups.jsonl');blocks=readlines(out/'block_spatial_clusters.jsonl');pm=readcsv(out/'page_metrics.csv');sens=readcsv(out/'granularity_sensitivity.csv')
    detections=readlines(SOURCE/'detections.jsonl');ids={r['analysis_uid']:r for r in detections}
    # Primary figure: denominators are independent for each pair.
    grid=[]
    for a,b in PAIRS:grid.append([100*float(r['fraction']) for r in h if r['scope']=='all_positive' and r['paper']=='ALL' and r['tool_a']==a and r['tool_b']==b])
    fig,ax=plt.subplots(figsize=(12,5));im=ax.imshow(grid,vmin=0,vmax=100,cmap='Blues',aspect='auto')
    ax.set_xticks(range(10),[f'{i/10:.1f}–{(i+1)/10:.1f}' for i in range(10)]);ax.set_yticks(range(6),[pair(a,b) for a,b in PAIRS]);ax.set_title('IoU de todos los pares con solapamiento positivo (%)\nUna caja puede participar en varios pares; no es precisión')
    for y,row in enumerate(grid):
        for x,v in enumerate(row):ax.text(x,y,f'{v:.1f}',ha='center',va='center',color='white' if v>55 else '#122b42',fontsize=9)
    fig.colorbar(im,ax=ax,label='% dentro de cada par');fig.tight_layout();fig.savefig(out/'iou_histogram_heatmap.png',dpi=170);fig.savefig(out/'iou_histogram_heatmap.svg');plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.8));vals=[r['area_jaccard_micro']*100 for r in s['comparisons']];ax.barh(range(6),vals,color=['#5484a8']*5+['#198579']);ax.set_yticks(range(6),[pair(a,b) for a,b in PAIRS]);ax.set_xlim(0,107);ax.invert_yaxis();ax.set_xlabel('Jaccard entre uniones de cajas (% de acuerdo de área)');ax.set_title('Superficie cubierta: elimina doble conteo y tolera particiones distintas')
    for i,v in enumerate(vals):ax.text(v+.5,i,f'{v:.4f}%',va='center')
    fig.tight_layout();fig.savefig(out/'area_agreement.png',dpi=170);fig.savefig(out/'area_agreement.svg');plt.close(fig)
    # Existing raster only. No PDF rendering/OCR. Choose preregistered granularity type, reproducible first matching page.
    eg=next(g for g in groups if g['tool_a']=='heron' and g['tool_b']=='basic' and g['paper']=='6.pdf' and g['page_idx']==14 and g['geometry_status']=='granularity_candidate')
    bb=[ids[i]['bbox_normalized'] for i in eg['ids_a']+eg['ids_b']];extent=[min(b[0] for b in bb),min(b[1] for b in bb),max(b[2] for b in bb),max(b[3] for b in bb)]
    image_path=BASE/'raw_results/code/mineru-nativefix-20261101T034122Z/viewer_source/pages'/eg['paper_sha256']/f"{eg['page_idx']}.png"
    image_hash=sha(image_path);img=plt.imread(image_path)
    fig,axes=plt.subplots(2,2,figsize=(10,8))
    for ax,t in zip(axes.flat,TOOLS):
        ax.imshow(img,extent=(0,1,1,0));hits=[]
        for r in detections:
            if r['tool']!=t or r['paper_sha256']!=eg['paper_sha256'] or r['page_idx']!=eg['page_idx'] or r.get('native_level')!='block' or box_state(r.get('bbox_normalized'))!='valid':continue
            b=r['bbox_normalized']
            if overlap(extent,b)['fraction_b']<.8:continue
            hits.append(r);ax.add_patch(Rectangle((b[0],b[1]),b[2]-b[0],b[3]-b[1],fill=False,edgecolor='#e14646',linewidth=1.7))
        ax.set_xlim(max(0,extent[0]-.015),min(1,extent[2]+.015));ax.set_ylim(min(1,extent[3]+.015),max(0,extent[1]-.015));ax.set_title(f'{NAMES[t]} · {len(hits)} bloques');ax.axis('off')
    fig.suptitle(f"6.pdf · página15 · región visual: candidato a diferencia de granularidad\nIoU de unión Heron/Basic={eg['union_iou']:.4f}; relación semántica pendiente",fontsize=11);fig.tight_layout();fig.savefig(out/'granularity_example.png',dpi=180);plt.close(fig)
    # Tables used in narrative.
    histogram_table=table(['IoU']+[f'{a}/{b}' for a,b in PAIRS],[[f'[{i/10:.1f},{(i+1)/10:.1f}'+(']' if i==9 else ')')]+[f'{grid[j][i]:.2f} %' for j in range(6)] for i in range(10)])
    pairtable=table(['Par','Pares positivos','Mediana IoU','Recíprocos','Mediana recíproca','IoU de área total'],[[pair(r['tool_a'],r['tool_b']),r['positive_pairs'],num(r['median_iou']),r['reciprocal_pairs'],num(r['reciprocal_median']),pct(c['area_jaccard_micro'])] for r,c in zip(s['pairs'],s['comparisons'])])
    blocktable=table(['Par','1:n','n:1','Granularidad compatible','1:1 con área distinta','n:m','Sin enlace fuerte'],[[pair(r['tool_a'],r['tool_b']),r.get('shape_1:n',0),r.get('shape_n:1',0),r.get('granularity_candidate',0),r.get('boundary_or_extent_difference',0),r.get('complex_many_many',0),r.get('no_strong_correspondence',0)] for r in ss['block_pairs']])
    cattable=table(['Par','Clusters equivalentes','Categorías comparables','Coinciden','Acuerdo condicionado'],[[pair(r['tool_a'],r['tool_b']),r['equivalent_spatial_clusters'],r['category_evaluable_clusters'],r['category_equal_clusters'],pct(r['category_agreement'])] for r in ss['block_pairs']])
    pattable=table(['Etiquetas declaradas','Zona/anchura','Casos','Páginas','Papers'],[['; '.join(f'{k}:{v}' for k,v in r['signature']['labels'].items()),r['signature']['band']+'/'+r['signature']['width'],r['cases'],r['pages'],r['papers']] for r in rpatterns if r['category_disagreement']][:12])
    duptable=table(['Herramienta','Registros con caja','Geometrías únicas','Grupos coincidentes'],[[NAMES[r['tool']],r['records'],r['unique_geometries'],r['coincident_groups']] for r in ss['duplicates']])
    # Semantics of specific labels remain separate from coarse cross-schema categories.
    availability=[]
    for t in TOOLS:
        rr=[r for r in detections if r['tool']==t]
        availability.append([NAMES[t],sum(r['raw_label'] in ('section_header','paragraph_title','doc_title','title') for r in rr),sum(r['raw_label'] in ('caption','image_caption','chart_caption','table_caption') and box_state(r.get('bbox_normalized'))=='valid' for r in rr),sum(r['raw_label']=='chart' for r in rr),sum(r['raw_label']=='ref_text' for r in rr)])
    avtable=table(['Herramienta','Encabezados declarados','Captions con caja propia','chart declarado','ref_text declarado'],availability)
    strict=[g for g in groups if g['geometry_status']=='granularity_candidate'];same=[g for g in strict if g['categories_a']==g['categories_b']]
    exampletable=table(['Paper/página','Par','Cajas A:B','IoU unión','Categorías A/B'],[[f"{g['paper']} / {g['page_idx']+1}",pair(g['tool_a'],g['tool_b']),f"{g['n_a']}:{g['n_b']}",num(g['union_iou']),str(g['categories_a'])+' / '+str(g['categories_b'])] for g in strict if g['tool_a']=='heron' and g['tool_b']=='basic'][:12])
    # Conditional rates show where a frequent reference/list schema pattern dominates.
    bc=[r for r in blockcats if r['tool_a']=='heron' and r['tool_b']=='basic'];topbc=sorted(bc,key=lambda r:-int(r['count']))[:12]
    schema_table=table(['Heron','MinerU Basic','Casos equivalentes','Comparación'],[[r['label_a'],r['label_b'],r['count'],'mapeada' if r['evaluable']=='True' else 'esquema parcial/no mapeado'] for r in topbc])
    worst=sorted([r for r in pm if r['tool_a']=='heron' and r['tool_b']=='basic' and r['area_jaccard']],key=lambda r:float(r['area_jaccard']))[:10]
    worsttable=table(['Paper/página','IoU de área','Solo Heron (% página)','Solo Basic (% página)'],[[f"{r['paper']} / {int(r['page_idx'])+1}",num(r['area_jaccard']),pct(r['a_only_area']),pct(r['b_only_area'])] for r in worst])
    # Aggregate sensitivity with explicit population (all localized levels, not block-only).
    sensitivity=[]
    for a,b in PAIRS:
        vals=[]
        for c,u in itertools.product((.85,.9,.95),repeat=2):
            n=sum(int(float(r.get('granularity_candidate') or 0)) for r in sens if r['tool_a']==a and r['tool_b']==b and float(r['containment'])==c and float(r['union_threshold'])==u);vals.append(n)
        sensitivity.append([pair(a,b),min(vals),max(vals)])
    senstable=table(['Par','Mínimo candidatos','Máximo candidatos'],sensitivity)
    feedback=readlines(out/'human_feedback_context.jsonl');ft=[]
    for r in feedback:
        labs=', '.join(sorted({x['label'] for x in r['intersecting_detections']}))
        ft.append([f"{r['paper']} / {r['page_idx']+1}",r['direction'],NAMES[r['tool']],labs,pct(r['roi_box_area_fraction']),r['note'] or '(sin nota)'])
    feedtable=table(['Página','Selección','Herramienta','Etiquetas que intersectan','Área ROI con cajas','Nota humana'],ft)
    # Macro area and leave-one-paper-out estimates are descriptive, not inferential CIs.
    perpaper=readcsv(out/'comparison_by_paper.csv');macro=[]
    for a,b in PAIRS:
        v=[float(r['area_jaccard_micro']) for r in perpaper if r['tool_a']==a and r['tool_b']==b and r['paper']!='ALL' and r['area_jaccard_micro']]
        macro.append([pair(a,b),pct(mean(v)),pct(min(v)),pct(max(v))])
    macrotable=table(['Par','Media entre papers','Mínimo paper','Máximo paper'],macro)
    report=f'''# Análisis técnico profundo de cajas, categorías y granularidad

Entrega vigente: deep-20261101-v2. 15 papers,397 páginas,1.588 salidas herramienta/página. No se ejecutaron parsers, OCR, Colab, modelos ni renders PDF. Se analizaron35.240 registros nativos y19.597 cajas válidas. El estudio reutiliza predicciones, fondos y métricas existentes; mantiene seis ejemplos humanos seleccionados separados de las predicciones.

## 1. Conclusión útil para este experimento

MinerU Basic y Standard son casi idénticos en geometría: Jaccard de área99,999102%; a nivel de bloque99,999296%. Sus4.168 bloques por herramienta entran en correspondencias espaciales de IoU>=.9 y tienen las mismas etiquetas nativas. No hay evidencia de una mejora general de Standard en las cajas o categorías medidas aquí.

Heron/Heron-101 también se parecen mucho entre sí:97,315% de acuerdo de superficie. Frente a MinerU el acuerdo de superficie es92,644–93,327%, aunque la mediana de IoU entre cajas individuales ronda.859–.862. Esto distingue discrepancias de contorno/partición de grandes diferencias de superficie. No es cobertura verdadera del PDF: una unión puede incluir blanco, mezclar bloques o compartir omisiones.

Existen candidatos concretos de granularidad equivalente. Al comparar solo bloques:7 entre Heron/101;29 entre Heron/Basic;29 entre Heron/Standard;29 entre101/Basic;29 entre101/Standard;0 entre Basic/Standard. Los conjuntos se solapan: no son123 casos independientes. No todos los1:n son aceptables, y ni siquiera un IoU alto demuestra pertenencia semántica o preservación del caption.

Las categorías se analizaron después de agrupar por coordenadas. El resultado permite identificar desacuerdos recurrentes y capacidades declaradas, pero no ordenar precisión semántica global sin referencia. Tu definición de precisión mantiene cobertura y límites por delante de una segmentación idéntica; no se penaliza automáticamente una figura conjunta ni varios párrafos consecutivos.

## 2. Método y fundamento Data Mining

Consulta bibliográfica mediante CLI oficial/Bases/Fileclass/gateway:8efd92ca022a433096fe643338bce152, revisión aceptada. Continuidad e inventario:6ffb384b75694bc9aaea699d8349142c, revisión aceptada. Capítulos originales sin clase documental se conservaron como bibliografía, sin reclasificarlos.

- Cap2, Data: atributos normalizados, ausentes, proximidades y discretización. Las cajas están en coordenadas relativas de página; la ausencia de caja de un hijo no se rellena con la del padre.
- Cap3, Exploring Data: histogramas, cuantiles y OLAP por herramienta/paper/página/categoría/nivel. Se distinguen micro por área, media por página y macro por paper.
- Cap4, Classification: una tabla entre herramientas expresa acuerdo. Una matriz de confusión de precisión necesita clases reales verificadas. No se usa votación de parsers como referencia.
- Cap6, Association Analysis: soporte/confianza/lift describen coocurrencia de salidas, con denominadores y desgloses por paper para evitar conclusiones agregadas engañosas. No son probabilidades de corrección.
- Cap8, Cluster Analysis: agrupamiento aglomerativo complete-link para evitar encadenar regiones por un puente, con evaluación interna separada de externa. Se restringe a una caja por herramienta por cluster; ese límite no elimina duplicados, los deja explícitos.
- Cap9: límites de algoritmos de clustering y de proximidades. No se usa K-means sobre centros: cajas con igual centro pueden tener extensiones muy distintas, y la partición exige incorporar el área.

Las reglas de IoU/contención, bandas y umbrales son adaptaciones del experimento, no valores prescritos por el libro. Método congelado antes de calcular en [PROTOCOL](../../deep_analysis/PROTOCOL.md). La revisión independiente detectó y se corrigieron: tres páginas vacías omitidas, prioridad de fusiones complete-link, hash de geometría compartida y momento del snapshot humano. V1 se conserva como diagnóstico; no es entrega vigente.

## 3. Seis comparaciones: histogramas y correspondencias

{pairtable}

Todos los pares positivos incluyen cruces pequeños entre vecinos y padre/cuerpo coincidentes. No son emparejamientos uno a uno; una caja puede intervenir varias veces. Los recíprocos eligen el mayor IoU en ambas direcciones y excluyen empates. Es una población seleccionada, tampoco referencia verdadera. Cajas sin correspondencia no se transforman en pares de IoU0.

{histogram_table}

Intervalos cerrados por la izquierda y abiertos por la derecha; el último incluye1. Denominadores por columna:5.824,5.934,5.933,5.890,5.888,6.309. Los35.778 pares se conservan íntegros. Basic/Standard:5.827 pares con IoU exactamente1,5.839 en[.9,1];470 pares por debajo de.2. No son470 errores: contienen cruces secundarios de registros distintos.

![Distribución IoU](iou_histogram_heatmap.png)

## 4. Superficie cubierta sin depender del número de cajas

Un barrido por todos los límitesx/y produce celdas geométricas disjuntas. Cada celda conserva qué herramientas y conjuntos de categorías la cubren; las áreas no se cuentan dos veces. El IoU de área es intersección de uniones / unión de uniones. No se usa un rectángulo envolvente ni se infiere contenido blanco.

![Acuerdo de superficie](area_agreement.png)

La comparación relativa no identifica quién tiene razón: área exclusiva de una herramienta puede ser contenido recuperado, padding o mezcla. Hay3 páginas sin cajas de ninguna herramienta; tienen Jaccard N/A, no1 ni0. Están incluidas en397 páginas y en el soporte de asociaciones. La media de Jaccard por páginas excluye esas tres N/A y lo dice en su denominador implícito; no las convierte en aprobación.

{macrotable}

Páginas con menor Jaccard Heron/Basic para inspección dirigida:

{worsttable}

No es muestra aleatoria ni ranking de errores. Las cifras de «solo» están divididas por área total de página. `comparison_by_paper.csv` y `page_metrics.csv` conservan todos los casos.

## 5. Duplicación geométrica, niveles y granularidad

{duptable}

Los437 grupos de MinerU se descomponen en213 chart/chart_body,162 image/image_body y62 table/table_body. Son representación padre/cuerpo coincidente; no437 figuras duplicadas erróneamente. Heron tiene83 grupos coincidentes;35 son section_header/text,16 footnote/list_item y12 page_footer/picture. Heron-101 tiene60, incluidos19 section_header/text. Etiquetas distintas sobre la misma caja deben conservarse como alternativas/ambigüedad de salida, sin elegir una silenciosamente.

MinerU tiene4.168 cajas de nivel block en cada versión; Basic agrega798 cajas child y Standard797. Heron tiene4.889 block y Heron-1014.777. Los conteos globales de área por caja mezclaban niveles y categorías. La mediana global de caja de MinerU es2,40% de página frente a1,28–1,31% de Heron, pero eso no permite concluir por sí solo quién agrupa más el mismo contenido.

Se construyen componentes bipartitos con IoU>=.5 o contención>=.9. Un grupo1:n/n:1 es candidato de granularidad cuando IoU de uniones>=.9, cada pequeña tiene menos de.98 del área de la grande y las pequeñas tienen redundancia<=1%. Con ello se rechazan huecos amplios, duplicaciones completas y componentesn:m. Las pequeñas pueden ser paneles o partes de otro tipo: no se les asigna ese significado automáticamente.

### Comparación a nivel block

{blocktable}

«Sin enlace fuerte» significa ausencia de correspondencia bajo esta regla, no omisión confirmada. «1:1 con área distinta» no distingue padding, recorte y contenido diferente: son límites por revisar. Losn:m se preservan; no se aplanan para forzar una respuesta.

En Heron/Basic,26 de29 candidatos son una caja Heron frente a varias Basic;3 al revés. En los26 hay24 visual/visual y2 visual/header; no se llaman todos equivalentes semánticos. De los3 inversos, uno incluye caption/table frente a table y otro índice/cabecera frente a índice. Una equivalencia de superficie puede coexistir con diferencia de categoría o de relación. Para los casos visual/visual, la granularidad es una explicación geométrica plausible y útil según tus prioridades.

{exampletable}

![Ejemplo localizado de granularidad](granularity_example.png)

Ejemplo reproducible:6.pdf,página15. Heron tiene una caja visual frente a4 bloques visuales de Basic; la unión tiene IoU cercano a.96. Se han reutilizado los fondos PNG existentes, sin volver a renderizar el PDF. Falta confirmar que las partes pertenecen al mismo conjunto y que el caption compartido queda asociado.

### Sensibilidad: no convertir umbrales en verdad

Se probaron las9 combinaciones de contención .85/.9/.95 y unión .85/.9/.95 sobre todos los niveles localizados:

{senstable}

Esta población incluye padres/cuerpos. Por eso no debe compararse como si fuera la tabla block: en Heron/Basic el valor base es3 con todos los niveles y29 con block. La diferencia muestra el efecto de la representación jerárquica. `granularity_sensitivity.csv` contiene todos los numeradores por página y umbral; no se eligió el umbral que maximiza el acuerdo. No se declara estable un caso solo por existir en una combinación.

## 6. Categorías después del agrupamiento espacial

El clustering considera solo coordenadas mediante IoU y complete-link; cada par interno debe alcanzar.9 y no puede haber dos cajas de una misma herramienta en el mismo cluster. Después se leen las etiquetas. Se repite a.8/.9/.95 en `cluster_sensitivity.csv`. No se mezclan páginas para afirmar que contienen el mismo objeto: los patrones entre páginas son firmas repetidas, no identidad de contenido.

En todos los niveles hay8.175 clusters,7.219 con varias herramientas y820 con más de una categoría descriptiva. Esos820 no son errores; incluyen esquemas y niveles diferentes. A nivelblock hay6.453 clusters multiherramienta. Para valoración conservadora se usa el mapa parcial ya definido en el plan, con `unmapped` fuera del denominador evaluable.

{cattable}

Estos porcentajes son acuerdo condicionado a cajas equivalentes, al nivelblock y a categorías mapeadas. No miden todas las detecciones, ni recall de títulos, ni precisión. La primera capa descriptiva de categorías de todos los niveles no debe usarse como ganador: incluye child bodies sin equivalencia de esquema. La tabla block es la comparación controlada.

MinerU Basic y Standard coinciden en todas las4.168 etiquetas nativas de sus clusters equivalentes de bloque, aunque solo2.742 entran en el mapa analítico conservador. Las otras1.426 no se descartan del resultado: se conservan como esquema no mapeado. No son1.426 errores.

### Qué desacuerdos dominan

{schema_table}

Los536 list_item/ref_text de Heron/Basic describen dos maneras de etiquetar regiones casi idénticas. Referencia bibliográfica e ítem de lista pueden ser propiedades compatibles, por lo que esa diferencia no demuestra que una herramienta falle. picture/chart e image expresan resolución de esquema distinta: chart es más específico, pero no necesariamente correcto. formula/equation es traducción de vocabulario, no fallo.

{avtable}

Estos conteos son disponibilidad declarada, no frecuencia verdadera en el PDF. En particular, caption propio de MinerU puede ser child localizado; no atribuir a caption los hijos sin caja ni tratar a todos los spans como elementos omitidos.

### Desacuerdos que sí merecen tu atención prioritaria

-28 clusters equivalentes de bloque muestran título frente a texto, en22 páginas de8 papers. Son candidatos de alto interés por tu coste asimétrico; todavía no sabemos qué lado representa el título real.
-3 muestran caption frente a texto, en3 páginas/3 papers.
-1 muestra visual frente a texto.
-31 aristas cruzadas en20 cajas de texto contienen casi completamente un título/visual/tabla de otra herramienta y son más de1,5 veces mayores. Son candidatos de absorción/mezcla; no31 mezclas confirmadas. Las etiquetas de otra herramienta no son referencia independiente.

Se conservan ejemplos completos en heading_vs_text_examples.jsonl, caption_vs_text_examples.jsonl, visual_vs_text_examples.jsonl y structural_boundary_candidates.csv. El clustering por coordenadas detecta discrepancias; para decidir precisión se necesita evidencia de función, separando errores título→texto de cuerpo→título. No se inventa un clasificador de títulos por tamaño.

## 7. Patrones entre páginas y papers

Se detectaron236 firmas recurrentes (al menos2 páginas). Cada firma incluye etiquetas por herramienta, franja vertical y anchura; conserva casos/páginas/papers, concentración en paper dominante y ejemplos con IDs. Las franjas .2/.8 y anchuras .35/.7 son descriptores exploratorios, no fronteras de columnas o secciones.

{pattable}

El patrón de referencia/lista de anchura media y zona central aparece254 veces en25 páginas/11 papers. No depende exclusivamente de un paper. El patrónpicture/header de una región estrecha superior aparece en7 páginas/7 papers; es especialmente pertinente para tu ejemplo del logo. No se valida automáticamente que los siete sean logos ni se corrigen sus etiquetas.

`pattern_macro_and_loo.csv` calcula soporte por paper incluyendo ceros, media macro y rango descriptivo al excluir cada paper. Esto verifica cuánto depende el conteo de la colección observada; no es un test externo ni un intervalo de confianza de generalización. Las firmas exactas incluyen las herramientas presentes; si falta una caja, puede cambiar la firma, por lo que los patrones no son disjuntos por función real.

Las reglas por página están en page_association_rules.csv: antecedente=presencia declarada de una categoría; consecuente=desacuerdo, granularidad o diferencia de área>0,5% de página. Se publican soporte/confianza/lift y desglose por paper. Umbrales mínimos de10 páginas de antecedente y5 conjuntas solo reducen rarezas accidentales. Son exploración, sin corrección por comparaciones múltiples ni confirmación independiente: no seleccionar reglas por lift y presentarlas como leyes documentales. Confianza elevada puede reflejar una categoría muy frecuente o un esquema; macro y micro no son intercambiables.

## 8. Tus ejemplos humanos: evidencia concreta y límites

{feedtable}

Las dos preferencias de cobertura en1.pdf,página1 concuerdan con una diferencia de superficie en esas regiones: Heron cubre aproximadamente12,7% y20,2% de tus ROI; Basic92,5% y79,5% de sus ROI preferidas. Las ROI de ambos lados tienen límites diferentes, incluyen blanco y no son cajas verdaderas. Esos porcentajes contextualizan la preferencia, no cuantifican recall del texto. La nota humana sí expresa contenido que te falta; se conserva como evidencia local seleccionada.

El ejemplo del logo ligaheader de Basic conpicture de Heron y coincide con una firma recurrente en7 papers. El número liga text de Heron conpage_number de Basic: preferencia de categoría local, sin extrapolarla a todos los números.

Hay una discrepancia que no conviene ocultar: en el ejemplo «es un autor, no un section», seleccionaste Basic como no preferido, pero su región intersecta text; la alternativa Heron intersecta text y section_header coincidentes. La nota y dirección de preferencia no determinan inequívocamente qué salida querías penalizar. Se conserva pendiente, sin invertir tu registro ni usarlo como etiqueta de entrenamiento.

En12.pdf,página4 se prefiere una segmentación Basic frente a Heron. El ROI incluye tabla ycaption; la superficie de caja de Heron incluso puede ser mayor sin que sea tu opción preferida. Esto confirma que cantidad de área no sustituye la adecuación estructural. Seis ejemplos dirigidos, cinco en una página, no permiten entrenar ni evaluar generalización de un modelo de gustos; tampoco son seis cajas exactas de referencia.

## 9. Matriz de valoración conforme a P01–P12

| Dimensión | Evidencia automática disponible | Qué falta para decidir según tus prioridades |
| --- | --- | --- |
| Cobertura, especialmente título/caption/cuerpo | Acuerdo de uniones, áreas exclusivas, ROI humanas seleccionadas | Inventario independiente del contenido; las omisiones comunes a todos son invisibles aquí |
| Párrafos, columnas, secciones |1:n/n:1, límites distintos y candidatos de absorción | Confirmar si cruza columnas/títulos o solo reúne párrafos válidos |
| Figura conjunta/paneles | Candidatos de granularidad y relaciones nativas conservadas | Validar pertenencia y caption compartido; una caja grande puede seguir siendo útil |
| Consistencia de relaciones | MinerU informa251 padres visuales con caption hijo en cada versión; Heron no informa aristas en esta proyección | Corrección y aplicabilidad de esos vínculos; sin inventar paneles por geometría |
| Listas | Ítems declarados Heron y referencias/texto MinerU; patrones recurrentes | Comprobar listas reales y agrupación; list_item aislado no es estructura completa |
| Etiquetas | Grupos equivalentes, vocabulario, coincidencia condicionada y ejemplos humanos | Función real de la región; prioridad título→texto separada de cuerpo→título |
| Recorte | Contornos diferentes y áreas exclusivas | Evidencia de letras/palabras visibles cortadas; no se ejecutó OCR ni se afirma recorte automático |
| Coste/fallos | Recibos preservados y memoria/tiempo por alcance | Medición temporal comparable y repeticiones; no sumar tiempos de detector con parsing SDK |

No hay puntuación agregada ni ganador semántico. La consistencia se describe por capacidad y contexto; una salida sistemáticamente incorrecta también puede ser consistente. Los captions localizados y relaciones no garantizan que el vínculo compartido sea correcto, y los nodosimage_body no se interpretan como paneles.

## 10. Coste y decisión técnica que permiten estos datos

Basic/Standard ofrecen resultados de bloques prácticamente iguales en esta colección. Los recibos previos registran para Basic301,352s de SDK parse excluyendo exportación, RAM pico5.853MiB y GPU2.862MiB; Standard321,891s, RAM9.707MiB y GPU12.473MiB. Son una pasada y muestras de etapa, no repetición estadística ni memoria atribuible exclusivamente al modelo. Dentro de ese alcance, no se observa una ganancia de geometría/categorías que explique el mayor coste de Standard. Esto apoya usar Basic como candidato operativo para esta colección, conservando Standard como comparación y sin afirmar equivalencia universal.

Heron12,598s y Heron-10116,685s corresponden solo a suma de inferencia de detector; no compararlos directamente con parsing MinerU. Los intentos corregidos completaron15 papers por herramienta sin fallos; los11 fallos previos de cada MinerU con otra versión quedan históricos separados. No se reejecutó nada para esta entrega.

La decisión útil es aprovechar la cobertura/estructura que resulte consistente y reconstruir uniformemente las capacidades que no lo sean. Este análisis todavía no implementa esa reconstrucción ni acredita un ensemble. Tu aceptación de granularidad variable permite reducir revisión: concentrarse en regiones exclusivas, títulos/captions discrepantes, grupos complejos y casos de relación compartida; no revisar cada pequeña diferencia de caja.

## 11. Artefactos, reproducibilidad y parada

- Histogramas y correspondencias: iou_histograms.csv, pair_summary.csv, matched_boxes.csv.
- Cobertura relativa: atomic_area_signatures.jsonl, page_metrics.csv, comparison_by_paper.csv.
- Granularidad: granularity_groups.jsonl (todos los niveles), block_granularity_groups.jsonl, strict_granularity_examples.jsonl, granularity_sensitivity.csv.
- Categorías: spatial_clusters.jsonl, block_spatial_clusters.jsonl, label_contingency.csv, block_label_contingency.csv, unlocalized_categories.csv, coincident_boxes.jsonl.
- Patrones: recurring_patterns.jsonl, pattern_macro_and_loo.csv, page_association_rules.csv; estos JSONL contienen IDs y páginas base0.
- Feedback: human_feedback_snapshot.json, human_feedback_context.jsonl. Los originales humanos no se modificaron.
- Revisión posterior: review_examples.jsonl más los archivos de desacuerdos prioritarios; no requiere revisar todos los bloques uno por uno.
- Verificación: verification.json, supplement_verification.json, report_verification.json y final_checks.json. Se comprobaron2.452 archivos originales antes/después, identidad de entradas usadas y particiones. La revisión independiente no equivale a revisión semántica de los397 PDFs.

Condición de parada de esta entrega: las seis comparaciones y estratos están calculados, los patrones tienen denominadores y ejemplos, los originales se preservan y no se presenta precisión semántica sin referencia. Quedan expresamente no determinadas la cobertura verdadera, la precisión de categorías global y cuáles diferencias son exclusivamente granularidad en el sentido semántico. Sí quedan identificados candidatos geométricos concretos y el trabajo necesario para confirmarlos.
'''
    # Repair markdown list spacing in generated prose.
    report=report.replace('\n-28','\n- 28').replace('\n-3 muestran','\n- 3 muestran').replace('\n-1 muestra','\n- 1 muestra').replace('\n-31 aristas','\n- 31 aristas')
    report_target=write_authored_report(out,report)
    # Pin dependency run.py through its main-run manifest; independent review noted omitted direct supplement hash.
    mainv=json.loads((out/'verification.json').read_text(encoding='utf-8'));runpath=str(Path(__file__).with_name('run.py').resolve())
    assert sha(runpath)==mainv['consumed_input_hashes'][runpath]
    assert all(sha(p)==h for p,h in hashes.items());assert sha(image_path)==image_hash
    jsonout(out/'report_verification.json',dict(input_tables_hashes=hashes,code_hash=sha(__file__),dependency_run_hash_verified=sha(runpath),existing_raster=str(image_path),existing_raster_hash=image_hash,unchanged=True,figure_tool='matplotlib '+matplotlib.__version__,pdf_rendered=False))
    print('Technical report and3 figure families generated:',report_target)

if __name__=='__main__':main(Path(sys.argv[1]))
