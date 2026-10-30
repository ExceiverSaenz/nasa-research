'use strict';
// Runs presentation logic without a browser. This is not visual/layout QA.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=__dirname,html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const script=fs.readFileSync(path.join(root,'viewer.js'),'utf8');
const payload=fs.readFileSync(path.join(root,'data/12.js'),'utf8');
const data=JSON.parse(payload.slice(payload.indexOf('(')+1,payload.lastIndexOf(')')));
class E {
  constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.attrs={};this.style={};this.checked=false;this.disabled=false;this.clientWidth=800;this.clientHeight=900;this._value='';this._text='';this.className='';const self=this;this.classList={contains:c=>self.className.split(' ').includes(c),toggle(c,force){const set=new Set(self.className.split(' ').filter(Boolean));const on=force??!set.has(c);if(on)set.add(c);else set.delete(c);self.className=[...set].join(' ');return on;},add(c){this.toggle(c,true);}};}
  set value(v){this._value=String(v);}get value(){return this._value;}
  set textContent(v){this._text=String(v);this.children=[];}get textContent(){return this._text+this.children.map(c=>c.textContent||'').join('');}
  append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children=nodes;this._text='';if(this.tag==='select')this._value='';}
  add(o){this.children.push(o);if(this.children.length===1)this.value=o.value;}
  setAttribute(k,v){this.attrs[k]=String(v);if(k==='class')this.className=String(v);}
}
function descendants(e){return [e,...e.children.flatMap(descendants)];}
let checks=0;
function ok(condition,label){assert.ok(condition,label);checks++;}
function create(width=1440,start='comparison'){
 const nodes={};for(const m of html.matchAll(/<([a-z]+)[^>]*\bid="([^"]+)"[^>]*>/g))nodes[m[2]]=new E(m[1]);
 for(const m of html.matchAll(/<select[^>]*\bid="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)){for(const o of m[2].matchAll(/<option value="([^"]*)"[^>]*>(.*?)<\/option>/g)){const e=new E('option');e.value=o[1];e.textContent=o[2];nodes[m[1]].add(e);}}
 for(const name of ['links','arrows','boxes'])nodes[name].checked=true;
 const modes=['comparison','classification','order','operational'].map(mode=>{const e=new E('button');e.dataset.mode=mode;return e;});
 const events={};let context;
 const document={body:new E('body'),head:new E('head'),getElementById:id=>{assert.ok(nodes[id],id);return nodes[id];},createElement:t=>new E(t),createElementNS:(_,t)=>new E(t),createTextNode:t=>{const e=new E('text');e.textContent=t;return e;},querySelectorAll:selector=>selector==='[data-mode]'?modes:[]};
 document.head.append=e=>{if(e.tag==='script'){ok(e.src==='data/12.js','only current paper payload requested');vm.runInContext(payload,context);}};
 const window={START_MODE:start,PAPER_IDS:['12'],addEventListener:(event,fn)=>events[event]=fn};
 context=vm.createContext({window,document,innerWidth:width,location:{search:''},URLSearchParams,Option:function(t,v){const e=new E('option');e.value=v;e.textContent=t;return e;},requestAnimationFrame:fn=>fn(),ResizeObserver:class{observe(){}},console});
 vm.runInContext(script,context);
 const mode=name=>modes.find(e=>e.dataset.mode===name).onclick();
 const change=(name,value)=>{nodes[name].value=value;nodes[name].onchange();};
 return {nodes,context,events,document,mode,change};
}

for(const width of [390,768,1440,1920]){
 const app=create(width),n=app.nodes;
 ok(n.attempt.textContent.includes('20261030T040105Z-4215756a'),'current run displayed');
 ok(n.page.children.length===13,'13 page options');
 ok(n.boards.children.length===(width<760?2:4),'mobile comparison pair / desktop native panels');
 for(const mode of ['comparison','classification','order','operational']){
  app.mode(mode);
  for(let page=1;page<=13;page++){
   app.change('page',page);
   ok(n.status.textContent.includes(`Page ${page}/13`),`${mode} page ${page} status`);
   ok(n.boards.children.every(b=>descendants(b).filter(e=>e.tag==='img').every(i=>i.src===`images/${String(page).padStart(4,'0')}.png`)),'all panels use this page image');
   const boardCount=mode==='comparison'?(width<760?2:4):mode==='order'?2:1;
   ok(n.boards.children.length===boardCount,'stage panel count');
   ok(descendants(n.boards).filter(e=>e.tag==='rect').every(e=>Object.values(e.attrs).every(v=>!v.includes('NaN'))),'finite boxes');
  }
 }
 // Toggling order graphics must not discard the saved step list.
 app.mode('operational');app.change('page',1);
 const steps=n.list.children.map(e=>e.textContent);
 ok(steps.some(t=>t.includes('#')),'saved route positions displayed');
 n.arrows.checked=false;n.arrows.onchange();
 assert.deepEqual(n.list.children.map(e=>e.textContent),steps,'hiding arrows must retain traversal list');checks++;
 n.arrows.checked=true;n.arrows.onchange();
 for(const mode of ['order','operational']){
  app.mode(mode);app.change('page',5);
  for(const board of n.boards.children){
   const note=descendants(board).find(e=>e.className==='board-note').textContent;
   ok(note.includes('Logical groups without boxes: 1'),'page 5 group without geometry is disclosed');
   ok(note.includes('Saved same-page edges without drawable endpoints: 2'),'omitted group edges are disclosed, not reconnected');
  }
 }
 app.mode('comparison');app.change('page',1);app.change('panels','mineru');
 n.list.children[0].onclick();
 ok(n.detail.textContent.startsWith('MinerU'),'parser inspector keeps native context for shared IDs');
 ok(!n.detail.textContent.includes('Classification evidence and alternatives'),'native records are not labeled as reconciled');
 app.change('panels','reconciled');
 ok(n.detail.textContent.startsWith('Select a box'),'switching panels clears stale native inspection');
 n.list.children[0].onclick();
 ok(n.detail.textContent.startsWith('Reconciled unit'),'reconciled inspector uses classification');
 app.change('dimension','category');app.change('value','table');
 ok(n.list.children.every(e=>e.textContent.includes('Table')),'category filter respects reconciled values');
 app.change('value','all');app.change('panels','reconciled+mineru');
 app.events.resize();ok(n.boards.children.length===2,'resize preserves selected comparison pair');
 n['close-details'].onclick();ok(app.document.body.classList.contains('hide-details'),'inspection can be dismissed on mobile');
 app.change('zoom','2');ok(descendants(n.boards).filter(e=>e.className==='stage').every(e=>parseFloat(e.style.width)>0),'zoom updates stage geometry');
 app.change('page',1);ok(n.prev.disabled,'previous disabled on first page');app.change('page',13);ok(n.next.disabled,'next disabled on last page');
}
const report={passed:true,checks,widths_simulated:[390,768,1440,1920],pages:13,modes:4,DOM_simulation:true,visual_QA:false};
fs.writeFileSync(path.join(root,'ui-test-results.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
