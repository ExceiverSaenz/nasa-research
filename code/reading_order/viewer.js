/* No requests or analysis: list, arrows and boxes read the exported traversal. */
(()=>{
 'use strict';
 const $=id=>document.getElementById(id),data=JSON.parse($('data-model').textContent),ns='http://www.w3.org/2000/svg';
 const units=new Map(data.units.map(u=>[u.id,u])),steps=new Map(data.steps.map(s=>[s.id,s]));
 const names={text:'Texto',title:'Título',figure:'Figura',table:'Tabla',caption:'Caption',equation:'Ecuación',margin:'Margen',other:'Otros',unresolved:'Ambigua'};
 const kinds={content:'Contenido',group:'Grupo',visual_structure:'Figura/tabla',deferred_structure:'Estructura diferida',reference:'Referencia compartida',unlocated_unit:'Sin localización',pending_reference:'Referencia pendiente'};
 let page=data.pages.some(p=>p.n===3)?3:data.pages[0].n,route='main',selected=null,zoom=1,current=[];
 const create=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 function viewSteps(){if(route!=='pending_structures')return data.routes[route].expanded_sequence.map(id=>steps.get(id));return (data.routes[route].unit_refs||[]).map(id=>({id:'pending:'+id,unit_ref:id,page:units.get(id).page,kind:'pending_reference',route,children:[],render_unit_refs:units.get(id).bbox?[id]:[],warnings:units.get(id).classification.warnings,order_basis:'fallback',evidence_status:'abstained'}));}
 function choose(id){const s=steps.get(id);if(s){route=s.route;$('route').value=route;page=s.page;selected=id;render();}}
 function valid(u,p){const b=u?.bbox;return Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&0<=b[0]&&b[0]<b[2]&&b[2]<=p.w&&0<=b[1]&&b[1]<b[3]&&b[3]<=p.h;}
 function position(s,p){const refs=s.render_unit_refs||[];const u=refs.map(id=>units.get(id)).find(u=>valid(u,p));if(!u)return null;return [(u.bbox[0]+u.bbox[2])/2,(u.bbox[1]+u.bbox[3])/2];}
 function detail(){
  const s=current.find(x=>x.id===selected),panel=$('detail');panel.replaceChildren();if(!s){panel.append(create('p','No hay pasos de este recorrido en esta página.'));return;}
  const u=units.get(s.unit_ref),cat=u.classification.category.value||'unresolved';
  panel.append(create('h2',`${kinds[s.kind]||s.kind} · ${names[cat]}`));
  panel.append(create('p',`Página ${s.page} · ${s.order_basis==='fallback'?'Elección provisional':s.order_basis} · ${s.evidence_status==='abstained'?'Evidencia abstendida':'Propuesta sin validar'}`,'small'));
  if(s.warnings?.length){panel.append(create('div','Requiere validación humana · '+[...new Set(s.warnings.map(w=>w.code))].join(' · '),'warning'));}
  if(s.kind==='reference'){
   panel.append(create('p','Referencia al contenido ya visitado; no se lee por segunda vez.'));
   const button=create('button','Ir a primera aparición');button.addEventListener('click',()=>choose(s.content_appearance_ref));panel.append(button);
  }else if(s.kind==='deferred_structure'){
   panel.append(create('p',`${s.deferred_child_refs.length} hijos conservados sin secuencia individual. No se les asigna la caja del padre.`));
   const d=create('details');d.append(create('summary','Ver textos conservados de los hijos (sin orden afirmado)'));
   for(const id of s.deferred_child_refs)d.append(create('p',units.get(id).text||'Sin texto disponible','fragment'));panel.append(d);
  }else if(s.kind==='group'||s.kind==='visual_structure'){
   panel.append(create('p','Entrada estructural: el contenido empieza por el caption y continúa por los cuerpos o paneles, sin cajas nuevas.'));
  }else panel.append(create('p',u.text||'Sin texto nativo disponible.','fragment'));
  if(!u.bbox&&u.kind!=='group')panel.append(create('p','Sin caja propia: no se dibuja una posición inventada.','small'));
  const related=data.relations.filter(r=>r.type==='paragraph_continues'&&(r.from===u.id||r.to===u.id));
  if(related.length)panel.append(create('p','Continuidad de párrafo: '+related.map(r=>r.status).join(' · '),'small'));
  panel.append(create('p',u.id,'small'));
 }
 function render(){
  current=viewSteps();const visible=current.filter(s=>s.page===page);if(!visible.some(s=>s.id===selected))selected=visible[0]?.id||null;
  const p=data.pages.find(p=>p.n===page),active=current.find(s=>s.id===selected),index=current.findIndex(s=>s.id===selected);
  $('page').value=String(page);$('paper').src=p.image;$('paper').alt=`12.pdf · página ${page} · render original`;
  $('position').textContent=index>=0?`${index+1} / ${current.length}`:'Sin pasos';$('previous').disabled=index<=0;$('next').disabled=index<0||index>=current.length-1;
  $('status').textContent=`Página ${page} de ${data.pages.length} · ${visible.length} visitas en esta página · ruta ${$('route').selectedOptions?.[0]?.textContent||route} · ${p.w} × ${p.h} px originales`;
  $('stage').style.width=zoom===1?'100%':`${zoom*100}%`;$('zoom').textContent=zoom===1?'Ajustada':`${Math.round(zoom*100)}%`;
  const svg=$('overlay');svg.setAttribute('viewBox',`0 0 ${p.w} ${p.h}`);svg.replaceChildren();
  const defs=document.createElementNS(ns,'defs'),marker=document.createElementNS(ns,'marker');Object.entries({id:'arrow-end',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'}).forEach(([k,v])=>marker.setAttribute(k,v));
  const tip=document.createElementNS(ns,'path');tip.setAttribute('d','M 0 0 L 10 5 L 0 10 z');tip.setAttribute('fill','#2368b3');marker.append(tip);defs.append(marker);svg.append(defs);
  const drawable=visible.filter(s=>s.kind==='content'||s.kind==='deferred_structure'||s.kind==='unlocated_unit');
  if($('arrows').checked)for(let i=1;i<drawable.length;i++){
   const a=drawable[i-1],b=drawable[i],pa=position(a,p),pb=position(b,p);if(!pa||!pb)continue;
   const line=document.createElementNS(ns,'path');line.setAttribute('d',`M ${pa[0]} ${pa[1]} L ${pb[0]} ${pb[1]}`);line.setAttribute('class','path'+(a.order_basis==='fallback'||b.order_basis==='fallback'?' fallback':''));line.setAttribute('marker-end','url(#arrow-end)');svg.append(line);
  }
  const unitVisits=new Map();for(const s of visible)for(const id of s.render_unit_refs||[])if(!unitVisits.has(id)||s.kind==='content')unitVisits.set(id,s);
  if($('containers').checked)for(const u of units.values())if(u.page===page&&u.kind==='container'&&!unitVisits.has(u.id))unitVisits.set(u.id,null);
  const activeIds=new Set(active?.render_unit_refs||[]);
  for(const [id,s] of unitVisits){const u=units.get(id);if(!valid(u,p))continue;const b=u.bbox,rect=document.createElementNS(ns,'rect');
   Object.entries({x:b[0],y:b[1],width:b[2]-b[0],height:b[3]-b[1],role:'button',tabindex:0,'aria-label':`${names[u.classification.category.value||'unresolved']} ${s?'paso '+(current.indexOf(s)+1):'contenedor'}`}).forEach(([k,v])=>rect.setAttribute(k,String(v)));
   rect.setAttribute('class','box'+(!s?' context':s.order_basis==='fallback'?' fallback':'')+(activeIds.has(id)?' active':''));
   const click=()=>{if(s){selected=s.id;render();}};rect.addEventListener('click',click);rect.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();click();}});svg.append(rect);
   if(s){const text=document.createElementNS(ns,'text');text.setAttribute('x',b[0]+3);text.setAttribute('y',b[1]+Math.max(16,p.w/50));text.setAttribute('class','number');const width=svg.getBoundingClientRect?.().width||800;text.setAttribute('font-size',Math.max(12*p.w/width,16));text.textContent=String(current.indexOf(s)+1);svg.append(text);}
  }
  const list=$('step-list');list.replaceChildren();visible.forEach(s=>{const u=units.get(s.unit_ref),i=current.indexOf(s);const button=create('button',`${i+1}. ${kinds[s.kind]||s.kind} · ${names[u.classification.category.value||'unresolved']}`,'route-step');button.setAttribute('aria-current',s.id===selected?'step':'false');button.append(create('span',s.kind==='content'?(u.text.slice(0,100)||'Objeto visual'):s.order_basis==='fallback'?'Provisional / pendiente':'Estructura o referencia'));button.addEventListener('click',()=>{selected=s.id;render();});list.append(button);});
  detail();
 }
 data.pages.forEach(p=>$('page').add(new Option(String(p.n),p.n)));
 $('page').addEventListener('change',()=>{page=Number($('page').value);selected=null;zoom=1;render();});
 $('route').addEventListener('change',()=>{route=$('route').value;selected=null;render();});
 for(const [id,delta] of [['previous',-1],['next',1]])$(id).addEventListener('click',()=>{const i=current.findIndex(s=>s.id===selected);if(current[i+delta]){selected=current[i+delta].id;page=current[i+delta].page;render();}});
 for(const id of ['arrows','containers'])$(id).addEventListener('change',render);
 $('fit').addEventListener('click',()=>{zoom=1;render();});$('in').addEventListener('click',()=>{zoom=Math.min(3,zoom+.25);render();});$('out').addEventListener('click',()=>{zoom=Math.max(.5,zoom-.25);render();});
 if(typeof window!=='undefined'&&window.matchMedia?.('(max-width:1000px)').matches)$('list-wrap').open=false;
 render();
})();
