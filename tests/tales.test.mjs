// tales.test.mjs — Cow Tall Tales (issue #100). Run: node --test
// Asserts the beef classifier (incl. override / fake-beef / mixed-menu
// edges), per-special determinism, cross-special distinctness over live
// data, template quality rules, and that rendered card HTML escapes tale data.
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

const {
  isBeefSpecial,
  taleFor,
  TALE_TEMPLATES,
  BANNED_TEMPLATE_PHRASES,
  TALE_COWS
} = globalThis.HappyCowTales;
const { esc, specialPriceLabel, specialAppliesToday } = globalThis.HappyCowFormat;
const { renderVenueCardHtml } = globalThis.HappyCowRender;
const helpers = { esc, specialPriceLabel, specialAppliesToday };

const data = JSON.parse(readFileSync(join(root, 'data/happy_hour_data.json'), 'utf8'));
const venues = data.venues;

const sp = (item, description = '') => ({ item, description, price: 5, category: 'food' });

// Awkward menu strings templates must survive without edible-only metaphors.
const AWKWARD_ITEMS = [
  'Steak Night',
  'B.A.B.B. night',
  '$8 Steak Frites',
  'Hand-Battered Steak Bites',
  'Fried Bison Short Rib Ravioli'
];

// ── Classifier ──
test('classifier: unambiguous beef items are detected', () => {
  const positives = [
    sp('Smash Burger'),
    sp('Ribeye', '12oz ribeye, chimichurri'),
    sp('Bison Tartare', 'hand chopped bison'),
    sp('Meatball Sliders', '3 beef & pork meatballs'),
    sp('Steak Night'),
    sp('B.A.B.B. night', 'big ass burger and a pint of beer'),
    sp('Cheesesteak', 'shaved ribeye'),
    sp('Philly', 'pastrami, swiss'),
    sp('Short Rib Ravioli', 'fried bison short rib ravioli'),
    sp('Burger', 'wagyu patty'),
    sp('Chicken-fried steak', 'with gravy'),
    sp('Chicken Fried Steak'),
    sp('Country fried steak', 'beef cutlet'),
    sp('Birria Tacos', 'slow cooked'),
    sp('Carne asada fries'),
    // "non-vegetarian" must not trip the vegan/vegetarian fake-beef gate
    sp('Ribeye', 'non-vegetarian entree, 12oz'),
    sp('Smash Burger', 'non vegan — real beef patty'),
    // Mushroom sauce in description must not suppress a beef item (#108)
    sp('Ribeye', '12oz ribeye with roasted mushroom demi'),
    sp('Steak Frites', 'portobello gravy on the side'),
  ];
  for (const s of positives) {
    assert.ok(isBeefSpecial(s), `should detect: ${s.item} — ${s.description}`);
  }
});

test('classifier: non-beef, fake-beef, and ambiguous mixed menus are rejected', () => {
  const negatives = [
    sp('Craft Beer Sliders', 'Tuesday special'),        // no beef wording
    sp('Nana Rose’s Meatball Dinner', 'Sunday special'), // no beef wording
    sp('Breakfast sandwich or burrito', 'Saturdays & Sundays'), // no beef wording
    sp('Fish Tacos', 'grilled cod'),
    sp('Chicken Wings', 'buffalo'),
    sp('Chicken Burger', 'grilled chicken patty'),
    sp('Veggie Burger', 'plant-based patty'),
    sp('Portobello Mushroom Sliders', 'roasted mushroom'),
    sp('Mushroom Swiss Burger', 'swiss and sauteed mushrooms'), // mushroom in item
    sp('Lamb Chops', 'with mint'),
    sp('Beyond Burger'),                                 // brand alone
    sp('Impossible Burger', 'plant protein'),
    sp('Slider night', 'beef and chicken options'),      // mixed → no tale
    sp('Tacos', 'including the famous Catfish taco or Birria tacos'), // mixed
    sp('Catfish Basket', 'fried catfish'),               // catfish ≠ fish word-boundary
    // fake-beef wins over chicken-fried-steak override
    sp('Chicken fried steak', 'plant-based'),
    sp('Country-fried steak', 'vegan mushroom cutlet'),
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

test('taleFor works from item alone (click handler may lack a special row)', () => {
  const a = taleFor('the-bay', { item: 'Smash Burger' }, 'The Bay');
  const b = taleFor('the-bay', sp('Smash Burger', 'ignored for seed'), 'The Bay');
  assert.equal(a.story, b.story);
  assert.equal(a.cow, b.cow);
});

// ── Live data ──
test('every live beef special gets a fully-rendered, unique tale', () => {
  const beefSpecials = [];
  for (const v of venues) {
    for (const s of v.specials || []) {
      if (isBeefSpecial(s)) beefSpecials.push({ venue: v, special: s });
    }
  }
  // Bourbon "Tacos" (catfish|birria) is correctly out; remaining live beef ≥ 10.
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

// ── Template quality (keep weak copy from slipping past) ──
test('every template has required slots and no banned phrases', () => {
  assert.ok(TALE_TEMPLATES.length >= 26, `expected ≥26 templates, got ${TALE_TEMPLATES.length}`);
  assert.ok(BANNED_TEMPLATE_PHRASES.length >= 5, 'banned-phrase list should stay non-empty');
  for (const [i, tpl] of TALE_TEMPLATES.entries()) {
    assert.ok(tpl.includes('{cow}'), `template ${i} missing {cow}`);
    assert.ok(tpl.includes('{item}'), `template ${i} missing {item}`);
    assert.ok(tpl.includes('{venue}'), `template ${i} missing {venue}`);
    for (const banned of BANNED_TEMPLATE_PHRASES) {
      assert.ok(!tpl.includes(banned), `template ${i} contains banned phrase "${banned}"`);
    }
  }
});

test('templates tolerate awkward event/priced/plural item names', () => {
  // Rendered leftovers that mean the template assumed edible singular food.
  const awkwardResidue = [
    'bites of the Steak Night',
    'bites of the B.A.B.B. night',
    'models the $8',
    'for 10% off',
    'is always sunny',
    'is her medal',
    'guards the Steak Night',
    'supervising the Steak Night',
    'each Steak Night as it hits the flat top',
    'each B.A.B.B. night as it hits the flat top'
  ];
  for (const item of AWKWARD_ITEMS) {
    for (const [i, tpl] of TALE_TEMPLATES.entries()) {
      const story = tpl
        .replace(/\{cow\}/g, 'Mildred')
        .replace(/\{item\}/g, item)
        .replace(/\{venue\}/g, 'Test Venue');
      assert.ok(!story.includes('{'), `template ${i} left unrendered slots for item="${item}"`);
      for (const bad of awkwardResidue) {
        assert.ok(!story.includes(bad), `template ${i} awkward with "${item}": contains "${bad}"`);
      }
    }
  }
});

test('tale cow names do not overlap Cow of the Day names', () => {
  const appSrc = readFileSync(join(root, 'assets/js/app.js'), 'utf8');
  const m = appSrc.match(/const COW_NAMES = \[([\s\S]*?)\];/);
  assert.ok(m, 'COW_NAMES not found in app.js');
  const dayCows = [...m[1].matchAll(/"([^"]+)"/g)].map(x => x[1]);
  const overlap = TALE_COWS.filter(n => dayCows.includes(n));
  assert.deepEqual(overlap, [], `tale cows overlap Cow of the Day: ${overlap.join(', ')}`);
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
