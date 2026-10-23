import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../qprint/static/tree-state.js',import.meta.url),'utf8');
const {createTreeExpansionStore}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const memory=()=>{const data=new Map();return {getItem:key=>data.get(key),setItem:(key,value)=>data.set(key,value)};};
const tree=entries=>({querySelectorAll:()=>entries.map(([treeKey,open])=>({dataset:{treeKey},open}))});

test('branches start closed; opening and closing persist across page reloads',()=>{
  const storage=memory(),load=()=>createTreeExpansionStore(()=>storage)('Library');
  let state=load();assert.equal(state.isOpen('folder:A'),false);
  state.setOpen('folder:A',true);state.setOpen('file:A/Note.md',true);
  state=load();assert.equal(state.isOpen('folder:A'),true);assert.equal(state.isOpen('file:A/Note.md'),true);
  state.setOpen('folder:A',false);state=load();
  assert.equal(state.isOpen('folder:A'),false);assert.equal(state.isOpen('file:A/Note.md'),true);
  state.setOpen('file:A/Note.md',false);assert.equal(load().isOpen('file:A/Note.md'),false);
});
test('capture preserves a click before its toggle event and search does not clear branches',()=>{
  const storage=memory(),state=createTreeExpansionStore(()=>storage)('Library');
  state.capture(tree([['folder:A',true],['file:A/Note.md',true]]));
  state.capture(tree([])); // Search temporarily replaces the directory tree.
  assert.equal(state.isOpen('file:A/Note.md'),true);
  state.capture(tree([['folder:A',false],['file:A/Note.md',true]]));
  const reloaded=createTreeExpansionStore(()=>storage)('Library');
  assert.equal(reloaded.isOpen('folder:A'),false);assert.equal(reloaded.isOpen('file:A/Note.md'),true);
});
test('workspace and complete path distinguish similarly named branches',()=>{
  const storage=memory(),get=createTreeExpansionStore(()=>storage);
  get('One').setOpen('folder:A/chapters',true);
  assert.equal(get('One').isOpen('folder:B/chapters'),false);
  assert.equal(get('Two').isOpen('folder:A/chapters'),false);
  assert.equal(get('One').isOpen('folder:A/chapters'),true);
});
test('unavailable or corrupt storage never blocks navigation',()=>{
  for(const storage of [()=>{throw Error('blocked');},()=>({getItem:()=>'{bad json',setItem(){throw Error('quota');}}),()=>({getItem:()=>'{}',setItem(){}})]){
    const get=createTreeExpansionStore(storage),state=get('Library');
    assert.equal(state.isOpen('folder:A'),false);state.setOpen('folder:A',true);
    assert.equal(get('Library').isOpen('folder:A'),true);
  }
});
test('actual tree markup is closed by default and restores folders/files without showing blueprint',()=>{
  const app=readFileSync(new URL('../qprint/static/app.js',import.meta.url),'utf8');
  const functions=app.slice(app.indexOf('function treeButton('),app.indexOf('async function selectNode('));
  const storage=memory(),container={innerHTML:'',querySelectorAll:()=>[]};
  const state={selected:'one',project:{name:'Library',nodes:[
    {id:'one',path:'A/blueprint/chapters/Note.md',title:'One',body:'',status:'complete'},
    {id:'two',path:'B/blueprint/chapters/Note.md',title:'Two',body:'',status:'complete'},
  ]}};
  const get=createTreeExpansionStore(()=>storage);
  const render=runInNewContext(`${functions};renderTree`,{state,treeExpansion:null,treeExpansions:get,
    $:selector=>selector==='#tree'?container:{value:''},esc:value=>String(value)});
  render();assert.doesNotMatch(container.innerHTML,/<details[^>]*\sopen(?:\s|>)/);
  assert.doesNotMatch(container.innerHTML,/<summary>▱ blueprint<\/summary>/);
  get('Library').setOpen('folder:A/blueprint/chapters',true);
  get('Library').setOpen('file:A/blueprint/chapters/Note.md',true);render();
  assert.match(container.innerHTML,/data-tree-key="folder:A\/blueprint\/chapters" open/);
  assert.match(container.innerHTML,/data-tree-key="file:A\/blueprint\/chapters\/Note.md" open/);
  assert.doesNotMatch(container.innerHTML,/data-tree-key="folder:B\/blueprint\/chapters" open/);
});
