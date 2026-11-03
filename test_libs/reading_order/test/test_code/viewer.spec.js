const {test,expect}=require('@playwright/test');

test.beforeEach(async({page})=>{await page.goto('/');await expect(page.locator('#control .box')).toHaveCount(1);});
test('sync zoom and page navigation',async({page})=>{
 const before=await page.locator('#control').getAttribute('viewBox');
 await page.locator('#zoomIn').click();
 expect(await page.locator('#control').getAttribute('viewBox')).not.toBe(before);
 expect(await page.locator('#control').getAttribute('viewBox')).toBe(await page.locator('#comparison').getAttribute('viewBox'));
 await page.locator('#next').click();await expect(page.locator('#page')).toHaveValue('1');
 await expect(page.locator('#control .box')).toHaveCount(1);
});
test('rank overlays preserve original IDs',async({page})=>{
 await page.locator('#comparison .box').click();
 await expect(page.locator('#inspector')).toContainText('block-0');
 await expect(page.locator('#comparison text').first()).toHaveText('1');
});
test('cross-page navigation is never native semantic prediction',async({page})=>{
 await page.locator('#crossPage').check();
 await expect(page.locator('#comparisonNext')).toBeVisible();
 await expect(page.locator('.continuity').first()).toContainText('semantic connection not predicted');
});
test('save reload export import with literal HTML note',async({page})=>{
 page.on('dialog',()=>{throw new Error('Untrusted note executed')});
 await page.locator('#note').fill('<img src=x onerror=alert(1)>');
 await page.locator('#preference').selectOption('equivalent');
 await page.getByRole('button',{name:'Save observation'}).click();
 await expect(page.locator('#message')).toContainText('Saved revision');
 await page.reload();await expect(page.locator('#notes')).toContainText('<img src=x onerror=alert(1)>');
 await expect(page.locator('#notes img')).toHaveCount(0);
 const download=page.waitForEvent('download');await page.locator('#export').click();expect((await download).suggestedFilename()).toContain('reviews.json');
 const state=await page.request.get('/api/state').then(r=>r.json());
 await page.locator('#import').setInputFiles({name:'reviews.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(state.reviews))});
 await expect.poll(async()=>page.request.get('/api/state').then(r=>r.json()).then(s=>s.reviews.revision)).toBe(state.reviews.revision+1);
});
test('concurrent revisions and missing token are rejected',async({page,request})=>{
 const state=await request.get('/api/state').then(r=>r.json());
 const observation={id:'concurrency',run_id:state.run.run_id,run_sha256:state.run_sha256,input_profile_id:state.run.input_profile_id,
  case_id:'12:0:hantian',candidate_id:'hantian',control:'docling',paper_id:'12',pages:[0],block_ids:[],scope:'page',
  preference:'equivalent',issue_type:null,note:'test',author:'test',ambiguity:false,review_state:'reviewed'};
 const headers={'Origin':'http://127.0.0.1:8876','X-Review-Token':state.token};
 const body={observation,expected_revision:state.reviews.revision};
 expect((await request.put('/api/reviews',{headers,data:body})).status()).toBe(200);
 expect((await request.put('/api/reviews',{headers,data:body})).status()).toBe(409);
 expect((await request.put('/api/reviews',{data:body})).status()).toBe(403);
});
test('real browser screenshot',async({page},info)=>{
 await page.screenshot({path:info.outputPath('viewer.png'),fullPage:true});
});
