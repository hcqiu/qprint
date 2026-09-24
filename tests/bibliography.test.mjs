import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

const source = readFileSync(new URL('../qprint/static/bibliography.js', import.meta.url), 'utf8');
const {referencesHash, referencesRoute, referencesMarkup, citationTarget} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

test('reference URLs preserve path, citation and return node across history and reload', () => {
  const path = '论文 A/main.tex', key = 'K&M+#?', from = 'Project/A#Theorem';
  assert.deepEqual(referencesRoute(referencesHash(path, key, from)), {path, key, from});
  assert.equal(referencesRoute('#node=A%23B'), null);
  assert.deepEqual(referencesRoute('#references=A%2Fmain.tex&cite=KM'), {path:'A/main.tex', key:'KM', from:''});
});

test('reference page shows formatted bibliography and escaped metadata', () => {
  const data = {path:'<paper>', warnings:['<warning>'], entries:[{key:'KM', label:'1', anchor:'entry-1', html:'<p><em>Title</em></p>'}], html:''};
  const html = referencesMarkup(data, 'A#"quoted"');
  assert.ok(html.includes('id="entry-1"'));
  assert.ok(html.includes('<em>Title</em>'));
  assert.ok(html.includes('&lt;paper&gt;') && html.includes('&lt;warning&gt;'));
  assert.ok(html.includes('data-node="A#&quot;quoted&quot;"'));
  assert.equal(citationTarget(data, 'KM'), 'entry-1');
  assert.equal(citationTarget(data, 'missing'), null);
  data.entries.push({...data.entries[0], anchor:'entry-2'});
  assert.equal(citationTarget(data, 'KM'), null);
});

test('failed bibliography page retains safe source fallback', () => {
  const html = referencesMarkup({path:'A.tex', warnings:[], entries:[], html:'<pre>BBL source</pre>'});
  assert.ok(html.includes('<pre>BBL source</pre>'));
  assert.ok(!html.includes('data-node='));
});
