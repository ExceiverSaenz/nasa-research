/* Read-only presentation. All geometry, associations and sequences come from frozen artifacts. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id), NS = 'http://www.w3.org/2000/svg';
  const labels = {text:'Text',title:'Title',figure:'Figure',table:'Table',caption:'Caption',equation:'Equation',margin:'Margin',other:'Other',unresolved:'Unresolved',main_body:'Main body',metadata:'Metadata',associated_content:'Associated content',editorial:'Editorial',navigation:'Navigation',main:'Main text',bibliography:'Bibliography',editorial_navigation:'Editorial / navigation',notes:'Notes',pending_structures:'Pending structures',paragraph_candidate:'Paragraph candidate',section_heading_candidate:'Section heading candidate',paper_title:'Paper title',metadata_candidate:'Metadata candidate',bibliographic_reference:'Bibliographic reference',caption_candidate:'Caption candidate',native_caption:'Native caption',label_and_description:'Label and description',display_equation:'Display equation',multipanel_group:'Multipanel group',recurring_margin_candidate:'Recurring margin candidate',header:'Header',footer:'Footer',page_number:'Page number',page_footnote:'Page footnote'};
  const nativeCategory = {'Texto':'text','Títulos':'title','Figuras':'figure','Tablas':'table','Captions':'caption','Ecuaciones':'equation','Márgenes':'margin','Otros':'other','Sin resolver':'unresolved'};
  const palette = ['#1769a6','#ad5c00','#087d66','#9c3ab4','#cc3472','#5b5dc5','#677b16','#944a3b','#176e75','#596879'];
  const names = {reconciled:'Reconciled',mineru:'MinerU',layoutlmv3:'LayoutLMv3',table_transformer:'Table Transformer',baseline:'Reading v1 baseline · this run',docling:'Docling · geometric rules',operational:'Operational traversal'};
  let data, page = 1, mode = new URLSearchParams(location.search).get('mode') || window.START_MODE || 'comparison', selected = null, activePanel = 'reconciled', zoom='fit';
  let regions = new Map(), colors = new Map(), routeMaps = {}, cache = new Map(), loadToken=0;
  const text = k => labels[k] || (k || 'unresolved').replaceAll('_',' ').replace(/^./, c=>c.toUpperCase());
  const el = (tag, content, cls) => {const e=document.createElement(tag);if(content!==undefined)e.textContent=content;if(cls)e.className=cls;return e;};
  const svg = (tag, attrs={}) => {const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;};
  const val = (r, dim) => r.classification ? r.classification[dim]?.value || 'unresolved' : dim==='category' ? nativeCategory[r.category] || 'unresolved' : dim==='subtype' ? r.subtype || 'unresolved' : 'unavailable';
  const valid = (r,p) => Array.isArray(r?.bbox) && r.bbox.length===4 && r.bbox.every(Number.isFinite) && r.bbox[0]>=0 && r.bbox[1]>=0 && r.bbox[2]>r.bbox[0] && r.bbox[3]>r.bbox[1] && r.bbox[2]<=p.w && r.bbox[3]<=p.h;
  const center = r => [(r.bbox[0]+r.bbox[2])/2,(r.bbox[1]+r.bbox[3])/2];
  function options(id, rows, preserve=true){const e=$(id),old=e.value;e.replaceChildren();for(const [v,t] of rows)e.add(new Option(t,v));if(preserve&&rows.some(x=>x[0]===old))e.value=old;}
  function orderKey(panel){return ['baseline','docling','operational'].includes(panel)?panel:'operational';}
  function eligible(r,panel){
    if(!$('containers').checked && ['container','container_only'].includes(r.kind))return false;
    if($('value').value!=='all' && val(r,$('dimension').value)!==$ ('value').value)return false;
    const route=$('route').value;
    if(route!=='all' && !['mineru','layoutlmv3','table_transformer'].includes(panel) && !(routeMaps[orderKey(panel)].get(r.id)||new Set()).has(route))return false;
    return true;
  }
  function panelKeys(){return mode==='comparison'?['reconciled','mineru','layoutlmv3','table_transformer']:mode==='order'?['baseline','docling']:mode==='operational'?['operational']:['reconciled'];}
  function setPanels(){const keys=panelKeys();const pairs=mode==='comparison'?keys.slice(1).map(k=>[`reconciled+${k}`,`Reconciled + ${names[k]}`]):[];options('panels',[...(keys.length>1?[['all','All panels']]:[]),...pairs,...keys.map(k=>[k,names[k]])],false);$('panels').value=innerWidth<760&&mode==='comparison'?'reconciled+mineru':keys.length>1?'all':keys[0];}
  function setupFilters(){
    const values=[...new Set([...data.regions,...(mode==='comparison'?data.records:[])].map(r=>val(r,$('dimension').value)))].sort();colors=new Map(values.map((v,i)=>[v,palette[i%palette.length]]));
    options('value',[['all','All values'],...values.map(k=>[k,text(k)])]);
    options('route',[['all','All routes'],...Object.keys(data.orders.operational.routes).map(k=>[k,text(k)])]);
    $('legend').replaceChildren();for(const k of values){const item=el('span',undefined,'key'),i=el('i');i.style.background=colors.get(k);item.append(i,document.createTextNode(text(k)));$('legend').append(item);}
  }
  function receive(d){
    cache.set(d.id,d);if(d.id!==$('paper').value)return;
    data=d;regions=new Map(d.regions.map(r=>[r.id,r]));routeMaps={};
    for(const [key,o] of Object.entries(d.orders)){const map=new Map();for(const s of o.steps){for(const id of [...(s.render_unit_refs||[]),s.unit_ref]){if(!map.has(id))map.set(id,new Set());map.get(id).add(s.route);}}routeMaps[key]=map;}
    page=d.pages.some(p=>p.n===page)?page:d.pages[0].n;options('page',d.pages.map(p=>[String(p.n),String(p.n)]),false);$('page').value=page;
    $('total').textContent=`/ ${d.pages.length}`;$('loading').textContent=`1 paper · ${d.pages.length} pages · offline`;$('attempt').textContent=`Both · ${d.run} · ${d.records.length} native detections · ${d.regions.length} reconciled units · semantic validation pending`;
    setupFilters();selected=null;render();
  }
  window.receivePaper=receive;
  function load(){const pid=$('paper').value;loadToken++;$('loading').textContent='Loading paper…';if(cache.has(pid))return receive(cache.get(pid));const script=el('script');script.src=`data/${pid}.js`;script.onerror=()=>{$('loading').textContent='Could not load paper. Keep the data folder beside index.html.';};document.head.append(script);}
  function choose(r,panel){selected=r.id;activePanel=panel;if(innerWidth<760)document.body.classList.toggle('hide-details',false);render();}
  function showDetail(){
    const nativePanel=['mineru','layoutlmv3','table_transformer'].includes(activePanel);const r=nativePanel?data.records.find(x=>x.id===selected&&x.parser===activePanel):regions.get(selected),box=$('detail');box.replaceChildren();if(!r){box.append(el('p','Select a box, number, or unit to inspect it.'));return;}
    box.append(el('strong',r.classification?'Reconciled unit':names[r.parser]||'Parser record'));
    for(const dim of ['category','subtype','function'])box.append(el('p',`${text(dim)}: ${val(r,dim)==='unavailable'?'Not assigned by this parser':text(val(r,dim))}`));
    box.append(el('p',`Kind: ${text(r.kind)} · Page ${r.page}`));
    if(nativePanel){box.append(el('p',`Native label: ${r.native_label || r.native_type || 'unavailable'} · ${r.score==null?'No score supplied':`Score: ${r.score}`}`));}
    const matches=(data.correspondences||[]).filter(c=>c.sources.includes(r.id));
    if(matches.length){const d=el('details');d.append(el('summary',`${matches.length} saved parser correspondences`),el('pre',JSON.stringify(matches,null,2)));box.append(d);}
    const order=data.orders[orderKey(activePanel)];
    if(['baseline','docling','operational'].includes(activePanel)){const steps=order.steps.filter(s=>s.unit_ref===r.id||(s.render_unit_refs||[]).includes(r.id));const d=el('details');d.append(el('summary','Saved traversal steps and warnings'),el('pre',JSON.stringify(steps,null,2)));box.append(d);}

    if(!r.bbox)box.append(el('p','No bounding box. Geometry is not inferred from the parent.','warning'));
    if(r.members)box.append(el('p',`Shared-caption group: ${r.members.length} referenced members. No synthetic enclosing box.`));
    const warnings=r.classification?.warnings||[];if(warnings.length)box.append(el('p','Human validation required: '+warnings.map(w=>text(w.code)).join(' · '),'warning'));
    if(r.classification){const d=el('details');d.append(el('summary','Classification evidence and alternatives'));const c={...r.classification};delete c.warnings;d.append(el('pre',JSON.stringify(c,null,2)));box.append(d);}
    box.append(el('p',r.text||'No native text available.'));
    if(r.source){const details=el('details');details.append(el('summary','Source and provenance'),el('pre',JSON.stringify(r.source,null,2)));box.append(details);}
    box.append(el('p',r.id,'muted'));
  }
  function sequence(panel,p){
    const o=data.orders[orderKey(panel)],byId=new Map(o.steps.map(s=>[s.id,s])),rows=[];
    for(const [rt,route] of Object.entries(o.routes)){
      if($('route').value!=='all'&&$('route').value!==rt)continue;
      route.expanded_sequence.forEach((id,i)=>{const s=byId.get(id);if(s?.page!==p.n)return;const r=regions.get(s.unit_ref);if(r&&eligible(r,panel))rows.push({s,r,rt,index:i+1});});
    }
    return rows;
  }
  function drawBoard(panel,p){
    const board=el('section',undefined,'board'),heading=el('h2',names[panel]),focus=el('button','Focus');focus.onclick=()=>{$('panels').value=panel;activePanel=panel;selected=null;render();};heading.append(focus);board.append(heading);
    const viewport=el('div',undefined,'viewport'),stage=el('div',undefined,'stage'),image=el('img');image.src=p.image;image.alt=`Paper ${data.id}, physical page ${p.n}, original render`;image.draggable=false;image.onerror=()=>{$('loading').textContent='Image unavailable. Keep the images folder beside index.html.';};
    const layer=svg('svg',{viewBox:`0 0 ${p.w} ${p.h}`,'aria-label':`${names[panel]} overlays`});stage.append(image,layer);viewport.append(stage);board.append(viewport);
    const isParser=['mineru','layoutlmv3','table_transformer'].includes(panel),isOrder=['baseline','docling','operational'].includes(panel);
    const all=isParser?data.records.filter(r=>r.page===p.n&&r.parser===panel):data.regions.filter(r=>r.page===p.n);
    const visible=all.filter(r=>eligible(r,panel)),byId=new Map(all.map(r=>[r.id,r]));
    // Caption lines use saved relations only, never proximity.
    if($('links').checked){for(const a of data.links.filter(a=>a.page===p.n)){const x=byId.get(a.member),y=byId.get(a.caption);if(!x||!y||!eligible(x,panel)||!eligible(y,panel)||!valid(x,p)||!valid(y,p))continue;const [x1,y1]=center(x),[x2,y2]=center(y);const line=svg('line',{x1,y1,x2,y2,class:'association'});const t=svg('title');t.textContent=`Existing caption association · ${text(a.status)}`;line.append(t);layer.append(line);}}
    const chosen=regions.get(selected),highlight=new Set([selected,...(chosen?.members||[]),chosen?.caption_ref]);
    for(const c of data.correspondences||[]){if(c.sources.includes(selected))for(const id of c.sources)highlight.add(id);}

    if($('boxes').checked)for(const r of visible){if(!valid(r,p))continue;const b=r.bbox,rect=svg('rect',{x:b[0],y:b[1],width:b[2]-b[0],height:b[3]-b[1],stroke:colors.get(val(r,$('dimension').value))||'#6b7280',fill:colors.get(val(r,$('dimension').value))||'#6b7280',class:`unit ${r.kind==='container'?'container':''} ${highlight.has(r.id)?'selected':''}`,tabindex:0,role:'button','aria-label':`${text(val(r,'category'))} · ${text(r.kind)}`});const t=svg('title');t.textContent=`${text(val(r,'category'))} · ${text(val(r,'subtype'))}`;rect.append(t);rect.onclick=()=>choose(r,panel);rect.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(r,panel);}};layer.append(rect);}
    const rows=isOrder?sequence(panel,p):[];
    if(isOrder&&$('arrows').checked){
      const order=data.orders[orderKey(panel)],lookup=new Map(rows.map(x=>[x.s.id,x]));
      const defs=svg('defs');const marker=svg('marker',{id:`arrow-${panel}`,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'});marker.append(svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#22628a'}));defs.append(marker);layer.append(defs);
      // Only draw explicitly exported next_in_route edges. Filtering never creates new edges.
      for(const edge of order.relations){const a=lookup.get(edge.from),b=lookup.get(edge.to);if(!a||!b||!valid(a.r,p)||!valid(b.r,p))continue;const [x1,y1]=center(a.r),[x2,y2]=center(b.r);layer.append(svg('line',{x1,y1,x2,y2,class:'order-line',stroke:'#22628a','marker-end':`url(#arrow-${panel})`}));}
      for(const row of rows){if(!valid(row.r,p))continue;const [cx,cy]=center(row.r),g=svg('g',{class:'number',tabindex:0,role:'button','aria-label':`${text(row.rt)} step ${row.index}`});g.append(svg('circle',{cx,cy,r:20,fill:row.r.id===selected?'#c02683':'#163e60'}));const n=svg('text',{x:cx,y:cy});n.textContent=row.index;g.append(n);g.onclick=()=>choose(row.r,panel);g.onkeydown=e=>{if(e.key==='Enter')choose(row.r,panel);};layer.append(g);}
    }
    const missing=visible.filter(r=>!valid(r,p)&&r.kind!=='group').length;
    let note=`${visible.length} units · ${missing} without drawable geometry`;
    const groupsWithoutBoxes=visible.filter(r=>r.kind==='group'&&!valid(r,p)).length;
    if(groupsWithoutBoxes)note+=` · Logical groups without boxes: ${groupsWithoutBoxes} (references retained in list)`;
    if(isOrder){const stepLookup=new Map(rows.map(row=>[row.s.id,row]));const omitted=data.orders[orderKey(panel)].relations.filter(edge=>{const a=stepLookup.get(edge.from),b=stepLookup.get(edge.to);return a&&b&&(!valid(a.r,p)||!valid(b.r,p));}).length;if(omitted)note+=` · Saved same-page edges without drawable endpoints: ${omitted}`;}
    if(isParser&&$('dimension').value==='function')note+=' · Function not assigned to parser records';
    if(isParser&&$('route').value!=='all')note+=' · Route membership unavailable for independent parser records';
    if(isParser&&$('dimension').value==='subtype')note+=' · Native subtype (not reconciled subtype)';
    if(isParser&&!visible.length)note+=' · No matching native records';
    board.append(el('div',note,'board-note'));$('boards').append(board);
    return {viewport,stage,p,visible,rows,panel};
  }
  let boards=[];
  function fit(){for(const {viewport,stage,p} of boards){const w=Math.max(1,viewport.clientWidth-16),h=Math.max(1,viewport.clientHeight-16);let scale=zoom==='fit'?Math.min(w/p.w,h/p.h):w/p.w*(zoom==='width'?1:Number(zoom));stage.style.width=`${p.w*scale}px`;stage.style.height=`${p.h*scale}px`;}}
  function render(){if(!data)return;const p=data.pages.find(p=>p.n===page);$('page').value=page;$('prev').disabled=page===data.pages[0].n;$('next').disabled=page===data.pages.at(-1).n;
    document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));
    $('notice').textContent=mode==='order'?'Reading v1 vs Docling geometric baseline from this execution. Changes are not verified improvements. Numbers retain their route positions; arrows show saved next-in-route links only.':'Category, subtype and function describe reconciled units. Pink dashed lines show saved caption associations. Semantic validation remains pending; independent parser records keep their native labels.';
    if(p.status==='blocked'||p.incidents.length)$('notice').textContent+=' Page incidents / geometry abstention preserved.';
    $('boards').replaceChildren();const keys=$('panels').value==='all'?panelKeys():$('panels').value.split('+');$('boards').dataset.count=keys.length;boards=keys.map(k=>drawBoard(k,p));
    const first=boards.find(b=>b.panel===activePanel)||boards[0];$('list').replaceChildren();
    const listRows=first.rows.length?first.rows.map(x=>({r:x.r,label:`${text(x.rt)} #${x.index} · ${text(x.s.kind)} · ${text(val(x.r,'category'))}`})):first.visible.map(r=>({r,label:`${text(r.kind)} · ${text(val(r,$('dimension').value))}`}));
    for(const {r,label} of listRows){const b=el('button',label,r.id===selected?'selected':'');b.onclick=()=>choose(r,first.panel);$('list').append(b);}
    showDetail();$('status').textContent=`${data.id}.pdf · Page ${page}/${data.pages.length} · ${p.w} × ${p.h} original pixels · Pink dashed: caption association · Blue arrows: traversal · Read-only`;
    requestAnimationFrame(fit);
  }
  for(const b of document.querySelectorAll('[data-mode]'))b.onclick=()=>{mode=b.dataset.mode;selected=null;activePanel=mode==='order'?'baseline':mode==='operational'?'operational':'reconciled';setPanels();setupFilters();render();};
  $('paper').onchange=()=>{page=1;load();};$('page').onchange=()=>{page=Number($('page').value);selected=null;render();};
  for(const [id,delta] of [['prev',-1],['next',1]])$(id).onclick=()=>{const i=data.pages.findIndex(p=>p.n===page),p=data.pages[i+delta];if(p){page=p.n;selected=null;render();}};
  $('dimension').onchange=()=>{options('value',[['all','All values']],false);setupFilters();render();};
  for(const id of ['value','route','links','arrows','boxes','containers'])$(id).onchange=render;
  $('panels').onchange=()=>{selected=null;activePanel=$('panels').value==='all'?panelKeys()[0]:$('panels').value.split('+')[0];render();};
  $('zoom').onchange=()=>{zoom=$('zoom').value;fit();};
  $('details-toggle').onclick=()=>{document.body.classList.toggle('hide-details');requestAnimationFrame(fit);};
  window.addEventListener('resize',fit);
  $('close-details').onclick=()=>{document.body.classList.add('hide-details');requestAnimationFrame(fit);};
  const ro=new ResizeObserver(fit);ro.observe($('boards'));
  if(innerWidth<1100)document.body.classList.add('hide-details');
  if(!['comparison','classification','order','operational'].includes(mode))mode='comparison';
  setPanels();const params=new URLSearchParams(location.search);if(window.PAPER_IDS.includes(params.get('paper')))$('paper').value=params.get('paper');load();
})();
