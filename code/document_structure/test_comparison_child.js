/* Execute actual exported child scripts in a minimal DOM; not browser visual QA. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(process.argv[2],'utf8'),model=JSON.parse(html.match(/<script id="data-model" type="application\/json">([\s\S]*?)<\/script>/)[1]);
class E{
 constructor(){this.children=[];this.style={};this.handlers={};this.value='';this.checked=false;this.textContent='';}
 append(...x){this.children.push(...x);}replaceChildren(...x){this.children=[...x];}add(x){this.append(x);}setAttribute(k,v){this[k]=v;}
 addEventListener(k,v){this.handlers[k]=v;}getBoundingClientRect(){return {width:800,height:1000};}get selectedOptions(){return [{textContent:this.value}];}
 fire(k){this.handlers[k]?.({key:'Enter',preventDefault(){}});}
}
const els=Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new E()]));els['data-model'].textContent=JSON.stringify(model);els.arrows.checked=true;
const window={handlers:{},matchMedia:()=>({matches:true}),addEventListener(k,f){this.handlers[k]=f;}};window.parent=window;
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
vm.runInNewContext(script,{window,document:{body:new E(),getElementById:id=>els[id],createElement:()=>new E(),createElementNS:()=>new E()},Option:function(t,v){this.textContent=t;this.value=v;}});
let cases=0;
for(const route of Object.keys(model.routes))for(const page of model.pages){
 els.route.value=route;els.route.fire('change');els.page.value=String(page.n);els.page.fire('change');assert.strictEqual(els.paper.src,page.image);
 for(const button of [...els['step-list'].children])button.fire('click');
 cases++;
}
let messages=[];window.parent={postMessage(m){messages.push(m);}};
const route='main',page=model.pages[0].n,step=model.routes.main.expanded_sequence.find(id=>model.steps.find(s=>s.id===id).page===page);
window.handlers.message({source:window.parent,data:{kind:'trial-control',page,route,step}});assert.strictEqual(messages.length,0,'remote sync must not echo');
const selectedText=els.position.textContent;
window.handlers.message({source:window.parent,data:{kind:'trial-control',page,route}});assert.strictEqual(els.position.textContent,selectedText,'missing step must preserve selection');
els.next.fire('click');assert.ok(messages.some(m=>m.kind==='trial-state'),'local navigation must notify parent');
console.log(JSON.stringify({page_route_cases:cases,remote_no_echo:true,independent_selection_preserved:true,visual_QA:false}));
