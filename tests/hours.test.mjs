// hours.js unit tests — issue #30 Phase 1. Run: node --test tests/
// Fixture strings are the 22 distinct hours values in data/happy_hour_data.json
// (2026-08-02) plus the MCR-flagged edge cases.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const code = readFileSync(new URL('../assets/js/hours.js', import.meta.url), 'utf8');
eval(code); // IIFE attaches to globalThis in Node
const { parseHours, parseBusinessHours, hhStatus, timeUntil } = globalThis.HappyCowHours;

// Fixed local instants (Aug 2026; Aug 2 = Sunday)
const sun = (h, m = 0) => new Date(2026, 7, 2, h, m);
const mon = (h, m = 0) => new Date(2026, 7, 3, h, m);
const fri = (h, m = 0) => new Date(2026, 7, 7, h, m); // Aug 7 2026 = Friday
const sat = (h, m = 0) => new Date(2026, 7, 8, h, m);

// ─── parseHours ───
test('parseHours: simple daily window', () => {
  const w = parseHours('Daily 4-6pm');
  assert.equal(w.length, 1);
  assert.deepEqual({ startDay: w[0].startDay, endDay: w[0].endDay, startMin: w[0].startMin, endMin: w[0].endMin }, { startDay: 1, endDay: 7, startMin: 960, endMin: 1080 });
});

test('parseHours: multi-window same days (The Bay)', () => {
  const w = parseHours('Daily 3-5pm & 8-9pm');
  assert.equal(w.length, 2);
  assert.deepEqual([w[0].startMin, w[0].endMin], [900, 1020]);
  assert.deepEqual([w[1].startMin, w[1].endMin], [1200, 1260]);
  assert.equal(w[1].startDay, 1); // inherits Daily
});

test('parseHours: secondary window with own days (Santa Fe)', () => {
  const w = parseHours('Daily 3-6pm, Fri-Sat 10pm-12am');
  assert.equal(w.length, 2);
  assert.deepEqual([w[1].startDay, w[1].endDay], [5, 6]);
  assert.deepEqual([w[1].startMin, w[1].endMin], [1320, 1440]); // ends exactly at midnight
});

test('parseHours: all-day terminal (Copper)', () => {
  const w = parseHours('Mon-Fri 3-5pm, Sun all day');
  assert.equal(w.length, 2);
  assert.deepEqual([w[1].startDay, w[1].endDay], [7, 7]);
  assert.deepEqual([w[1].startMin, w[1].endMin], [0, 1439]);
});

test('parseHours: close endpoint (Dave\u2019s)', () => {
  const w = parseHours('Mon 3-close');
  assert.equal(w.length, 1);
  assert.equal(w[0].close, true);
  assert.equal(w[0].startMin, 900);
});

test('parseHours: minute times + 12pm start', () => {
  assert.deepEqual(parseHours('Daily 2:30-4pm')[0].startMin, 870);
  assert.deepEqual(parseHours('Fri 12-8pm')[0].startMin, 720);
  assert.deepEqual(parseHours('Daily 4:30-5:30pm')[0].startMin, 990);
});

test('parseHours: midnight crossing spans next day', () => {
  const w = parseHours('Fri-Sat 11am-2am')[0];
  assert.equal(w.startMin, 660);
  assert.equal(w.endMin, 1560); // 2am + 24h
  assert.equal(w.spansNextDay, true);
});

test('parseHours: empty / garbage', () => {
  assert.deepEqual(parseHours(''), []);
  assert.deepEqual(parseHours(null), []);
  assert.deepEqual(parseHours('nonsense'), []);
});

// ─── parseBusinessHours ───
test('parseBusinessHours: simple daily', () => {
  const b = parseBusinessHours('Mon-Sun 4pm-10pm');
  assert.equal(b[1], 1320);
  assert.equal(b[7], 1320);
});

test('parseBusinessHours: closed days omitted', () => {
  const b = parseBusinessHours('Mon Closed, Tue-Sat 10am-6pm');
  assert.equal(b[1], undefined);
  assert.equal(b[2], 1080);
  assert.equal(b[6], 1080);
  assert.equal(b[7], undefined);
});

test('parseBusinessHours: midnight close + messy kitchen suffix', () => {
  const b = parseBusinessHours('Fri-Sat 4pm-Midnight (Kitchen Sun-Thu 4-8pm)');
  assert.equal(b[5], 1440);
  assert.equal(b[6], 1440);
});

test('parseBusinessHours: close end token is FALLBACK_CLOSE not NaN (#103)', () => {
  const b = parseBusinessHours('Daily 4pm-close');
  for (let d = 1; d <= 7; d++) {
    assert.equal(b[d], 23 * 60 + 59);
  }
});

test('parseBusinessHours: midnight stays 1440 (#103)', () => {
  const b = parseBusinessHours('Mon-Sun 11am-Midnight');
  assert.equal(b[1], 1440);
});

// ─── hhStatus — the reported bug and friends ───
test('BUG FIX: The Bay live in its second window (8-9pm)', () => {
  assert.equal(hhStatus('Daily 3-5pm & 8-9pm', '', sun(20, 41)).kind, 'live'); // was 'closed'
  assert.equal(hhStatus('Daily 3-5pm & 8-9pm', '', sun(15, 30)).kind, 'live');
  assert.equal(hhStatus('Daily 3-5pm & 8-9pm', '', sun(19, 0)).kind, 'soon');
  assert.equal(hhStatus('Daily 3-5pm & 8-9pm', '', sun(12, 0)).kind, 'closed');
});

test('live status includes endMin for countdown', () => {
  const st = hhStatus('Daily 3-6pm', '', sun(17, 0));
  assert.equal(st.kind, 'live');
  assert.equal(st.endMin, 18 * 60); // 6pm
});

test('Dave\u2019s 3-close resolves via business hours', () => {
  const biz = 'Mon-Sun 4pm-10pm';
  assert.equal(hhStatus('Mon 3-close', biz, mon(17, 0)).kind, 'live');
  assert.equal(hhStatus('Mon 3-close', biz, mon(14, 30)).kind, 'soon'); // before 3pm
  assert.equal(hhStatus('Mon 3-close', biz, mon(22, 30)).kind, 'closed'); // after 10pm close
  // fallback when business hours missing/unparseable
  assert.equal(hhStatus('Mon 3-close', '', mon(20, 0)).kind, 'live');
});

test('close-window × past-midnight biz hours is live mid-afternoon (#103)', () => {
  const st = hhStatus('Mon 3-close', 'Mon-Sun 11am-2am', mon(18, 0));
  assert.equal(st.kind, 'live');
  assert.ok(st.endMin > 1440, `expected absolute end >1440, got ${st.endMin}`);
  // Still live just before 2am next morning (Tue spill of Mon window)
  const tue = (h, m = 0) => new Date(2026, 7, 4, h, m);
  assert.equal(hhStatus('Mon 3-close', 'Mon-Sun 11am-2am', tue(1, 30)).kind, 'live');
  assert.equal(hhStatus('Mon 3-close', 'Mon-Sun 11am-2am', tue(2, 30)).kind, 'closed');
});

test('Copper all-day Sunday', () => {
  assert.equal(hhStatus('Mon-Fri 3-5pm, Sun all day', '', sun(10, 0)).kind, 'live');
  assert.equal(hhStatus('Mon-Fri 3-5pm, Sun all day', '', mon(16, 0)).kind, 'live');
  assert.equal(hhStatus('Mon-Fri 3-5pm, Sun all day', '', sat(16, 0)).kind, 'closed');
});

test('Santa Fe late-night window ends at midnight', () => {
  assert.equal(hhStatus('Daily 3-6pm, Fri-Sat 10pm-12am', '', fri(23, 0)).kind, 'live');
  assert.equal(hhStatus('Daily 3-6pm, Fri-Sat 10pm-12am', '', sat(0, 30)).kind, 'closed');
  assert.equal(hhStatus('Daily 3-6pm, Fri-Sat 10pm-12am', '', fri(14, 0)).kind, 'soon');
});

test('daily midnight-crossing window is live after midnight', () => {
  assert.equal(hhStatus('Daily 11am-2am', '', sun(1, 0)).kind, 'live');
  assert.equal(hhStatus('Daily 11am-2am', '', sun(13, 0)).kind, 'live');
  assert.equal(hhStatus('Daily 11am-2am', '', sun(5, 0)).kind, 'closed');
});

test('empty hours = unknown', () => {
  assert.equal(hhStatus('', '', sun(12, 0)).kind, 'unknown');
  assert.equal(hhStatus(null, '', sun(12, 0)).kind, 'unknown');
});

test('day-range wrap: Thu-Sat on a Friday', () => {
  assert.equal(hhStatus('Thu-Sat 4-6pm', '', fri(17, 0)).kind, 'live');
  assert.equal(hhStatus('Thu-Sat 4-6pm', '', sun(17, 0)).kind, 'closed');
});

// ─── timeUntil ───
test('timeUntil formats', () => {
  assert.equal(timeUntil(11 * 60, new Date(2026, 7, 2, 10, 0)), '1h 0m');
  assert.equal(timeUntil(11 * 60, new Date(2026, 7, 2, 10, 30)), '30m');
  assert.equal(timeUntil(11 * 60, new Date(2026, 7, 2, 12, 0)), '');
});
