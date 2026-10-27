/* Offline data/filter tests. No browser or parser execution. */
const assert = require('node:assert/strict');
const ui = require('./comparison_view.js');
const fs = require('node:fs');
const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const state = {boxes:true, containers:false, historical:false, alternatives:false,
  types:new Set(ui.TYPES.map(x=>x[0]))};
for (const page of data.pages) {
  const original = JSON.stringify(page);
  for (const view of ['reconciled','mineru','tatr','lm']) {
    assert.equal(ui.visibleRegions(page,view,state).length,
      page.views[view].filter(x=>x.layer!=='container').length);
    assert.equal(ui.visibleRegions(page,view,{...state,boxes:false}).length,0);
  }
  assert.equal(ui.visibleRegions(page,'reconciled',{...state,containers:true}).length,
    page.views.reconciled.length);
  assert.equal(ui.visibleRegions(page,'reconciled',{...state,alternatives:true}).length,
    page.views.reconciled.filter(x=>x.layer!=='container').length+page.views.lm.length+page.views.tatr.length);
  assert.equal(ui.visibleRegions(page,'reconciled',{...state,historical:true}).length,
    page.views.reconciled.filter(x=>x.layer!=='container').length+page.historical.length);
  const textOnly = ui.visibleRegions(page,'mineru',{...state,types:new Set(['text'])});
  assert(textOnly.every(x=>ui.category(x.type)==='text'));
  for (const edge of ui.groupEdges(page)) assert(edge.from.length===2 && edge.to.length===2);
  assert.equal(JSON.stringify(page),original);
}
assert.equal(data.pages.flatMap(ui.groupEdges).length,14);
assert.equal(ui.category('paragraph_title'),'title');
assert.equal(ui.category('table_body'),'table');
assert.equal(ui.category('page_number'),'margin');
assert.equal(ui.pageNumber(-1,13),1);
assert.equal(ui.pageNumber(99,13),13);
assert.equal(ui.pageNumber(8,13),8);
console.log('UI logic: 13 pages, 4 views, filters, alternatives, history, 14 group links, no data mutation: PASS');

// Minimal DOM unit harness: exercises event wiring without launching a browser.
const vm = require('node:vm');
class Node {
  constructor(tag='div') { this.tagName=tag.toUpperCase();this.children=[];this.events={};this.dataset={};this.attrs={};
    this.style={setProperty(k,v){this[k]=v;}};this.textContent='';this.className='';
    this.scrollTop=0;this.scrollLeft=0;this.scrollHeight=1600;this.scrollWidth=900;this.clientHeight=600;this.clientWidth=400; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children=nodes; }
  setAttribute(k,v) { this.attrs[k]=v;if(k==='class')this.className=v; }
  addEventListener(k,fn) { (this.events[k]??=[]).push(fn); }
  emit(k,event={}) { for(const fn of this.events[k]||[])fn({target:this,currentTarget:this,...event}); }
  all() { return this.children.flatMap(x=>x instanceof Node?[x,...x.all()]:[]); }
  querySelector(selector) { return this.all().find(x=>x.className.split(' ').includes(selector.slice(1)))||null; }
  getBoundingClientRect() { return {width:800}; }
  scrollTo({left,top}) { this.scrollLeft=left;this.scrollTop=top; }
}
const ids=['view-data','page','prev','next','all','zoom','zoomValue','viewOptions','types','boxes','labels',
  'containers','groups','historical','alternatives','clear','detail','detailTitle','summary','outline','groupList','warnings','panes'];
const nodes=new Map(ids.map(x=>[x,new Node()]));nodes.get('view-data').textContent=JSON.stringify(data);
const documentStub={events:{},getElementById:id=>nodes.get(id),createElement:tag=>new Node(tag),
  createElementNS:(_,tag)=>new Node(tag),createTextNode:text=>{const n=new Node('#text');n.textContent=text;return n;},
  addEventListener(k,fn){this.events[k]=fn;},
  all(){return [...nodes.values()].flatMap(n=>n.all());},
  querySelectorAll(selector){return this.all().filter(n=>n.className.split(' ').includes(selector.slice(1)));},
  querySelector(selector){const match=selector.match(/^\[data-view="([^"]+)"\] (.+)$/);
    if(match){const parent=this.all().find(x=>x.dataset.view===match[1]);return parent?.querySelector(match[2])||null;}
    return this.querySelectorAll(selector)[0]||null;}};
vm.runInNewContext(fs.readFileSync(require.resolve('./comparison_view.js'),'utf8'),
  {document:documentStub,requestAnimationFrame:fn=>fn(),console});
const at=id=>nodes.get(id);
assert.equal(at('panes').children.length,4);
assert.equal(at('page').children.length,13);
assert.equal(at('prev').disabled,true);
at('next').emit('click');assert.equal(at('page').value,2);
at('page').value=13;at('page').emit('change');assert.equal(at('next').disabled,true);
at('page').value=4;at('page').emit('change');
assert(at('outline').children.length>0);
at('outline').children[0].emit('click');assert.equal(at('panes').children.length,1);
assert(at('detailTitle').textContent.includes('title'));
at('all').emit('click');assert.equal(at('panes').children.length,4);
at('zoom').value='200';at('zoom').emit('input');
assert(documentStub.querySelectorAll('.sheet').every(n=>n.style.width==='200%'));
at('containers').checked=true;at('containers').emit('change');
at('alternatives').checked=true;at('alternatives').emit('change');
at('page').value=5;at('page').emit('change');
at('groupList').children[0].emit('click');assert.equal(at('panes').children.length,1);
assert(at('detailTitle').textContent.includes('accepted link'));
at('clear').emit('click');assert.equal(at('detailTitle').textContent,'Select a region');
at('all').emit('click');const ports=documentStub.querySelectorAll('.canvasScroll');
ports[0].scrollTop=500;ports[0].emit('scroll');assert(ports.every(p=>p.scrollTop===500));
console.log('DOM unit harness: initialization, page controls, focus, titles, groups, zoom, layers, inspector, synchronized scrolling: PASS (not browser visual validation)');
