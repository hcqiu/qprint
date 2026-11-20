import {formatContext} from './clipboard-context.js';
import {captureAnchor, rangeForAnchor} from './chat-anchors.js';
import {createModelPicker} from './chat-model-picker.js';

const $ = selector => document.querySelector(selector);
const element = (tag, className, text) => {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
};

export function createChatPanel({api, state, toast, navigate, renderMath}) {
  let settings = null, sessions = [], active = null, selection = null, timer, drawing = false;
  let loading = false, opening = 0, sending = false, pendingSelection = null, rendered = '';
  const drafts = new Map();
  const requests = new Map();
  const content = $('#content'), panel = $('#agent-panel'), dialog = $('#agent-dialog');
  const ask = $('#ask-agent'), markers = $('#agent-markers'), list = $('#agent-messages');
  const safe = fn => (...args) => Promise.resolve().then(() => fn(...args)).catch(error => toast(error.message));
  const post = (path, body) => api(path, {method: 'POST', body: JSON.stringify(body || {})});
  const currentProfile = () => settings?.profiles.find(p => p.id === settings.selected);
  const modelPicker = createModelPicker({request:post, changed:() => { if (active) render(); }});

  function fillSettings() {
    const select = $('#agent-choice');
    select.replaceChildren(...settings.profiles.map(profile => {
      const option = element('option', '', `${profile.name}${profile.available ? profile.kind === 'api' ? ' · 已配置' : ' · 已找到' : ' · 待配置'}`);
      option.value = profile.id;
      return option;
    }));
    select.value = settings.selected;
    showProfile();
    $('#agent-settings-open').title = `Agent 设置 · ${currentProfile()?.name || '选择 Agent'}`;
  }

  function showProfile() {
    const profile = settings.profiles.find(p => p.id === $('#agent-choice').value);
    const isApi = profile.kind === 'api';
    $('#agent-cli-fields').hidden = isApi;
    $('#agent-api-fields').hidden = !isApi;
    $('#agent-custom-args-label').hidden = profile.id !== 'custom';
    $('#agent-command').value = profile.command;
    $('#agent-args').value = JSON.stringify(profile.args);
    $('#agent-model').value = profile.model || '';
    $('#agent-model-label').hidden = profile.kind === 'acp';
    $('#agent-base-url').value = profile.base_url || 'https://api.openai.com/v1';
    $('#agent-key').value = '';
    $('#agent-key').placeholder = profile.has_key ? '已提供，留空保持不变' : '输入 API key';
    $('#agent-detected').textContent = isApi
      ? '兼容 OpenAI Chat Completions 的服务。密钥仅保存在本次服务内存中；也可设置 OPENAI_API_KEY。'
      : profile.path ? `已找到：${profile.path}\n使用该 Agent 自己的登录和配置，连接时检查是否可用。`
        : '尚未找到。可安装并登录后重新查找，或填写可执行文件的完整路径。';
    $('#agent-permissions').textContent = profile.kind === 'codex' ? 'Codex 默认只读；需要额外权限时会在会话中询问。'
      : profile.kind === 'claude' ? 'Claude Code 使用非交互模式；需要人工授权的工具会被拒绝，并在回答中说明。'
      : profile.kind === 'acp' ? '使用 Agent 自身的权限配置；ACP 授权请求会显示在会话中。' : 'API 模式提供文本问答，不执行本地工具。';
  }

  async function refresh() {
    const results = await Promise.all([api('/api/chat/settings'), api('/api/chat/sessions')]);
    settings = results[0]; sessions = results[1].sessions;
    fillSettings(); draw(); history();
  }

  function history() {
    const select = $('#agent-history');
    select.replaceChildren(element('option', '', '选择已保存的会话…'));
    select.firstChild.value = '';
    for (const session of [...sessions].reverse()) {
      const option = element('option', '', `${session.anchor.quote.slice(0, 55)} · ${session.agent}`);
      option.value = session.id;
      select.append(option);
    }
    select.value = active?.id || '';
  }

  function draw() {
    if (drawing) return;
    drawing = true;
    requestAnimationFrame(() => {
      drawing = false;
      markers.replaceChildren();
      const ranges = [], positions = [];
      if (state.view === 'reader' && state.mode !== 'edit') {
        const box = content.getBoundingClientRect(), frame = markers.getBoundingClientRect();
        for (const session of sessions) {
          if (session.anchor.node !== state.detail?.id || session.anchor.view !== state.mode) continue;
          const range = rangeForAnchor(content, session.anchor);
          if (!range) continue;
          ranges.push(range);
          const rects = [...range.getClientRects()].filter(r => r.width && r.height);
          const rect = rects.find(r => r.bottom > box.top + 4 && r.top < box.bottom - 24);
          if (!rect) continue;
          let top = Math.max(box.top, rect.top) - frame.top;
          while (positions.some(y => Math.abs(y - top) < 27)) top += 28;
          if (top + frame.top > box.bottom - 24) continue;
          positions.push(top);
          const button = element('button', 'agent-bubble', '◌');
          button.title = `打开会话：${session.anchor.quote.slice(0, 100)}`;
          button.setAttribute('aria-label', button.title);
          button.style.top = `${top}px`;
          // Use the reading gutter so a bubble never covers the next word.
          button.style.left = `${box.right - frame.left - 29}px`;
          button.classList.toggle('active', active?.id === session.id);
          button.onclick = safe(() => openSession(session.id));
          markers.append(button);
        }
      }
      if (globalThis.CSS?.highlights && globalThis.Highlight) CSS.highlights.set('agent-passages', new Highlight(...ranges));
    });
  }

  function selectionChanged() {
    if (dialog.open || !settings || state.view !== 'reader' || !state.detail?.copy_context) { ask.hidden = true; return; }
    const selected = window.getSelection();
    const anchor = captureAnchor(content, selected, state.detail.id, state.mode);
    if (!anchor) { ask.hidden = true; return; }
    const range = selected.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    selection = {anchor, context: formatContext(state.detail.copy_context, String(selected))};
    ask.hidden = false;
    ask.style.left = `${Math.max(8, Math.min(innerWidth - 130, rect.left))}px`;
    ask.style.top = `${Math.max(70, Math.min(innerHeight - 45, rect.top - 40))}px`;
  }

  async function startSelection(value) {
    if (loading) return;
    loading = true;
    try {
      const session = await post('/api/chat/sessions', value);
      sessions.push(session);
      await openSession(session.id);
      history(); draw();
      window.getSelection()?.removeAllRanges();
      $('#agent-question').focus();
    } finally { loading = false; }
  }

  function rememberDraft() { if (active) drafts.set(active.id, $('#agent-question').value); }
  async function openSession(id) {
    rememberDraft();
    const sequence = ++opening;
    const session = await api(`/api/chat/sessions/${id}`);
    if (sequence !== opening) return;
    active = session;
    rendered = '';
    panel.hidden = false;
    document.body.classList.add('agent-panel-open');
    $('#agent-question').value = drafts.get(id) || '';
    modelPicker.open(session);
    render(); history(); draw(); poll();
  }

  function render() {
    if (!active) return;
    $('#agent-session-title').textContent = settings?.profiles.find(p => p.id === active.agent)?.name || active.agent;
    $('#agent-quote').textContent = active.anchor.quote;
    $('#agent-quote').title = '返回这段文字';
    $('#agent-context').textContent = active.context;
    const busy = ['running', 'waiting'].includes(active.status);
    modelPicker.setBusy(busy || sending);
    $('#agent-send').disabled = busy || sending || modelPicker.blocked() || !$('#agent-question').value.trim();
    $('#agent-send').hidden = busy;
    $('#agent-stop').hidden = !busy;
    $('#agent-activity').textContent = active.error || (busy ? '正在思考…' : '');
    $('#agent-activity').classList.toggle('agent-error', Boolean(active.error));
    const signature = JSON.stringify([active.messages, busy]);
    if (signature !== rendered) {
      const atBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 70;
      const nodes = active.messages.map((message, index) => {
        const article = element('article', `agent-message ${message.role}`);
        article.append(element('strong', '', message.role === 'user' ? '你' : $('#agent-session-title').textContent));
        if (message.role === 'assistant' && message.model) article.append(element('small', 'agent-message-model', [message.model, message.effort].filter(Boolean).join(' · ')));
        const body = element('div', 'agent-message-text', message.text || (busy && index === active.messages.length - 1 ? '正在思考…' : '未返回回答'));
        article.append(body);
        // Render math only after a turn, never interpret model output as HTML.
        if (!busy && message.role === 'assistant') renderMath(body);
        return article;
      });
      list.replaceChildren(...nodes);
      if (atBottom || !rendered) list.scrollTop = list.scrollHeight;
      rendered = signature;
    }
    renderPending();
  }

  function renderPending() {
    const target = $('#agent-pending'), pending = active.pending;
    if (target.dataset.request === (pending?.id || '')) return;
    target.replaceChildren(); target.dataset.request = pending?.id || '';
    if (!pending) return;
    target.append(element('strong', '', pending.questions.length ? 'Agent 需要你的回复' : 'Agent 请求授权'));
    const detail = element('details'); detail.append(element('summary', '', '查看请求详情'), element('pre', '', pending.detail)); target.append(detail);
    if (pending.questions.length) {
      const form = element('form');
      for (const question of pending.questions) {
        const label = element('label', '', question.question || question.header);
        const input = element('input'); input.name = question.id; input.required = true;
        input.placeholder = (question.options || []).map(o => o.label).join(' / ');
        label.append(input); form.append(label);
      }
      const submit = element('button', '', '回复'); submit.type = 'submit'; form.append(submit);
      form.onsubmit = safe(async event => { event.preventDefault(); await post(`/api/chat/sessions/${active.id}/answer`, {request_id: pending.id, answers: Object.fromEntries(new FormData(form))}); submit.disabled = true; });
      target.append(form);
    } else for (const option of pending.options) {
      const button = element('button', '', option.label);
      button.onclick = safe(async () => { await post(`/api/chat/sessions/${active.id}/answer`, {request_id: pending.id, option: option.id}); target.querySelectorAll('button').forEach(b => b.disabled = true); });
      target.append(button);
    }
  }

  function poll() {
    clearTimeout(timer);
    if (!active || panel.hidden || !['running', 'waiting'].includes(active.status)) return;
    const id = active.id;
    timer = setTimeout(async () => {
      try {
        const session = await api(`/api/chat/sessions/${id}`);
        if (active?.id !== id) return;
        active = session; render();
      } catch (error) { $('#agent-activity').textContent = `连接暂时中断：${error.message}；正在重连…`; }
      poll();
    }, 700);
  }

  $('#agent-settings-open').onclick = safe(async () => { if (!settings) await refresh(); dialog.showModal(); });
  $('#agent-choice').onchange = showProfile;
  $('#agent-discover').onclick = safe(async () => {
    $('#agent-discover').disabled = true;
    try { settings = await post('/api/chat/discover'); fillSettings(); } finally { $('#agent-discover').disabled = false; }
  });
  $('#agent-settings-form').onsubmit = safe(async event => {
    event.preventDefault();
    let args;
    try { args = JSON.parse($('#agent-args').value || '[]'); } catch { throw new Error('启动参数应是 JSON 字符串数组，例如 ["acp"]'); }
    if (!Array.isArray(args) || args.some(arg => typeof arg !== 'string')) throw new Error('启动参数应是字符串数组');
    settings = await api('/api/chat/settings', {method: 'PUT', body: JSON.stringify({selected: $('#agent-choice').value,
      command: $('#agent-command').value, args, model: $('#agent-model').value, base_url: $('#agent-base-url').value,
      api_key: $('#agent-key').value || null})});
    fillSettings(); dialog.close();
    if (active) modelPicker.reload();
    if (pendingSelection && currentProfile()?.available) { const value = pendingSelection; pendingSelection = null; await startSelection(value); }
    toast('Agent 设置已保存');
  });
  ask.onpointerdown = event => event.preventDefault();
  ask.onclick = safe(async () => {
    if (!selection || selection.anchor.node !== state.detail?.id) return;
    ask.hidden = true;
    if (!currentProfile()?.available) { pendingSelection = selection; dialog.showModal(); return; }
    await startSelection(selection);
  });
  $('#agent-chat-open').onclick = safe(async () => {
    if (!settings) await refresh();
    if (active) await openSession(active.id);
    else if (sessions.length) await openSession(sessions.at(-1).id);
    else { panel.hidden = false; document.body.classList.add('agent-panel-open'); }
  });
  $('#agent-panel-close').onclick = () => { rememberDraft(); panel.hidden = true; document.body.classList.remove('agent-panel-open'); clearTimeout(timer); draw(); };
  $('#agent-history').onchange = safe(event => event.target.value && openSession(event.target.value));
  $('#agent-quote').onclick = safe(async () => {
    if (!active) return;
    await navigate(active.anchor.node, active.anchor.view);
    const range = rangeForAnchor(content, active.anchor);
    if (range) {
      const el = range.startContainer.parentElement;
      el.scrollIntoView({block: 'center'});
    } else toast('原文已改变，无法准确定位；会话仍然保留');
    draw();
  });
  $('#agent-chat-form').onsubmit = safe(async event => {
    event.preventDefault();
    const text = $('#agent-question').value.trim();
    if (!active || !text || sending || modelPicker.blocked() || ['running', 'waiting'].includes(active.status)) return;
    const id = active.id;
    const previous = requests.get(id);
    const selected = modelPicker.selection();
    const request = previous?.text === text && previous.model === selected.model && previous.effort === selected.effort
      ? previous : {text, request_id: crypto.randomUUID(), ...selected};
    requests.set(id, request);
    sending = true; render();
    try {
      const session = await post(`/api/chat/sessions/${id}/messages`, request);
      requests.delete(id);
      drafts.delete(id);
      if (active?.id === id) { active = session; $('#agent-question').value = ''; }
    } finally { sending = false; render(); poll(); }
  });
  $('#agent-question').oninput = () => { if (active) render(); };
  $('#agent-question').onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('#agent-chat-form').requestSubmit(); } };
  $('#agent-stop').onclick = safe(() => active && post(`/api/chat/sessions/${active.id}/stop`));
  document.addEventListener('selectionchange', selectionChanged);
  document.addEventListener('pointerup', selectionChanged);
  content.addEventListener('scroll', () => { ask.hidden = true; draw(); });
  window.addEventListener('resize', () => { ask.hidden = true; draw(); });
  new ResizeObserver(draw).observe(content);
  new MutationObserver(() => { ask.hidden = true; selection = null; draw(); }).observe(content, {subtree: true, childList: true, characterData: true});
  document.addEventListener('qprint-view-change', () => { ask.hidden = true; draw(); });
  return {refresh};
}
