import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

const source = readFileSync(new URL('../qprint/static/tex-references.js', import.meta.url), 'utf8');
const {followTexReference} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

function harness(selected = true) {
  const calls = [];
  const services = {
    currentNode: 'A#First',
    selectNode: async id => {calls.push(['select', id]); return selected;},
    openPaper: async (path, line) => calls.push(['paper', path, line]),
    showReader: () => calls.push(['reader']),
    findAnchor: id => ({scrollIntoView: options => calls.push(['scroll', id, options])}),
  };
  return {calls, services};
}

test('same-node references scroll without reloading the node', async () => {
  const {calls, services} = harness();
  await followTexReference({dataset: {texAnchor: 'label'}}, services);
  assert.deepEqual(calls, [['reader'], ['scroll', 'label', {block: 'center'}]]);
});

test('cross-node references wait for rendering before locating the label', async () => {
  const {calls, services} = harness();
  await followTexReference({dataset: {texNode: 'A#Second', texAnchor: 'label'}}, services);
  assert.deepEqual(calls, [['select', 'A#Second'], ['reader'], ['scroll', 'label', {block: 'center'}]]);
});

test('cancelled navigation does not scroll or change views', async () => {
  const {calls, services} = harness(false);
  await followTexReference({dataset: {texNode: 'A#Second', texAnchor: 'label'}}, services);
  assert.deepEqual(calls, [['select', 'A#Second']]);
});

test('labels outside bound fragments open the source at the original line', async () => {
  const {calls, services} = harness();
  await followTexReference({dataset: {paper: 'paper.tex', line: '12'}}, services);
  assert.deepEqual(calls, [['paper', 'paper.tex', 12]]);
});
