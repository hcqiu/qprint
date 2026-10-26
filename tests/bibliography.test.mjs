import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

const source = readFileSync(new URL('../qprint/static/bibliography.js', import.meta.url), 'utf8');
const {referencesHash, referencesRoute, referencesMarkup, citationTarget, referenceImportDefaults, prefillReferenceImport} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

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
  assert.ok(html.includes('data-reference-import="0"'));
  assert.ok(html.includes('>导入资料</button>'));
  assert.equal(citationTarget(data, 'KM'), 'entry-1');
  assert.equal(citationTarget(data, 'missing'), null);
  data.entries.push({...data.entries[0], anchor:'entry-2'});
  assert.equal(citationTarget(data, 'KM'), null);
});

test('reference imports use the citation key and a sibling project, even from a nested chapter', () => {
  const data = {path:'Topology/Ren25/chapters/introduction.tex', project_path:'Topology/Ren25'};
  const entry = {key:'budney2019knotted', label:'BG19', arxiv_id:'1912.09029'};
  assert.deepEqual(referenceImportDefaults(data, entry), {
    kind:'paper', source:'1912.09029', name:'budney2019knotted',
    dest:'Topology/budney2019knotted', auto_blueprint:true,
  });
  assert.equal(referenceImportDefaults({...data, project_path:'Ren25'}, entry).dest, entry.key);
  assert.equal(referenceImportDefaults({...data, project_path:'.'}, entry).dest, entry.key);
});

test('every entry has its own import button, with escaped labels and no guessed arxiv ID', () => {
  const data = {path:'A/main.tex', warnings:[], entries:[
    {key:'quoted"<key>', label:'1', anchor:'one', html:'<p>Paper</p>'},
    {key:'second', label:'2', anchor:'two', html:'<p>Other paper</p>'},
  ]};
  const html = referencesMarkup(data);
  assert.equal((html.match(/data-reference-import=/g)||[]).length, 2);
  assert.ok(html.includes('data-reference-import="1"'));
  assert.ok(html.includes('导入资料：quoted&quot;&lt;key&gt;'));
  assert.equal(referenceImportDefaults(data, data.entries[1]).source, '');
});

test('prefill replaces previous paper values and restores automatic Blueprint generation', () => {
  const form = {elements:Object.fromEntries(['kind','source','dest','name','auto_blueprint'].map(name=>[name,{value:'old',checked:false}]))};
  const defaults = referenceImportDefaults({path:'Topology/Ren25/main.tex'}, {key:'BG19',arxiv_id:'1912.09029'});
  prefillReferenceImport(form, defaults);
  assert.equal(form.elements.source.value, '1912.09029');
  assert.equal(form.elements.kind.value, 'paper');
  assert.equal(form.elements.dest.value, 'Topology/BG19');
  assert.equal(form.elements.name.value, 'BG19');
  assert.equal(form.elements.auto_blueprint.checked, true);
  prefillReferenceImport(form, referenceImportDefaults({path:'A.tex'}, {key:'Unknown'}));
  assert.equal(form.elements.source.value, '');
  assert.equal(form.elements.dest.value, 'Unknown');
});

test('unsafe citation characters cannot create nested or reserved destination paths', () => {
  const data = {path:'Topology/Ren25/main.tex'};
  for(const key of ['../../other', 'A:B', 'CON', 'NUL.txt', 'trailing. ', '']) {
    const defaults = referenceImportDefaults(data, {key});
    assert.equal(defaults.dest.split('/').length, 2);
    assert.ok(!/[<>:"/\\|?*\x00-\x1f]/.test(defaults.name));
    assert.ok(!/[ .]$/.test(defaults.name));
    assert.ok(defaults.name.length > 0);
  }
});

test('failed bibliography page retains safe source fallback', () => {
  const html = referencesMarkup({path:'A.tex', warnings:[], entries:[], html:'<pre>BBL source</pre>'});
  assert.ok(html.includes('<pre>BBL source</pre>'));
  assert.ok(!html.includes('data-node='));
});
