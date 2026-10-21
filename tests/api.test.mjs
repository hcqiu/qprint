import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../qprint/static/api.js',import.meta.url),'utf8');
const {requestJson}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

test('successful API responses preserve JSON and request headers',async t=>{
  t.mock.method(globalThis,'fetch',async(path,options)=>{
    assert.equal(path,'/api/project');assert.equal(options.headers['X-Qprint-Token'],'test');
    return {ok:true,json:async()=>({nodes:[]})};
  });
  assert.deepEqual(await requestJson('/api/project',{headers:{'X-Qprint-Token':'test'}}),{nodes:[]});
});
for(const body of [false,true])test(`read timeout aborts a stalled ${body?'response body':'connection'}`,async t=>{
  t.mock.method(globalThis,'fetch',async(_,options)=>{
    const stalled=()=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new Error('aborted'))));
    return body?{ok:true,json:stalled}:stalled();
  });
  await assert.rejects(requestJson('/api/project',{},5),/读取知识库超时/);
});
test('API errors and invalid responses retain a useful diagnostic',async t=>{
  t.mock.method(globalThis,'fetch',async()=>({ok:false,status:404,json:async()=>({detail:'文件不存在'})}));
  await assert.rejects(requestJson('/api/node'),/文件不存在/);
  globalThis.fetch=async()=>({ok:false,status:500,json:async()=>{throw new Error('not JSON');}});
  await assert.rejects(requestJson('/api/project'),/服务响应异常 \(500\)/);
});
