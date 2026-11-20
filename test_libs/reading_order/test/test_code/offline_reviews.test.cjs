const {test}=require('node:test'),assert=require('node:assert/strict');
const {OfflineReviewStore,OfflineSource}=require('../../code/reading_order/viewer/offline.js');
function fixture(){
 const identity={run_id:'synthetic',input_profile_id:'profile',run_sha256:'manifest-sha'};
 const p={candidate_id:'hantian',scope:{paper_id:'12',page_idx:0}};
 const payload={state:{run:{documents:[{paper_id:'12',pages:[{}]}],predictions:[p]},...identity,
  reviews:{schema:'reading-order-reviews/1',...identity,revision:0,states:{'12:0:hantian':'not_reviewed'},observations:[]}},
  pages:{'12:0':{blocks:[{id:'a'}]}}};
 const saved=new Map(),storage={getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v)};
 const observation={...identity,id:'one',case_id:'12:0:hantian',candidate_id:'hantian',control:'docling',paper_id:'12',pages:[0],
  block_ids:['a'],review_state:'reviewed',preference:'equivalent',issue_type:null,note:'<img src=x onerror=alert(1)>',author:'test'};
 return {payload,storage,observation};
}
test('local observations survive a new viewer and preserve literal text',()=>{
 const {payload,storage,observation}=fixture();const a=new OfflineReviewStore(payload,storage);
 assert.equal(a.save(observation,0).revision,1);
 const b=new OfflineReviewStore(payload,storage);assert.equal(b.load().observations[0].note,observation.note);
 assert.equal(payload.state.reviews.revision,0);
});
test('stale revisions and foreign manifests cannot overwrite local notes',()=>{
 const {payload,storage,observation}=fixture(),a=new OfflineReviewStore(payload,storage);a.save(observation,0);
 assert.throws(()=>a.save({...observation,note:'changed'},0),/Revision conflict/);
 assert.throws(()=>a.importReviews({...a.load(),run_sha256:'foreign'},1),/identity/);
 assert.equal(a.load().observations[0].note,observation.note);
});
test('unknown blocks and states fail before a storage write',()=>{
 const {payload,storage,observation}=fixture(),a=new OfflineReviewStore(payload,storage);
 assert.throws(()=>a.save({...observation,block_ids:['foreign']},0),/Unknown block/);
 assert.throws(()=>a.importReviews({...a.load(),states:{foreign:'reviewed'}},0),/Invalid review states/);
 assert.equal(a.load().revision,0);
});
test('editing retains prior note values and states in review history',()=>{
 const {payload,storage,observation}=fixture(),a=new OfflineReviewStore(payload,storage);a.save(observation,0);
 const result=a.save({...observation,note:'second',review_state:'partial'},1);
 assert.equal(result.history[1].previous_observations[0].note,observation.note);
 assert.equal(result.history[1].previous_states['12:0:hantian'],'reviewed');
});
test('export-compatible reviews import without changing the run identity',()=>{
 const {payload,storage,observation}=fixture(),a=new OfflineReviewStore(payload,storage);a.save(observation,0);
 const b=new OfflineReviewStore(payload,null);const result=b.importReviews(JSON.parse(JSON.stringify(a.load())),0);
 assert.equal(result.revision,1);assert.equal(result.run_sha256,payload.state.run_sha256);
 assert.equal(result.observations.length,1);
});
test('memory fallback retains notes and identifies persistence limits',()=>{
 const {payload,observation}=fixture(),source=new OfflineSource(payload,null);
 source.put('/api/reviews',{observation,expected_revision:0});
 assert.equal(source.state().reviews.observations.length,1);
 assert.match(source.savedMessage(1),/memory/);assert.throws(()=>source.page('foreign',0),/not registered/);
});
test('import preserves source timestamps and edit history in a separate import event',()=>{
 const {payload,storage,observation}=fixture(),a=new OfflineReviewStore(payload,storage);
 a.save(observation,0);a.save({...observation,note:'edited'},1);
 const exported=JSON.parse(JSON.stringify(a.load()));exported.observations[0].utc='2025-01-02T03:04:05Z';
 const b=new OfflineReviewStore(payload,null),imported=b.importReviews(exported,0);
 assert.equal(imported.observations[0].utc,exported.observations[0].utc);
 const event=imported.history.at(-1);assert.equal(event.kind,'import');
 assert.deepEqual(event.source_history,exported.history);assert.equal(event.source_revision,2);
 assert.notEqual(event.imported_utc,exported.observations[0].utc);
 assert.deepEqual(exported.history,a.load().history);
});
test('import does not invent a missing source observation timestamp',()=>{
 const {payload,storage,observation}=fixture(),a=new OfflineReviewStore(payload,storage);
 const legacy={...a.load(),observations:[observation]};const imported=a.importReviews(legacy,0);
 assert.equal(Object.hasOwn(imported.observations[0],'utc'),false);
 assert.equal(typeof imported.history.at(-1).imported_utc,'string');
});
