(()=>{'use strict';const $=id=>document.getElementById(id),data=JSON.parse($('grobid-data').textContent),ns='http://www.w3.org/2000/svg';let page=data.pages[0].n,selected=null;
function el(tag,text){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;}
function conflict(u){return Object.values(u.comparison.dimensions).some(d=>d.C_decision.status==='unresolved_conflict');}
function changed(u){return Object.values(u.comparison.dimensions).some(d=>d.B_decision.operational_proposal!==d.C_decision.operational_proposal);}
function visible(u){const f=$('filter').value;return u.page===page&&($('route').value==='all'||$('route').value===u.route)&&(f==='all'||f==='changed'&&changed(u)||f==='conflict'&&conflict(u)||f==='unobserved'&&u.comparison.observation==='not_observed_by_grobid');}
function inspect(u){const d=$('detail');d.replaceChildren();if(!u){d.append(el('p','Select a region or evidence.'));return;}d.append(el('h3',u.id),el('p','Requires human validation · baseline unchanged.'));
 const t=el('table'),h=el('tr'),mode=$('mode').value;h.append(el('th','Dimension'));if(mode!=='C')h.append(el('th','B'));if(mode!=='B')h.append(el('th','C'));h.append(el('th','C status'));t.append(h);
 for(const [dim,value] of Object.entries(u.comparison.dimensions)){const r=el('tr');r.append(el('td',dim));if(mode!=='C')r.append(el('td',String(value.B_decision.operational_proposal??'Unresolved')));if(mode!=='B')r.append(el('td',String(value.C_decision.operational_proposal??'Unresolved')));r.append(el('td',value.C_decision.status));t.append(r);}d.append(t,el('h3','Retained original text'),el('pre',u.text));
 for(const [label,value] of [['Decisions, alternatives, and claims',u.comparison],['Matches / fragments',u.links]]){const x=el('details');x.append(el('summary',label),el('pre',JSON.stringify(value,null,2)));d.append(x);}
 for(const id of new Set(u.links.map(l=>l.evidence_ref))){const x=el('details');x.append(el('summary',id),el('pre',JSON.stringify(data.evidence[id],null,2)));d.append(x);}
}
function choose(u){selected=u.id;render();}
function render(){const p=data.pages.find(p=>p.n===page);$('page').value=String(page);$('image').src=p.image;$('sheet').style.width=$('zoom').value+'%';$('boxes').setAttribute('viewBox',`0 0 ${p.w} ${p.h}`);$('boxes').replaceChildren();$('list').replaceChildren();const units=data.units.filter(visible);$('count').textContent=units.length+' units';
 for(const u of units){const title=u.id+' · '+(changed(u)?'change':conflict(u)?'conflict':'retained');const b=el('button',title);b.type='button';b.setAttribute('aria-current',String(u.id===selected));b.addEventListener('click',()=>choose(u));$('list').append(b);if(u.bbox){const r=document.createElementNS(ns,'rect'),[x,y,x2,y2]=u.bbox;for(const [k,v] of Object.entries({x,y,width:x2-x,height:y2-y,tabindex:0,role:'button','aria-label':title,class:(conflict(u)?'conflict ':'')+(u.id===selected?'active':'')}))r.setAttribute(k,String(v));r.addEventListener('click',()=>choose(u));r.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(u);}});$('boxes').append(r);}}
 inspect(data.units.find(u=>u.id===selected&&u.page===page));
}
$('paper-name').textContent=data.paper;for(const p of data.pages){const o=el('option',String(p.n));o.value=String(p.n);$('page').append(o);}for(const rt of data.routes){const o=el('option',rt);o.value=rt;$('route').append(o);}
for(const l of data.unlocated){const b=el('button',l.evidence_ref+' · '+l.status);b.addEventListener('click',()=>{$('detail').replaceChildren(el('pre',JSON.stringify({alignment:l,evidence:data.evidence[l.evidence_ref]},null,2)));});$('unlocated').append(b);}
$('structure').textContent=JSON.stringify(data.structure,null,2);for(const id of ['page','route','mode','filter','zoom'])$(id).addEventListener('change',()=>{if(id==='page'){page=Number($('page').value);selected=null;}render();});render();
})();
