const fs=require('fs'),vm=require('vm'),assert=require('assert');
class E{constructor(){this.children=[];this.style={};this.handlers={};this.value='';this.checked=true;this.contentWindow={messages:[],postMessage(m){this.messages.push(m);}};}add(e){this.children.push(e);}append(e){this.children.push(e);}addEventListener(k,f){this.handlers[k]=f;}}
const model={pages:[1,3],routes:['main','notes'],comparison:[{page:3,route:'main',content:2,changed_positions:2,reversed_pairs:1,comparable_pairs:1}]};
const els=Object.fromEntries(['comparison-data','baseline','docling','page','route','display','link','stats','rows','panels','baseline-panel','docling-panel'].map(x=>[x,new E()]));els['comparison-data'].textContent=JSON.stringify(model);
const window={handlers:{},addEventListener(k,f){this.handlers[k]=f;}};
vm.runInNewContext(fs.readFileSync(__dirname+'/../../../new_code/reconciliation_system/integration/structure/comparison.js','utf8'),{window,document:{getElementById:id=>els[id],createElement:()=>new E()},Option:function(t,v){this.textContent=t;this.value=v;}});
window.handlers.message({source:els.baseline.contentWindow,data:{kind:'trial-state',page:3,route:'main',step:'s1'}});
assert.strictEqual(els.docling.contentWindow.messages.at(-1).step,'s1');
els.link.checked=false;
window.handlers.message({source:els.baseline.contentWindow,data:{kind:'trial-state',page:3,route:'main',step:'s2'}});
assert.ok(!Object.hasOwn(els.docling.contentWindow.messages.at(-1),'step'),'independent selection must remain unchanged');
window.handlers.message({source:els.docling.contentWindow,data:{kind:'trial-height',height:1200}});assert.strictEqual(els.docling.style.height,'1200px');
els.display.value='docling';els.display.handlers.change();assert.strictEqual(els['baseline-panel'].hidden,true);assert.strictEqual(els['docling-panel'].hidden,false);
console.log('Comparison DOM sync, independent selection, display and height checks passed.');
