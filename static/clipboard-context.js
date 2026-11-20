// The bundle arrives with node detail, before the reader becomes selectable.
// A native copy event must stay synchronous: never fetch or await here.
export function formatContext(bundle, question) {
  const dependencies = bundle.dependencies.map((entry, index) =>
    `${index + 1}. ${entry.title}\nNode: ${entry.node}\n${entry.description || '(No description recorded.)'}`);
  if (bundle.dependencies_omitted) dependencies.push(`(${bundle.dependencies_omitted} additional dependencies omitted; use Knowledge Navigator to expand.)`);
  if (bundle.unresolved_dependencies.length) dependencies.push(`Unresolved references (not verified dependencies):\n${bundle.unresolved_dependencies.join('\n')}`);
  if (bundle.unresolved_omitted) dependencies.push(`(${bundle.unresolved_omitted} additional unresolved references omitted.)`);
  return [
    '[Qprint Context]',
    `Current node:\n${bundle.node}`,
    `Source (relative to workspace):\n${bundle.source}`,
    bundle.tex === null
      ? `Current node tex:\n(No TeX source is available for this node.)\n\nNode description:\n${bundle.description}`
      : `Current node tex:\n${bundle.tex}`,
    `Dependencies (direct; names and descriptions only):\n${dependencies.join('\n\n') || '(None recorded.)'}`,
    'Instruction:\nAnswer using the mathematical context above. If it is insufficient, use Knowledge Navigator: resolve a node ID, open its description and dependencies, then read its TeX source as needed.',
    `User question:\n${question}`,
  ].join('\n\n');
}

function elementFor(node) {
  return node?.nodeType === 1 ? node : node?.parentElement;
}

export function copyWithContext(event, {selection, content, bundle, nodeId, enabled, activeElement}) {
  if (!enabled || event.defaultPrevented || !event.clipboardData || !bundle || bundle.node !== nodeId) return false;
  if (!selection || selection.isCollapsed || !selection.rangeCount) return false;
  const editable = element => element?.closest('input, textarea, select') || element?.isContentEditable;
  if (editable(activeElement) || editable(elementFor(selection.anchorNode)) || editable(elementFor(selection.focusNode))) return false;
  // Both endpoints of every range must belong to this visible node's reader.
  for (let i = 0; i < selection.rangeCount; i++) {
    const range = selection.getRangeAt(i);
    if (!content?.contains(range.startContainer) || !content.contains(range.endContainer)) return false;
  }
  const question = String(selection);
  if (!question.trim()) return false;
  event.clipboardData.setData('text/plain', formatContext(bundle, question));
  event.preventDefault();
  return true;
}
