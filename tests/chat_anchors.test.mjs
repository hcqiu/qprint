import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
const source = readFileSync(new URL('../qprint/static/chat-anchors.js', import.meta.url), 'utf8');
const {resolveAnchor} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

test('anchors survive preceding edits and preserve Unicode UTF-16 offsets', () => {
  const text = '前言 😀 Here is the selected lemma. End.';
  const quote = 'selected lemma', start = text.indexOf(quote);
  const anchor = {quote, start, prefix: 'Here is the ', suffix: '. End.'};
  assert.equal(resolveAnchor(text, anchor), start);
  assert.equal(resolveAnchor('Added section. ' + text, anchor), start + 15);
  assert.equal(resolveAnchor(text.replace(quote, 'different statement'), anchor), -1);
});

test('repeated passages are only attached when context disambiguates them', () => {
  const text = 'A. same text. B. same text.';
  assert.equal(resolveAnchor(text, {quote:'same text', start:100}), -1);
  assert.equal(resolveAnchor(text, {quote:'same text', start:100, prefix:'B. '}), 17);
  assert.equal(resolveAnchor('changed text', {quote:'', start:0}), -1);
});
