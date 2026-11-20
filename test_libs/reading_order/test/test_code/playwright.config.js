const {defineConfig}=require('@playwright/test');
const path=require('path');
const fixture=path.resolve(__dirname,'../../raw_results/tests_results/browser-fixture-'+Date.now());
module.exports=defineConfig({testDir:__dirname,testMatch:'viewer.spec.js',workers:1,fullyParallel:false,
  use:{baseURL:'http://127.0.0.1:8876',headless:true,viewport:{width:1600,height:1100}},
  outputDir:path.resolve(__dirname,'../../raw_results/tests_results/browser-artifacts'),
  reporter:[['list']],webServer:{command:`python -B browser_fixture.py --root "${fixture}" --port 8876`,
    url:'http://127.0.0.1:8876/api/state',reuseExistingServer:false,timeout:30000}});
