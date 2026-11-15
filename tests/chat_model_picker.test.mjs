import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../qprint/static/chat-model-picker.js',import.meta.url),'utf8');
const {pickerState}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const catalog={default_model:'fast',default_effort:'high',models:[
  {id:'fast',efforts:[{id:'low'},{id:'high'}],default_effort:'low',efforts_loaded:true},
  {id:'deep',efforts:[{id:'medium'},{id:'max'}],default_effort:'medium',efforts_loaded:true},
  {id:'unknown',efforts:[],efforts_loaded:false},
]};
test('default follows configured model and effort; explicit model has its own default',()=>{
  assert.equal(pickerState(catalog,{model:'',effort:''}).defaultEffort,'high');
  assert.equal(pickerState(catalog,{model:'deep',effort:''}).defaultEffort,'medium');
});
test('incompatible and removed selections are not silently accepted',()=>{
  assert.equal(pickerState(catalog,{model:'deep',effort:'high'}).invalidEffort,true);
  assert.equal(pickerState(catalog,{model:'missing',effort:''}).invalidModel,true);
  assert.equal(pickerState(catalog,{model:'deep',effort:'max'}).invalidEffort,false);
});
test('ACP dependent capabilities require discovery; missing API metadata has no invented choices',()=>{
  assert.equal(pickerState(catalog,{model:'unknown',effort:''}).needsDiscovery,true);
  assert.deepEqual(pickerState({models:[{id:'api',efforts:[],efforts_loaded:true}]},{model:'api',effort:''}).levels,[]);
});
test('an API catalog without a configured default requires an explicit model',()=>{
  assert.equal(pickerState({...catalog,default_model:'',requires_model:true},{model:'',effort:''}).invalidModel,true);
  assert.equal(pickerState({...catalog,default_model:'',requires_model:true},{model:'fast',effort:''}).invalidModel,false);
});
