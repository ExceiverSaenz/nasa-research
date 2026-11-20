const path=require('path'),fs=require('fs');
const root=path.resolve(__dirname,'../../..');
const {chromium}=require(path.join(root,'test/test_code/node_modules/@playwright/test'));
(async()=>{
 const base='http://127.0.0.1:8878',browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);
 const state=await page.request.get(base+'/api/state').then(r=>r.json());
 if(state.run.predictions.length!==2382||state.run.documents.length!==15)throw Error('Incomplete collection');
 if(state.run.predictions.some(p=>p.status!=='PASS'))throw Error('Collection has non-PASS results');
 if(state.reviews.revision!==0)throw Error('Review state must remain untouched');
 const captures=[];
 await page.waitForSelector('#control .box',{timeout:60000});
 for(const paper of state.run.documents.map(d=>d.paper_id)){
  await page.locator('#paper').selectOption(paper);
  await page.waitForFunction(p=>document.querySelector('#control image')?.getAttribute('href')===`/asset/${p}/0`,paper,{timeout:60000});
  const response=await page.request.get(base+`/asset/${paper}/0`);
  if(response.status()!==200)throw Error('Referenced background unavailable: '+paper);
  captures.push({paper,page_idx:0,boxes:await page.locator('#comparison .box').count(),background_status:response.status()});
 }
 await page.locator('#paper').selectOption('14');
 await page.locator('#page').selectOption('4');
 await page.waitForFunction(()=>document.querySelector('#control image')?.getAttribute('href')==='/asset/14/4',{timeout:60000});
 for(const candidate of ['hantian','xycut_plus_plus','xycut','pp_doclayout_v2','doctr']){
  await page.locator('#candidate').selectOption(candidate);
  if(await page.locator('#candidateStatus').textContent()!=='PASS')throw Error('Missing displayed prediction');
 }
 await page.locator('#crossPage').check();
 await page.evaluate(async()=>{await Promise.all([...document.querySelectorAll('svg image')].map(async n=>{const im=new Image();im.src=n.getAttribute('href');await im.decode();}));});
 await page.waitForLoadState('networkidle');
 await page.screenshot({path:path.join(__dirname,'collection-index-transition.png'),fullPage:true});
 if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync(path.join(__dirname,'browser-qa.json'),JSON.stringify({status:'PASS',papers:15,predictions:2382,captures,all_candidates_displayed:true,cross_page:'physical navigation only',reviews_unchanged:true,semantic_acceptance:false},null,2));
 await browser.close();console.log('COLLECTION_BROWSER_QA_PASS');
})().catch(e=>{console.error(e);process.exit(1)});
