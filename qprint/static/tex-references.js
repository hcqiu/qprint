// Keep ordinary TeX references separate from Blueprint wikilink navigation.
export async function followTexReference(link, {currentNode, selectNode, openPaper, showReader, findAnchor}) {
  if (link.dataset.paper) {
    await openPaper(link.dataset.paper, Number(link.dataset.line) || 1);
    return;
  }
  const node = link.dataset.texNode;
  if (node && node !== currentNode && !await selectNode(node)) return;
  showReader();
  findAnchor(link.dataset.texAnchor)?.scrollIntoView({block: 'center'});
}
