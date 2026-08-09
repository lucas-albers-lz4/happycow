// assets/js/tales.js — Cow Tall Tales (issue #100).
// Loaded BEFORE render.js and app.js. Pure, deterministic, unit-tested.
//
// Detects beef-adjacent specials and generates a stable, unique, ridiculous
// origin story per (venueId, item). Canon: the cows run the app, and every
// beef deal exists because a specific cow made a bad decision, got unlucky,
// or was simply too absurd for this world.
//
// Why procedural and not data: specials are LLM-extracted on every scrape, so
// curated story fields in data/ would be overwritten or orphaned. Seeding on
// hash(venueId + '::' + item) keeps each special's story fixed across days,
// distinct across specials, and future-proof for new beef specials.
//
// ── Classifier rules (keep tests/tales.test.mjs in sync) ──
// 1. Fake-beef brands / plant signals reject FIRST (Beyond, Impossible,
//    veggie…, and plant-based "chicken fried steak" style names).
// 2. Override: chicken-/country-fried steak is beef even though it says
//    "chicken" (only after fake-beef is cleared).
// 3. Competing proteins anywhere reject (chicken, catfish, fish, lamb…).
//    Mixed "birria or catfish" menus do NOT get a tale — too ambiguous.
// 4. Else positive beef keywords (burger/steak/birria/…) win.
// Note: "non-vegetarian" / "non-vegan" must NOT trip the fake-beef gate.
//
// ── Template writing rules (enforced by tests) ──
// - Every template must include {cow}, {item}, and {venue}.
// - Assume {item} may be an event ("Steak Night"), priced ("$8 Steak Frites"),
//   or plural — prefer "the {item} special/deal", "tonight's {item}", or
//   "ordering the {item}", never edible-only metaphors.
// - Banned closers/phrases: "is always sunny", "is her medal",
//   "models the {item}", "for 10% off", "between bites of the {item}",
//   "guards the {item}", "supervising the {item}", "each {item} as it hits
//   the flat top".
// - Vary ending shapes (deal exists because… / podcast / consulting rate /
//   apology monetized / ticket rail / etc.) — do not end every tale with
//   "She now … at {venue} … {item}."
(function (global) {
  'use strict';

  // ── Beef detection ──
  // Positive words that unambiguously signal beef (word-boundary regex).
  // 'pork' is deliberately NOT a negative: "3 beef & pork meatballs" is beef.
  const BEEF_WORDS = [
    'beef', 'burger', 'steak', 'ribeye', 'sirloin', 'brisket', 'wagyu', 'kobe',
    'short rib', 'prime rib', 'birria', 'carne', 'pastrami', 'philly',
    'cheesesteak', 'corned beef', 'bison'
  ];

  // Wins even when a competing-protein token is present ("chicken-fried steak"),
  // but only after fake-beef is cleared (plant-based CFS stays out).
  const BEEF_OVERRIDE_RE = /\b(?:chicken[\s-]*fried[\s-]*steak|country[\s-]*fried[\s-]*steak)\b/i;

  // Plant / fake-beef signals — reject before override/positives.
  // vegan/vegetarian use negative lookbehind so "non-vegan" / "non-vegetarian"
  // (hyphen or space) do not suppress a real beef special.
  // Brand/diet fakes apply to item+description. Mushroom/portobello only reject
  // when they appear in the item name (a ribeye with mushroom demi stays beef).
  const FAKE_BEEF_RE = /\b(?:beyond|impossible|veggie|plant[\s-]?based)\b|(?<!non-)(?<!non\s)\b(?:vegan|vegetarian)\b/i;
  const FAKE_BEEF_ITEM_RE = /\b(?:portobello|mushroom)\b/i;

  // Competing proteins. catfish is listed explicitly: \bfish\b does not match it.
  // A negative anywhere suppresses the tale (mixed "beef and chicken" menus → no tale).
  const NOT_BEEF_RE = /\b(?:chicken|turkey|fish|catfish|salmon|shrimp|crab|cod|tilapia|tuna|lamb|duck)\b/i;

  const BEEF_RE = new RegExp('\\b(?:' + BEEF_WORDS.join('|') + ')\\b', 'i');

  function isBeefSpecial(special) {
    if (!special) return false;
    const item = String(special.item || '');
    const description = String(special.description || '');
    const text = item + ' ' + description;
    if (FAKE_BEEF_RE.test(text)) return false;
    if (FAKE_BEEF_ITEM_RE.test(item)) return false;
    if (BEEF_OVERRIDE_RE.test(text)) {
      // CFS override must still reject mushroom/portobello cutlets in the description
      if (FAKE_BEEF_ITEM_RE.test(description)) return false;
      return true;
    }
    if (NOT_BEEF_RE.test(text)) return false;
    return BEEF_RE.test(text);
  }

  // ── Deterministic seed machinery (HappyCowFormat — shared with app.js) ──
  const { hashStr, seededRandom } = global.HappyCowFormat;

  // ── The cursed (names are cow-adjacent but never drawn by Cow of the Day) ──
  const TALE_COWS = [
    'Mildred', 'Gertrude', 'Bertha', 'Mabel', 'Ethel', 'Agnes', 'Henrietta',
    'Beulah', 'Prudence', 'Winifred', 'Clarabelle', 'Matilda', 'Blanche',
    'Opal', 'Fern', 'Hazel', 'Petunia', 'Doris', 'Myrtle', 'Edna', 'Velma',
    'Muriel', 'Ingrid', 'Eunice'
  ];

  // Phrases templates must never contain (also asserted in tests/tales.test.mjs).
  const BANNED_TEMPLATE_PHRASES = [
    'is always sunny',
    'is her medal',
    'models the {item}',
    'for 10% off',
    'between bites of the {item}',
    'guards the {item}',
    'supervising the {item}',
    'each {item} as it hits the flat top'
  ];

  // ── The tales (bad luck / bad life choices / general ridiculousness) ──
  // Slots: {cow} {item} {venue}. Copy must tolerate event/priced/plural items.
  const TALE_TEMPLATES = [
    "{cow} once quit the dairy to \"follow her dreams\" of becoming a bull. Two seasons of being yelled at by actual bulls and one very confusing vet visit later, she now narrates specials in her head. They say she's why the {item} special at {venue} is such a deal — she keeps lowering the price in her imagination, and the kitchen just... went with it.",
    "{cow} put her entire retirement into a startup that pasteurized the internet. It did not pasteurize the internet. The only thing it pasteurized was her savings. She now works the line at {venue}, whispering encouragement whenever tonight's {item} boards the ticket rail.",
    "{cow} joined a multi-level mooving scheme. Her upline was a goat. Her inventory was thirty unsellable bales of \"artisanal hay.\" She still believes the next hoof-deal will pay off. The {item} deal at {venue} is priced to cover her monthly subscription.",
    "{cow} took out a second mortgage on the barn to buy a timeshare in the pasture. The pasture was already hers. Nobody has the heart to tell her. Every order of the {item} at {venue} pays down a debt that should not exist.",
    "{cow} decided to become an actuary because it was \"safe.\" She now calculates the actuarial risk of tonight's {item} at {venue} being ordered, and it haunts her. The spreadsheet has 47 tabs. She is on tab 12.",
    "{cow} maxed out her udder's credit on a \"self-care retreat\" that was just a damp field with a sign. She now leases her grazing rights to {venue}, which is why the {item} special costs what it costs.",
    "{cow} bet her entire inheritance on a race between two winds. It was declared a tie, then voided. The bookie — a suspiciously well-dressed raccoon — kept the money. She now moonlights as the unofficial mascot whenever {venue} runs the {item}.",
    "Born on a Tuesday the 13th under a ladder that was also on fire, {cow} has never caught a break. The one time she won a raffle, the prize was a lifetime supply of Mondays. She watches the {item} special at {venue} with the resigned dignity of a cow who knows.",
    "{cow} stood in the wrong place during a lightning storm. The lightning missed. The storm filed a complaint. She has been \"under observation\" ever since, which is why she loiters near the pass at {venue} during the {item}.",
    "{cow}'s parachute was a feedbag. She doesn't jump out of planes — the plane jumped out of her. Rehabilitation was slow. She now tells her story to anyone who will listen, usually while {venue} pushes the {item}.",
    "{cow} once found a winning lottery ticket. It was a hay receipt. She keeps it framed. The {item} special at {venue} is named in her will, which currently just says \"feed it to someone sad.\"",
    "{cow} slipped on a banana peel into the annual stockyard auction. By the time anyone looked, she had been sold, re-sold, and given a standing ovation. She escaped, but only as far as {venue}, where the {item} deal now carries her unofficial endorsement.",
    "A seagull stole {cow}'s sandwich. This was in Montana. There are no seagulls in Montana. The mystery of it broke her. She now sits near the kitchen at {venue} waiting for the {item} special to be reborn.",
    "{cow} was born with her spots on backwards. Vets called it a miracle. Her mother called it a phase. The fashion press called it \"avant-garde.\" She auditioned as the face of {venue}'s happy hour; they hired her silhouette instead. She still shows up early, stares at the {item} special, and whispers \"work it\" to the ticket rail.",
    "{cow} tried to become a line cook at {venue} but kept seasoning everything with grass clippings. She was banned from the kitchen — not for the grass, but for calling the head chef \"babe.\" Locals swear the {item} special still tastes faintly of her influence.",
    "{cow} entered a hot-dog eating contest. It was a hot-DOG contest. She misunderstood, ate a hot dog, and was disqualified for \"being a cow at a dog event.\" She has never recovered. Ordering the {item} at {venue} is how she processes it.",
    "{cow} wanted to be a weather cow. She stood on a hill and predicted rain. It rained. She predicted more rain. It rained more. She has not been wrong once, which frightens the town. The forecast finally failed her: she called \"partly cloudy with a chance of dignity,\" and it hailed hamburger buns. She refuses to leave {venue} until someone orders the {item} under a clear sky — which, in Montana, is a long wait.",
    "{cow} audited a stand-up comedy class. Her set: \"Why am I beef? Why is anything beef?\" She bombed. She blames the crowd. The crowd blames the material. Tonight's {item} at {venue} is billed as her farewell tour, which has now lasted eleven weeks.",
    "{cow} tried to join the rodeo as a bull. She was flagged for \"incorrect energy.\" She now holds the record for the longest sulk in Montana history — measured in how many times the {item} has been ordered at {venue}.",
    "{cow} wanted to be a bison influencer. The bison blocked her. All of them. One bison was very rude about it. She now runs a tiny podcast called \"Moo-cast: The Beef Within\" from a shed behind {venue}. Episode 12 is about the {item} special.",
    "{cow} studied to be a sommelier but drinks exclusively from puddles. Her tasting notes say \"terroir: puddle.\" The program asked her to leave, but not before she rated the {item} at {venue} a \"splashy little number.\"",
    "{cow} opened a coworking space for cows called MooSpace. Tenants: one pigeon who pays in crumbs. She pivoted to consulting. Her consulting rate is one {item} special at {venue} per hour, which is honestly a steal.",
    "{cow}'s memoir, \"A Moo Too Far,\" was rejected by forty publishers for being \"too dairy-forward.\" She self-published. It sold one copy, to the pigeon. She now does a one-cow show about it at {venue}, followed by a Q&A, followed by whatever they're calling the {item}.",
    "{cow} attempted to become a marathon cow. She was disqualified for grazing mid-race. She maintains it was \"fueling.\" The race officials maintain it was \"lunch.\" She now paces the patio at {venue} between \"fueling\" sessions. Staff swear the {item} deal exists because she grazed the finish-line banner and someone had to monetize the apology.",
    "{cow} once tried to become a DJ. Her entire set was the sound of a gate opening, for ninety minutes. The crowd demanded a refund. She now spins \"gate-core\" for tips at {venue} whenever the {item} is on.",
    "{cow} signed up for a \"biggest loser\" reality show thinking it was about losing the ability to lose. She won the season by default after the host tripped over a hay bale. The prize was a lifetime of the {item} special at {venue}, which she now shares — grudgingly — with the public.",
    "{cow} invented \"happy hour\" thinking it meant happier cows. A clock sued her for trademark confusion. The settlement is why {venue} still runs the {item} deal at slightly embarrassed prices.",
    "{cow} left a one-star review of grass (\"too grassy,\" \"mouthfeel: lawn\"). A food feud followed. Somehow {venue}'s {item} special became famous in the crossfire, and she has never apologized."
  ];

  // ── The engine ──
  // taleFor(venueId, special, venueName) -> { cow, item, venue, story, seed }
  // Deterministic per (venueId, item): stable across days and renders.
  // Full story text differs across specials via interpolated item/venue;
  // cow+template pairs can recur — that is expected with a small pool.
  function taleFor(venueId, special, venueName) {
    const item = String(special && special.item || 'Special');
    const venue = String(venueName || venueId || 'the venue');
    const seed = hashStr(String(venueId || '') + '::' + item);
    const rng = seededRandom(seed);
    const cow = TALE_COWS[Math.floor(rng() * TALE_COWS.length)];
    const template = TALE_TEMPLATES[Math.floor(rng() * TALE_TEMPLATES.length)];
    const story = template
      .replace(/\{cow\}/g, cow)
      .replace(/\{item\}/g, item)
      .replace(/\{venue\}/g, venue);
    return { cow: cow, item: item, venue: venue, story: story, seed: seed };
  }

  global.HappyCowTales = {
    isBeefSpecial: isBeefSpecial,
    taleFor: taleFor,
    BEEF_WORDS: BEEF_WORDS,
    BANNED_TEMPLATE_PHRASES: BANNED_TEMPLATE_PHRASES,
    TALE_TEMPLATES: TALE_TEMPLATES,
    TALE_COWS: TALE_COWS
  };
})(typeof window !== 'undefined' ? window : globalThis);
