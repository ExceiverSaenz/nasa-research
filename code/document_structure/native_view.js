(()=>{'use strict';const $=id=>document.getElementById(id),data=JSON.parse($('native-data').textContent),ns='http://www.w3.org/2000/svg';let page=data.pages[0].n,selected=null;
const byid=new Map(data.units.map(u=>[u.id,u]));
function el(tag,text,cls){const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x;}
function role(u){return u.proposal.decisions.document_role.operational_proposal;}
function conflict(u){return Object.values(u.proposal.decisions).some(d=>d.status==='conflict');}
function visible(u){const f=$('filter').value;return u.page===page&&(f==='all'||f==='role'&&role(u)||f==='conflict'&&conflict(u)||f==='unknown'&&!role(u));}
function choose(id){const u=byid.get(id);if(!u)return;selected=id;page=u.page;$('filter').value='all';render();}
function inspect(u){const d=$('detail');d.replaceChildren();if(!u){d.append(el('p','Select a box or region.'));return;}
 d.append(el('h3',u.id),el('p','Requires human validation · proposals do not alter the baseline.','badge'));
 const table=el('table'),head=el('tr');for(const t of ['Dimension','Previous','Proposal','Status'])head.append(el('th',t));table.append(head);
 for(const [key,decision] of Object.entries(u.proposal.decisions)){const tr=el('tr');const old=key==='flow'?u.proposal.original_route:u.original[key]?.value;for(const v of [key,old??'—',decision.operational_proposal??'Unresolved',decision.status])tr.append(el('td',String(v)));table.append(tr);}d.append(table);
 d.append(el('h3','Retained original text'),el('div',u.original_text||'No text in this unit.','text'),el('h3','Native text aligned for comparison'),el('div',u.link.native_text||'No usable alignment.','text'));
 const membership=data.memberships.find(m=>m.unit_ref===u.id);if(membership){d.append(el('h3','Membership and context'));d.append(el('pre',JSON.stringify(membership,null,2)));}
 for(const [title,value] of [['Alignment and span pointers',u.link],['Decisions, alternatives, and provenance',u.proposal.decisions],['Unapplied native candidates',u.proposal.unapplied_native_candidates],['Inherited warnings',u.proposal.inherited_warnings]]){const details=el('details');details.append(el('summary',title));details.append(el('pre',JSON.stringify(value??[],null,2)));d.append(details);}
 const refs=[...new Set(Object.values(u.proposal.decisions).flatMap(d=>d.claims.flatMap(c=>c.evidence_refs)))].filter(r=>data.evidence[r]);for(const ref of refs){const e=el('details');e.append(el('summary',ref),el('pre',JSON.stringify(data.evidence[ref],null,2)));d.append(e);}
}
function render(){const p=data.pages.find(p=>p.n===page);$('page').value=String(page);$('image').src=p.image;$('image').alt='Page '+page+' original from 12.pdf';$('sheet').style.width=$('zoom').value+'%';$('boxes').setAttribute('viewBox',`0 0 ${p.w} ${p.h}`);$('boxes').replaceChildren();$('list').replaceChildren();const list=data.units.filter(visible);$('count').textContent=list.length+' units on page '+page;
 for(const u of list){const label=(role(u)||u.original.category?.value||'Unresolved')+' · '+u.id.split(':').slice(-2).join(':');const b=el('button',label);b.type='button';b.setAttribute('aria-current',String(u.id===selected));b.addEventListener('click',()=>choose(u.id));$('list').append(b);if(u.bbox){const r=document.createElementNS(ns,'rect'),[x,y,x2,y2]=u.bbox;for(const [k,v] of Object.entries({x,y,width:x2-x,height:y2-y,tabindex:0,role:'button','aria-label':label,class:(conflict(u)?'conflict ':'')+(u.id===selected?'active':'')}))r.setAttribute(k,String(v));r.addEventListener('click',()=>choose(u.id));r.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(u.id);}});const t=document.createElementNS(ns,'title');t.textContent=label;r.append(t);$('boxes').append(r);}}
 inspect(byid.get(selected));$('prev').disabled=page===data.pages[0].n;$('next').disabled=page===data.pages.at(-1).n;
}
for(const p of data.pages){const o=el('option',String(p.n));o.value=String(p.n);$('page').append(o);}
for(const s of data.sections){const b=el('button',s.title+' · '+s.status);b.type='button';b.style.paddingLeft=(8+Math.max(0,(s.declared_level||1)-1)*10)+'px';b.addEventListener('click',()=>{page=s.page||page;selected=s.heading_candidates.length===1?s.heading_candidates[0]:null;render();});$('tree').append(b);}
$('page').addEventListener('change',()=>{page=Number($('page').value);selected=null;render();});for(const id of ['filter','zoom'])$(id).addEventListener('change',render);
for(const [id,delta] of [['prev',-1],['next',1]])$(id).addEventListener('click',()=>{const i=data.pages.findIndex(p=>p.n===page)+delta;if(data.pages[i]){page=data.pages[i].n;selected=null;render();}});render();
})();
