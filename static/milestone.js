const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export function milestoneRoute(hash){
  if(!hash.startsWith('#milestone='))return null;
  try{return decodeURIComponent(hash.slice(11));}catch{return null;}
}

export function milestoneMarkup(file,nodes,indexId){
  const link=node=>`<a class="wikilink tex-use" href="#node=${encodeURIComponent(node.id)}">↗ ${esc(node.title)}</a>`;
  return `<header class="node-heading"><span class="eyebrow">MILESTONE</span><h1>${esc(file.title)}</h1></header><div class="paper-content">${nodes.length?`<ul>${nodes.map(node=>`<li>${link(node)}</li>`).join('')}</ul>`:'<p>暂无节点。</p>'}${indexId?`<p>${link({id:indexId,title:'index'})}</p>`:''}</div>`;
}
