// Anchors use UTF-16 offsets, just like DOM Range. Never guess among duplicates.
export function resolveAnchor(text, anchor) {
  const {quote, start, prefix = '', suffix = ''} = anchor;
  if (!quote) return -1;
  const contextMatches = at => (!prefix || text.slice(Math.max(0, at - prefix.length), at) === prefix)
    && (!suffix || text.slice(at + quote.length, at + quote.length + suffix.length) === suffix);
  if (text.slice(start, start + quote.length) === quote && contextMatches(start)) return start;
  const matches = [];
  for (let at = text.indexOf(quote); at !== -1; at = text.indexOf(quote, at + 1)) matches.push(at);
  const contextual = matches.filter(contextMatches);
  if (contextual.length === 1) return contextual[0];
  return matches.length === 1 ? matches[0] : -1;
}

export function rangeForAnchor(content, anchor) {
  const start = resolveAnchor(content.textContent, anchor);
  if (start < 0) return null;
  const range = document.createRange();
  const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
  let offset = 0, began = false, node;
  while ((node = walker.nextNode())) {
    const next = offset + node.length;
    if (!began && start < next) { range.setStart(node, start - offset); began = true; }
    if (began && start + anchor.quote.length <= next) {
      range.setEnd(node, start + anchor.quote.length - offset);
      return range;
    }
    offset = next;
  }
  return null;
}

export function captureAnchor(content, selection, node, view) {
  if (!selection || selection.isCollapsed || selection.rangeCount !== 1 || !node || !['rendered', 'tex'].includes(view)) return null;
  const range = selection.getRangeAt(0);
  if (!content.contains(range.startContainer) || !content.contains(range.endContainer)) return null;
  const parent = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
  if (parent.closest('input, textarea, select, [contenteditable="true"]')) return null;
  const quote = range.toString();
  if (!quote.trim() || quote.length > 20000) return null;
  const before = range.cloneRange();
  before.selectNodeContents(content);
  before.setEnd(range.startContainer, range.startOffset);
  const start = before.toString().length, text = content.textContent;
  return {node, view, quote, start, end: start + quote.length,
    prefix: text.slice(Math.max(0, start - 40), start), suffix: text.slice(start + quote.length, start + quote.length + 40)};
}
