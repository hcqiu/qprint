const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));

export function referencesHash(path, key = '', from = '') {
  return '#references=' + encodeURIComponent(path) + '&cite=' + encodeURIComponent(key) + '&from=' + encodeURIComponent(from);
}

export function referencesRoute(hash) {
  if (!hash.startsWith('#references=')) return null;
  const params = new URLSearchParams(hash.slice(1));
  return {path: params.get('references'), key: params.get('cite') || '', from: params.get('from') || ''};
}

export function referencesMarkup(data, from = '') {
  const back = from ? `<button data-node="${esc(from)}">← 返回引用节点</button>` : '';
  const warnings = data.warnings.map(w => `<div class="warning">${esc(w)}</div>`).join('');
  const entries = data.entries.map((entry, index) => `<li id="${esc(entry.anchor)}" class="bibliography-entry"><span class="bibliography-label">[${esc(entry.label)}]</span><div class="bibliography-body">${entry.html}<button type="button" class="bibliography-import" data-reference-import="${index}" aria-label="导入资料：${esc(entry.key)}">导入资料</button></div></li>`).join('');
  return `${back}<header class="node-heading"><span class="eyebrow">PAPER REFERENCES</span><h1>参考文献 / References</h1><p>${esc(data.path)}</p></header>${warnings}<div class="paper-content">${entries ? `<ul class="bibliography-list">${entries}</ul>` : data.html || '<p class="hint">当前论文没有可显示的参考文献。</p>'}</div>`;
}

export function citationTarget(data, key) {
  const matches = data.entries.filter(entry => entry.key === key);
  return matches.length === 1 ? matches[0].anchor : null;
}

export function referenceImportDefaults(data, entry) {
  // Citation keys are the project names, except characters invalid in filenames.
  let name = String(entry.key).replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/[ .]+$/g, '');
  if (!name || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(name)) name = '_' + name;
  const project = data.project_path ?? data.path.split('/').slice(0, -1).join('/');
  const parent = project === '.' ? '' : project.split('/').slice(0, -1).join('/');
  return {kind: 'paper', source: entry.arxiv_id || '', name,
    dest: parent ? `${parent}/${name}` : name, auto_blueprint: true};
}

export function prefillReferenceImport(form, defaults) {
  for (const name of ['kind', 'source', 'dest', 'name']) form.elements[name].value = defaults[name];
  form.elements.auto_blueprint.checked = true;
}
