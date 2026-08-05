// tales.test.mjs — Cow Tall Tales (issue #100). Run: node --test
// Asserts the beef classifier, per-special determinism, cross-special
// distinctness over the live dataset, template rendering (no unrendered
// slots), and that rendered card HTML escapes tale data.
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
eval(readFileSync(join(root, 'assets/js/tales.js'), 'utf8'));
eval(readFileSync(join(root, 'assets/js/render.js'), 'utf8'));

const { isBeefSpecial, taleFor } = globalThis.HappyCowTales;
const { esc, specialPriceLabel, specialAppliesToday } = globalThis.HappyCowFormat;
const { renderVenueCardHtml } = globalThis.HappyCowRender;
const helpers = { esc, specialPriceLabel, specialAppliesToday };

const data = JSON.parse(readFileSync(join(root, 'data/happy_hour_data.json'), 'utf8'));
const venues = data.venues;

const sp = (item, description = '') => ({ item, description, price: 5, category: 'food' });

// ── Classifier ──
test('classifier: unambiguous beef items are detected', () => {
  const positives = [
    sp('Smash Burger'),
    sp('Ribeye', '12oz ribeye, chimichurri'),
    sp('Bison Tartare', 'hand chopped bison'),
    sp('Meatball Sliders', '3 beef & pork meatballs'),
    sp('Tacos', 'including the famous Catfish taco or Birria tacos'),
    sp('Steak Night'),
    sp('B.A.B.B. night', 'big ass burger and a pint of beer'),
    sp('Cheesesteak', 'shaved ribeye'),
    sp('Philly', 'pastrami, swiss'),
    sp('Short Rib Ravioli', 'fried bison short rib ravioli'),
    sp('Burger', 'wagyu patty'),
  ];
  for (const s of positives) {
    assert.ok(isBeefSpecial(s), `should detect: ${s.item} — ${s.description}`);
  }
});

test('classifier: non-beef and ambiguous items are rejected', () => {
  const negatives = [
    sp('Craft Beer Sliders', 'Tuesday special'),        // no beef wording
    sp('Nana Rose’s Meatball Dinner', 'Sunday special'), // no beef wording
    sp('Breakfast sandwich or burrito', 'Saturdays & Sundays'), // no beef wording
    sp('Fish Tacos', 'grilled cod'),
    sp('Chicken Wings', 'buffalo'),
    sp('Chicken Burger', 'grilled chicken patty'),
    sp('Veggie Burger', 'plant-based patty'),
    sp('Portobello Mushroom Sliders', 'roasted mushroom'),
    sp('Lamb Chops', 'with mint'),
  ];
  for (const s of negatives) {
    assert.ok(!isBeefSpecial(s), `should reject: ${s.item} — ${s.description}`);
  }
});

test('classifier: "all beef hot dog" is detected (beef is beef, wording-wise)', () => {
  assert.ok(isBeefSpecial(sp('Hot Dog', 'all beef hot dog')));
});

// ── Determinism ──
test('taleFor is deterministic per (venue, special)', () => {
  const a = taleFor('the-bay', sp('Sirloin Steak Tostadas'), 'The Bay');
  const b = taleFor('the-bay', sp('Sirloin Steak Tostadas'), 'The Bay');
  assert.deepEqual(a, b);
  assert.equal(a.story, b.story);
});

test('taleFor returns different stories for different specials', () => {
  const one = taleFor('the-bay', sp('Sirloin Steak Tostadas'), 'The Bay');
  const two = taleFor('the-bay', sp('Hand-Battered Steak Bites'), 'The Bay');
  assert.notEqual(one.story, two.story);
});

test('taleFor differs across venues with the same item', () => {
  const a = taleFor('the-bay', sp('Burger'), 'The Bay');
  const b = taleFor('brigade', sp('Burger'), 'Brigade');
  assert.notEqual(a.story, b.story);
});

// ── Live data ──
test('every live beef special gets a fully-rendered, unique tale', () => {
  const beefSpecials = [];
  for (const v of venues) {
    for (const s of v.specials || []) {
      if (isBeefSpecial(s)) beefSpecials.push({ venue: v, special: s });
    }
  }
  assert.ok(beefSpecials.length >= 10, `expected ≥10 live beef specials, got ${beefSpecials.length}`);
  const stories = new Set();
  for (const { venue, special } of beefSpecials) {
    const tale = taleFor(venue.id, special, venue.name);
    assert.ok(tale.cow, `missing cow for ${venue.id}/${special.item}`);
    assert.ok(tale.story.includes(tale.cow), `story must mention the cow for ${venue.id}/${special.item}`);
    assert.ok(tale.story.includes(String(special.item)), `story must mention the item for ${venue.id}/${special.item}`);
    assert.ok(!tale.story.includes('{'), `unrendered slot in story for ${venue.id}/${special.item}: ${tale.story}`);
    assert.ok(!stories.has(tale.story), `duplicate story across specials: ${venue.id}/${special.item}`);
    stories.add(tale.story);
  }
});

test('beef specials render a tale link; non-beef specials do not', () => {
  for (const v of venues) {
    const html = renderVenueCardHtml(v, helpers, new Date(2026, 7, 3, 17, 0));
    const nBeef = (v.specials || []).filter(isBeefSpecial).length;
    const nLinks = (html.match(/tale-link/g) || []).length;
    assert.equal(nLinks, nBeef, `${v.id}: expected ${nBeef} tale links, got ${nLinks}`);
    assert.equal((html.match(/class="tale-link"/g) || []).length, nLinks);
  }
});

// ── Escaping ──
test('tale link escapes item and cow name in card HTML', () => {
  const evil = sp('Burger <script>alert(1)</script>', 'beef patty');
  const venue = { id: 'evil-test', name: 'Evil & Sons <b>', hours: '', business_hours: '', specials: [evil], tags: [], noise_level: '', mood: '' };
  const html = renderVenueCardHtml(venue, helpers, new Date(2026, 7, 3, 17, 0));
  assert.ok(!html.includes('<script>'), 'raw script tag leaked into card HTML');
  assert.ok(html.includes('&lt;script&gt;'), 'item not escaped in card HTML');
});

test('story carries the raw item as plain text (safe: modal uses textContent)', () => {
  // taleFor output is plain text by construction. The modal renders it via
  // textContent (app.js), so item characters like <b> are inert there. The
  // real invariant — tale data enters innerHTML ONLY through esc() in
  // render.js — is covered by the escaping tests above/below.
  const tale = taleFor('evil-test', sp('Burger <b>bold</b>', 'beef'), 'The Bay');
  assert.ok(tale.story.includes('Burger <b>bold</b>'), 'story should carry the plain item text');
});

test('rendered card escapes raw HTML in the tale-link item attribute', () => {
  const evil = sp('Burger <b>bold</b>', 'beef patty');
  const venue = { id: 'evil-test', name: 'Evil & Sons <b>', hours: '', business_hours: '', specials: [evil], tags: [], noise_level: '', mood: '' };
  const html = renderVenueCardHtml(venue, helpers, new Date(2026, 7, 3, 17, 0));
  assert.ok(html.includes('data-tale-item="Burger &lt;b&gt;bold&lt;/b&gt;"'),
    'item attribute not escaped in tale-link');
  assert.ok(!html.includes('data-tale-item="Burger <b>'), 'raw item leaked into tale-link attribute');
});
