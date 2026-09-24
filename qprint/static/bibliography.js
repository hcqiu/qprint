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
  const entries = data.entries.map(entry => `<li id="${esc(entry.anchor)}" class="bibliography-entry"><span class="bibliography-label">[${esc(entry.label)}]</span><div>${entry.html}</div></li>`).join('');
  return `${back}<header class="node-heading"><span class="eyebrow">PAPER REFERENCES</span><h1>参考文献 / References</h1><p>${esc(data.path)}</p></header>${warnings}<div class="paper-content">${entries ? `<ul class="bibliography-list">${entries}</ul>` : data.html || '<p class="hint">当前论文没有可显示的 BBL 参考文献。</p>'}</div>`;
}

export function citationTarget(data, key) {
  const matches = data.entries.filter(entry => entry.key === key);
  return matches.length === 1 ? matches[0].anchor : null;
}
