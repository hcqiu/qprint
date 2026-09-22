import {renderImportJob, renderReports} from './import-progress.js';
import {KnowledgeGraph} from './graph.js';
import {createGraphView, syncGraphContext, changeGraphLevel, drillGraph, graphProjection} from './graph-view.js';

const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const kindLabel={definition:'定义',lemma:'引理',theorem:'定理',conjecture:'猜想',proof:'证明',other:'数学对象'};
const statusLabel={complete:'已完成',in_progress:'进行中',not_started:'未开始'};
const state={project:null,detail:null,selected:null,mode:'rendered',view:'reader',binding:0,document:null,dirty:false,request:0,boundary:null,lastWheel:0};
const graphView=createGraphView();
let toastTimer;
function toast(message){$('#toast').textContent=message;$('#toast').classList.remove('hidden');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.add('hidden'),5000);}
async function api(path,options={}){const response=await fetch(path,{...options,headers:{'Content-Type':'application/json','X-Qprint-Token':state.project?.token??'',...options.headers}});let result;try{result=await response.json();}catch{throw new Error(`服务响应异常 (${response.status})`);}if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:JSON.stringify(result.detail));return result;}
function guarded(fn){return(...args)=>Promise.resolve().then(()=>fn(...args)).catch(e=>toast(e.message));}
function canLeave(){return !state.dirty||window.confirm('Markdown 有未保存的更改，确定放弃这些更改？');}
function math(container){if(!window.katex)return;container.querySelectorAll('[data-tex]').forEach(el=>{let source=el.dataset.tex;source=source.replace(/^\$\$?|\$\$?$/g,'').replace(/^\\\(|\\\)$/g,'').replace(/^\\\[|\\\]$/g,'');source=source.replace(/^\\begin\{(?:equation\*?|displaymath)\}|\\end\{(?:equation\*?|displaymath)\}$/g,'');try{window.katex.render(source,el,{throwOnError:false,displayMode:el.dataset.display==='true',trust:false,strict:false});}catch{el.textContent=source;}});window.renderMathInElement?.(container,{delimiters:[{left:'$$',right:'$$',display:true},{left:'\\[',right:'\\]',display:true},{left:'$',right:'$',display:false},{left:'\\(',right:'\\)',display:false}],throwOnError:false,trust:false});}
function setHash(id){const hash=`#node=${encodeURIComponent(id)}`;if(location.hash!==hash)history.pushState(null,'',hash);}

async function loadProject(preserve=true){const data=await api('/api/project');state.project=data;$('#project-name').textContent=data.name;$('#node-count').textContent=`${data.stats.nodes} 节点`;$('#progress-label').textContent=`${data.stats.complete} / ${data.stats.nodes}`;$('#progress-bar').style.width=`${data.stats.nodes?data.stats.complete/data.stats.nodes*100:0}%`;$('#diagnostic-count').textContent=data.diagnostics.length;renderTree();
  let requested;try{requested=decodeURIComponent(location.hash.replace(/^#node=/,''));}catch{requested='';}
  const chosen=data.nodes.find(n=>n.id===(preserve?state.selected:requested))||data.nodes.find(n=>n.id===requested)||data.nodes.find(n=>n.tex)||data.nodes[0];
  if(chosen){await selectNode(chosen.id,false);history.replaceState(null,'',`#node=${encodeURIComponent(chosen.id)}`);}else{state.selected=null;state.detail=null;$('#content').innerHTML='<div class="empty-state"><span class="empty-symbol">Q</span><h1>从一个数学对象开始</h1><p>在工作区 blueprint/ 中创建 Markdown 文件，<br>以一级标题定义节点，然后点击刷新。</p></div>';$('#formal-content').innerHTML='<div class="empty-code">没有选中的节点</div>';$('#previous').disabled=true;$('#next').disabled=true;}
  if(state.view==='graph')renderGraph();
}
function treeButton(node){return `<button class="node-entry ${state.selected===node.id?'active':''}" data-node="${esc(node.id)}"><i class="dot ${node.status}"></i><span>${esc(node.title)}</span></button>`;}
function fileTree(items,renderFile){const root={folders:new Map(),files:[]};for(const item of items){const parts=item.path.split('/');let cursor=root;for(const name of parts.slice(0,-1)){if(!cursor.folders.has(name))cursor.folders.set(name,{folders:new Map(),files:[]});cursor=cursor.folders.get(name);}cursor.files.push({...item,name:parts.at(-1)});}const render=branch=>[...branch.folders].map(([name,child])=>`<details open class="folder"><summary>▱ ${esc(name)}</summary><div class="folder-contents">${render(child)}</div></details>`).join('')+branch.files.map(renderFile).join('');return render(root);}
function renderTree(){if(!state.project)return;const query=$('#search').value.toLowerCase().trim();const nodes=state.project.nodes.filter(n=>`${n.title} ${n.path} ${n.body}`.toLowerCase().includes(query));if(query){$('#tree').innerHTML=`<div class="tree-group"><div class="tree-title">搜索结果 · ${nodes.length}</div>${nodes.map(treeButton).join('')||'<p class="hint">没有匹配的节点</p>'}</div>`;return;}
  const papers=fileTree(state.project.papers,p=>`<details open><summary title="${esc(p.path)}">▤ ${esc(p.name)}</summary>${p.sections.map(s=>`<button class="section-entry" style="padding-left:${14+s.level*8}px" ${s.node_id?`data-node="${esc(s.node_id)}"`:`data-paper="${esc(p.path)}" data-line="${s.line}"`}>${esc(s.title)}</button>`).join('')}${!p.sections.length?`<button class="section-entry" ${p.nodes[0]?`data-node="${esc(p.nodes[0])}"`:`data-paper="${esc(p.path)}"`}>打开论文</button>`:''}</details>`);
  const files=new Map();for(const n of nodes){if(!files.has(n.path))files.set(n.path,[]);files.get(n.path).push(n);}
  $('#tree').innerHTML=`<div class="tree-group"><div class="tree-title">PAPERS / 论文目录</div>${papers||'<p class="hint">暂无 TeX 文件</p>'}</div><div class="tree-group"><div class="tree-title">BLUEPRINT / 数学对象</div>${fileTree([...files].map(([path,items])=>({path,items})),file=>`<details open><summary title="${esc(file.path)}">◇ ${esc(file.name)}</summary>${file.items.map(treeButton).join('')}</details>`)}</div>`;
}
async function selectNode(id,updateHash=true){if(!canLeave())return false;const request=++state.request;const detail=await api(`/api/node?id=${encodeURIComponent(id)}`);if(request!==state.request)return false;const changed=state.selected!==id;state.selected=id;syncGraphContext(graphView,state.project,id,changed);state.detail=detail;state.binding=0;state.document=null;state.dirty=false;state.boundary=null;state.lastWheel=performance.now();if(updateHash)setHash(id);renderTree();await renderContent();renderFormal();return true;}
function nodeHeader(n){return `<header class="node-heading"><span class="eyebrow">${n.tex?'PAPER BLUEPRINT':'MATHEMATICAL OBJECT'}</span><h1>${esc(n.title)}</h1><div class="node-meta"><span class="badge">${kindLabel[n.kind]}</span><span class="status-badge"><i class="dot ${n.status}"></i>${statusLabel[n.status]}</span><span>${esc(n.path)} : ${n.line}</span></div></header>`;}
function relationMarkup(n){const chips=items=>items.map(r=>`<button data-node="${esc(r.id)}">↗ ${esc(r.title)}</button>`).join('');return `<section class="relations"><h4>DEPENDENCIES / 依赖</h4><div class="relation-chips">${chips(n.relations.filter(r=>r.kind==='uses'))||'<span class="hint">无前置依赖</span>'}</div>${n.relations.some(r=>r.kind==='inspired_by')?`<h4>INSPIRED BY / 思想来源</h4><div class="relation-chips">${chips(n.relations.filter(r=>r.kind==='inspired_by'))}</div>`:''}${n.backlinks.length?`<h4>USED BY / 反向引用</h4><div class="relation-chips">${chips(n.backlinks)}</div>`:''}</section>`;}
async function renderContent(){const n=state.detail;if(!n)return;$('#breadcrumb').textContent=n.tex_content?`tex / ${n.tex_content.path}`:`blueprint / ${n.path}`;document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===state.mode));$('#previous').disabled=!n.previous;$('#next').disabled=!n.next;$('#position').textContent=n.tex_content?`§ ${n.tex_content.label}`:'LIBRARY OBJECT';
  const content=$('#content');
  if(state.mode==='edit'){const selected=state.selected;const doc=await api(`/api/document?path=${encodeURIComponent(n.path)}`);if(state.selected!==selected||state.mode!=='edit')return;state.document=doc;content.innerHTML=`${nodeHeader(n)}<p class="hint">编辑整份 Markdown 文件。每个一级标题是一个节点。</p><textarea id="markdown-editor" class="editor" aria-label="Markdown 源文件" spellcheck="false"></textarea><div class="editor-actions"><span id="save-state">已与磁盘同步</span><button id="save-document" class="primary">保存文件</button></div>`;$('#markdown-editor').value=doc.text;$('#markdown-editor').addEventListener('input',()=>{state.dirty=$('#markdown-editor').value!==state.document.text;$('#save-state').textContent=state.dirty?'有未保存的更改':'已与磁盘同步';});$('#save-document').onclick=guarded(saveDocument);
  }else if(state.mode==='tex'){content.innerHTML=`${nodeHeader(n)}${n.tex_content?`<div class="hint">${esc(n.tex_content.path)} · 第 ${n.tex_content.line} 行</div><pre class="tex-source">${esc(n.tex_content.source)}</pre>`:'<div class="empty-state"><h3>这个节点没有绑定 TeX</h3><p>标准库数学对象可以独立于论文存在。</p></div>'}${relationMarkup(n)}`;
  }else{content.innerHTML=`${nodeHeader(n)}<div class="description">${n.body_html||'<p>暂无节点描述，可在 Markdown 中补充。</p>'}</div>${n.tex_content?`${n.tex_content.warnings.map(w=>`<div class="warning">${esc(w)}</div>`).join('')}<div class="paper-content">${n.tex_content.html}</div>`:`<div class="hint">LIBRARY NOTE · 独立数学对象</div>`}${relationMarkup(n)}`;math(content);}
  content.scrollTop=0;
}
async function saveDocument(){const button=$('#save-document');button.disabled=true;try{await api('/api/document',{method:'PUT',body:JSON.stringify({...state.document,text:$('#markdown-editor').value})});state.dirty=false;toast('已保存，索引已更新');await loadProject();}finally{if(button.isConnected)button.disabled=false;}}
function highlight(line){const escaped=esc(line);if(/^\s*(--|\/\/|\(\*)/.test(line))return `<span class="code-comment">${escaped}</span>`;return escaped.replace(/\b(theorem|lemma|def|by|simp|exact|intro|apply|namespace|end|import|open|where|module|data|Set|Definition|Theorem|Proof|Qed|forall|fun|variable|structure|inductive|axiom)\b/g,'<span class="code-keyword">$1</span>');}
function renderFormal(){const n=state.detail;if(!n?.formal.length){$('#formal-content').innerHTML='<div class="empty-code"><span class="empty-symbol">⌘</span><strong>还没有形式化代码</strong>在 Markdown 节点中添加 Lean、Agda 或 Coq 绑定，开始连接证明。</div>';return;}const binding=n.formal[state.binding]||n.formal[0];$('#formal-content').innerHTML=`<div class="formal-tabs">${n.formal.map((b,i)=>`<button data-binding="${i}" class="${i===state.binding?'active':''}">${esc(b.language.toUpperCase())}${n.formal.filter(x=>x.language===b.language).length>1?` · ${i+1}`:''}</button>`).join('')}</div><div class="binding-name">${esc(binding.declaration)}</div>${binding.code!==null?`<div class="code-location"><span>⌑ ${esc(binding.file)}</span><span>L${binding.lines[0]}–${binding.lines[1]}</span></div><pre class="code-block">${binding.code.split('\n').map((line,i)=>`<span class="code-line"><span class="line-number">${binding.lines[0]+i}</span><span class="code-text">${highlight(line)}</span></span>`).join('')}</pre>`:`<div class="empty-code"><strong>${esc(binding.error)}</strong>可通过「导入资料」下载仓库，或填写准确的 file / lines。</div>`}${binding.url?`<a class="source-link" target="_blank" rel="noopener noreferrer" href="${esc(binding.url)}">查看代码来源 ↗</a>`:''}`;}

function setView(view){state.view=view;$('#reader').classList.toggle('hidden',view!=='reader');$('#graph').classList.toggle('hidden',view!=='graph');$('#reader-view').classList.toggle('active',view==='reader');$('#graph-view').classList.toggle('active',view==='graph');if(view==='graph')renderGraph();else graph.stop();}
const graph=new KnowledgeGraph($('#graph-svg'),node=>{
  graphView.focusId=node.id;
  const label=graphView.level==='project'?'项目':graphView.level==='file'?'Milestone':kindLabel[node.kind];
  const action=graphView.level==='project'?'查看 milestones':graphView.level==='file'?'查看 blueprint 节点':'打开节点';
  const preview=$('#graph-preview');preview.classList.remove('hidden');
  preview.innerHTML=`<span class="badge">${label} · ${statusLabel[node.status]}</span><h3>${esc(node.title)}</h3><p>${esc(node.body.replace(/\[\[|\]\]/g,'').replace(/\*\*/g,''))||'暂无描述'}</p><button data-graph-open="${esc(node.id)}">${action} →</button>`;
},guarded(openGraphItem));

async function openGraphItem(id){
  if(graphView.level==='node'){
    if(await selectNode(id))setView('reader');
    return;
  }
  drillGraph(graphView,state.project,id);
  // Drilling must show every member, even if the previous view was filtered.
  $('#graph-kind').value='';$('#graph-status').value='';$('#graph-local').checked=false;
  renderGraph();
}

function renderGraph(){
  if(!state.project)return;
  syncGraphContext(graphView,state.project,state.selected);
  const groups=state.project.graph.projects;
  $('#graph-level').value=graphView.level;
  $('#graph-scope').value=graphView.scope;
  $('#graph-scope').disabled=graphView.level==='project';
  $('#graph-project').innerHTML=groups.map(p=>`<option value="${esc(p.id)}">${esc(p.path==='.'?p.title:p.path)}</option>`).join('');
  $('#graph-project').value=graphView.projectId??'';
  $('#graph-project').disabled=graphView.level==='project'||!groups.length;
  $('#graph-kind').disabled=graphView.level!=='node';
  const data=graphProjection(state.project,graphView,state.selected);
  const unit={node:'blueprint 节点',file:'milestones',project:'项目'}[graphView.level];
  $('#graph-context').textContent=`${graphView.scope==='all'?'全范围':`当前项目：${graphView.projectId??'无项目'}`} · ${graphView.highlightLabel?`${graphView.highlightLabel}：高亮 ${data.highlightIds.length} 个${unit}`:'单击预览，双击'+(graphView.level==='node'?'打开节点':'下钻')}`;
  $('#graph-preview').classList.add('hidden');
  graph.render(data,data.selected,{layout:$('#graph-layout').value,kind:graphView.level==='node'?$('#graph-kind').value:'',status:$('#graph-status').value,local:$('#graph-local').checked,highlightIds:data.highlightIds,unit});
}
async function openPaper(path,line=1){if(!canLeave())return;const data=await api(`/api/tex?path=${encodeURIComponent(path)}`);state.dirty=false;state.detail=null;state.mode='tex';setView('reader');$('#breadcrumb').textContent=`tex / ${path}`;$('#content').innerHTML=`<span class="eyebrow">PAPER SOURCE</span><h2>${esc(path)}</h2><p class="hint">此位置尚无绑定节点。可以在 Markdown 中用 tex 字段关联 bpnode 标签。</p><pre class="tex-source">${data.source.split('\n').map((s,i)=>`<span id="tex-line-${i+1}">${esc(s)}\n</span>`).join('')}</pre>`;$('#formal-content').innerHTML='<div class="empty-code">选择 Blueprint 节点以定位代码</div>';$('#previous').disabled=true;$('#next').disabled=true;$(`#tex-line-${line}`)?.scrollIntoView({block:'start'});}

document.addEventListener('click',guarded(async e=>{const node=e.target.closest('[data-node]');if(node){if(await selectNode(node.dataset.node))setView('reader');return;}const paper=e.target.closest('[data-paper]');if(paper){await openPaper(paper.dataset.paper,Number(paper.dataset.line)||1);return;}const binding=e.target.closest('[data-binding]');if(binding){state.binding=Number(binding.dataset.binding);renderFormal();return;}const mode=e.target.closest('[data-mode]');if(mode&&state.detail){if(!canLeave())return;state.dirty=false;state.mode=mode.dataset.mode;await renderContent();return;}const open=e.target.closest('[data-graph-open]');if(open){await openGraphItem(open.dataset.graphOpen);return;}const link=e.target.closest('a.wikilink');if(link){e.preventDefault();if(await selectNode(decodeURIComponent(link.hash.slice(6))))setView('reader');}}));
$('#search').addEventListener('input',renderTree);$('#reader-view').onclick=()=>setView('reader');$('#graph-view').onclick=()=>setView('graph');$('#toggle-sidebar').onclick=()=>$('#sidebar').classList.toggle('hidden');$('#toggle-code').onclick=()=>$('#formal').classList.toggle('hidden');$('#previous').onclick=guarded(()=>state.detail?.previous&&selectNode(state.detail.previous));$('#next').onclick=guarded(()=>state.detail?.next&&selectNode(state.detail.next));$('#reload').onclick=guarded(async()=>{if(!canLeave())return;state.dirty=false;await api('/api/reload',{method:'POST'});await loadProject();toast('已重新读取工作区');});
for(const id of ['graph-layout','graph-kind','graph-status','graph-local'])$('#'+id).addEventListener('change',renderGraph);
$('#graph-level').onchange=()=>{changeGraphLevel(graphView,$('#graph-level').value);$('#graph-local').checked=false;renderGraph();};
$('#graph-scope').onchange=()=>{graphView.scope=$('#graph-scope').value;graphView.focusId=null;renderGraph();};
$('#graph-project').onchange=()=>{graphView.projectId=$('#graph-project').value;graphView.highlightIds=[];graphView.highlightLabel=null;graphView.focusId=null;renderGraph();};
$('#graph-reset').onclick=()=>{graphView.focusId=null;renderGraph();};
$('#content').addEventListener('wheel',guarded(async e=>{if(state.mode==='edit'||!state.detail||state.view!=='reader')return;const el=$('#content'),now=performance.now();if(now-state.lastWheel<800)return;const direction=e.deltaY>0?'next':'previous';const edge=direction==='next'?el.scrollTop+el.clientHeight>=el.scrollHeight-3:el.scrollTop<=3;if(!edge){state.boundary=null;return;}if(state.boundary?.direction===direction&&now-state.boundary.at>220){const target=state.detail[direction];state.boundary=null;if(target)await selectNode(target);}else if(!state.boundary||state.boundary.direction!==direction){state.boundary={direction,at:now};}}),{passive:true});
document.addEventListener('keydown',guarded(async e=>{const typing=/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);if(e.key==='/'&&!typing&&!document.querySelector('dialog[open]')){e.preventDefault();$('#sidebar').classList.remove('hidden');$('#search').focus();}if(e.altKey&&['ArrowLeft','ArrowRight'].includes(e.key)&&!typing){e.preventDefault();const id=state.detail?.[e.key==='ArrowRight'?'next':'previous'];if(id)await selectNode(id);}if((e.ctrlKey||e.metaKey)&&e.key==='s'&&state.mode==='edit'&&state.document){e.preventDefault();await saveDocument();}}));
window.addEventListener('popstate',guarded(async()=>{const id=decodeURIComponent(location.hash.replace(/^#node=/,''));if(state.project?.nodes.some(n=>n.id===id)){if(await selectNode(id,false))setView('reader');else setHash(state.selected);}}));
window.addEventListener('beforeunload',e=>{if(state.dirty){e.preventDefault();e.returnValue='';}});
if(matchMedia('(max-width:800px)').matches)$('#sidebar').classList.add('hidden');

$('#diagnostics-open').onclick=()=>{const diagnostics=state.project?.diagnostics||[];$('#diagnostics-list').innerHTML=diagnostics.length?diagnostics.map(d=>`<div class="diagnostic"><strong>${d.severity==='error'?'错误':'提示'} · ${esc(d.path)}${d.line?`:${d.line}`:''}</strong><div>${esc(d.message)}</div></div>`).join(''):'<p class="muted">没有发现索引错误或断开的依赖链接。</p>';$('#diagnostics-dialog').showModal();};
document.querySelectorAll('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());$('#import-open').onclick=()=>$('#import-dialog').showModal();$('#import-kind').onchange=()=>{const paper=$('#import-kind').value==='paper';$('#code-options').classList.toggle('hidden',paper);$('#import-verify-option').classList.toggle('hidden',paper);$('#paper-name').classList.toggle('hidden',!paper);$('#paper-name input').required=paper;$('#source-label').firstChild.textContent=paper?'arXiv 编号或地址':'仓库 URL';$('#source-label input').placeholder=paper?'2001.00001 或 https://arxiv.org/abs/…':'https://github.com/owner/repository';};
$('#import-form').addEventListener('submit',guarded(async e=>{e.preventDefault();const values=Object.fromEntries(new FormData(e.target));values.ref=values.ref||null;values.verify_after_download=e.target.elements.verify_after_download.checked;const button=$('#import-submit');button.disabled=true;$('#import-result').textContent='正在提交下载任务…';try{const job=await api('/api/import',{method:'POST',body:JSON.stringify(values)});let finished=false;while(!finished){await new Promise(resolve=>setTimeout(resolve,1200));const current=await api(`/api/jobs/${job.id}`);renderImportJob($('#import-result'),current);finished=['succeeded','failed'].includes(current.status);if(current.status==='succeeded'){if(!state.dirty)await loadProject();else toast('资料已导入；保存当前编辑后刷新索引');}}}finally{button.disabled=false;}}));

guarded(()=>loadProject(false))();

$('#import-history').addEventListener('click',guarded(async()=>{const data=await api('/api/formal-reports');const target=$('#import-result');target.textContent=data.reports.length?'最近验证报告':'当前工作区暂无验证报告';renderReports(target,data.reports);}));
