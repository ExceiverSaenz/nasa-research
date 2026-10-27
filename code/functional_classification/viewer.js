/* A single reconciled layer. Data are read-only; parsers never become units. */
(() => {
  'use strict';
  const data=JSON.parse(document.getElementById('data-model').textContent);
  const $=id=>document.getElementById(id),svgNS='http://www.w3.org/2000/svg';
  const category={text:'Text',title:'Title',figure:'Figure',table:'Table',caption:'Caption',equation:'Equation',margin:'Margin',other:'Other',unresolved:'Ambiguous'};
  const func={main_body:'Body',metadata:'Metadata',associated_content:'Associated content',editorial:'Editorial',navigation:'Navigation',unresolved:'Unresolved'};
  const colorFor={category:Object.fromEntries(Object.keys(category).map(k=>[k,`var(--${k})`])),function:{main_body:'var(--text)',metadata:'var(--title)',associated_content:'var(--figure)',editorial:'var(--equation)',navigation:'var(--margin)',unresolved:'var(--unresolved)'}};
  const warningText={category_ambiguous:'Ambiguous category',subtype_unresolved:'Pending subtype',function_ambiguous:'Ambiguous function',function_insufficient_evidence:'Insufficient evidence for function',retained_native_category_disagreement:'Difference between reconciled and native category',parser_evidence_category_conflict:'Conflicting parser evidence',retained_group_member_overlap:'Retained member overlap',member_validation_pending:'Members awaiting validation',container_function_unresolved:'Pending container function',geometry_deferred:'Deferred geometry',inherited_page_geometry_abstention:'Retained page geometry abstention',inherited_page_incident:'Retained page incident',unknown_native_class:'Unknown class',retained_classification_abstention:'Retained classification abstention'};
  const subtype={paragraph_candidate:'Candidate paragraph',section_heading_candidate:'Candidate section heading',paper_title:'Paper title',metadata_candidate:'Candidate metadata',bibliographic_reference:'Bibliographic reference',caption_candidate:'Candidate caption',native_caption:'Native caption',label_and_description:'Label and description',display_equation:'Display equation',multipanel_group:'Multipanel group',recurring_margin_candidate:'Candidate recurring margin',header:'Header',footer:'Footer',page_number:'Page number',page_footnote:'Footnote'};
  const regions=new Map(data.regions.map(r=>[r.id,r])), evidence=new Map(data.evidence.map(r=>[r.id,r]));
  let page=data.pages.some(p=>p.n===3)?3:data.pages[0].n,mode='category',zoom=1,selected=null,units=[];
  const create=(tag,text,className)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;};
  const dim=(c,key)=>c[key].value||'unresolved';
  function setZoom(){ $('stage').style.width=zoom===1?'100%':`${zoom*100}%`;$('zoom').textContent=zoom===1?'Fitted':`${Math.round(zoom*100)}%`; }
  function showDetail(){
    const u=units.find(x=>x.id===selected),panel=$('detail');panel.replaceChildren();
    const highlighted=new Set(u?.kind==='group'?u.members:[selected]);
    $('overlay').querySelectorAll('rect').forEach(r=>r.classList.toggle('active',highlighted.has(r.dataset.id)));
    if(!u){panel.append(create('p','There are no objects on this page.'));return;}
    const c=u.classification;
    panel.append(create('h2',`${category[dim(c,'category')]} · ${func[dim(c,'function')]}`));
    panel.append(create('p',`Retained category: ${u.retained_category||Object.values(c.retained_classification?.member_categories||{}).join(' / ')||'See members'}`,'label'));
    if(c.category.candidates.length>1)panel.append(create('p','Candidate categories: '+c.category.candidates.map(x=>category[x]||x).join(' / ')));
    if(c.function.value===null)panel.append(create('p','Candidate functions: '+(c.function.candidates.map(x=>func[x]||x).join(' / ')||'Pending')));
    const st=c.subtype.value?[c.subtype.value]:c.subtype.candidates;
    panel.append(create('p','Subtype: '+(st.map(x=>subtype[x]||x).join(' / ')||'Pending'),'label'));
    if(c.warnings.length){const warning=create('div',undefined,'warning-text');warning.append(create('strong','Requires human validation'));warning.append(create('div',c.warnings.map(w=>warningText[w.code]||w.code).join(' · ')));panel.append(warning);}
    panel.append(create('p','Automatic proposal · semantic validation pending','label'));
    if(u.kind==='group'){
      panel.append(create('p',`${u.members.length} members · original boxes, no new enclosing box`));
      const caption=regions.get(u.caption_ref);if(caption)panel.append(create('p',caption.text||'Caption without available text','text'));
    }else panel.append(create('p',u.text||'No native text available.','text'));
    const detail=create('details');detail.append(create('summary','Evidence and provenance'));
    const body=create('div',undefined,'evidence');
    body.append(create('p','Reconciliation category and status: '+JSON.stringify(c.retained_classification)));
    (c.parser_evidence||[]).forEach(e=>{const r=evidence.get(e.record_ref);body.append(create('p',`${r?.parser||'Source'} · ${e.retained_source_category} · ${e.kind}`));});
    body.append(create('p',`${c.reconciliation_decision_refs?.length||0} related previous decisions`));
    body.append(create('p','Rules: '+c.rule_refs.join(', ')));body.append(create('p',u.id));detail.append(body);panel.append(detail);
  }
  function draw(){
    const p=data.pages.find(p=>p.n===page),all=data.regions.filter(r=>r.page===page);
    const visible=all.filter(r=>r.kind!=='container'||$('containers').checked);
    visible.sort((a,b)=>(a.bbox?.[1]??Infinity)-(b.bbox?.[1]??Infinity)||a.id.localeCompare(b.id));
    units=[...data.groups.filter(g=>g.page===page).map(g=>({...g,kind:'group'})),...visible];
    if(!units.some(x=>x.id===selected))selected=units.find(x=>x.kind!=='group')?.id||units[0]?.id||null;
    $('page').value=String(page);$('prev').disabled=page===data.pages[0].n;$('next').disabled=page===data.pages.at(-1).n;
    $('paper').src=p.image;$('paper').alt=`12.pdf · physical page ${page} · original image`;
    $('overlay').setAttribute('viewBox',`0 0 ${p.w} ${p.h}`);$('overlay').replaceChildren();$('unit').replaceChildren();
    units.forEach((u,i)=>$('unit').add(new Option(`${u.kind==='group'?'Group':u.kind==='container'?'Container':'Region'} ${i+1} · ${category[dim(u.classification,'category')]}${u.classification.warnings.length?' ⚠':''}`,u.id)));
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
    $('status').textContent=`Page ${page} of ${data.pages.length} · ${all.filter(r=>r.kind!=='container').length} reconciled regions · ${all.filter(r=>r.kind==='container').length} containers · ${data.groups.filter(g=>g.page===page).length} groups · ${p.w} × ${p.h} original px`;
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
