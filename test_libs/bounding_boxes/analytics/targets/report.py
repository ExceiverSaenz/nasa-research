"""Narrative and plots for the fixed targets audit; not generic automatic truth."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path, authored_report_path, write_authored_report
import sys,json,csv
from pathlib import Path
from collections import Counter
from analytics.geometry.run import BASE,TOOLS,PAIRS,readlines,sha,jsonout
from analytics.targets.targets import family
OUT=BASE/'raw_results/analytics/targets-20261101-v1'
N={'heron':'Heron','heron101':'Heron-101','basic':'MinerU Basic','standard':'MinerU Standard'}
def csvread(name):
    with (OUT/name).open(encoding='utf-8') as f:return list(csv.DictReader(f))
def table(h,rows):return '\n'.join(['| '+' | '.join(h)+' |','| '+' | '.join('---' for _ in h)+' |']+['| '+' | '.join(str(x) for x in row)+' |' for row in rows])
def get(r,k):return int(r.get(k) or 0)

def main():
    if authored_report_path(OUT).exists() or (OUT/'report.md').exists():raise RuntimeError('Report exists')
    files=[p for p in OUT.iterdir() if p.suffix in ('.json','.jsonl','.csv')];hashes={str(p.resolve()):sha(p) for p in files}
    summary=csvread('agent_tool_summary.csv');target=csvread('agent_target_summary.csv');heads=csvread('heading_asymmetric_costs.csv');profiles=csvread('target_profiles.csv');patterns=csvread('target_patterns.csv');scores=readlines(OUT/'native_score_alternatives.jsonl');a=readlines(OUT/'agent_assessments.jsonl');refs=readlines(OUT/'agent_reference_cases.jsonl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig,ax=plt.subplots(figsize=(11,5));left=[0]*4
    statuses=[('adequate','Etiqueta adecuada','#1b8a72'),('coarse_usable','General utilizable','#71b8a5'),('contradictory','Targets simultáneos','#dfa12d'),('wrong','Etiqueta incorrecta','#d86262'),('no_own_correspondence','Sin caja comparable','#9baaba')]
    for key,name,color in statuses:
        vals=[get(r,key) for r in summary];ax.barh(range(4),vals,left=left,label=name,color=color);left=[x+y for x,y in zip(left,vals)]
    ax.set_yticks(range(4),[N[t] for t in TOOLS]);ax.invert_yaxis();ax.set_xlim(0,59);ax.set_xlabel('Número de casos de la muestra dirigida (59 objetos únicos)');ax.set_title('Targets revisados visualmente por el agente\nMuestra dirigida y desbalanceada: no es precisión global');ax.legend(loc='upper center',bbox_to_anchor=(.5,-.15),ncol=3);fig.tight_layout();fig.savefig(OUT/'target_audit_summary.png',dpi=170);fig.savefig(OUT/'target_audit_summary.svg');plt.close(fig)
    chosen=['T005','T021','T023','T026','T056','T003'];fig,axes=plt.subplots(3,2,figsize=(15,11));images={}
    for ax,cid in zip(axes.flat,chosen):
        c=next(r for r in refs if r['case_id']==cid);p=BASE/'raw_results/code/mineru-nativefix-20261101T034122Z/viewer_source/pages'/c['paper_sha256']/f"{c['page_idx']}.png";images[str(p)]=sha(p);img=plt.imread(p);b=c['roi'];ax.imshow(img,extent=(0,1,1,0));ax.add_patch(Rectangle((b[0],b[1]),b[2]-b[0],b[3]-b[1],fill=False,edgecolor='#1285a6',linewidth=1.2));ax.set_xlim(max(0,b[0]-.02),min(1,b[2]+.02));ax.set_ylim(min(1,b[3]+.02),max(0,b[1]-.02));ax.set_title(f"{cid} · {c['paper']} p{c['page_idx']+1} · observado: {c['reference']}",fontsize=10);ax.axis('off')
        labels=[' / '.join(r['labels']) or 'sin caja comparable' for t in TOOLS for r in a if r['case_id']==cid and r['tool']==t]
        ax.text(.02,-.12,'\n'.join(f'{N[t]}: {v}' for t,v in zip(TOOLS,labels)),transform=ax.transAxes,fontsize=8,va='top')
    fig.suptitle('Errores y diferencias de especificidad: evidencia localizada, sin corregir originales',fontsize=13);fig.subplots_adjust(hspace=.75,wspace=.12,top=.94,bottom=.09);fig.savefig(OUT/'target_examples.png',dpi=160);plt.close(fig)
    census=table(['Target localizado','Heron','Heron-101','Basic','Standard'],[[k]+[next(get(r,'localized') for r in profiles if r['tool']==t and r['target']==k) for t in TOOLS] for k in ('heading','text','caption','visual','table','equation','list','reference') if all(any(r['tool']==t and r['target']==k for r in profiles) for t in TOOLS)])
    ct=table(['Herramienta','Casos','Adecuada','General útil','Multitarget','Errónea','Sin correspondencia propia'],[[N[r['tool']],r['sampled_cases'],get(r,'adequate'),get(r,'coarse_usable'),get(r,'contradictory'),get(r,'wrong'),get(r,'no_own_correspondence')] for r in summary])
    ht=table(['Herramienta','Títulos observados','Solo título adecuado','Título + otra clase','Solo texto','No-títulos con señal de título'],[[N[r['tool']],r['observed_headings'],r['heading_adequate'],r['heading_conflicting'],r['heading_to_text'],r['nonheading_with_heading_label']] for r in heads])
    pertarget=[]
    for k in ('heading','text','caption','visual','author','reference','list','table','equation','number','metadata','note'):
        rr=[r for r in target if r['target']==k]
        pertarget.append([k,rr[0]['cases']]+[f"{get(r,'adequate')} / {get(r,'coarse_usable')} / {get(r,'contradictory')} / {get(r,'wrong')} / {get(r,'no_own_correspondence')}" for r in rr])
    tt=table(['Referencia','N','Heron','Heron-101','Basic','Standard'],pertarget)
    baseline=[]
    for t in TOOLS:
        v=[r for r in a if r['tool']==t and 4<=int(r['case_id'][1:])<=14];c=Counter(r['status'] for r in v);baseline.append([N[t],c['adequate'],c['contradictory'],c['wrong']])
    bt=table(['Herramienta','Título único','Título + texto','Solo texto'],baseline)
    sch=[]
    for t in ('heron','heron101'):
        v=[r for r in scores if r['tool']==t and r['reference']=='heading'];count=sum(any(family(l)=='heading' for l in r['max_score_labels']) for r in v);sch.append([N[t],len(v),count,len(v)-count])
    st=table(['Herramienta','Títulos revisados con score','Máximo score conserva título','Máximo score elige texto'],sch)
    patt=table(['Par','Etiquetas A/B','Casos','Páginas','Papers'],[[N[r['tool_a']]+'/'+N[r['tool_b']],r['label_a']+' / '+r['label_b'],r['cases'],r['pages'],r['papers']] for r in patterns if r['label_a']!=r['label_b'] and (r['tool_a'],r['tool_b']) in [('heron','basic'),('heron','heron101')]][:16])
    detail=[]
    for c in refs:
        if not c['eligible']:continue
        vals=[]
        for t in TOOLS:
            r=next(r for r in a if r['case_id']==c['case_id'] and r['tool']==t);vals.append(','.join(r['labels'])+' → '+r['status'])
        detail.append([c['case_id'],f"{c['paper']} p{c['page_idx']+1}",c['reference']]+vals)
    detailtable=table(['Caso','Localización','Observado','Heron','Heron-101','Basic','Standard'],detail)
    text=f'''# Targets de bloques: precisión, especificidad e inconsistencias

## Resultado principal

No hay un ganador único por etiquetas. En esta colección, Basic y Standard producen prácticamente las mismas etiquetas de bloque; Standard no muestra una mejora de targets que justifique preferirlo por esa dimensión. MinerU ofrece salida menos ambigua y reconoce referencias y números explícitamente, pero pierde señales de título y usa header para imágenes editoriales. Heron conserva más señales de título e imagen en la muestra revisada, pero entrega alternativas text/section_header sobre una misma región; esa ambigüedad impide tratarlas como decisiones limpias. Heron-101 no muestra mejora consistente sobre Heron en los casos observados.

Se aplicó el método ya acordado: bloques espacialmente correspondientes, tabla de acuerdos conservando etiquetas nativas, referencia visual explícita para casos revisados y prioridad ordinal mayor para título→texto que texto→título. Los bloques ayudan a comparar el mismo contenido; no son por sí mismos la clase verdadera.

## 1. Alcance y evidencia

- Censo completo de35.240 registros de15 papers/397 páginas y todos los targets nativos, separados por nivel y presencia de bbox.
- Correspondencias a nivelblock del análisis profundo previo, IoU interno>=.9 y una caja por herramienta en cluster; relaciones de granularidad y captions child se mantienen aparte.
-65 ROI inspeccionadas visualmente sobre PNG ya existentes, con etiquetas ocultas en las láminas de referencia. Se excluyeron4 repeticiones del mismo objeto (T031/T016,T062/T056,T063/T021,T064/T022) y2 casos adicionales sin clase única inequívoca (T024,T065): quedan59 objetos únicos elegibles,236 evaluaciones herramienta/caso.
- La muestra es dirigida a discrepancias más controles, no aleatoria:19 títulos,10 visuales,6 autores/afiliaciones,5 captions,4 textos,4 referencias,3 tablas,3 ecuaciones,2 notas,1 lista,1 número y1 fecha. Doce de los19 títulos proceden de8.pdf. Los casos son únicos por objeto, no estadísticamente independientes.
- La clase observada la asignó el agente por el fondo visual, no por mayoría de herramientas ni texto extraído de un parser. La selección sí depende de las predicciones y el agente conoce las hipótesis del proyecto: no es un ensayo ciego completo. No se llama validación humana.

Fuente metodológica: Data Mining cap4 (matriz de confusión con referencia) y cap5§5.7 (clases desbalanceadas, precision/recall y coste asimétrico). Consulta/revisión CLI/Bases/Fileclass: faae4823e31543b5aa5d75bb594b34f4, estado reviewed. El libro fundamenta el método; no establece los umbrales geométricos ni los pesos del usuario. No se inventaron pesos numéricos, scores ni clases de referencia por heurística de tamaño.

## 2. Vocabulario y estados: qué cuenta como error

| Estado | Interpretación |
| --- | --- |
| adequate | La etiqueta corresponde a la familia visualmente observada; el subtipo se comprueba por separado |
| coarse_usable | General pero utilizable: text para autor, list_item para referencia, header para logo editorial; no identifica necesariamente el target específico que te interesa |
| contradictory | Varias familias sobre el mismo objeto que no se resuelven como una función única; no se elige silenciosamente la favorable ni se declara que todas sean falsas |
| wrong | Correspondencia propia con etiqueta incompatible y referencia visual inequívoca |
| no_own_correspondence | No hay una caja que alcance los criterios de correspondencia propia; se separa de error de tagging y no se convierte en omisión semántica global |
| excluded_reference | Recorte ambiguo, conjunto de varias clases o repetición del mismo objeto |

Las afiliaciones pueden ser a la vez elementos de una lista y notas; footnote/list_item no se penaliza como contradicción en ese subtipo. Referencia bibliográfica e ítem de lista también son propiedades compatibles. picture/image/chart se comparan primero como familia visual, pero el vocabulario original y su especificidad se conservan. section_header/paragraph_title pertenecen a encabezados; document_title frente a section_heading se registra aparte.

La correspondencia propia usa IoU>=.5, o contención de la caja enROI>=.9 con cobertura deROI>=.5. Un grupo grande que cubreROI>=.9 pero no es comparable se distingue como group_coverage; no se copia su bbox a un hijo ni se imputa una etiqueta específica a cada parte. Las intersecciones y alternativas están preservadas por caso para revisar sensibilidad de límites.

## 3. Censo de targets y sesgo de los conteos

{census}

Estos son registros localizados declarados, no el número real de elementos del PDF. Heron tiene563 registros de encabezado pero557 geometrías únicas; Heron-101543 y541; cada MinerU505. Los targetsheading aparecen en262,255 y259 páginas respectivamente. No se infiere que Heron recupere58 títulos adicionales correctos: puede contener falsos encabezados y duplicaciones.

Los registros text de MinerU incluyen muchos hijos sin bbox: Basic8.496 textos,1.730 localizados y6.766 sin caja; Standard8.440,1.730 y6.710. Mezclarlos con los bloques de Heron distorsiona distribuciones y exactitud micro. Los hijos sin caja no se cuentan como contenido omitido ni como millones de casos de clasificación.

Referencias: cada MinerU declara688 ref_text en41 páginas de15 papers; Heron usa principalmente list_item. No se declara peor al segundo por no usar el mismo nombre. `target_census.csv` conserva también objetivos fuera de las familias principales y categoríaschild/inline sin equivalencia analítica.

### Alternativas sobre exactamente la misma caja

- Heron:35 geometrías heading/text y3 caption/text.
- Heron-101:19 heading/text y3 caption/text.
- MinerU:0 de estas combinaciones exactas a nivel de targets localizados.

No confundir con los437 grupos padre/cuerpo de MinerU del análisis previo:chart/chart_body oimage/image_body no son contradicciones semánticas de target. Una salida multilabel válida puede existir, pero para una tarea que necesita una sola función requiere una política posterior explícita. Aquí no se modifica la salida.

## 4. Resultados de la muestra revisada: sin ranking global

{ct}

Las columnas separan especificidad de error. No sumar general útil con error, ni contar ambiguos como éxito porque una de sus etiquetas coincide. Tampoco clasificar sin correspondencia como falsa etiqueta. Las diferencias reflejan la muestra elegida; no publicar «X% de precisión de la herramienta» sobre397 páginas a partir de esta tabla.

![Muestra dirigida por estado](target_audit_summary.png)

Desglose por referencia: cada celda expresa **adecuada / general útil / multitarget / errónea / sin correspondencia propia**.

{tt}

## 5. Títulos: la dimensión con mayor coste para ti

{ht}

En estos19 títulos, Heron conserva una señal heading en todos, pero9 son simultáneamente text/section_header. Eso no significa19 decisiones correctas limpias. Heron-101 ofrece8 limpias,9 ambiguas y2 solo texto. MinerU ofrece9 limpias y10 como text. Los cinco no-títulos con señal heading de cada Heron incluyen autores, avisos o metadatos; algunos son multilabel y otros errores únicos.

La consecuencia práctica depende de tu prioridad: un título localizado como text obliga a redescubrir su función; Heron al menos ofrece una señal de título en muchos de esos casos, aunque resolver candidatos conflictivos también cuesta. No hay una dominancia completa: mayor disponibilidad de señal y menor ambigüedad son dimensiones diferentes.

### Patrón repetido: misma plantilla, resultados distintos

En8.pdf se inspeccionaron11 rótulos internos Baseline for Current Fuel-System Designs/New Baseline for Licensing, separados de Application/Assessment y del cuerpo (T004–T014):

{bt}

Basic/Standard alternan entre paragraph_title(4) ytext(7) para la misma función de plantilla. Es una inconsistencia documentada, no solo una diferencia de nombre entre motores. Heron alterna salida única y doble; Heron-101 incluso pierde la señal en2. No se extrapola el patrón a todos los encabezados: el texto, disposición y paper están conservados en cada ROI.

Otros ejemplos:12.pdf,página4,T020 y4.pdf,página2,T027 son subtítulos numerados reales conservados como text por ambos MinerU.12.pdf,página1,T019 es título de documento: Basic/Standard lo declaran doc_title; Heron aporta section_header (familia correcta, subtipo de jerarquía más grueso); Heron-101 añade text.

### El score nativo no resuelve automáticamente la inconsistencia

Se recuperaron scores de los JSON originales Heron por igualdad de bbox/label, sin crear scores de MinerU ni compararlos entre motores. Si hipotéticamente se tomara la etiqueta de mayor score entre las correspondencias propias:

{st}

La señal heading disponible en19 casos de Heron se reduciría a13 usando máximo score, porque6 favorecen text. Esto es un diagnóstico, no una nueva política implementada ni un score calibrado de corrección. `native_score_alternatives.jsonl` conserva todas las alternativas.

Las tasas en `heading_sample_rates.csv` son medidas operativas de señal limpia y límites con conflictos dentro de esta muestra dirigida; no son estimaciones poblacionales. Los límites no son intervalos estadísticos de confianza. La matriz estricta convencional se limita a una familia predicha; multietiquetas, cobertura por grupo y falta de correspondencia se presentan fuera. No se usa una accuracy global dominada por text.

## 6. Texto, autores, fechas y falsos títulos

-1.pdf,página1,T021: Tetsuji Noda es autor. Basic/Standard usan text (general útil). Heron entrega text+section_header; Heron-101 section_header. Aquí el nombre no es un encabezado de sección.
-2.pdf,página1,T028: lista de autores con superíndices; Heron-101 section_header es incompatible con la función observada.
-8.pdf,páginas4 y6,T002/T003: Page intentionally left blank es aviso, no sección. Heron devuelve encabezado como alternativa en una y como única categoría en otra; MinerU conserva text.
-8.pdf,página1,T033: SEPTEMBER2024 es fecha editorial. text es general utilizable; section_header no describe la función real. No toda tipografía grande es título.
- Afiliaciones T034/T050: text/list_item/footnote pueden describir distintos aspectos. No convertirlos en falsos errores por diferencias de esquema.

El feedback humano del autor decía «no un section», pero la dirección guardada enfrentaba Basic(text) con Heron(text+section_header). La observación visual aclara qué función tiene el contenido, sin invertir ni corregir el feedback original. T063 era el mismo objeto queT021 y se excluyó del denominador.

## 7. Captions: clase correcta, marcadores y relación son tres preguntas

En cinco captions revisados (cinco papers), Heron ofrece4 con familia caption inequívoca y1 caption/text; Heron-101 y cada MinerU ofrecen4 con familia caption inequívoca y1 texto erróneo. El caso17.pdf,página26,T026 es Figure5A:...B:...C:...: caption multipanel conservado como text por101 y ambos MinerU. Es un error compartido: acuerdo no implica verdad.

Hay además un error de subtipo: T018,15.pdf,página30, es el caption deFigure6 sobre propiedades elásticas. Basic yStandard lo etiquetan table_caption. La familia caption es adecuada pero el subtipo de tabla no corresponde a la figura observada. Se registra figure_as_table_caption enagent_subtype_assessments.csv; no se contabiliza dos veces como fallo de familia. Heron usa caption genérico. Por tanto,4/5 con familia correcta no significa4/5 etiquetas específicas correctas.

El caso contrario está en14.pdf,página24,T023: Figure2.9 shows the layout... es un párrafo del cuerpo, no el caption. Heron-101 lo etiqueta caption. Por tanto, buscar únicamente un prefijo Figure/Tabla no bastaría para reconstruir tagging preciso; hay que considerar función y contexto, no solo palabra inicial.

### La aparente ventaja338 frente a337 captions es un marcador

Se inspeccionaron los textos ya conservados de cada caption MinerU, sin OCR:

| Patrón de texto nativo | Basic | Standard |
| --- | --- | --- |
| Marcador aislado(a)/(b)/letra |53|52|
| Prefijo Figure/Fig |207|207|
| Prefijo Table |46|46|
| Otros textos de caption |32|32|

Los338/337 registros no son338/337 captions completos. La diferencia concreta está en6.pdf,página12: Basic incluye `(b)` como image_caption; Standard no. Ambos conservan el caption completo Figure4 y el deFigure5. No hay evidencia de que Standard pierda allí un caption compartido completo. Los patrones son descriptores léxicos, no una clasificación infalible de textos.

Además, el análisis previo documentó6.pdf,página15: el caption deFigure8 está declarado hijo de un gráfico deFigure9. La etiqueta caption puede ser correcta y la relación padre–caption incorrecta. Ese fallo de pertenencia se mantiene separado del tagging y no se arregla por cambiar la clase del bloque.

## 8. Imagen, logo y cabecera: especificidad de contenido frente a posición

De10 visuales revisados en8 papers, los Heron identifican9 con picture y carecen de correspondencia propia para1 ilustración decorativa. Basic/Standard reconocen esa ilustración como visual, pero usan header para9 logos/portadas editoriales. Son cajas útiles y header describe una función de posición; **no aporta la identificación específica de imagen que prefieres**.

Ejemplos: logos Elsevier en5.pdf/7.pdf,página1; CrossMark en1.pdf,página1; portadas de revista en5/7/12/2.pdf,página1 y11.pdf,página2. Este patrón está repetido, no es un caso aislado del logo que señalaste. No es correcto sumar los9 como imágenes omitidas ni declarar todos losheader «erróneos»: el déficit es de especificidad del target de contenido.

Para gráficos científicos, picture frente a chart/image es familia visual compartida y vocabulario de distinta resolución. chart es más específico pero no se considera más preciso automáticamente sin observar si la región es realmente un gráfico. Este muestreo de visuales se concentra en logos y portadas; no se usa para afirmar precisión de todas las figuras científicas.

El17 de1.pdf es número de capítulo. Basic/Standard lo etiquetan page_number: familia numérica útil, subtipo impreciso. Heron usa text y101picture. No afirmar que Basic identificó correctamente un número de página: la referencia observada es chapter_marker y se registra `chapter_as_page_number`.

## 9. Referencias, listas, tablas y ecuaciones

Cuatro entradas/fragmentos bibliográficos revisados (tres papers): MinerU usa ref_text, Heron list_item. Ambas pueden ser útiles, pero ref_text identifica mejor la función bibliográfica. El patrón completo tiene536 correspondencias casi equivalentes list_item/ref_text entre Heron yBasic en la colección; no son536 errores de Heron.

La única viñeta no bibliográfica revisada,T051(8.pdf,página18), es list_item enHeron ytext enMinerU. Señal de lista disponible enHeron y texto general aprovechable enMinerU; una observación no acredita listas consistentes en todo el documento. La agrupación de la lista y su continuidad no se evaluaron como parte del target.

Tres tablas y tres ecuaciones revisadas fueron reconocidas adecuadamente por las cuatro herramientas. Los controles incluyen casos donde las herramientas ya coincidían, por lo que no acreditan precisión universal ni demuestran empate poblacional. formula/equation se normalizan como familia ecuación; table_body comparte geometría con padre y no se cuenta como una segunda tabla acertada.

## 10. Patrones completos entre herramientas y papers

{patt}

Estas frecuencias se basan en clusters de bloque casi equivalentes y conservan el texto de la etiqueta, páginas, papers, concentración y soporte macro. Son igualdad/desigualdad de familias, no exactitud: clases distintas pueden ser compatibles. Ni cuatro votos ni dos familias de motores forman la referencia; Basic/Standard y Heron/101 tienen dependencia y comparten errores.

`target_pair_conditionals.csv` expresa, por ejemplo, qué etiquetaB acompaña aheading deA sobre las correspondencias disponibles. El denominador es el target declarado porA que sí tiene correspondencia: no es el conjunto de títulos reales ni recall. La asimetría A→B yB→A se conserva.

Un patrón repetido entre páginas muestra comportamiento consistente de salida, no corrección por sí solo. La plantillaBaseline permite documentar inconsistencia funcional porque las ROI fueron revisadas; el patrónreference/list solo muestra alternativas de esquema hasta contrastar función real. No se entrenó un clasificador ni se ajustó un umbral a los resultados de un paper.

## 11. Qué herramienta aporta más para tus prioridades

| Target/capacidad | Evidencia observada | Valoración acotada |
| --- | --- | --- |
| Títulos localizados como título | Heron conserva más señales en la muestra; MinerU pierde10/19 como text | Heron aporta candidatos útiles, pero9 son ambiguos. No usarlo como tagging final ni extrapolar10/19 a toda la colección |
| Texto sin falsos encabezados | MinerU mantiene autores/avisos como text y no devuelve alternativas heading en esos casos | Más limpio en estos casos; puede ser demasiado general para títulos reales |
| Caption |4/5 limpios por herramienta, con fallo compartido o alternativa | Sin ganador acreditado; separar marcador de panel, caption completo y relación compartida |
| Imagen editorial/logo | Heron picture en9 casos donde MinerU usa header | Heron aporta el target de contenido específico que prefieres; no implica mejor segmentación general |
| Referencia bibliográfica | MinerU ref_text en los4 casos; Heron list_item | Mayor especificidad bibliográfica de MinerU; list_item no es necesariamente falso |
| Lista | Una viñeta list_item frente atext | Señal favorable aHeron, muestra insuficiente para consistencia general |
| Tabla/ecuación | Todos adecuados en3+3 controles | No se detectó ventaja en los controles elegidos; no evaluación completa |
| Standard frente aBasic | Mismas etiquetas de4.168 bloques equivalentes; diferencia de caption aislado(b) | Sin ventaja de Standard demostrada en targets de bloque de esta colección |

No se recomienda una etiqueta ganadora por votación ni se implementa un ensemble. Según tu preferencia por reconstrucción uniforme, los **títulos** y la **clase de contenido de logos/header** son tareas que requieren una política uniforme si se adopta MinerU como base. Heron puede aportar evidencia candidata, pero elegirla automáticamente aquí volvería a introducir la inconsistencia que quieres evitar. Esto es diagnóstico, no validación de una técnica complementaria.

## 12. Evidencia por caso

![Ejemplos de targets](target_examples.png)

{detailtable}

Cada caso tieneROI, papel/página, lámina visual, clase/subtipo observado, confianza y nota en `agent_reference_cases.jsonl`; cada evaluación guarda todas las cajas propias y otras intersecciones en `agent_assessments.jsonl`. Se pueden revisar conjuntamente regiones equivalentes sin solicitar al usuario etiquetado pieza por pieza.

## 13. Verificación, procedencia y límites

- Censo: target_census.csv,target_profiles.csv,target_correspondences.csv,target_patterns.csv.
- Ambigüedades: same_box_target_conflicts.jsonl ystrict_same_box_target_alternatives.csv; no confundir grupos padre/cuerpo con conflicto de clase.
- Referencia del agente:65 ROI,59 objetos puntuados,4 duplicados excluidos,2 referencias sin clase única;236 evaluaciones elegibles. T062 es ROI parcial del logo;T065 mezcla tabla/caption.
- Evaluación: agent_target_summary.csv,agent_tool_summary.csv,agent_confusion_counts.csv,heading_asymmetric_costs.csv,heading_sample_rates.csv yagent_subtype_assessments.csv. Tasas dirigidas y abstenciones explícitas, sin accuracy global.
- Scores y texto originales: native_score_alternatives.jsonl,native_caption_text.csv. Sin OCR ni scores imputados; JSON originales preservados.
- Se conservaron resultados intermedios diagnósticos de la auditoría antes de corregir el duplicadoARTICLE INFO y la compatibilidad de afiliaciones. Están en diagnostic-audit-v1; no son la entrega vigente. El mapa family no cambió; snapshots del código fijan versiones de preparación y auditoría.
- Revisión independiente: corrigió el duplicadoT016/T031 y el falso conflicto de afiliaciones. No constituye aprobación semántica humana. Pruebas8/8; verificaciones finales y hashes en final_checks.json.
- Originales, resultados anteriores, feedback yvisor no se modificaron. No se ejecutaron parsers, OCR, modelos, Colab ni renders PDF. Las láminas son recortes de presentación de PNG existentes.

El hallazgo es una matriz de ventajas y problemas por target, no un ganador universal. Para afirmar precision/recall de toda la colección faltan referencia representativa e inventario de elementos reales, incluidos los que ninguna herramienta detecta. La revisión del agente hace verificables los ejemplos y permite distinguir error de mera discrepancia; no sustituye la revisión humana ni elimina el sesgo de selección.
'''
    # Ensure CommonMark list spacing for numeral-leading generated bullets.
    for word in ('1.pdf','2.pdf','8.pdf'):text=text.replace('\n-'+word,'\n- '+word)
    report_target=write_authored_report(OUT,text)
    assert all(sha(p)==h for p,h in hashes.items());assert all(sha(p)==h for p,h in images.items())
    jsonout(OUT/'report_verification.json',dict(input_hashes=hashes,image_hashes=images,code_hash=sha(__file__),unchanged=True,report_scope='fixed_collection_narrative_review_required_for_other_inputs'))
    print(report_target)

if __name__=='__main__':main()
