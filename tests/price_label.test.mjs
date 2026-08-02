// format.js unit tests — issue #42. Run: node --test tests/
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const code = readFileSync(new URL('../assets/js/format.js', import.meta.url), 'utf8');
eval(code); // IIFE attaches to globalThis in Node
const { esc, specialPriceLabel } = globalThis.HappyCowFormat;

// ─── specialPriceLabel ───
test('price > 0 formats as dollars', () => {
  assert.equal(specialPriceLabel({ price: 4, description: '' }), '$4.00');
  assert.equal(specialPriceLabel({ price: 2.5, description: 'well drinks' }), '$2.50');
  assert.equal(specialPriceLabel({ price: 10.99, description: '$1 off' }), '$10.99');
});

test('price 0 + no pricing signal → FREE', () => {
  assert.equal(specialPriceLabel({ price: 0, description: 'House wine pour' }), 'FREE');
  assert.equal(specialPriceLabel({ price: 0, description: '' }), 'FREE');
  assert.equal(specialPriceLabel({ price: 0 }), 'FREE');
});

test('price 0 + discount wording → dash (not FREE)', () => {
  assert.equal(specialPriceLabel({ price: 0, description: '$1.00 off well drinks' }), '—');
  assert.equal(specialPriceLabel({ price: 0, description: 'half price apps' }), '—');
  assert.equal(specialPriceLabel({ price: 0, description: '2 for 1 drafts' }), '—');
  assert.equal(specialPriceLabel({ price: 0, description: '20% discount on bottles' }), '—');
  assert.equal(specialPriceLabel({ price: 0, description: 'happy hour special' }), '—');
});

// Production bug fixture (#22/#24): discount-only must never render FREE
test('NEGATIVE: FREE-with-discount must not return FREE', () => {
  const label = specialPriceLabel({ price: 0, description: '$1.00 off well drinks' });
  assert.notEqual(label, 'FREE');
  assert.equal(label, '—');
});

test('edge: missing / empty fields', () => {
  assert.equal(specialPriceLabel({ price: 0, description: null }), 'FREE');
  assert.equal(specialPriceLabel({ price: 0, description: undefined }), 'FREE');
  assert.equal(specialPriceLabel({ price: 5.5, description: undefined }), '$5.50');
});

// ─── esc ───
test('esc escapes HTML special chars', () => {
  assert.equal(esc('&<>"\''), '&amp;&lt;&gt;&quot;&#39;');
  assert.equal(esc('<script>alert(1)</script>'), '&lt;script&gt;alert(1)&lt;/script&gt;');
});

test('esc null/undefined → safe empty-ish string', () => {
  assert.equal(esc(null), '');
  assert.equal(esc(undefined), '');
  assert.equal(esc('plain'), 'plain');
});
