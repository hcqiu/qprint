import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../qprint/static/clipboard-context.js',import.meta.url),'utf8');
const {formatContext,copyWithContext}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

const bundle={node:'P#A',source:'tex/P.tex',tex:'A full proof.',description:'A summary',
  dependencies:[{node:'P#B',title:'B',description:'B summary'}],dependencies_omitted:3,
  unresolved_dependencies:['missing'],unresolved_omitted:0};

test('context includes bounded dependency metadata and puts the user question last',()=>{
  const output=formatContext(bundle,'Why is $x=1$?');
  assert.ok(output.includes('A full proof.'));
  assert.ok(output.includes('Node: P#B\nB summary'));
  assert.ok(output.includes('3 additional dependencies omitted'));
  assert.ok(output.includes('Unresolved references (not verified dependencies):\nmissing'));
  assert.ok(output.includes('Knowledge Navigator'));
  assert.ok(output.endsWith('User question:\nWhy is $x=1$?'));
  assert.ok(formatContext({...bundle,tex:null},'Why?').includes('(No TeX source is available for this node.)'));
});

function copyFixture(){
  const textNode={nodeType:3,parentElement:{closest:()=>null}};
  const range={startContainer:textNode,endContainer:textNode};
  const selection={isCollapsed:false,rangeCount:1,anchorNode:textNode,focusNode:textNode,getRangeAt:()=>range,toString:()=> '  Selected τ̃ theorem\n'};
  const written=[];
  const event={clipboardData:{setData:(...args)=>written.push(args)},preventDefault(){this.defaultPrevented=true;}};
  const context={selection,content:{contains:n=>n===textNode},bundle,nodeId:'P#A',enabled:true};
  return {event,context,written,range};
}

test('native copy synchronously writes context without requests',()=>{
  const {event,context,written}=copyFixture();
  assert.equal(copyWithContext(event,context),true);
  assert.equal(event.defaultPrevented,true);
  assert.equal(written.length,1);
  assert.equal(written[0][0],'text/plain');
  assert.ok(written[0][1].endsWith('User question:\n  Selected τ̃ theorem\n'));
});

test('leaves native copying untouched for edit/code/outside/empty or stale context',()=>{
  const variations=[{enabled:false},{bundle:null},{nodeId:'P#Other'},
    {selection:{isCollapsed:true}}, {activeElement:{closest:()=>true}},
    {activeElement:{closest:()=>null,isContentEditable:true}}, {content:{contains:()=>false}}];
  for(const change of variations){
    const {event,context,written}=copyFixture();
    assert.equal(copyWithContext(event,{...context,...change}),false);
    assert.equal(written.length,0);
    assert.equal(event.defaultPrevented,undefined);
  }
  const {event,context,range}=copyFixture();
  range.endContainer={};
  assert.equal(copyWithContext(event,context),false);
  assert.equal(copyWithContext({...event,clipboardData:null},context),false);
});
