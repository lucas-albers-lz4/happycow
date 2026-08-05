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
  // A negative word anywhere suppresses the tale even if a positive is present
  // ("chicken burger" is not beef; "veggie burger" is a salad in disguise).
  const NOT_BEEF_WORDS = [
    'veggie', 'vegan', 'vegetarian', 'plant', 'chicken', 'turkey', 'fish',
    'salmon', 'shrimp', 'crab', 'lamb', 'mushroom', 'portobello'
  ];

  const BEEF_RE = new RegExp('\\b(?:' + BEEF_WORDS.join('|') + ')\\b', 'i');
  const NOT_BEEF_RE = new RegExp('\\b(?:' + NOT_BEEF_WORDS.join('|') + ')\\b', 'i');

  function isBeefSpecial(special) {
    if (!special) return false;
    const text = String(special.item || '') + ' ' + String(special.description || '');
    if (NOT_BEEF_RE.test(text)) return false;
    return BEEF_RE.test(text);
  }

  // ── Deterministic seed machinery (same idiom as app.js nicknames) ──
  function hashStr(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
    return Math.abs(h);
  }

  function seededRandom(seed) {
    let s = seed % 2147483647;
    if (s <= 0) s += 2147483646;
    return function () {
      s = (s * 16807) % 2147483647;
      return (s - 1) / 2147483646;
    };
  }

  // ── The cursed (names are cow-adjacent but never drawn by Cow of the Day) ──
  const TALE_COWS = [
    'Mildred', 'Gertrude', 'Bertha', 'Mabel', 'Ethel', 'Agnes', 'Henrietta',
    'Beulah', 'Prudence', 'Winifred', 'Clarabelle', 'Matilda', 'Blanche',
    'Opal', 'Fern', 'Hazel', 'Petunia', 'Doris', 'Myrtle', 'Edna', 'Velma',
    'Muriel', 'Ingrid', 'Eunice'
  ];

  // ── The tales (bad luck / bad life choices / general ridiculousness) ──
  // Slots: {cow} {item} {venue}. Kept free of venue names so the pool stays
  // generic; uniqueness comes from the seed, not the copy.
  const TALE_TEMPLATES = [
    "{cow} once quit the dairy to \"follow her dreams\" of becoming a bull. Two seasons of being yelled at by actual bulls and one very confusing vet visit later, she now narrates the nightly specials in her head. They say she's the reason the {item} at {venue} is such a deal — she keeps lowering the price in her imagination, and the kitchen just... went with it.",
    "{cow} put her entire retirement into a startup that pasteurized the internet. It did not pasteurize the internet. The only thing it pasteurized was her savings. She now works the line at {venue}, whispering encouragement to each {item} as it hits the flat top.",
    "{cow} joined a multi-level mooving scheme. Her upline was a goat. Her inventory was thirty unsellable bales of \"artisanal hay.\" She still believes the next hoof-deal will pay off. The {item} at {venue} is priced to cover her monthly subscription.",
    "{cow} took out a second mortgage on the barn to buy a timeshare in the pasture. The pasture was already hers. Nobody has the heart to tell her. Every {item} sold at {venue} pays down a debt that should not exist.",
    "{cow} decided to become an actuary because it was \"safe.\" She now calculates the actuarial risk of every {item} at {venue} being ordered, and it haunts her. The spreadsheet has 47 tabs. She is on tab 12.",
    "{cow} maxed out her udder's credit on a \"self-care retreat\" that was just a damp field with a sign. She now leases her grazing rights to {venue}, which is why the {item} costs what it costs.",
    "{cow} bet her entire inheritance on a race between two winds. It was declared a tie, then voided. The bookie — a suspiciously well-dressed raccoon — kept the money. She now moonlights as the mascot for the {item} at {venue}.",
    "Born on a Tuesday the 13th under a ladder that was also on fire, {cow} has never caught a break. The one time she won a raffle, the prize was a lifetime supply of Mondays. She now guards the {item} at {venue} with the resigned dignity of a cow who knows.",
    "{cow} stood in the wrong place during a lightning storm. The lightning missed. The storm filed a complaint. She has been \"under observation\" ever since, which is why she now spends her days supervising the {item} at {venue}.",
    "{cow}'s parachute was a feedbag. She doesn't jump out of planes — the plane jumped out of her. Rehabilitation was slow. She now tells her story to anyone who will listen, usually between bites of the {item} at {venue}.",
    "{cow} once found a winning lottery ticket. It was a hay receipt. She keeps it framed. The {item} at {venue} is named in her will, which currently just says \"feed it to someone sad.\"",
    "{cow} slipped on a banana peel into the annual stockyard auction. By the time anyone looked, she had been sold, re-sold, and given a standing ovation. She escaped, but only as far as {venue}, where the {item} now carries her name.",
    "A seagull stole {cow}'s sandwich. This was in Montana. There are no seagulls in Montana. The mystery of it broke her. She now sits near the kitchen at {venue} waiting for the {item} to be reborn.",
    "{cow} was born with her spots on backwards. Vets called it a miracle. Her mother called it a phase. The fashion press called it \"avant-garde.\" She now models the {item} at {venue} for 10% off.",
    "{cow} tried to become a line cook at {venue} but kept seasoning everything with grass clippings. She was banned from the kitchen — not for the grass, but for calling the head chef \"babe.\" The {item} still tastes faintly of her influence.",
    "{cow} entered a hot-dog eating contest. It was a hot-DOG contest. She misunderstood, ate a hot dog, and was disqualified for \"being a cow at a dog event.\" She has never recovered. The {item} at {venue} is her therapy.",
    "{cow} wanted to be a weather cow. She stood on a hill and predicted rain. It rained. She predicted more rain. It rained more. She has not been wrong once, which frightens the town. She now lives at {venue}, where the {item} is always sunny.",
    "{cow} audited a stand-up comedy class. Her set: \"Why am I beef? Why is anything beef?\" She bombed. She blames the crowd. The crowd blames the material. The {item} at {venue} is her farewell tour.",
    "{cow} tried to join the rodeo as a bull. She was flagged for \"incorrect energy.\" She now holds the record for the longest sulk in Montana history — measured in {item} ordered at {venue}.",
    "{cow} wanted to be a bison influencer. The bison blocked her. All of them. One bison was very rude about it. She now runs a tiny podcast called \"Moo-cast: The Beef Within\" from a shed behind {venue}. Episode 12 is about the {item}.",
    "{cow} studied to be a sommelier but drinks exclusively from puddles. Her tasting notes say \"terroir: puddle.\" The program asked her to leave, but not before she rated the {item} at {venue} a \"splashy little number.\"",
    "{cow} opened a coworking space for cows called MooSpace. Tenants: one pigeon who pays in crumbs. She pivoted to consulting. Her consulting rate is one {item} at {venue} per hour, which is honestly a steal.",
    "{cow}'s memoir, \"A Moo Too Far,\" was rejected by forty publishers for being \"too dairy-forward.\" She self-published. It sold one copy, to the pigeon. She now does a one-cow show about it, followed by a Q&A, followed by the {item} at {venue}.",
    "{cow} attempted to become a marathon cow. She was disqualified for grazing mid-race. She maintains it was \"fueling.\" The race officials maintain it was \"lunch.\" She now paces the patio at {venue}, where the {item} is her medal.",
    "{cow} once tried to become a DJ. Her entire set was the sound of a gate opening, for ninety minutes. The crowd demanded a refund. She now spins \"gate-core\" for tips at {venue}, between plates of the {item}.",
    "{cow} signed up for a \"biggest loser\" reality show thinking it was about losing the ability to lose. She won the season by default after the host tripped over a hay bale. The prize was a lifetime of {item} at {venue}, which she now shares — grudgingly — with the public."
  ];

  // ── The engine ──
  // taleFor(venueId, special, venueName) -> { cow, item, venue, story, seed }
  // Deterministic per (venueId, item): stable across days and renders, unique
  // across specials (seed includes venueId), immune to re-scrapes.
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
    NOT_BEEF_WORDS: NOT_BEEF_WORDS
  };
})(typeof window !== 'undefined' ? window : globalThis);
