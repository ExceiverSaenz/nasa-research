'use strict';
class OfflineReviewStore {
 constructor(payload,storage){
  this.payload=payload;this.storage=storage;this.initial=structuredClone(payload.state.reviews);
  this.key='reading-order:'+payload.state.run_sha256;
  this.cases=new Map(payload.state.run.predictions.filter(p=>p.candidate_id!=='docling').map(p=>[`${p.scope.paper_id}:${p.scope.page_idx}:${p.candidate_id}`,p]));
 }
 identity(value){for(const key of ['run_id','input_profile_id','run_sha256'])if(value[key]!==this.initial[key])throw Error('Review identity differs from this result');}
 load(){const raw=this.storage?.getItem(this.key);const value=raw?JSON.parse(raw):structuredClone(this.initial);this.identity(value);return value;}
 validate(observation){
  this.identity(observation);const p=this.cases.get(observation.case_id);
  if(!p||observation.candidate_id!==p.candidate_id||observation.control!=='docling'||observation.paper_id!==p.scope.paper_id)throw Error('Unknown comparison case');
  const pages=observation.pages,doc=this.payload.state.run.documents.find(d=>d.paper_id===observation.paper_id);
  if(!Array.isArray(pages)||!pages.includes(p.scope.page_idx)||pages.some(i=>!Number.isInteger(i)||i<0||i>=doc.pages.length))throw Error('Invalid review pages');
  const ids=new Set(pages.flatMap(i=>{const page=this.payload.pages[`${observation.paper_id}:${i}`];return [...page.blocks.map(b=>b.id),...(page.excluded_ids||[])];}));
  if(!Array.isArray(observation.block_ids)||observation.block_ids.some(id=>!ids.has(id)))throw Error('Unknown block IDs');
  if(!['not_reviewed','partial','reviewed'].includes(observation.review_state))throw Error('Invalid review state');
  if(![null,'candidate_better','equivalent','docling_better','indeterminate'].includes(observation.preference))throw Error('Invalid preference');
  if(![null,'column_mix','paragraph_break','heading_after_content','route_intrusion','grouping','other'].includes(observation.issue_type))throw Error('Invalid issue type');
  if(typeof observation.id!=='string'||!observation.id||typeof observation.note!=='string')throw Error('Invalid observation');
 }
 commit(observations,states,revision,imported=null){
  const current=this.load();if(current.revision!==revision)throw Error('Revision conflict. Reload before editing.');
  for(const o of observations)this.validate(o);
  if(!states||Object.entries(states).some(([key,state])=>!this.cases.has(key)||!['not_reviewed','partial','reviewed'].includes(state)))throw Error('Invalid review states');
  const known=new Map(current.observations.map(o=>[o.id,o])),previous=[];
  for(const o of observations){if(known.has(o.id))previous.push(known.get(o.id));known.set(o.id,imported?structuredClone(o):{...o,utc:new Date().toISOString()});}
  const event={revision:current.revision,previous_observations:previous,previous_states:Object.fromEntries(Object.keys(states).map(k=>[k,current.states[k]]))};
  if(imported)Object.assign(event,{kind:'import',imported_utc:new Date().toISOString(),source_revision:imported.revision,source_history:structuredClone(imported.history||[])});
  const value={...current,revision:current.revision+1,observations:[...known.values()],states:{...current.states,...states},
   history:[...(current.history||[]),event]};
  if(this.storage)this.storage.setItem(this.key,JSON.stringify(value));else this.initial=structuredClone(value);
  return value;
 }
 save(observation,revision){return this.commit([observation],{[observation.case_id]:observation.review_state},revision);}
 importReviews(value,revision){this.identity(value);if(!Array.isArray(value.observations))throw Error('Invalid review file');return this.commit(value.observations,value.states,revision,value);}
}
class OfflineSource {
 constructor(payload,storage){
  this.payload=payload;
  if(storage===undefined){try{storage=globalThis.localStorage;storage.getItem('reading-order-check');}catch{storage=null;}}
  this.reviews=new OfflineReviewStore(payload,storage);
 }
 state(){return {...this.payload.state,reviews:this.reviews.load()};}
 page(paper,index){const value=this.payload.pages[`${paper}:${index}`];if(!value)throw Error('Page is not registered');return value;}
 put(path,body){if(path==='/api/reviews')return this.reviews.save(body.observation,body.expected_revision);if(path==='/api/import')return this.reviews.importReviews(body.data,body.expected_revision);throw Error('Unknown review operation');}
 savedMessage(revision){return this.reviews.storage?`Saved in this browser · revision ${revision}. Export reviews to keep a JSON file.`:`Saved in memory · revision ${revision}. Export reviews before closing.`;}
 notice(){return this.reviews.storage?'Local HTML · reviews are stored in this browser; use Export reviews for a JSON file.':'Local HTML · browser storage unavailable; export reviews before closing.';}
}
if(typeof module!=='undefined')module.exports={OfflineReviewStore,OfflineSource};
