// specialAppliesToday / daysMentionedInSpecial — weekday free-text match +
// Mon–Sun .special-row.today render coverage (fixture + live data).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');

eval(readFileSync(join(root, 'assets/js/hours.js'), 'utf8'));
eval(readFileSync(join(root, 'assets/js/format.js'), 'utf8'));
eval(readFileSync(join(root, 'assets/js/render.js'), 'utf8'));

const {
  esc,
  specialPriceLabel,
  specialAppliesToday,
  daysMentionedInSpecial,
  dayOfDate
} = globalThis.HappyCowFormat;
const { renderVenueCardHtml } = globalThis.HappyCowRender;
const helpers = { esc, specialPriceLabel, specialAppliesToday };

const data = JSON.parse(readFileSync(join(root, 'data/happy_hour_data.json'), 'utf8'));
const venues = data.venues;

// Week of Mon Aug 3 – Sun Aug 9 2026 at 17:00 (dayOfDate 1..7)
const WEEK = [1, 2, 3, 4, 5, 6, 7].map(d => new Date(2026, 7, 2 + d, 17, 0));
const DAY_NAMES = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const MON = WEEK[0];
const TUE = WEEK[1];

/** True if the special-row opening tag for this item includes "today". */
function rowIsToday(html, item) {
  const itemEsc = esc(item);
  const idx = html.indexOf(`<div>${itemEsc}</div>`);
  if (idx === -1) {
    // Fallback: unescaped item (tests use plain ASCII fixtures)
    const idx2 = html.indexOf(`<div>${item}</div>`);
    if (idx2 === -1) return null;
    const rowStart = html.lastIndexOf('special-row', idx2);
    return html.slice(rowStart, rowStart + 40).includes('special-row today');
  }
  const rowStart = html.lastIndexOf('special-row', idx);
  return html.slice(rowStart, rowStart + 40).includes('special-row today');
}

// ─── Parser unit cases ───

test('dayOfDate Mon=1 … Sun=7', () => {
  for (let i = 0; i < 7; i++) {
    assert.equal(dayOfDate(WEEK[i]), i + 1, DAY_NAMES[i + 1]);
  }
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

test('abbrevs as whole tokens (Mon-Fri mention semantics: both Mon and Fri)', () => {
  // Mention-based: Mon-Fri lights on Mon AND Fri, not exclusive-day semantics.
  const days = daysMentionedInSpecial({ item: 'deal', description: 'Mon-Fri special' });
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

// ─── A. Synthetic fixture — all 7 weekdays ───

const FIXTURE = {
  id: 'weekday-fixture',
  name: 'Weekday Fixture Pub',
  hours: 'Daily 3-7pm',
  business_hours: '',
  address: '1 Test St',
  maps: 'https://example.com',
  website: '',
  notes: '',
  specials: [
    { item: 'Always Draft', price: 3, category: 'drinks', description: 'Happy hour price' },
    { item: 'Mon Wings', price: 1, category: 'food', description: 'Monday special' },
    { item: 'Tue Sliders', price: 0, category: 'food', description: 'Tuesday special' },
    { item: 'Wed Mussels', price: 0, category: 'food', description: 'Wednesday special' },
    { item: 'Thu Brats', price: 0, category: 'food', description: 'Thursday special' },
    { item: 'Fri Flights', price: 0, category: 'drinks', description: 'Friday special' },
    { item: 'Sat Brats', price: 0, category: 'food', description: 'Saturday special' },
    { item: 'Sun Dinner', price: 0, category: 'food', description: 'Sunday special' },
    { item: '2 for 1', price: 0, category: 'drinks', description: 'Tuesday/Thursday: 2 for 1 drinks' }
  ]
};

test('fixture: each weekday highlights matching specials only (mention semantics)', () => {
  for (let d = 1; d <= 7; d++) {
    const clock = WEEK[d - 1];
    assert.equal(dayOfDate(clock), d);
    const html = renderVenueCardHtml(FIXTURE, helpers, clock);

    for (const s of FIXTURE.specials) {
      const days = daysMentionedInSpecial(s);
      const expectToday = days.size > 0 && days.has(d);
      const got = rowIsToday(html, s.item);
      assert.notEqual(got, null, `${DAY_NAMES[d]}: missing row for "${s.item}"`);
      assert.equal(
        got,
        expectToday,
        `${DAY_NAMES[d]}: "${s.item}" days=${[...days]} expectToday=${expectToday} got=${got}`
      );
    }

    // Always-on never today
    assert.equal(rowIsToday(html, 'Always Draft'), false, `${DAY_NAMES[d]}: always-on`);
    // Slash pair on Tue and Thu only
    const slashToday = d === 2 || d === 4;
    assert.equal(rowIsToday(html, '2 for 1'), slashToday, `${DAY_NAMES[d]}: Tue/Thu slash`);
  }
});

test('fixture: Mon-Fri mention lights on both Mon and Fri', () => {
  const venue = {
    ...FIXTURE,
    id: 'mon-fri-fixture',
    specials: [
      { item: 'Weekday Deal', price: 0, category: 'drinks', description: 'Mon-Fri special' }
    ]
  };
  for (const d of [1, 5]) {
    const html = renderVenueCardHtml(venue, helpers, WEEK[d - 1]);
    assert.equal(rowIsToday(html, 'Weekday Deal'), true, `${DAY_NAMES[d]} should light`);
  }
  for (const d of [2, 3, 4, 6, 7]) {
    const html = renderVenueCardHtml(venue, helpers, WEEK[d - 1]);
    assert.equal(rowIsToday(html, 'Weekday Deal'), false, `${DAY_NAMES[d]} should not light`);
  }
});

// ─── B. Live-data sweep — each weekday ───

test('live data: each weekday has at least one special-row today', () => {
  for (let d = 1; d <= 7; d++) {
    const clock = WEEK[d - 1];
    let found = false;
    for (const venue of venues) {
      const html = renderVenueCardHtml(venue, helpers, clock);
      if (html.includes('special-row today')) {
        found = true;
        break;
      }
    }
    assert.ok(found, `${DAY_NAMES[d]}: expected at least one .special-row.today in live data`);
  }
});

test('live data: specialAppliesToday matches .today class for every day-tagged special', () => {
  for (let d = 1; d <= 7; d++) {
    const clock = WEEK[d - 1];
    for (const venue of venues) {
      const dayTagged = (venue.specials || []).filter(s => daysMentionedInSpecial(s).size > 0);
      if (!dayTagged.length) continue;
      const html = renderVenueCardHtml(venue, helpers, clock);
      for (const s of dayTagged) {
        const expect = specialAppliesToday(s, clock);
        const got = rowIsToday(html, s.item);
        assert.notEqual(
          got,
          null,
          `${DAY_NAMES[d]} ${venue.id}: missing row for "${s.item}"`
        );
        assert.equal(
          got,
          expect,
          `${DAY_NAMES[d]} ${venue.id}: "${s.item}" applies=${expect} classToday=${got}`
        );
      }
    }
  }
});
