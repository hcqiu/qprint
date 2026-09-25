import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../qprint/static/navigator-state.js',import.meta.url),'utf8');
const {createFocusPublisher,browserSession}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

test('browser creates and reuses a session without agent-side configuration',()=>{
  const data=new Map();
  const storage={getItem:key=>data.get(key),setItem:(key,value)=>data.set(key,value)};
  assert.equal(browserSession('',storage,()=> 'generated'),'generated');
  assert.equal(browserSession('',storage,()=> 'different'),'generated');
  assert.equal(browserSession('?navigator_session=explicit',storage,()=> 'unused'),'explicit');
  assert.equal(browserSession('',{getItem(){throw new Error('blocked');}},()=> 'fallback'),'fallback');
  assert.equal(browserSession('',()=>{throw new Error('storage unavailable');},()=> 'private-tab'),'private-tab');
});

test('publishes snapshots in order and continues after a failed update', async()=>{
  const seen=[],errors=[];
  let release;
  const blocked=new Promise(resolve=>{release=resolve;});
  const publish=createFocusPublisher(async payload=>{
    seen.push(payload.node_id);
    if(payload.node_id==='first'){await blocked;throw new Error('transient');}
  },error=>errors.push(error.message));
  const payload={node_id:'first'};
  publish(payload);
  payload.node_id='mutated';
  const done=publish({node_id:'second'});
  await Promise.resolve();
  assert.deepEqual(seen,['first']);
  release();await done;
  assert.deepEqual(seen,['first','second']);
  assert.deepEqual(errors,['transient']);
});
