// ========================================
// Happy Cow — All the Magic
// ========================================

// ─── State ───
function readStore(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw == null ? fallback : JSON.parse(raw);
  } catch (e) {
    return fallback;
  }
}

const state = {
  data: null,
  expanded: null,
  cows: [],
  collected: readStore('hc_collected', []),
  bingo: readStore('hc_bingo', {}),
  dark: localStorage.getItem('hc_dark') === 'true',
  todaySeed: dateSeed(),
  dealRevealed: false,
};

function dateSeed() {
  const d = new Date();
  return d.getFullYear() * 10000 + (d.getMonth()+1) * 100 + d.getDate();
}

// Simple seeded random
function seededRandom(seed) {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return function() {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

// ─── Impostor Cows ───
const IMPOSTORS = [13, 21, 23, 25, 27];
const IMPOSTOR_REAL_ANIMAL = {
  13: "🦎 Mutant Cow — Two tails. The elders speak of this one in whispers.",
  21: "🐂 That's a Bull. No udder. Definitely masculine energy. Still cool though.",
  23: "🦒 Impostor! That's a Giraffe in a cow onesie. Look at the snout.",
  25: "🐂 Another Bull. Someone's not checking IDs at the cow door.",
  27: "🐕 That's a BEAGLE in a cow-print onesie inside a robot suit. Triple disguise."
};
const IMPOSTOR_TAGLINE = {
  13: "twice the tail, half the tail",
  21: "technically a bull but we don't gatekeep",
  23: "long neck energy in a compact package",
  25: "the cool uncle who is definitely not a cow",
  27: "this is a dog. we know. we kept it anyway."
};

const COW_NAMES = [
  "Bessie", "Clover", "Daisy", "Moo-donna", "Sir Loin", "Patty",
  "Angus", "Wagyu", "Brisket", "Moolan Rouge", "Moo-tang Clan",
  "Lactose", "Heifer", "Cal-f", "Rumi-nation", "Cow-bert",
  "Moo-lissa", "James Herd", "Moo-hammad", "Udderly",
  "Cow-stanza", "Bovine Jovi", "Moo-zart", "Moo-nica",
  "Rodeo", "Moo-llennium", "Holy Cow", "Cowabunga",
  "Moo-deng", "Notorious C.O.W."
];

const COW_PROPHECIES = [
  "The margarita you're thinking about? Order it.",
  "A shot of well whiskey approaches. Accept it.",
  "Someone at the bar is about to buy a round. Could be you.",
  "The universe wants you to try the IPA you've never heard of.",
  "Nachos are in your immediate future. Do not fight this.",
  "Tonight you will tell a story that starts 'remember that one time'.",
  "A stranger will compliment your drink order. Bask in it.",
  "The jukebox selection you're about to hear will change you.",
  "You will meet someone who also orders the weird thing. Marry them.",
  "That $2 special is a trap. A delicious, delicious trap.",
  "The bartender remembers your name. You've made it.",
  "Tonight's closing time will be 'whenever'.",
  "A pickleback is calling your name. Answer it.",
  "The cheapest thing on the menu is the best thing on the menu.",
  "Free popcorn is the highest form of cuisine at this hour.",
  "Someone will ask 'what's in a Malört?' Don't look it up.",
  "The dive bar stool you sit on has held 47,000 butts before yours.",
  "Tonight you will attempt karaoke. So will everyone else.",
  "The next person to walk through that door is a friend you haven't met.",
  "Your tab will be a perfect round number. The universe is watching.",
  "A glass of water between rounds is a love letter to tomorrow you.",
  "That person on their phone at the bar? They're reading this.",
  "The special changes when you're not looking. The special always changes.",
  "There is no such thing as 'one more round'. Accept your fate.",
  "The cow says: drink water. The cow also says: one more.",
  "You will discover a new favorite drink tonight. It's on special.",
  "The peanuts on the bar are free. The consequences are not.",
  "Happy hour is a state of mind. You're already there.",
  "Venmo requests sent tonight will be awkward by Tuesday.",
  "The best conversation of your night hasn't started yet."
];

const COW_MOODS = [
  "tired", "partying", "chill", "mysterious", "hungry",
  "confused", "flirtatious", "wise", "sleepy", "chaotic"
];

function getCowForDay(daySeed) {
  const rng = seededRandom(daySeed);
  const idx = Math.floor(rng() * 30);
  const isImpostor = IMPOSTORS.includes(idx);
  const cowRng = seededRandom(daySeed + idx * 100);
  return {
    id: idx,
    name: COW_NAMES[idx],
    mood: COW_MOODS[Math.floor(rng() * COW_MOODS.length)],
    prophecy: isImpostor ? IMPOSTOR_REAL_ANIMAL[idx] : COW_PROPHECIES[Math.floor(rng() * COW_PROPHECIES.length)],
    tagline: isImpostor ? IMPOSTOR_TAGLINE[idx] : null,
    collected: state.collected.includes(idx),
    isImpostor: isImpostor,
    image: assetUrl(`assets/cows/cow-${idx}.png`),
    stats: {
      "Drink Capacity": Math.floor(cowRng() * 7 + 4) + "/10",
      "Dance Moves": Math.floor(cowRng() * 10) + 1 + "/10",
      "Will Call You Tomorrow": Math.floor(cowRng() * 10) + 1 + "/10",
      "Bar Stool Mastery": Math.floor(cowRng() * 10) + 1 + "/10"
    }
  };
}

// ─── Load Data ───
function pageBaseUrl() {
  // GitHub project pages: /happycow or /happycow/ or /happycow/index.html
  const { origin, pathname } = window.location;
  if (pathname.endsWith('/')) return origin + pathname;
  if (/\.html?$/i.test(pathname)) return origin + pathname.replace(/\/[^/]+$/, '/');
  return origin + pathname + '/';
}

function assetUrl(relPath) {
  return new URL(relPath, pageBaseUrl()).toString();
}

async function loadData() {
  const url = assetUrl('data/happy_hour_data.json');
  try {
    const resp = await fetch(url, { cache: 'no-cache' });
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status} fetching ${url}`);
    }
    state.data = await resp.json();
  } catch (e) {
    console.error('Happy Cow data load failed:', e);
    document.body.innerHTML = `<div style="padding:40px;text-align:center;font-size:1.1rem;max-width:28rem;margin:0 auto;line-height:1.5">
      🐄 Couldn't load happy hour data.<br>
      <span style="font-size:0.85rem;color:#8b7355">${(e && e.message) || e}</span><br><br>
      <span style="font-size:0.85rem;color:#8b7355">If you opened this as a file, run:<br><code>python3 -m http.server 8000</code></span>
    </div>`;
    return;
  }
  try {
    render();
  } catch (e) {
    console.error('Happy Cow render failed:', e);
    document.body.innerHTML = `<div style="padding:40px;text-align:center;font-size:1.1rem">
      🐄 Data loaded, but the page failed to render.<br>
      <span style="font-size:0.85rem;color:#8b7355">${(e && e.message) || e}</span>
    </div>`;
  }
}

// ─── Time Helpers ───
// Align with Date.getDay(): Sun=0 … Sat=6
const DAY_MAP = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };

function parseAmpmHour(hour, ampm, fallbackAmpm) {
  let h = parseInt(hour, 10);
  const mer = (ampm || fallbackAmpm || 'pm').toLowerCase();
  if (mer === 'pm' && h < 12) h += 12;
  if (mer === 'am' && h === 12) h = 0;
  return h;
}

function isTodayInDayRange(dayRange) {
  if (!dayRange) return false;
  const raw = dayRange.trim();
  const lower = raw.toLowerCase();
  if (lower === 'daily' || lower === 'everyday' || lower === 'every day') return true;

  const today = new Date().getDay();
  const dayParts = raw.split('-').map(p => p.trim());
  const startDay = DAY_MAP[dayParts[0]];
  const endDay = dayParts[1] ? DAY_MAP[dayParts[1]] : startDay;
  if (startDay === undefined || endDay === undefined) return false;

  if (endDay >= startDay) return today >= startDay && today <= endDay;
  return today >= startDay || today <= endDay;
}

function isHHLive(hoursStr) {
  if (!hoursStr) return 'unknown';

  // Parse "Mon-Fri 4-6pm", "Daily 3-6pm", "Thu-Sat 4-7pm" style
  const parts = hoursStr.trim().split(/\s+/);
  if (parts.length < 2) return 'unknown';

  const dayRange = parts[0];
  const timeRange = parts.slice(1).join(' ');

  if (!isTodayInDayRange(dayRange)) return 'closed';

  const timeMatch = timeRange.match(/(\d+)(?::(\d+))?(am|pm)?\s*-\s*(\d+)(?::(\d+))?(am|pm)?/i);
  if (!timeMatch) return 'unknown';

  const startAmpm = timeMatch[3] || timeMatch[6] || 'pm';
  const endAmpm = timeMatch[6] || startAmpm;
  const startH = parseAmpmHour(timeMatch[1], timeMatch[3], startAmpm);
  const endH = parseAmpmHour(timeMatch[4], timeMatch[6], endAmpm);
  const startMin = startH * 60 + parseInt(timeMatch[2] || '0', 10);
  const endMin = endH * 60 + parseInt(timeMatch[5] || '0', 10);

  const now = new Date();
  const currentMin = now.getHours() * 60 + now.getMinutes();

  if (currentMin >= startMin && currentMin < endMin) return 'live';
  if (currentMin < startMin && (startMin - currentMin) <= 120) return 'soon';
  return 'closed';
}

function timeUntil(startMin) {
  const diff = startMin - (new Date().getHours() * 60 + new Date().getMinutes());
  if (diff <= 0) return '';
  const h = Math.floor(diff / 60);
  const m = diff % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

// ─── Render ───
function render() {
  if (!state.data) return;
  const todayCow = getCowForDay(state.todaySeed);

  // ── Cow Bar ──
  document.getElementById('cow-icon').src = todayCow.image;
  document.getElementById('cow-name').textContent = todayCow.name;
  document.getElementById('cow-mood').textContent = todayCow.mood;
  document.getElementById('cow-prophecy').textContent = `"${todayCow.prophecy}"`;
  document.getElementById('cow-collected').textContent = `${state.collected.length}/30 collected`;

  // Impostor detection badge
  const badge = document.getElementById('cow-impostor-badge');
  if (todayCow.isImpostor) {
    badge.textContent = todayCow.tagline;
    badge.style.display = 'inline';
  } else {
    badge.style.display = 'none';
  }

  // ── Hero ──
  document.getElementById('hero-title').innerHTML = `Happy Cow <span>${state.data.city}</span>`;
  document.getElementById('last-updated').textContent = `Updated ${formatDate(state.data.last_updated)}`;
  const footerUpdated = document.getElementById('footer-updated');
  if (footerUpdated) footerUpdated.textContent = formatDate(state.data.last_updated);

  // ── Deal of the Day ──
  renderDealOfDay();

  // ── Status Bar ──
  renderStatusBar();

  // ── Venue List ──
  renderVenues();

  // ── Cow icon click → modal + moo ──
  const cowIcon = document.getElementById('cow-icon');
  cowIcon.style.cursor = 'pointer';
  cowIcon.setAttribute('role', 'button');
  cowIcon.setAttribute('tabindex', '0');
  cowIcon.setAttribute('aria-label', 'Open cow of the day');
  const openCow = () => { playMoo(); openModal('cow-modal'); };
  cowIcon.onclick = openCow;
  cowIcon.onkeydown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openCow(); }
  };
  setupCowModal(todayCow);

  // ── Feature buttons ──
  document.getElementById('btn-bingo').onclick = () => { openModal('bingo-modal'); renderBingo(); };
  document.getElementById('btn-horoscope').onclick = () => { openModal('horoscope-modal'); renderHoroscope(todayCow); };
  document.getElementById('btn-moo').onclick = () => playMoo();
  document.getElementById('btn-tip').onclick = () => { openModal('tip-modal'); };
  document.getElementById('btn-quiz').onclick = () => { openModal('quiz-modal'); };

  // ── Mystery Drink ──
  document.getElementById('mystery-btn').onclick = doMysteryDrink;

  // ── Sad Hour (no fake crowd counts) ──
  renderSadHour();

  // ── Dark Mode ──
  if (state.dark) document.body.classList.add('dark');
  document.getElementById('dark-toggle').textContent = state.dark ? '☀️' : '🌙';
  document.getElementById('dark-toggle').onclick = toggleDark;

  // ── Roulette ──
  document.getElementById('roulette-btn').onclick = doRoulette;

  // ── Quiz ──
  document.getElementById('quiz-form').onsubmit = handleQuiz;

  // ── Tip Calculator ──
  document.getElementById('tip-total').oninput = renderTipCalc;
  document.getElementById('tip-people').oninput = renderTipCalc;

  // ── Filter ──
  document.getElementById('filter-search').oninput = renderVenues;
  document.getElementById('filter-tag').onchange = renderVenues;
}

// ─── Deal of the Day ───
function renderDealOfDay() {
  const allSpecials = [];
  state.data.venues.forEach(v => {
    v.specials.forEach(s => {
      allSpecials.push({ ...s, venue: v.name });
    });
  });
  const best = allSpecials.filter(s => s.price > 0).sort((a,b) => a.price - b.price)[0];
  const dealBtn = document.getElementById('deal-day');
  const lie = document.getElementById('deal-lie');
  if (best) {
    document.getElementById('deal-text').textContent =
      `${best.item} — $${best.price.toFixed(2)} at ${best.venue}`;
  }
  lie.hidden = !state.dealRevealed;
  dealBtn.setAttribute('aria-expanded', state.dealRevealed ? 'true' : 'false');
  dealBtn.onclick = () => {
    state.dealRevealed = true;
    lie.hidden = false;
    dealBtn.setAttribute('aria-expanded', 'true');
  };
}

// ─── Status Bar ───
function renderStatusBar() {
  const bar = document.getElementById('status-bar');
  bar.innerHTML = '';
  state.data.venues.forEach(v => {
    const status = isHHLive(v.hours);
    const pill = document.createElement('button');
    pill.type = 'button';
    pill.className = 'status-pill' + (status === 'live' ? ' active' : status === 'soon' ? ' ending' : '');
    pill.textContent = status === 'live' ? `● ${v.name}` :
                       status === 'soon' ? `▲ ${v.name}` :
                       `○ ${v.name}`;
    pill.setAttribute('aria-label', `${v.name}: ${status === 'live' ? 'live now' : status === 'soon' ? 'opening soon' : 'closed'}`);
    pill.onclick = () => scrollToVenue(v.id);
    bar.appendChild(pill);
  });
}

// ─── Venue List ───
function renderVenues() {
  const search = (document.getElementById('filter-search').value || '').toLowerCase();
  const tagFilter = document.getElementById('filter-tag').value;

  const container = document.getElementById('venue-list');
  container.innerHTML = '';

  let filtered = state.data.venues.filter(v => {
    if (search && !v.name.toLowerCase().includes(search) &&
        !v.specials.some(s => s.item.toLowerCase().includes(search)))
      return false;
    if (tagFilter && !v.tags.includes(tagFilter)) return false;
    return true;
  });

  // Sort: live first, then alphabetical
  filtered.sort((a,b) => {
    const statusA = isHHLive(a.hours);
    const statusB = isHHLive(b.hours);
    if (statusA === 'live' && statusB !== 'live') return -1;
    if (statusA !== 'live' && statusB === 'live') return 1;
    return a.name.localeCompare(b.name);
  });

  filtered.forEach(v => renderVenueCard(v, container));
}

function renderVenueCard(venue, container) {
  const status = isHHLive(venue.hours);
  const expanded = state.expanded === venue.id;
  const card = document.createElement('article');
  card.className = 'venue-card' + (expanded ? ' expanded' : '');
  card.id = `venue-${venue.id}`;

  const statusText = status === 'live' ? '● Live now' :
                     status === 'soon' ? `▲ Opens in ${timeUntil(getStartMinutes(venue.hours))}` :
                     '○ Closed';

  const specialsId = `specials-${venue.id}`;
  card.innerHTML = `
    <button type="button" class="venue-toggle" aria-expanded="${expanded}" aria-controls="${specialsId}">
      <div class="venue-header">
        <div>
          <div class="venue-name">${venue.name}</div>
          <div class="venue-detail">${venue.hours} · ${venue.address}</div>
          <div class="venue-tags">${venue.tags.map(t => `<span class="tag">${t}</span>`).join('')}</div>
        </div>
        <div class="hh-status ${status}">${statusText}</div>
      </div>
    </button>
    <div class="venue-specials" id="${specialsId}" ${expanded ? '' : 'hidden'}>
      ${venue.specials.map(s => `
        <div class="special-row">
          <div>
            <div>${s.item}</div>
            <div class="special-desc">${s.description}</div>
          </div>
          <div class="special-price">${s.price === 0 ? 'FREE' : '$' + s.price.toFixed(2)}</div>
        </div>
      `).join('')}
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;">
        <a href="${venue.maps}" target="_blank" rel="noopener" style="font-size:0.75rem;color:var(--cow-spot-2);">📍 Directions</a>
        ${venue.website ? `<a href="${venue.website}" target="_blank" rel="noopener" style="font-size:0.75rem;color:var(--cow-spot-2);">🔗 Website</a>` : ''}
        <span style="font-size:0.7rem;color:var(--text-dim);margin-left:auto;">Noise: ${venue.noise_level} · ${venue.mood}</span>
      </div>
    </div>
  `;

  const toggle = card.querySelector('.venue-toggle');
  const specials = card.querySelector('.venue-specials');
  toggle.onclick = () => {
    const open = state.expanded === venue.id;
    state.expanded = open ? null : venue.id;
    // Re-render list so only one stays expanded cleanly
    renderVenues();
    if (!open) {
      const el = document.getElementById(`venue-${venue.id}`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  };
  // Keep specials visible via CSS class + hidden attr sync
  if (expanded) {
    specials.hidden = false;
  }
  container.appendChild(card);
}

function getStartMinutes(hoursStr) {
  const timeMatch = (hoursStr || '').match(/(\d+)(?::(\d+))?(am|pm)?/i);
  if (!timeMatch) return 0;
  const h = parseAmpmHour(timeMatch[1], timeMatch[3], 'pm');
  return h * 60 + parseInt(timeMatch[2] || '0', 10);
}

function scrollToVenue(id) {
  const el = document.getElementById(`venue-${id}`);
  if (el) {
    state.expanded = id;
    renderVenues();
    const again = document.getElementById(`venue-${id}`);
    if (again) again.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// ─── Roulette ───
function doRoulette() {
  const live = state.data.venues.filter(v => isHHLive(v.hours) === 'live');
  const pool = live.length > 0 ? live : state.data.venues;
  const pick = pool[Math.floor(Math.random() * pool.length)];
  scrollToVenue(pick.id);
}

// ─── Modal System ───
function openModal(id) {
  document.getElementById(id).classList.add('open');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

// ─── Cow Modal ───
function setupCowModal(cow) {
  document.getElementById('cow-modal-img').src = cow.image;
  document.getElementById('cow-modal-name').textContent = cow.name;
  document.getElementById('cow-modal-mood').textContent = `Mood: ${cow.mood}`;
  document.getElementById('cow-modal-prophecy').textContent = `"${cow.prophecy}"`;

  // RPG Stats
  const statsContainer = document.getElementById('rpg-stats');
  statsContainer.innerHTML = '';
  Object.entries(cow.stats || {}).forEach(([key, val]) => {
    const s = document.createElement('span');
    s.className = 'rpg-stat';
    s.textContent = `${key}: ${val}`;
    statsContainer.appendChild(s);
  });

  // Impostor badge
  const impostorBadge = document.getElementById('cow-modal-impostor');
  if (cow.isImpostor) {
    impostorBadge.textContent = `⚠️ IMPOSTOR DETECTED — ${cow.tagline}`;
    impostorBadge.style.display = 'block';
  } else {
    impostorBadge.style.display = 'none';
  }

  document.getElementById('cow-modal-status').textContent =
    cow.collected ? '✓ Collected' : '◎ Not yet collected';
  document.getElementById('cow-modal-status').style.color = cow.collected ? 'var(--green)' : 'var(--text-dim)';
  document.getElementById('cow-modal-collect').textContent =
    cow.collected ? 'Already yours!' : 'Collect this cow';
  document.getElementById('cow-modal-collect').disabled = cow.collected;
  document.getElementById('cow-modal-collect').onclick = () => {
    if (!state.collected.includes(cow.id)) {
      state.collected.push(cow.id);
      localStorage.setItem('hc_collected', JSON.stringify(state.collected));
      document.getElementById('cow-modal-collect').textContent = '✓ Collected!';
      document.getElementById('cow-modal-collect').disabled = true;
      document.getElementById('cow-modal-status').textContent = '✓ Collected';

      // Check if all 5 impostors collected
      const impostorsCollected = IMPOSTORS.filter(i => state.collected.includes(i));
      if (impostorsCollected.length === IMPOSTORS.length) {
        setTimeout(() => alert('🐄🕵️ SECRET ACHIEVEMENT: You collected all 5 impostors! A giraffe, a beagle, a mutant, and two bulls walked into a bar...\n\n你太牛了! (nǐ tài niú le) — you\'re TOO cow! 🐄🇨🇳'), 300);
      }

      render(); // refresh bar
    }
  };
}

// ─── Bingo ───
const BINGO_ITEMS = [
  "Someone orders a Jägerbomb", "Bartender knows a regular's name",
  "Cowbell rings", "Asks for wifi password", "Spilled drink",
  "Someone says 'I love this song'", "Craft beer snob lecture",
  "Shot of Malört ordered", "Someone on their phone at the bar",
  "Couple on a first date", "Karaoke starts", "Someone falls off stool",
  "Free round of shots", "$1 bill tip on a $12 tab",
  "Someone orders wine at a dive bar", "Bartender pours a heavy one",
  "'I'm not drunk, you're drunk'", "Phone dies",
  "Someone asks what's on tap", "Group photo at the bar",
  "Says 'one more' then leaves", "Picks up someone else's tab",
  "Dance floor has exactly 2 people", "Jukebox plays twice in a row",
  "Someone yells 'CHUG'", "Nachos arrive for a table of one",
  "Asks the bartender for their life advice", "Someone's ID gets rejected",
  "Someone spills the free popcorn", "Last call singalong"
];

function renderBingo() {
  const rng = seededRandom(state.todaySeed + 2);
  const shuffled = [...BINGO_ITEMS].sort(() => rng() - 0.5);
  const grid = document.getElementById('bingo-grid');
  grid.innerHTML = '';

  for (let i = 0; i < 25; i++) {
    const cell = document.createElement('div');
    cell.className = 'bingo-cell';
    if (i === 12) {
      cell.textContent = '🐄 FREE';
      cell.classList.add('marked');
    } else {
      const idx = i > 12 ? i - 1 : i;
      cell.textContent = shuffled[idx];
      cell.dataset.idx = idx;
      if (state.bingo[idx]) cell.classList.add('marked');
    }
    cell.onclick = () => {
      if (i === 12) return;
      const idx = parseInt(cell.dataset.idx);
      if (isNaN(idx)) return;
      state.bingo[idx] = !state.bingo[idx];
      localStorage.setItem('hc_bingo', JSON.stringify(state.bingo));
      cell.classList.toggle('marked');
    };
    grid.appendChild(cell);
  }
}

// ─── Horoscope ───
function renderHoroscope(cow) {
  const rng = seededRandom(state.todaySeed + 3);
  const signs = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra",
                 "Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"];
  const sign = signs[Math.floor(rng() * signs.length)];
  const extras = [
    "A well drink at a dive bar holds more wisdom than a sommelier.",
    "The jukebox is about to play exactly what you needed to hear.",
    "Your next round will be bought by a stranger. Pay it forward.",
    "The universe is telling you to try the fried pickles.",
    "A toast made tonight will be remembered for years. Choose your words.",
    "The person next to you has a story you need to hear.",
    "Tonight's impulse decision will be tomorrow's fondest memory.",
    "The cheapest beer is the most honest beer.",
    "Release your expectations for the night. Let the bar provide.",
    "Your spirit animal is a cow at happy hour. You have arrived."
  ];
  document.getElementById('horoscope-sign').textContent = `♈ ${sign} · ${cow.name} the ${cow.mood} Cow`;
  document.getElementById('horoscope-text').innerHTML =
    `${extras[Math.floor(rng() * extras.length)]}<br><br>
     <span style="font-size:0.8rem;color:var(--text-dim);">
     Lucky drink: ${['$4 PBR','$6 Margarita','$5 Old Fashioned','$3 Wells','$2.50 Hamms','$7 Wine','$4 Local IPA'][Math.floor(rng()*7)]}
     </span>`;
}

// ─── Moo ───
let mooAudio = null;
function playMoo() {
  try {
    // Fresh instance so overlapping taps can stack / vary independently
    const a = new Audio(assetUrl('assets/sounds/moo.mp3'));
    // Random bovine: pitch + loudness drift so each tap is different
    a.playbackRate = 0.75 + Math.random() * 0.7; // ~0.75–1.45
    a.volume = 0.55 + Math.random() * 0.45;
    const p = a.play();
    if (p && typeof p.catch === 'function') p.catch(() => {});
    mooAudio = a;
  } catch (e) {}
}

// ─── Tip Calculator ───
function renderTipCalc() {
  const total = parseFloat(document.getElementById('tip-total').value) || 0;
  const people = parseInt(document.getElementById('tip-people').value) || 1;
  if (total <= 0 || people <= 0) {
    document.getElementById('tip-result').innerHTML = 'Enter a total and number of people, genius.';
    return;
  }
  const tips = [0.15, 0.18, 0.20, 0.22, 0.25];
  const insults = [
    "C'mon, you can do this in your head.",
    "Your phone has a calculator. But fine.",
    "This is literally elementary school math.",
    "I'm a cow and I know this.",
    "You went to the moon, not the menu."
  ];
  const lines = tips.map(pct => {
    const tip = total * pct;
    const per = (total + tip) / people;
    return `${(pct*100).toFixed(0)}% = <b>$${tip.toFixed(2)} tip</b> → <b>$${per.toFixed(2)}/person</b>`;
  }).join('<br>');
  document.getElementById('tip-result').innerHTML = `
    ${lines}<br><br>
    <span style="font-size:0.75rem;color:var(--text-dim);">
    🐄 ${insults[Math.floor(Math.random() * insults.length)]}
    </span>`;
}

// ─── Quiz ───
const QUIZ_QUESTIONS = [
  {
    q: "Happy hour starts in 10 minutes. What do you do?",
    a: ["Walk slowly toward the bar", "Speedwalk like it's the olympics",
        "You've been there for 45 minutes already", "Text your group chat 'who's out?'"]
  },
  {
    q: "The special is $3 wells. What do you order?",
    a: ["Whiskey ginger", "Vodka soda (diet starts tomorrow)", "Gin and tonic",
        "Whatever the person before you ordered"]
  },
  {
    q: "Best happy hour snack?",
    a: ["Nachos", "Wings", "Free popcorn", "Whatever's half off"]
  },
  {
    q: "Your friend says 'one more round.' It's 20 minutes before last call. You:",
    a: ["Absolutely", "One more then I'm out (lie)", "Already have my coat on",
        "Water? Never heard of her"]
  }
];

function handleQuiz(e) {
  e.preventDefault();
  const answers = [];
  for (let i = 0; i < QUIZ_QUESTIONS.length; i++) {
    const selected = document.querySelector(`input[name="q${i}"]:checked`);
    if (!selected) { document.getElementById('quiz-result').textContent = 'Answer all questions, cowpoke.'; return; }
    answers.push(parseInt(selected.value));
  }

  const score = answers.reduce((a,b) => a + b, 0);
  const results = [
    "You are a <b>Lightweight Cow</b>. One drink and you're under the table. Respect.",
    "You are a <b>Social Cow</b>. You're here for the vibes, not the volume. Acceptable.",
    "You are a <b>Party Cow</b>. You know the bartender's name. You've earned the stool.",
    "You are a <b>Legendary Cow</b>. The bar closes when YOU say it closes. Bow down."
  ];
  const tier = Math.min(3, Math.floor(score / QUIZ_QUESTIONS.length));
  document.getElementById('quiz-result').innerHTML = results[tier];
}

// ─── Format Date ───
function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric' });
}

// ─── Mystery Drink ───
function doMysteryDrink() {
  if (!state.data) return;
  const allSpecials = [];
  state.data.venues.forEach(v => {
    v.specials.forEach(s => {
      allSpecials.push({ ...s, venue: v.name });
    });
  });
  const pick = allSpecials[Math.floor(Math.random() * allSpecials.length)];
  const btn = document.getElementById('mystery-btn');
  btn.textContent = `🍸 ${pick.item} — $${pick.price.toFixed(2)} at ${pick.venue}! Tap for another`;
  setTimeout(() => {
    btn.textContent = "🍸 I'll Have What They're Having — Surprise Me";
  }, 8000);
}

// ─── Sad Hour ───
function renderSadHour() {
  if (!state.data) return;
  const anyLive = state.data.venues.some(v => isHHLive(v.hours) === 'live');
  const banner = document.getElementById('sad-hour');
  banner.hidden = !!anyLive;
}

// ─── Dark Mode ───
function toggleDark() {
  state.dark = !state.dark;
  document.body.classList.toggle('dark', state.dark);
  document.getElementById('dark-toggle').textContent = state.dark ? '☀️' : '🌙';
  localStorage.setItem('hc_dark', state.dark);
}

// ─── Footer: 你很牛 ↔ nǐ hěn niú toggle ───
function setupFooterNiu() {
  const link = document.getElementById('footer-cow-link');
  if (!link) return;
  const hanzi = '你很牛';
  const pinyin = 'nǐ hěn niú';
  link.textContent = hanzi;
  link.onclick = (e) => {
    e.preventDefault();
    link.textContent = link.textContent === hanzi ? pinyin : hanzi;
    link.title = link.textContent === hanzi ? '你太牛了!' : 'ni tài niú le — too cow!';
  };
}

// ─── Init ───
document.addEventListener('DOMContentLoaded', () => {
  loadData();
  setupFooterNiu();

  // Modal close buttons
  document.querySelectorAll('.modal-close').forEach(btn => {
    btn.onclick = () => btn.closest('.modal-overlay').classList.remove('open');
  });
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.onclick = (e) => {
      if (e.target === overlay) overlay.classList.remove('open');
    };
  });
});
