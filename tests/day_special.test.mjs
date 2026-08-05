// specialAppliesToday / daysMentionedInSpecial — weekday free-text match.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');
eval(readFileSync(join(root, 'assets/js/format.js'), 'utf8'));

const {
  specialAppliesToday,
  daysMentionedInSpecial,
  dayOfDate
} = globalThis.HappyCowFormat;

const MON = new Date(2026, 7, 3, 17, 0); // Mon Aug 3 2026
const TUE = new Date(2026, 7, 4, 17, 0);

test('dayOfDate Mon=1 … Sun=7', () => {
  assert.equal(dayOfDate(MON), 1);
  assert.equal(dayOfDate(TUE), 2);
  assert.equal(dayOfDate(new Date(2026, 7, 9, 12, 0)), 7); // Sun
});

test('full weekday names and plurals', () => {
  const days = daysMentionedInSpecial({ item: 'x', description: 'Whiskey Wednesdays' });
  assert.ok(days.has(3));
  assert.equal(days.size, 1);
});

test('slash pairs Tuesday/Thursday', () => {
  const days = daysMentionedInSpecial({
    item: '2 for 1',
    description: 'Tuesday/Thursday: 2 for 1 drinks'
  });
  assert.ok(days.has(2));
  assert.ok(days.has(4));
});

test('abbrevs as whole tokens', () => {
  const days = daysMentionedInSpecial({ item: 'deal', description: 'Mon-Fri special' });
  // "Mon" and "Fri" as tokens via \bmon\b — but "Mon-Fri" has mon then - then fri
  // \bmon\b matches Mon; \bfri\b matches Fri
  assert.ok(days.has(1), 'mon');
  assert.ok(days.has(5), 'fri');
});

test('fries does not match fri', () => {
  const days = daysMentionedInSpecial({
    item: 'Hand-cut fries',
    description: '$7 — with house fry sauce'
  });
  assert.equal(days.size, 0);
});

test('specialAppliesToday true only for matching weekday', () => {
  const mon = { item: 'Wings', description: '$1 wings Mondays' };
  const tue = { item: 'Pot roast', description: '$13 Tuesdays' };
  assert.equal(specialAppliesToday(mon, MON), true);
  assert.equal(specialAppliesToday(mon, TUE), false);
  assert.equal(specialAppliesToday(tue, MON), false);
  assert.equal(specialAppliesToday(tue, TUE), true);
});

test('always-on specials are not today', () => {
  const s = { item: '$3 martinis', description: 'Happy Hour Prices' };
  assert.equal(specialAppliesToday(s, MON), false);
  assert.equal(daysMentionedInSpecial(s).size, 0);
});
