// Explicit direct-file browser tests. No HTTP server and no browser security flags.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{pathToFileURL}=require('url');
const {chromium}=require('@playwright/test');
const root=path.resolve(__dirname,'../..'),output=path.join(root,'raw_results/tests_results/offline-file-viewer-20261102');
const fixture=path.join(output,'fixture/run/viewer.html');
const collection=path.join(root,'raw_results/code_results/collection-20261102-delivery/canonical/viewer.html');
(async()=>{
 const browser=await chromium.launch({headless:true}),errors=[],http=[];
 function monitor(page){page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))http.push(r.url());});page.on('dialog',async d=>{errors.push('Unexpected dialog');await d.dismiss();});}
 const testContext=await browser.newContext({acceptDownloads:true,viewport:{width:1600,height:1100}});
 const page=await testContext.newPage();monitor(page);await page.goto(pathToFileURL(fixture).href);
 await page.waitForSelector('#control .box');assert.equal(new URL(page.url()).protocol,'file:');
 const view=await page.locator('#control').getAttribute('viewBox');await page.locator('#zoomIn').click();
 assert.notEqual(await page.locator('#control').getAttribute('viewBox'),view);
 assert.equal(await page.locator('#control').getAttribute('viewBox'),await page.locator('#comparison').getAttribute('viewBox'));
 await page.locator('#comparison .box').click();assert.match(await page.locator('#inspector').textContent(),/block-0/);
 const note='<img src=x onerror=alert(1)> synthetic review';await page.locator('#note').fill(note);
 await page.locator('#preference').selectOption('equivalent');await page.locator('#review button[type=submit]').click();
 await page.waitForFunction(()=>document.getElementById('message').textContent.includes('Saved in this browser'));
 await page.reload();await page.waitForSelector('#control .box');assert.match(await page.locator('#notes').textContent(),/synthetic review/);
 assert.equal(await page.locator('#notes img').count(),0);
 const event=page.waitForEvent('download');await page.locator('#export').click();
 const download=await event,exported=path.join(output,'synthetic-reviews.json');await download.saveAs(exported);
 const saved=JSON.parse(fs.readFileSync(exported,'utf8'));assert.equal(saved.revision,1);assert.equal(saved.observations[0].note,note);
 await page.locator('#import').setInputFiles(exported);
 await page.waitForFunction(()=>localSource.reviews.load().revision===2);
 const foreign={...saved,run_sha256:'foreign'};
 await page.locator('#import').setInputFiles({name:'foreign.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(foreign))});
 await page.waitForFunction(()=>document.getElementById('message').textContent.includes('identity'));
 await page.locator('#crossPage').check();assert.equal(await page.locator('#comparisonNext').isVisible(),true);
 await page.locator('#next').click();await page.waitForFunction(()=>document.getElementById('page').value==='1');
 await testContext.close();
 const context=await browser.newContext({viewport:{width:1600,height:1100}}),real=await context.newPage();monitor(real);
 await real.goto(pathToFileURL(collection).href);await real.waitForSelector('#control .box');
 const total=await real.evaluate(()=>({papers:READING_ORDER_STATIC.state.run.documents.length,predictions:READING_ORDER_STATIC.state.run.predictions.length}));
 assert.deepEqual(total,{papers:15,predictions:2382});
 const papers=await real.locator('#paper option').evaluateAll(options=>options.map(o=>o.value));
 for(const paper of papers){
  await real.locator('#paper').selectOption(paper);
  await real.waitForFunction(p=>document.querySelector('#control image')?.getAttribute('href')===READING_ORDER_STATIC.pages[p+':0'].background,paper);
  await real.evaluate(async()=>{const image=new Image();image.src=document.querySelector('#control image').getAttribute('href');await image.decode();});
 }
 await real.locator('#paper').selectOption('14');await real.locator('#page').selectOption('4');
 await real.waitForFunction(()=>document.querySelector('#control image')?.getAttribute('href')===READING_ORDER_STATIC.pages['14:4'].background);
 for(const candidate of ['hantian','xycut_plus_plus','xycut','pp_doclayout_v2','doctr']){
  await real.locator('#candidate').selectOption(candidate);assert.equal(await real.locator('#candidateStatus').textContent(),'PASS');
 }
 await real.locator('#crossPage').check();
 await real.evaluate(async()=>{await Promise.all([...document.querySelectorAll('svg image')].map(async node=>{const image=new Image();image.src=node.getAttribute('href');await image.decode();}));});
 await real.screenshot({path:path.join(output,'viewer-local.png'),fullPage:true});
 assert.equal(await real.evaluate(()=>localSource.reviews.load().revision),0);
 assert.deepEqual(errors,[]);assert.deepEqual(http,[]);
 await context.close();await browser.close();
 fs.writeFileSync(path.join(output,'browser-qa.json'),JSON.stringify({status:'PASS',protocol:'file:',http_requests:0,
  papers:15,predictions:2382,all_candidates_displayed:true,referenced_images_loaded:true,
  synthetic_reviews_save_reload_export_import:true,real_reviews_untouched:true,semantic_acceptance:false},null,2));
 console.log('OFFLINE_FILE_VIEWER_PASS');
})().catch(error=>{console.error(error);process.exit(1)});
