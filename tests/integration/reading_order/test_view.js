/* Offline DOM simulation; does not claim browser visual validation. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(process.argv[2],'utf8');
const model=JSON.parse(html.match(/<script id="data-model" type="application\/json">([\s\S]*?)<\/script>/)[1]);
class Element{
 constructor(){this.children=[];this.style={};this.handlers={};this.value='';this.checked=false;this.textContent='';}
 append(...nodes){this.children.push(...nodes);} replaceChildren(...nodes){this.children=[...nodes];}
 add(node){this.append(node);} setAttribute(k,v){this[k]=v;}
 addEventListener(k,v){this.handlers[k]=v;} getBoundingClientRect(){return {width:800};}
 get selectedOptions(){return [{textContent:this.value}];}
 fire(type){this.handlers[type]?.({key:'Enter',preventDefault(){}});}
}
const ids=[...html.matchAll(/id="([^"]+)"/g)].map(m=>m[1]);
const elements=Object.fromEntries(ids.map(id=>[id,new Element()]));
elements['data-model'].textContent=JSON.stringify(model);elements.arrows.checked=true;
const context={document:{getElementById:id=>elements[id],createElement:()=>new Element(),createElementNS:()=>new Element()},Option:function(t,v){this.textContent=t;this.value=v;},window:{matchMedia:()=>({matches:true})}};
vm.runInNewContext(fs.readFileSync(__dirname+'/../../../new_code/reconciliation_system/integration/reading_order/viewer.js','utf8'),context);
let cases=0;
for(const route of Object.keys(model.routes))for(const page of model.pages){
 elements.route.value=route;elements.route.fire('change');elements.page.value=String(page.n);elements.page.fire('change');
 assert.strictEqual(elements.paper.src,page.image);assert.ok(elements.status.textContent.includes(`Página ${page.n}`));
 for(const id of ['containers','arrows']){elements[id].checked=!elements[id].checked;elements[id].fire('change');}
 for(const id of ['in','out','fit'])elements[id].fire('click');
 const buttons=[...elements['step-list'].children];for(const b of buttons)b.fire('click');
 cases++;
}
elements.route.value='main';elements.route.fire('change');elements.page.value=String(model.pages[0].n);elements.page.fire('change');
let visited=0;while(!elements.next.disabled&&visited<=model.steps.length){elements.next.fire('click');visited++;}
assert.ok(visited<=model.steps.length,'navigation must terminate');
assert.ok(elements.next.disabled,'last main step reached');
console.log(JSON.stringify({simulated_page_route_cases:cases,navigation_transitions:visited,visual_browser_validation:false}));
