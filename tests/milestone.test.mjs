import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

const source=readFileSync(new URL('../qprint/static/milestone.js',import.meta.url),'utf8');
const {milestoneRoute,milestoneMarkup}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

test('milestone links round-trip Unicode paths and reject malformed routes',()=>{
  const path='论文/03-结果 & 更多.md';
  assert.equal(milestoneRoute('#milestone='+encodeURIComponent(path)),path);
  assert.equal(milestoneRoute('#node=A%23B'),null);
  assert.equal(milestoneRoute('#milestone=%'),null);
});

test('milestone directory uses node labels, escaped markup and an index return link',()=>{
  const html=milestoneMarkup({title:'<Results>'},[{id:'Paper/results#Lemma <1>',title:'Lemma <1>'}],'Paper/index#index');
  assert.ok(html.includes('href="#node=Paper%2Fresults%23Lemma%20%3C1%3E"'));
  assert.ok(html.includes('>↗ Lemma &lt;1&gt;</a>'));
  assert.ok(html.includes('>↗ index</a>'));
  assert.ok(!html.includes('<Results>'));
  assert.ok(milestoneMarkup({title:'Empty'},[],null).includes('暂无节点'));
});
