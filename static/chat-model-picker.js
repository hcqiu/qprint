const effortNames = {none:'关闭', minimal:'最低', low:'低', medium:'中', high:'高', xhigh:'很高', max:'最高', ultra:'Ultra'};
const effortLabel = entry => effortNames[entry.id] || entry.name || entry.id;

export function pickerState(catalog, choice) {
  const models = catalog?.models || [];
  const effective = choice.model || catalog?.default_model || '';
  const model = models.find(item => item.id === effective);
  const levels = model?.efforts || [];
  const defaultEffort = (effective === catalog?.default_model ? catalog?.default_effort : '') || model?.default_effort || '';
  return {models, model, levels, defaultEffort,
    invalidModel: Boolean((choice.model && !model) || (catalog?.requires_model && !effective)),
    invalidEffort: Boolean(choice.effort && !levels.some(item => item.id === choice.effort)),
    needsDiscovery: Boolean(model && !model.efforts_loaded)};
}

export function createModelPicker({request, changed}) {
  const modelSelect = document.querySelector('#agent-model-select');
  const effortSelect = document.querySelector('#agent-effort-select');
  const refresh = document.querySelector('#agent-model-refresh');
  const hint = document.querySelector('#agent-model-hint');
  const drafts = new Map();
  let sessionId = null, choice = {model:'', effort:''}, catalog = null, loading = false, busy = false, sequence = 0;
  const option = (value, label) => { const result = document.createElement('option'); result.value = value; result.textContent = label; return result; };

  function render() {
    const state = pickerState(catalog, choice);
    modelSelect.replaceChildren(option('', catalog?.default_model ? state.models.find(m => m.id === catalog.default_model)?.name || catalog.default_model : catalog?.requires_model ? '选择模型' : '默认模型'),
      ...state.models.map(m => option(m.id, m.name)));
    if (state.invalidModel && choice.model) modelSelect.append(option(choice.model, `${choice.model}（暂不可用）`));
    modelSelect.value = choice.model;
    effortSelect.replaceChildren(option('', state.defaultEffort ? effortLabel({id:state.defaultEffort}) : '默认强度'),
      ...state.levels.map(e => option(e.id, effortLabel(e))));
    if (state.invalidEffort) effortSelect.append(option(choice.effort, `${choice.effort}（当前不可用）`));
    effortSelect.value = choice.effort;
    modelSelect.disabled = !sessionId || loading || busy;
    effortSelect.disabled = !sessionId || loading || busy || (!state.levels.length && !state.invalidEffort);
    refresh.disabled = !sessionId || loading || busy;
    hint.textContent = loading ? '' : catalog?.requires_model && !choice.model && !catalog.default_model
      ? (catalog.error ? `模型列表暂不可用：${catalog.error}` : '请选择模型后发送。')
      : state.invalidModel || state.invalidEffort
      ? '原选择当前不可用，请重新选择模型和强度。'
      : catalog?.error ? `模型列表暂不可用：${catalog.error}`
      : '';
    hint.hidden = !hint.textContent;
    modelSelect.setAttribute('aria-busy', String(loading));
  }

  async function load(force = false) {
    if (!sessionId) return;
    const id = sessionId, version = ++sequence, selected = choice.model;
    loading = true; render(); changed();
    try {
      const data = await request(`/api/chat/sessions/${id}/models`, {model:selected, refresh:force});
      if (version !== sequence || id !== sessionId) return;
      catalog = data;
    } catch (error) {
      if (version !== sequence || id !== sessionId) return;
      catalog = {models:[], error:error.message};
    } finally {
      if (version === sequence && id === sessionId) { loading = false; render(); changed(); }
    }
  }

  modelSelect.onchange = () => {
    choice = {model:modelSelect.value, effort:''};
    drafts.set(sessionId, {...choice});
    if (pickerState(catalog, choice).needsDiscovery) load();
    else { render(); changed(); }
  };
  effortSelect.onchange = () => { choice.effort = effortSelect.value; drafts.set(sessionId, {...choice}); render(); changed(); };
  refresh.onclick = () => load(true);
  render();
  return {
    open(session) {
      sessionId = session.id; choice = {...(drafts.get(session.id) || session.selection || {model:'', effort:''})};
      catalog = null; load();
    },
    setBusy(value) { busy = value; render(); },
    blocked() { const state = pickerState(catalog, choice); return loading || state.invalidModel || state.invalidEffort; },
    selection() { return {...choice}; },
    reload() { return load(true); },
  };
}
