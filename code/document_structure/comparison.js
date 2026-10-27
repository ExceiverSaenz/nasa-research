(()=>{'use strict';const $=id=>document.getElementById(id),data=JSON.parse($('comparison-data').textContent);
const frames=[$('baseline'),$('docling')],names={main:'Main',notes:'Notes',bibliography:'Bibliography',metadata:'Metadata',editorial_navigation:'Editorial and navigation',pending_structures:'Pending'};
let state={page:data.pages.includes(3)?3:data.pages[0],route:'main',step:null};
for(const n of data.pages)$('page').add(new Option(n,n));for(const r of data.routes)$('route').add(new Option(names[r]||r,r));
function update(){ $('page').value=state.page;$('route').value=state.route;const r=data.comparison.find(r=>r.page===state.page&&r.route===state.route);$('stats').textContent=r?`${r.changed_positions} of ${r.content} different content positions · ${r.reversed_pairs} of ${r.comparable_pairs} reversed pairs relative to baseline · no reading-order GT`:'';}
function broadcast(skip=null){const msg={kind:'trial-control',page:state.page,route:state.route};if(state.step!==undefined)msg.step=state.step;for(const f of frames)if(f!==skip)f.contentWindow.postMessage(msg,'*');}
for(const id of ['page','route'])$(id).addEventListener('change',()=>{state={page:Number($('page').value),route:$('route').value,step:null};update();broadcast();});
$('display').addEventListener('change',()=>{const d=$('display').value;for(const name of ['baseline','docling'])$(name+'-panel').hidden=d!=='both'&&d!==name;$('panels').className='panels'+(d==='both'?'':' single');broadcast();});
window.addEventListener('message',e=>{const f=frames.find(f=>f.contentWindow===e.source),m=e.data;if(!f||!m)return;
 if(m.kind==='trial-height'&&Number.isFinite(m.height)){f.style.height=Math.min(16000,Math.max(750,m.height))+'px';return;}
 if(m.kind!=='trial-state'||!data.pages.includes(m.page)||!data.routes.includes(m.route))return;
 state={page:m.page,route:m.route,step:$('link').checked?m.step:undefined};update();broadcast(f);
});
for(const r of data.comparison.filter(r=>r.content)){const tr=document.createElement('tr');if(r.changed_positions)tr.className='changed';for(const v of [r.page,names[r.route]||r.route,r.content,r.changed_positions,`${r.reversed_pairs}/${r.comparable_pairs}`]){const td=document.createElement('td');td.textContent=String(v);tr.append(td);}$('rows').append(tr);}
for(const f of frames)f.addEventListener('load',()=>broadcast());update();
})();
