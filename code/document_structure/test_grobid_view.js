/* Fixture-only DOM test, never real GROBID output or browser visual QA. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const dim=(before,after,status)=>({B_decision:{operational_proposal:before},C_decision:{operational_proposal:after,status},grobid_claims:[]});
const fixture={paper:'UI fixture — not a paper result',pages:Array.from({length:13},(_,i)=>({n:i+1,w:1000,h:1000,image:`fixture/${i+1}.png`})),routes:['main','parallel'],units:[],evidence:{missing:{text:'unlocated fixture'}},unlocated:[{evidence_ref:'missing',status:'unlocated'}],structure:{section_candidates:[]}};
for(const p of fixture.pages)for(const route of fixture.routes)fixture.units.push({id:`fixture-${p.n}-${route}`,page:p.n,route,bbox:[100,100,450,200],text:'Fixture text',links:[],comparison:{observation:p.n%2?'observed_by_grobid':'not_observed_by_grobid',dimensions:{document_role:dim(null,p.n%2?'body_paragraph':null,p.n===1?'unresolved_conflict':'model_inferred')}}});
const html=process.argv[2]?fs.readFileSync(process.argv[2],'utf8'):fs.readFileSync(__dirname+'/grobid_view.html','utf8');
const data=process.argv[2]?JSON.parse(html.match(/id="grobid-data" type="application\/json">([\s\S]*?)<\/script>/)[1]):fixture;
class E{constructor(){this.children=[];this.style={};this.handlers={};this.value='';}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=[...x];}setAttribute(k,v){this[k]=v;}addEventListener(k,v){this.handlers[k]=v;}fire(k){this.handlers[k]?.({key:'Enter',preventDefault(){}});}}
const els=Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new E()]));els['grobid-data'].textContent=JSON.stringify(data);els.filter.value='all';els.route.value='all';els.mode.value='compare';els.zoom.value='100';
vm.runInNewContext(process.argv[2]?html.match(/<script>([\s\S]*?)<\/script>/)[1]:fs.readFileSync(__dirname+'/grobid_view.js','utf8'),{document:{getElementById:id=>els[id],createElement:()=>new E(),createElementNS:()=>new E()}});
let cases=0,selections=0;
for(const p of data.pages)for(const route of ['all',...data.routes])for(const mode of ['compare','B','C'])for(const filter of ['all','changed','conflict','unobserved'])for(const zoom of ['100','150','200']){
for(const [id,value] of [['page',String(p.n)],['route',route],['mode',mode],['filter',filter],['zoom',zoom]]){els[id].value=value;els[id].fire('change');}
const expected=data.units.filter(u=>u.page===p.n&&(route==='all'||route===u.route)&&(filter==='all'||filter==='changed'&&Object.values(u.comparison.dimensions).some(d=>d.B_decision.operational_proposal!==d.C_decision.operational_proposal)||filter==='conflict'&&Object.values(u.comparison.dimensions).some(d=>d.C_decision.status==='unresolved_conflict')||filter==='unobserved'&&u.comparison.observation==='not_observed_by_grobid'));
assert.strictEqual(els.list.children.length,expected.length);assert.strictEqual(els.image.src,p.image);assert.strictEqual(els.sheet.style.width,zoom+'%');for(const b of [...els.list.children]){b.fire('click');selections++;}if(els.boxes.children[0])els.boxes.children[0].fire('keydown');cases++;
}
for(const b of els.unlocated.children)b.fire('click');assert.ok(els.detail.children.length);
console.log(JSON.stringify({fixture_only:!process.argv[2],page_route_mode_filter_zoom_cases:cases,region_selections:selections,keyboard_selection:true,unlocated_inspection:true,visual_QA:false}));
