/* Minimal DOM execution, not browser/visual QA. Optional exported HTML argument. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const decision=(v,status='retained_unvalidated')=>({operational_proposal:v,status,claims:[]});
const fixture={pages:[{n:1,w:1000,h:1000,image:'one.png'},{n:2,w:1000,h:1000,image:'two.png'}],sections:[{title:'Results',page:1,declared_level:1,heading_candidates:['u'],status:'aligned_unique'}],memberships:[],continuities:[],evidence:{},units:[{id:'u',page:1,bbox:[10,10,400,200],original:{category:{value:'title'}},original_text:'Results',link:{native_text:'Results'},proposal:{original_route:'main',inherited_warnings:[],decisions:{category:decision('title'),document_role:decision('section_heading','direct_supported')}}},{id:'v',page:2,bbox:null,original:{category:{value:'text'}},link:{native_text:''},proposal:{original_route:'main',inherited_warnings:[],decisions:{category:decision('text'),document_role:decision(null),function:decision('metadata','conflict')}}}]};
const html=process.argv[2]?fs.readFileSync(process.argv[2],'utf8'):fs.readFileSync(__dirname+'/native_view.html','utf8');
const model=process.argv[2]?JSON.parse(html.match(/id="native-data">([\s\S]*?)<\/script>/)[1]):fixture;
class E{constructor(){this.children=[];this.style={};this.handlers={};this.value='';this.textContent='';}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=[...x];}setAttribute(k,v){this[k]=v;}addEventListener(k,f){this.handlers[k]=f;}fire(k){this.handlers[k]?.({key:'Enter',preventDefault(){}});}}
const els=Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new E()]));els['native-data'].textContent=JSON.stringify(model);els.filter.value='all';els.zoom.value='100';
const script=process.argv[2]?html.match(/<script>([\s\S]*?)<\/script>/)[1]:fs.readFileSync(__dirname+'/native_view.js','utf8');
vm.runInNewContext(script,{document:{getElementById:id=>els[id],createElement:()=>new E(),createElementNS:()=>new E()}});
let cases=0,selections=0;
for(const page of model.pages)for(const filter of ['all','role','conflict','unknown'])for(const zoom of ['100','150','200']){
 els.page.value=String(page.n);els.page.fire('change');els.filter.value=filter;els.filter.fire('change');els.zoom.value=zoom;els.zoom.fire('change');
 assert.strictEqual(els.image.src,page.image);assert.strictEqual(els.sheet.style.width,zoom+'%');
 const expected=model.units.filter(u=>u.page===page.n&&(filter==='all'||filter==='role'&&u.proposal.decisions.document_role.operational_proposal||filter==='unknown'&&!u.proposal.decisions.document_role.operational_proposal||filter==='conflict'&&Object.values(u.proposal.decisions).some(d=>d.status==='conflict')));
 assert.strictEqual(els.list.children.length,expected.length);assert.strictEqual(els.boxes.children.length,expected.filter(u=>u.bbox).length);
 for(const b of [...els.list.children]){b.fire('click');selections++;}cases++;
}
for(const b of els.tree.children)b.fire('click');
els.page.value=String(model.pages[0].n);els.page.fire('change');els.filter.value='all';els.filter.fire('change');if(els.boxes.children[0])els.boxes.children[0].fire('keydown');
assert.ok(els.detail.children.length>0);els.next.fire('click');assert.strictEqual(els.image.src,model.pages[1].image);els.prev.fire('click');assert.strictEqual(els.image.src,model.pages[0].image);
console.log(JSON.stringify({page_filter_zoom_cases:cases,region_selections:selections,section_links:model.sections.length,keyboard_selection:true,visual_QA:false}));
