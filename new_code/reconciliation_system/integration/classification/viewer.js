/* A single reconciled layer. Data are read-only; parsers never become units. */
(() => {
  'use strict';
  const data=JSON.parse(document.getElementById('data-model').textContent);
  const $=id=>document.getElementById(id),svgNS='http://www.w3.org/2000/svg';
  const category={text:'Texto',title:'Título',figure:'Figura',table:'Tabla',caption:'Caption',equation:'Ecuación',margin:'Margen',other:'Otros',unresolved:'Ambigua'};
  const func={main_body:'Cuerpo',metadata:'Metadatos',associated_content:'Contenido asociado',editorial:'Editorial',navigation:'Navegación',unresolved:'Sin resolver'};
  const colorFor={category:Object.fromEntries(Object.keys(category).map(k=>[k,`var(--${k})`])),function:{main_body:'var(--text)',metadata:'var(--title)',associated_content:'var(--figure)',editorial:'var(--equation)',navigation:'var(--margin)',unresolved:'var(--unresolved)'}};
  const warningText={category_ambiguous:'Categoría ambigua',subtype_unresolved:'Subtipo pendiente',function_ambiguous:'Función ambigua',function_insufficient_evidence:'Función sin evidencia suficiente',retained_native_category_disagreement:'Diferencia entre categoría conciliada y nativa',parser_evidence_category_conflict:'Evidencia contradictoria de parsers',retained_group_member_overlap:'Solapamiento de miembros conservado',member_validation_pending:'Miembros con validación pendiente',container_function_unresolved:'Función de contenedor pendiente',geometry_deferred:'Geometría diferida',inherited_page_geometry_abstention:'Abstención geométrica de página conservada',inherited_page_incident:'Incidente de página conservado',unknown_native_class:'Clase desconocida',retained_classification_abstention:'Abstención de clasificación conservada'};
  const subtype={paragraph_candidate:'Párrafo candidato',section_heading_candidate:'Encabezado de sección candidato',paper_title:'Título del paper',metadata_candidate:'Metadatos candidatos',bibliographic_reference:'Referencia bibliográfica',caption_candidate:'Caption candidato',native_caption:'Caption nativo',label_and_description:'Rótulo y descripción',display_equation:'Ecuación independiente',multipanel_group:'Grupo multipanel',recurring_margin_candidate:'Margen recurrente candidato',header:'Encabezado',footer:'Pie',page_number:'Número de página',page_footnote:'Nota al pie'};
  const regions=new Map(data.regions.map(r=>[r.id,r])), evidence=new Map(data.evidence.map(r=>[r.id,r]));
  let page=data.pages.some(p=>p.n===3)?3:data.pages[0].n,mode='category',zoom=1,selected=null,units=[];
  const create=(tag,text,className)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;};
  const dim=(c,key)=>c[key].value||'unresolved';
  function setZoom(){ $('stage').style.width=zoom===1?'100%':`${zoom*100}%`;$('zoom').textContent=zoom===1?'Ajustada':`${Math.round(zoom*100)}%`; }
  function showDetail(){
    const u=units.find(x=>x.id===selected),panel=$('detail');panel.replaceChildren();
    const highlighted=new Set(u?.kind==='group'?u.members:[selected]);
    $('overlay').querySelectorAll('rect').forEach(r=>r.classList.toggle('active',highlighted.has(r.dataset.id)));
    if(!u){panel.append(create('p','No hay objetos en esta página.'));return;}
    const c=u.classification;
    panel.append(create('h2',`${category[dim(c,'category')]} · ${func[dim(c,'function')]}`));
    panel.append(create('p',`Categoría conservada: ${u.retained_category||Object.values(c.retained_classification?.member_categories||{}).join(' / ')||'Ver miembros'}`,'label'));
    if(c.category.candidates.length>1)panel.append(create('p','Categorías candidatas: '+c.category.candidates.map(x=>category[x]||x).join(' / ')));
    if(c.function.value===null)panel.append(create('p','Funciones candidatas: '+(c.function.candidates.map(x=>func[x]||x).join(' / ')||'Pendiente')));
    const st=c.subtype.value?[c.subtype.value]:c.subtype.candidates;
    panel.append(create('p','Subtipo: '+(st.map(x=>subtype[x]||x).join(' / ')||'Pendiente'),'label'));
    if(c.warnings.length){const warning=create('div',undefined,'warning-text');warning.append(create('strong','Requiere validación humana'));warning.append(create('div',c.warnings.map(w=>warningText[w.code]||w.code).join(' · ')));panel.append(warning);}
    panel.append(create('p','Propuesta automática · validación semántica pendiente','label'));
    if(u.kind==='group'){
      panel.append(create('p',`${u.members.length} miembros · cajas originales, sin envolvente nueva`));
      const caption=regions.get(u.caption_ref);if(caption)panel.append(create('p',caption.text||'Caption sin texto disponible','text'));
    }else panel.append(create('p',u.text||'Sin texto nativo disponible.','text'));
    const detail=create('details');detail.append(create('summary','Evidencia y procedencia'));
    const body=create('div',undefined,'evidence');
    body.append(create('p','Categoría y estado de la conciliación: '+JSON.stringify(c.retained_classification)));
    (c.parser_evidence||[]).forEach(e=>{const r=evidence.get(e.record_ref);body.append(create('p',`${r?.parser||'Fuente'} · ${e.retained_source_category} · ${e.kind}`));});
    body.append(create('p',`${c.reconciliation_decision_refs?.length||0} decisiones previas relacionadas`));
    body.append(create('p','Reglas: '+c.rule_refs.join(', ')));body.append(create('p',u.id));detail.append(body);panel.append(detail);
  }
  function draw(){
    const p=data.pages.find(p=>p.n===page),all=data.regions.filter(r=>r.page===page);
    const visible=all.filter(r=>r.kind!=='container'||$('containers').checked);
    visible.sort((a,b)=>(a.bbox?.[1]??Infinity)-(b.bbox?.[1]??Infinity)||a.id.localeCompare(b.id));
    units=[...data.groups.filter(g=>g.page===page).map(g=>({...g,kind:'group'})),...visible];
    if(!units.some(x=>x.id===selected))selected=units.find(x=>x.kind!=='group')?.id||units[0]?.id||null;
    $('page').value=String(page);$('prev').disabled=page===data.pages[0].n;$('next').disabled=page===data.pages.at(-1).n;
    $('paper').src=p.image;$('paper').alt=`12.pdf · página física ${page} · imagen original`;
    $('overlay').setAttribute('viewBox',`0 0 ${p.w} ${p.h}`);$('overlay').replaceChildren();$('unit').replaceChildren();
    units.forEach((u,i)=>$('unit').add(new Option(`${u.kind==='group'?'Grupo':u.kind==='container'?'Contenedor':'Región'} ${i+1} · ${category[dim(u.classification,'category')]}${u.classification.warnings.length?' ⚠':''}`,u.id)));
    $('unit').value=selected||'';
    for(const r of visible){
      const b=r.bbox;if(!Array.isArray(b)||b.length!==4||!b.every(Number.isFinite)||!(0<=b[0]&&b[0]<b[2]&&b[2]<=p.w&&0<=b[1]&&b[1]<b[3]&&b[3]<=p.h))continue;
      const rect=document.createElementNS(svgNS,'rect'),c=r.classification,k=dim(c,mode),color=colorFor[mode][k];
      const attrs={x:b[0],y:b[1],width:b[2]-b[0],height:b[3]-b[1],fill:color,stroke:color,role:'button',tabindex:'0','aria-label':`${category[dim(c,'category')]} · ${func[dim(c,'function')]}`};
      Object.entries(attrs).forEach(([key,value])=>rect.setAttribute(key,String(value)));rect.dataset.id=r.id;
      rect.setAttribute('class','region'+(c.warnings.length?' warning':''));
      const select=()=>{selected=r.id;$('unit').value=r.id;showDetail();};rect.addEventListener('click',select);rect.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}});
      const title=document.createElementNS(svgNS,'title');title.textContent=attrs['aria-label'];rect.append(title);$('overlay').append(rect);
    }
    $('legend').replaceChildren();Object.entries(mode==='category'?category:func).forEach(([key,label])=>{const item=create('span',undefined,'key'),swatch=create('i');swatch.style.background=colorFor[mode][key];item.append(swatch,document.createTextNode(label));$('legend').append(item);});
    $('status').textContent=`Página ${page} de ${data.pages.length} · ${all.filter(r=>r.kind!=='container').length} regiones conciliadas · ${all.filter(r=>r.kind==='container').length} contenedores · ${data.groups.filter(g=>g.page===page).length} grupos · ${p.w} × ${p.h} px originales`;
    setZoom();showDetail();
  }
  data.pages.forEach(p=>$('page').add(new Option(String(p.n),p.n)));
  $('page').addEventListener('change',()=>{page=Number($('page').value);selected=null;zoom=1;draw();});
  for(const [id,delta] of [['prev',-1],['next',1]])$(id).addEventListener('click',()=>{const i=data.pages.findIndex(p=>p.n===page);if(data.pages[i+delta]){page=data.pages[i+delta].n;selected=null;zoom=1;draw();}});
  $('mode').addEventListener('change',()=>{mode=$('mode').value;draw();});$('containers').addEventListener('change',draw);
  $('unit').addEventListener('change',()=>{selected=$('unit').value;showDetail();});
  $('fit').addEventListener('click',()=>{zoom=1;setZoom();});$('in').addEventListener('click',()=>{zoom=Math.min(3,Math.round((zoom+.25)*100)/100);setZoom();});$('out').addEventListener('click',()=>{zoom=Math.max(.5,Math.round((zoom-.25)*100)/100);setZoom();});
  draw();
})();
