/* Offline DOM contract test. Optional argument: exported index.html. */
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const source=process.argv[2];
const fixture={pages:[{n:1,w:1000,h:1400,image:'images/0001.png'},{n:3,w:1000,h:1400,image:'images/0003.png'}],regions:[],groups:[],evidence:[]};
let data=fixture,script=fs.readFileSync(path.join(__dirname,'viewer.js'),'utf8');
if(source){const html=fs.readFileSync(source,'utf8');data=JSON.parse(html.match(/id="data-model" type="application\/json">([\s\S]*?)<\/script>/)[1]);}
class E{
 constructor(t){this.tag=t;this.children=[];this.events={};this.style={};this.attrs={};this.dataset={};this.value='';this.checked=false;this.textContent='';this.classList={toggle(){}};}
 append(...x){this.children.push(...x)}add(x){this.children.push(x)}replaceChildren(...x){this.children=x}setAttribute(k,v){this.attrs[k]=v}addEventListener(k,f){this.events[k]=f}querySelectorAll(t){return this.children.filter(x=>x.tag===t)}
}
const nodes={};for(const id of ['data-model','stage','zoom','detail','overlay','page','prev','next','paper','unit','legend','status','mode','containers','fit','in','out'])nodes[id]=new E(id);
nodes['data-model'].textContent=JSON.stringify(data);
const ctx={document:{getElementById:id=>{assert(nodes[id],id);return nodes[id]},createElement:t=>new E(t),createElementNS:(_,t)=>new E(t),createTextNode:t=>({textContent:t})},Option:function(t,v){this.text=t;this.value=v}};
vm.runInNewContext(script,ctx);
assert.equal(nodes.stage.style.width,'100%');
let checks=0;
for(const p of data.pages)for(const mode of ['category','function'])for(const containers of [false,true]){
 nodes.page.value=String(p.n);nodes.page.events.change();nodes.mode.value=mode;nodes.mode.events.change();nodes.containers.checked=containers;nodes.containers.events.change();
 const expected=data.regions.filter(r=>r.page===p.n&&(r.kind!=='container'||containers)&&Array.isArray(r.bbox)&&r.bbox.every(Number.isFinite)&&0<=r.bbox[0]&&r.bbox[0]<r.bbox[2]&&r.bbox[2]<=p.w&&0<=r.bbox[1]&&r.bbox[1]<r.bbox[3]&&r.bbox[3]<=p.h).length;
 assert.equal(nodes.overlay.children.length,expected);assert.equal(nodes.stage.style.width,'100%');
 if(nodes.overlay.children[0]){nodes.overlay.children[0].events.click();assert(nodes.detail.children.length>=3)}checks++;
}
nodes.in.events.click();assert.equal(nodes.stage.style.width,'125%');nodes.fit.events.click();assert.equal(nodes.stage.style.width,'100%');
for(const g of data.groups){nodes.page.value=String(g.page);nodes.page.events.change();nodes.unit.value=g.id;nodes.unit.events.change();assert(nodes.detail.children.length>=4)}
console.log(JSON.stringify({ui_combinations:checks,original_geometry:true,group_selection:true,default_fit_width:true,zoom:true,execution:'simulated DOM'}));
