// render_smoke.test.mjs — issue #45. Run: node --test
// Loads all venues from data; asserts every card string-renders without gaps.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');

// Load IIFE modules into globalThis (same pattern as hours.test.mjs)
eval(readFileSync(join(root, 'assets/js/hours.js'), 'utf8'));
eval(readFileSync(join(root, 'assets/js/format.js'), 'utf8'));
eval(readFileSync(join(root, 'assets/js/render.js'), 'utf8'));

const { esc, specialPriceLabel, specialAppliesToday } = globalThis.HappyCowFormat;
const { renderVenueCardHtml } = globalThis.HappyCowRender;
const helpers = { esc, specialPriceLabel, specialAppliesToday };

const data = JSON.parse(readFileSync(join(root, 'data/happy_hour_data.json'), 'utf8'));
const venues = data.venues;

// Fixed clock: Monday 5pm (peak happy hour, gives deterministic status badges)
const NOW = new Date(2026, 7, 3, 17, 0); // Mon Aug 3 2026 17:00

// Discount wording pattern (mirrors specialPriceLabel logic)
const DISCOUNT_RE = /\$|cents|%|off|discount|half|bogo|special|deal|price|happy\s*hour|2\s*for\s*1|2-4-1|one\s*free/i;

test('card count matches venue count', () => {
  assert.equal(venues.length > 0, true, 'data must have venues');
  const cards = venues.map(v => renderVenueCardHtml(v, helpers, NOW));
  assert.equal(cards.length, venues.length);
});

test('every card contains escaped venue name', () => {
  for (const venue of venues) {
    const html = renderVenueCardHtml(venue, helpers, NOW);
    const escapedName = esc(venue.name);
    assert.ok(
      html.includes(escapedName),
      `card for "${venue.id}" missing escaped name "${escapedName}"`
    );
  }
});

test('specials chip or rows present when venue has specials', () => {
  for (const venue of venues) {
    const nSpecials = (venue.specials || []).length;
    if (nSpecials === 0) continue;
    const html = renderVenueCardHtml(venue, helpers, NOW);
    const hasDeal = html.includes('venue-deal');
    const hasRow = html.includes('special-row');
    assert.ok(
      hasDeal || hasRow,
      `venue "${venue.id}" has ${nSpecials} specials but no deal line or rows in card`
    );
  }
});

test('dense row exposes name and when label', () => {
  for (const venue of venues) {
    const html = renderVenueCardHtml(venue, helpers, NOW);
    assert.ok(html.includes('venue-row-l1'), `venue "${venue.id}" missing dense row layout`);
    assert.ok(html.includes('venue-when'), `venue "${venue.id}" missing when label`);
  }
});

test('hours panel ids are unique across all cards', () => {
  const seen = new Set();
  for (const venue of venues) {
    if (!venue.hours) continue;
    const html = renderVenueCardHtml(venue, helpers, NOW);
    const id = `hours-${venue.id}`;
    assert.ok(html.includes(`id="${id}"`), `venue "${venue.id}" hours panel id missing`);
    assert.ok(!seen.has(id), `duplicate hours panel id "${id}"`);
    seen.add(id);
  }
});

test('never renders FREE when special description has discount wording', () => {
  for (const venue of venues) {
    for (const s of venue.specials || []) {
      if (s.price === 0 && s.description && DISCOUNT_RE.test(s.description)) {
        const html = renderVenueCardHtml(venue, helpers, NOW);
        // Find the special-price cell for this item
        const itemEscaped = esc(s.item);
        const rowStart = html.indexOf(itemEscaped);
        if (rowStart === -1) continue;
        const rowSnippet = html.slice(rowStart, rowStart + 500);
        assert.ok(
          !rowSnippet.includes('>FREE<'),
          `venue "${venue.id}" special "${s.item}" (discount desc) rendered as FREE`
        );
      }
    }
  }
});

test('no raw unescaped angle brackets from venue fields in card HTML', () => {
  for (const venue of venues) {
    const html = renderVenueCardHtml(venue, helpers, NOW);
    // Check that venue.name raw angle brackets (if any) are not literally in the output
    // (esc() must have replaced them). We can only check if the raw name contains them.
    if (venue.name.includes('<') || venue.name.includes('>')) {
      assert.ok(
        !html.includes(venue.name),
        `venue "${venue.id}" name has unescaped angle brackets in output`
      );
    }
  }
});

test('closed venues show over (not em dash)', () => {
  // Late Monday night — most HH windows closed
  const late = new Date(2026, 7, 3, 23, 0);
  let sawOver = false;
  for (const venue of venues) {
    if (!venue.hours) continue;
    const st = globalThis.HappyCowHours.hhStatus(venue.hours, venue.business_hours, late);
    if (st.kind !== 'closed') continue;
    const html = renderVenueCardHtml(venue, helpers, late);
    assert.ok(html.includes('>over<'), `closed venue "${venue.id}" should show over`);
    assert.ok(!html.includes('>—<') || html.includes('special-price'), `closed venue "${venue.id}" should not use em dash as when label`);
    sawOver = true;
  }
  assert.ok(sawOver, 'expected at least one closed venue at late Monday');
});

test('deal headline prefers today special when present', () => {
  // Bridger: specials[0] is always-on Beers; Monday Cod Cakes should win on Monday clock
  const bridger = venues.find(v => v.id === 'bridger-brewing');
  assert.ok(bridger, 'Bridger Brewing should exist');
  const monday = (bridger.specials || []).find(s => specialAppliesToday(s, NOW));
  assert.ok(monday, 'Bridger should have a Monday special');
  assert.notEqual(bridger.specials[0], monday, 'precondition: today special is not specials[0]');
  const html = renderVenueCardHtml(bridger, helpers, NOW);
  const dealMatch = html.match(/class="venue-deal">([^<]*)/);
  assert.ok(dealMatch, 'venue-deal present');
  assert.ok(
    dealMatch[1].includes(esc(monday.item)),
    `headline should prefer Monday special "${monday.item}", got "${dealMatch[1]}"`
  );
});
