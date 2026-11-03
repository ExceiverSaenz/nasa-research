const path=require('path');
const root=path.resolve(__dirname,'../../..');
const {chromium}=require(path.join(root,'test/test_code/node_modules/@playwright/test'));
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:1100}});
 const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8877');
 await page.waitForSelector('#control .box');
 const state=await page.request.get('http://127.0.0.1:8877/api/state').then(r=>r.json());
 if(state.run.predictions.length!==78)throw Error('Incomplete pilot');
 if(state.reviews.revision!==0)throw Error('QA must preserve unreviewed state');
 const captures=[];
 for(const index of [0,2]){
  await page.locator('#page').selectOption(String(index));
  await page.waitForFunction(index=>document.querySelector('#control image')?.getAttribute('href')===`/asset/12/${index}`,index);
  await page.evaluate(async()=>{await Promise.all([...document.querySelectorAll('#control image,#comparison image')].map(async n=>{const image=new Image();image.src=n.getAttribute('href');await image.decode();}));});
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);
  const images=await page.locator('#control image').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')));
  for(const image of images){const r=await page.request.get('http://127.0.0.1:8877'+image);if(r.status()!==200)throw Error('Missing referenced background');}
  await page.screenshot({path:path.join(__dirname,`pilot-page-${index+1}.png`),fullPage:true});
  captures.push({page_idx:index,boxes:await page.locator('#comparison .box').count(),backgrounds:images});
 }
 await page.locator('#crossPage').check();
 await page.evaluate(async()=>{await Promise.all([...document.querySelectorAll('svg image')].map(async n=>{const image=new Image();image.src=n.getAttribute('href');await image.decode();}));});
 await page.waitForLoadState('networkidle');
 await page.waitForTimeout(700);
 await page.screenshot({path:path.join(__dirname,'pilot-transition-3-4.png'),fullPage:true});
 if(!await page.locator('#comparisonNext').isVisible())throw Error('Missing transition panel');
 if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync(path.join(__dirname,'browser-pilot-qa.json'),JSON.stringify({status:'PASS',run_id:state.run.run_id,captures,cross_page:'physical navigation; semantic connection not predicted',reviews_unchanged:true},null,2));
 await browser.close();
 console.log('PILOT_BROWSER_QA_PASS');
})().catch(e=>{console.error(e);process.exit(1)});
