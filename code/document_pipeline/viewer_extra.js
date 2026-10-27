 /* Extension of the immutable reading viewer; this only reads exported data. */
 const operationalVersion={steps:data.steps,routes:data.routes,relations:data.relations};
 const originalDetail=detail;
 detail=function(){
  originalDetail();const step=current.find(x=>x.id===selected);if(!step)return;const id=step.unit_ref,sem=data.semantics[id],membership=data.structure.memberships.find(m=>m.unit_ref===id),panel=$('detail');
  panel.append(create('p','Proposed structural layer · '+($('order-mode').value==='baseline'?'baseline traversal':'operational traversal')+' · without semantic validation','small'));
  if(membership){const section=data.structure.sections.find(s=>s.id===membership.section_ref);panel.append(create('p','Physical context: '+(section?.title||'Unresolved')+' · '+membership.status,'small'));}
  const details=create('details');details.append(create('summary','Function, hierarchy, native evidence, and alternatives'));details.append(create('pre',JSON.stringify({semantics:sem,membership,native_alignment:data.native_links[id]},null,2)));panel.append(details);
 };
 for(const section of data.structure.sections){const button=create('button',section.title+' · '+section.status);button.style.paddingLeft=(8+Math.max(0,(section.level||1)-1)*10)+'px';button.addEventListener('click',()=>{const unit=units.get(section.heading_ref);if(unit?.appearance_ref)choose(unit.appearance_ref);else $('detail').replaceChildren(create('pre',JSON.stringify(section,null,2)));});$('sections-tree').append(button);}
 $('order-mode').addEventListener('change',()=>{const version=$('order-mode').value==='baseline'?data.baseline:operationalVersion;steps.clear();for(const s of version.steps)steps.set(s.id,s);data.routes=version.routes;data.relations=version.relations;selected=null;render();});
