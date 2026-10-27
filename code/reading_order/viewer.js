/* No requests or analysis: list, arrows and boxes read the exported traversal. */
(()=>{
 'use strict';
 const $=id=>document.getElementById(id),data=JSON.parse($('data-model').textContent),ns='http://www.w3.org/2000/svg';
 const units=new Map(data.units.map(u=>[u.id,u])),steps=new Map(data.steps.map(s=>[s.id,s]));
 const names={text:'Text',title:'Title',figure:'Figure',table:'Table',caption:'Caption',equation:'Equation',margin:'Margin',other:'Other',unresolved:'Ambiguous'};
 const kinds={content:'Content',group:'Group',visual_structure:'Figure/tabla',deferred_structure:'Deferred structure',reference:'Shared reference',unlocated_unit:'Unlocated',pending_reference:'Pending reference'};
 let page=data.pages.some(p=>p.n===3)?3:data.pages[0].n,route='main',selected=null,zoom=1,current=[];
 const create=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 function viewSteps(){if(route!=='pending_structures')return data.routes[route].expanded_sequence.map(id=>steps.get(id));return (data.routes[route].unit_refs||[]).map(id=>({id:'pending:'+id,unit_ref:id,page:units.get(id).page,kind:'pending_reference',route,children:[],render_unit_refs:units.get(id).bbox?[id]:[],warnings:units.get(id).classification.warnings,order_basis:'fallback',evidence_status:'abstained'}));}
 function choose(id){const s=steps.get(id);if(s){route=s.route;$('route').value=route;page=s.page;selected=id;render();}}
 function valid(u,p){const b=u?.bbox;return Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&0<=b[0]&&b[0]<b[2]&&b[2]<=p.w&&0<=b[1]&&b[1]<b[3]&&b[3]<=p.h;}
 function position(s,p){const refs=s.render_unit_refs||[];const u=refs.map(id=>units.get(id)).find(u=>valid(u,p));if(!u)return null;return [(u.bbox[0]+u.bbox[2])/2,(u.bbox[1]+u.bbox[3])/2];}
 function detail(){
  const s=current.find(x=>x.id===selected),panel=$('detail');panel.replaceChildren();if(!s){panel.append(create('p','There are no steps for this traversal on this page.'));return;}
  const u=units.get(s.unit_ref),cat=u.classification.category.value||'unresolved';
  panel.append(create('h2',`${kinds[s.kind]||s.kind} · ${names[cat]}`));
  panel.append(create('p',`Page ${s.page} · ${s.order_basis==='fallback'?'Provisional choice':s.order_basis} · ${s.evidence_status==='abstained'?'Abstained evidence':'Unvalidated proposal'}`,'small'));
  if(s.warnings?.length){panel.append(create('div','Requires human validation · '+[...new Set(s.warnings.map(w=>w.code))].join(' · '),'warning'));}
  if(s.kind==='reference'){
   panel.append(create('p','Reference to previously visited content; it is not read a second time.'));
   const button=create('button','Go to first appearance');button.addEventListener('click',()=>choose(s.content_appearance_ref));panel.append(button);
  }else if(s.kind==='deferred_structure'){
   panel.append(create('p',`${s.deferred_child_refs.length} children retained without an individual sequence. They are not assigned their parent's box.`));
   const d=create('details');d.append(create('summary','View retained child text (without asserted order)'));
   for(const id of s.deferred_child_refs)d.append(create('p',units.get(id).text||'No text available','fragment'));panel.append(d);
  }else if(s.kind==='group'||s.kind==='visual_structure'){
   panel.append(create('p','Structural entry: content starts with the caption and continues through bodies or panels, without new boxes.'));
  }else panel.append(create('p',u.text||'No native text available.','fragment'));
  if(!u.bbox&&u.kind!=='group')panel.append(create('p','No own box: no invented position is drawn.','small'));
  const related=data.relations.filter(r=>r.type==='paragraph_continues'&&(r.from===u.id||r.to===u.id));
  if(related.length)panel.append(create('p','Paragraph continuity: '+related.map(r=>r.status).join(' · '),'small'));
  panel.append(create('p',u.id,'small'));
 }
 function render(){
  current=viewSteps();const visible=current.filter(s=>s.page===page);if(!visible.some(s=>s.id===selected))selected=visible[0]?.id||null;
  const p=data.pages.find(p=>p.n===page),active=current.find(s=>s.id===selected),index=current.findIndex(s=>s.id===selected);
  $('page').value=String(page);$('paper').src=p.image;$('paper').alt=`12.pdf · page ${page} · original render`;
  $('position').textContent=index>=0?`${index+1} / ${current.length}`:'No steps';$('previous').disabled=index<=0;$('next').disabled=index<0||index>=current.length-1;
  $('status').textContent=`Page ${page} of ${data.pages.length} · ${visible.length} visits on this page · route ${$('route').selectedOptions?.[0]?.textContent||route} · ${p.w} × ${p.h} original px`;
  $('stage').style.width=zoom===1?'100%':`${zoom*100}%`;$('zoom').textContent=zoom===1?'Fitted':`${Math.round(zoom*100)}%`;
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
   Object.entries({x:b[0],y:b[1],width:b[2]-b[0],height:b[3]-b[1],role:'button',tabindex:0,'aria-label':`${names[u.classification.category.value||'unresolved']} ${s?'step '+(current.indexOf(s)+1):'container'}`}).forEach(([k,v])=>rect.setAttribute(k,String(v)));
   rect.setAttribute('class','box'+(!s?' context':s.order_basis==='fallback'?' fallback':'')+(activeIds.has(id)?' active':''));
   const click=()=>{if(s){selected=s.id;render();}};rect.addEventListener('click',click);rect.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();click();}});svg.append(rect);
   if(s){const text=document.createElementNS(ns,'text');text.setAttribute('x',b[0]+3);text.setAttribute('y',b[1]+Math.max(16,p.w/50));text.setAttribute('class','number');const width=svg.getBoundingClientRect?.().width||800;text.setAttribute('font-size',Math.max(12*p.w/width,16));text.textContent=String(current.indexOf(s)+1);svg.append(text);}
  }
  const list=$('step-list');list.replaceChildren();visible.forEach(s=>{const u=units.get(s.unit_ref),i=current.indexOf(s);const button=create('button',`${i+1}. ${kinds[s.kind]||s.kind} · ${names[u.classification.category.value||'unresolved']}`,'route-step');button.setAttribute('aria-current',s.id===selected?'step':'false');button.append(create('span',s.kind==='content'?(u.text.slice(0,100)||'Visual object'):s.order_basis==='fallback'?'Provisional / pending':'Structure or reference'));button.addEventListener('click',()=>{selected=s.id;render();});list.append(button);});
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
