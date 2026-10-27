/* Presentation only. All geometry comes from recorded sources. */
(() => {
  'use strict';
  const TYPES = [['text','Texto','#30856a'],['title','Títulos','#8161b0'],
    ['figure','Figuras','#4679b7'],['table','Tablas','#b76550'],
    ['caption','Captions','#b08532'],['equation','Ecuaciones','#8c6d55'],
    ['margin','Márgenes','#8b929a'],['other','Otros','#606b77']];
  const VIEWS = [['reconciled','Conciliada'],['mineru','MinerU'],['tatr','TATR'],['lm','LayoutLMv3']];
  function category(type) {
    if (/caption/.test(type)) return 'caption';
    if (/title/.test(type)) return 'title';
    if (/table/.test(type)) return 'table';
    if (/figure|chart|image|picture/.test(type)) return 'figure';
    if (/equation|formula/.test(type)) return 'equation';
    if (/text|paragraph|list/.test(type)) return 'text';
    if (/header|footer|page_number|footnote/.test(type)) return 'margin';
    return 'other';
  }
  function visibleRegions(page, view, state) {
    if (!state.boxes) return [];
    let regions = page.views[view].slice();
    if (view==='reconciled' && state.historical) regions.push(...page.historical);
    if (view==='reconciled' && state.alternatives)
      regions.push(...page.views.lm.concat(page.views.tatr).map(x=>({...x,renderAlternative:true})));
    return regions.filter(x=>(state.containers || x.layer!=='container') && state.types.has(category(x.type)));
  }
  function groupEdges(page) {
    const nodes = new Map(page.views.reconciled.map(x=>[x.id,x]));
    const center = r=>[(r.bbox[0]+r.bbox[2])/2,(r.bbox[1]+r.bbox[3])/2];
    return page.groups.flatMap(g=>g.members.filter(id=>nodes.has(id)&&nodes.has(g.caption))
      .map(id=>({group:g,member:nodes.get(id),from:center(nodes.get(id)),to:center(nodes.get(g.caption))})));
  }
  function pageNumber(value,total) { return Math.max(1,Math.min(total,Number(value)||1)); }
  if (typeof module!=='undefined') module.exports={TYPES,category,visibleRegions,groupEdges,pageNumber};
  if (typeof document==='undefined') return;

  const data = JSON.parse(document.getElementById('view-data').textContent);
  const $ = id=>document.getElementById(id);
  const state = {page:1,zoom:100,visible:new Set(VIEWS.map(x=>x[0])),types:new Set(TYPES.map(x=>x[0])),
    boxes:true,labels:false,containers:false,groups:true,historical:true,alternatives:false,selected:null};
  const color = type=>TYPES.find(x=>x[0]===category(type))[2];
  const element = (tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  const svgElement = (tag,attrs)=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));return n;};
  const current = ()=>data.pages[state.page-1];

  for (const p of data.pages) { const option=element('option',`Página ${p.number} de ${data.pages.length}`);option.value=p.number;$('page').append(option); }
  const viewChecks = new Map();
  for (const [key,title] of VIEWS) {
    const label=element('label');const input=element('input');input.type='checkbox';input.checked=true;
    input.addEventListener('change',()=>{if(input.checked)state.visible.add(key);else state.visible.delete(key);
      if(!state.visible.size){state.visible.add(key);input.checked=true;}render();});
    label.append(input,document.createTextNode(title));$('viewOptions').append(label);viewChecks.set(key,input);
  }
  const typeChecks = new Map();
  for (const [key,title,c] of TYPES) {
    const label=element('label');const input=element('input');input.type='checkbox';input.checked=true;
    input.addEventListener('change',()=>{if(input.checked)state.types.add(key);else state.types.delete(key);renderPanes();});
    const dot=element('i');dot.style.background=c;label.append(input,dot,document.createTextNode(title));$('types').append(label);typeChecks.set(key,input);
  }
  for (const name of ['boxes','labels','containers','groups','historical','alternatives'])
    $(name).addEventListener('change',()=>{state[name]=$(name).checked;renderPanes();});
  $('page').addEventListener('change',()=>changePage($('page').value));
  $('prev').addEventListener('click',()=>changePage(state.page-1));
  $('next').addEventListener('click',()=>changePage(state.page+1));
  $('all').addEventListener('click',()=>{state.visible=new Set(VIEWS.map(x=>x[0]));state.zoom=100;$('zoom').value=100;render();});
  $('zoom').addEventListener('input',()=>{state.zoom=Number($('zoom').value);$('zoomValue').textContent=state.zoom+'%';
    document.querySelectorAll('.sheet').forEach(x=>x.style.width=state.zoom+'%');});
  $('clear').addEventListener('click',()=>{state.selected=null;showDetail();renderPanes();});
  document.addEventListener('keydown',e=>{
    if(['INPUT','SELECT','TEXTAREA','BUTTON'].includes(e.target.tagName))return;
    if(e.key==='ArrowRight')changePage(state.page+1);
    if(e.key==='ArrowLeft')changePage(state.page-1);
  });
  function changePage(value) { state.page=pageNumber(value,data.pages.length);state.selected=null;render(); }
  function focusView(key) { state.visible=new Set([key]);render(); }

  function selectRegion(region,view,focus=false) {
    state.selected={kind:'region',region,view};
    if(focus){state.visible=new Set([view]);state.boxes=true;$('boxes').checked=true;state.types.add(category(region.type));}
    showDetail();renderPanes();
    if(focus)requestAnimationFrame(()=>centerOn(view,region.bbox));
    viewChecks.forEach((box,key)=>box.checked=state.visible.has(key));
    typeChecks.forEach((box,key)=>box.checked=state.types.has(key));
  }
  function selectGroup(group,focus=false) {
    state.selected={kind:'group',group,view:'reconciled'};
    if(focus){state.visible=new Set(['reconciled']);state.groups=true;$('groups').checked=true;}
    showDetail();renderPanes();
    if(focus)requestAnimationFrame(()=>{
      const node=current().views.reconciled.find(x=>x.id===group.members[0]);if(node)centerOn('reconciled',node.bbox);
    });
    viewChecks.forEach((box,key)=>box.checked=state.visible.has(key));
  }
  function centerOn(view,bbox) {
    const port=document.querySelector(`[data-view="${view}"] .canvasScroll`);if(!port)return;
    const scale=port.querySelector('.sheet').getBoundingClientRect().width/current().identity.width_px;
    port.scrollTo({left:((bbox[0]+bbox[2])/2)*scale-port.clientWidth/2,
      top:((bbox[1]+bbox[3])/2)*scale-port.clientHeight/2,behavior:'smooth'});
  }
  function showDetail() {
    const target=$('detail');target.replaceChildren();
    if(!state.selected){$('detailTitle').textContent='Selecciona una región';target.append(element('p','Pulsa una caja, un título o un grupo para consultar su evidencia.','hint'));return;}
    if(state.selected.kind==='group'){
      const g=state.selected.group;$('detailTitle').textContent=g.figure+' · vínculo aceptado';
      target.append(element('p',`${g.members.length} paneles · caption compartido · aceptación del usuario.`));
      target.append(element('p','Geometría: '+g.geometry_status,'hint'));
      const list=element('div',undefined,'memberButtons');
      for(const id of g.members.concat([g.caption])){const r=current().views.reconciled.find(x=>x.id===id);if(!r)continue;
        const b=element('button',r.local_id);b.addEventListener('click',()=>selectRegion(r,'reconciled',true));list.append(b);}
      target.append(list,element('pre',JSON.stringify({source:g.source,pointer:g.pointer,acceptance:g.acceptance},null,2)));return;
    }
    const r=state.selected.region;$('detailTitle').textContent=r.local_id+' · '+r.type;
    const tags=element('div',undefined,'tags');
    for(const label of [r.renderAlternative?'Alternativa pendiente':r.layer==='historical'?'Recuperación histórica':r.layer==='container'?'Contenedor nativo':state.selected.view==='reconciled'?'Segmento seleccionado provisional':'Salida individual',r.level!=null?'Nivel nativo '+r.level:null])
      if(label)tags.append(element('span',label));
    target.append(tags,element('p',r.text||'No hay transcripción de texto en este registro.','nativeText'));
    target.append(element('pre',JSON.stringify({id:r.id,source:r.source,pointer:r.pointer,bbox:r.bbox,status:r.native_status},null,2)));
    const details=element('details');details.append(element('summary','Registro nativo'));details.append(element('pre',JSON.stringify(r.source_data,null,2)));target.append(details);
  }

  function render() {
    $('page').value=state.page;$('prev').disabled=state.page===1;$('next').disabled=state.page===data.pages.length;
    $('zoomValue').textContent=state.zoom+'%';viewChecks.forEach((box,key)=>box.checked=state.visible.has(key));
    const p=current();$('summary').textContent=`Página ${state.page} / 13 · ${p.views.reconciled.filter(x=>x.layer==='segment').length} segmentos · ${p.groups.length} grupos aceptados`;
    $('outline').replaceChildren();
    for(const title of p.outline){const b=element('button',title.text||title.local_id,'outlineItem');
      b.style.paddingLeft=(Math.max(0,Math.min(5,(title.level||1)-1))*10+4)+'px';
      b.title='Nivel nativo '+(title.level??'no indicado');b.addEventListener('click',()=>selectRegion(title,'reconciled',true));$('outline').append(b);}
    if(!p.outline.length)$('outline').append(element('p','Sin títulos nativos en esta página.','hint'));
    $('groupList').replaceChildren();
    for(const g of p.groups){const b=element('button',`${g.figure} · ${g.members.length} paneles`,'outlineItem');b.addEventListener('click',()=>selectGroup(g,true));$('groupList').append(b);}
    if(!p.groups.length)$('groupList').append(element('p','Sin grupos adicionales aceptados. Se conserva la estructura nativa.','hint'));
    $('warnings').replaceChildren();for(const w of p.warnings)$('warnings').append(element('li',w.description));
    showDetail();renderPanes();
  }
  let syncing=false;
  function syncScroll(event) {
    if(syncing)return;syncing=true;const source=event.currentTarget;
    const y=source.scrollTop/Math.max(1,source.scrollHeight-source.clientHeight);
    const x=source.scrollLeft/Math.max(1,source.scrollWidth-source.clientWidth);
    document.querySelectorAll('.canvasScroll').forEach(port=>{if(port!==source){port.scrollTop=y*(port.scrollHeight-port.clientHeight);port.scrollLeft=x*(port.scrollWidth-port.clientWidth);}});
    requestAnimationFrame(()=>syncing=false);
  }
  let renderedPage=null;
  function renderPanes() {
    const previous=document.querySelector('.canvasScroll');
    const keep=renderedPage===state.page&&previous;
    const top=keep?previous.scrollTop/Math.max(1,previous.scrollHeight-previous.clientHeight):0;
    const left=keep?previous.scrollLeft/Math.max(1,previous.scrollWidth-previous.clientWidth):0;
    const p=current();const holder=$('panes');holder.replaceChildren();holder.style.setProperty('--views',state.visible.size);renderedPage=state.page;
    for(const [key,title] of VIEWS){if(!state.visible.has(key))continue;
      const pane=element('article',undefined,'pane');pane.dataset.view=key;
      const head=element('div',undefined,'paneHead');const label=element('div');label.append(element('h2',title));
      const count=p.views[key].filter(x=>x.layer!=='container').length;
      const note=key==='reconciled'?'Estructura nativa + decisiones aceptadas':key==='mineru'?'Estructura y texto originales':key==='tatr'?'Localización de tablas':'Regiones de layout';
      label.append(element('p',`${note} · ${count} regiones`));
      const focus=element('button',state.visible.size===1?'Comparar':'Ampliar');focus.addEventListener('click',()=>{if(state.visible.size===1){state.visible=new Set(VIEWS.map(x=>x[0]));render();}else focusView(key);});head.append(label,focus);
      const port=element('div',undefined,'canvasScroll');port.tabIndex=0;port.setAttribute('aria-label',`${title}, página ${state.page}`);port.addEventListener('scroll',syncScroll);
      const sheet=element('div',undefined,'sheet');sheet.style.width=state.zoom+'%';
      const svg=svgElement('svg',{viewBox:`0 0 ${p.identity.width_px} ${p.identity.height_px}`,role:'group','aria-label':title+' segmentación'});
      svg.append(svgElement('image',{href:p.image,width:p.identity.width_px,height:p.identity.height_px}));
      for(const r of visibleRegions(p,key,state)){
        const [x0,y0,x1,y1]=r.bbox;const g=svgElement('g',{class:'region'+(state.selected?.kind==='region'&&state.selected.region.id===r.id?' selected':''),tabindex:'0',role:'button','aria-label':r.local_id+' '+r.type});
        const alternative=r.renderAlternative;const c=r.layer==='historical'?'#ac7625':color(r.type);
        const rect=svgElement('rect',{x:x0,y:y0,width:x1-x0,height:y1-y0,fill:'none',stroke:c,'stroke-width':2,'vector-effect':'non-scaling-stroke'});
        if(r.layer==='container'||alternative||r.layer==='historical')rect.setAttribute('stroke-dasharray',alternative?'3 6':'7 4');
        if(alternative)rect.setAttribute('opacity','.65');
        const tip=svgElement('title',{});tip.textContent=r.local_id+' · '+r.type+(alternative?' · alternativa pendiente':'');g.append(rect,tip);
        if(state.labels){const t=svgElement('text',{x:x0+3,y:Math.max(18,y0+16),fill:c,'font-size':20,'font-family':'system-ui'});t.textContent=r.local_id;g.append(t);}
        g.addEventListener('click',()=>selectRegion(r,key));g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectRegion(r,key);}});svg.append(g);
      }
      if(key==='reconciled'&&state.groups){
        for(const edge of groupEdges(p)){
          const line=svgElement('line',{x1:edge.from[0],y1:edge.from[1],x2:edge.to[0],y2:edge.to[1],stroke:'#287956','stroke-width':2,'stroke-dasharray':'6 6','vector-effect':'non-scaling-stroke',class:'groupLink'});line.style.pointerEvents='none';svg.append(line);
          const [a,b,c,d]=edge.member.bbox;
          const outline=svgElement('rect',{x:a,y:b,width:c-a,height:d-b,fill:'transparent',stroke:'#287956','stroke-width':3,'vector-effect':'non-scaling-stroke',class:'groupMember',tabindex:'0',role:'button','aria-label':edge.group.figure+' grupo aceptado'});
          const tip=svgElement('title',{});tip.textContent=edge.group.figure+' · panel de grupo aceptado';outline.append(tip);
          outline.addEventListener('click',()=>selectGroup(edge.group));outline.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectGroup(edge.group);}});svg.append(outline);
        }
      }
      sheet.append(svg);port.append(sheet);pane.append(head,port);
      if(!count)pane.append(element('p',key==='tatr'?'Sin detecciones de tabla en esta página. Las figuras y el texto quedan fuera de esta salida.':'Sin regiones registradas.','emptyNote'));
      holder.append(pane);
      port.scrollTop=top*(port.scrollHeight-port.clientHeight);port.scrollLeft=left*(port.scrollWidth-port.clientWidth);
    }
  }
  render();
})();
