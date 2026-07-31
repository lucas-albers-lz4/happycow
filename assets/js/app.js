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
  document.getElementById('btn-what').onclick = () => { openModal('cowq-modal'); renderCowQuestion(); };
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

// ─── Cow Questions (the "what" quiz) ───
// Each question: q (prompt), a (4 options), correct (index). If correct === -1,
// it's a TRICK question — no answer will be accepted, ever. The cow is annoyed.
const COW_QUESTIONS = [
  { q: "How many stomachs does a cow have?", a: ["One, it's just really big", "Two", "Three", "Four"], correct: 3 },
  { q: "What is a baby cow called?", a: ["A foal", "A calf", "A cub", "A larva"], correct: 1 },
  { q: "What is a female cow called before she's had a calf?", a: ["A heifer", "A steer", "A bull", "A cowlette"], correct: 0 },
  { q: "What is a castrated male cow called?", a: ["A bull", "A steer", "A heifer", "A sad bull"], correct: 1 },
  { q: "How many gallons of milk does a dairy cow produce per day?", a: ["About 1", "About 3", "About 7", "About 40"], correct: 2 },
  { q: "What color can cows NOT see well?", a: ["Blue", "Green", "Red", "Gray"], correct: 2 },
  { q: "Do cows have upper front teeth?", a: ["Yes, all of them", "No, just a hard dental pad", "Only on Tuesdays", "Only baby cows"], correct: 1 },
  { q: "What is a group of cows called?", a: ["A flock", "A herd", "A murder", "A parliament"], correct: 1 },
  { q: "How long is a cow pregnant?", a: ["3 months", "6 months", "About 9 months", "14 months"], correct: 2 },
  { q: "What do cows eat to make them so moo-dy?", a: ["Meat", "Mostly grass and hay", "Only corn", "Smaller cows"], correct: 1 },
  { q: "Which of these is a REAL cow name in this app?", a: ["Moo-tang Clan", "Spaghetti", "Sir Loin", "Moo-donna"], correct: 0 },
  { q: "How many cows are in this app's rotation?", a: ["10", "20", "30", "100"], correct: 2 },
  { q: "What sound does a cow make?", a: ["Baa", "Moo", "Oink", "Honk"], correct: 1 },
  { q: "What does a cow's four-chambered stomach help it do?", a: ["Fly", "Digest grass twice", "Breathe underwater", "See in the dark"], correct: 1 },
  { q: "What is the largest cattle breed?", a: ["Chianina", "Dexter", "Holstein", "Munchkin"], correct: 0 },
  { q: "What is the smallest cattle breed?", a: ["Dexter", "Chianina", "Hereford", "Teacup Cow"], correct: 0 },
  { q: "What is the oldest cow on record?", a: ["Big Bertha, 48 years", "Methuselah, 200 years", "Bessie, 12 years", "The first cow, still alive"], correct: 0 },
  { q: "About how many gallons of water does a cow drink per day?", a: ["1-2", "5-8", "30-50", "200+"], correct: 2 },
  { q: "What do you call the process of a cow chewing food it already swallowed?", a: ["Cud chewing", "Reverse dinner", "Second lunch", "The ol' redo"], correct: 0 },
  { q: "Can cows swim?", a: ["No, they sink", "Yes, surprisingly well", "Only in milk", "Only backwards"], correct: 1 },
  { q: "What is a cow's average body temperature?", a: ["98.6°F", "101.5°F", "104.9°F", "It depends on the mood"], correct: 1 },
  { q: "Which sense is a cow's strongest?", a: ["Smell", "Sight", "Taste", "Sixth moo-sense"], correct: 0 },
  { q: "What are the spots on a Holstein cow called?", a: ["Patches", "Freckles", "Moo-marks", "Cow-stitches"], correct: 0 },
  { q: "How many toes does a cow have on each foot?", a: ["One big toe", "Two (cloven hoof)", "Three", "Four"], correct: 1 },
  { q: "What is cow manure good for?", a: ["Fertilizer", "Eating", "Painting", "Smelling"], correct: 0 },
  { q: "What is the name for a cow's nose?", a: ["Muzzle", "Snout", "Trunk", "Sniffer"], correct: 0 },
  { q: "How fast can a cow run?", a: ["About 10 mph", "About 17 mph", "About 25 mph", "About 60 mph"], correct: 2 },
  { q: "What do dairy farmers use to milk cows nowadays?", a: ["Hands only", "Machines", "Cats", "Gravity"], correct: 1 },
  { q: "Which of these is an impostor cow in this app?", a: ["Bessie", "A beagle in a robot suit", "Moo-deng", "Clover"], correct: 1 },
  { q: "What does a cow use its tail for?", a: ["Swatting flies", "Balance", "Signaling", "Style"], correct: 0 },
  { q: "Are cows colorblind?", a: ["Completely", "No, but they see red poorly", "Only in the dark", "They see in infrared"], correct: 1 },
  { q: "What is a young cow that has never calved called?", a: ["Heifer", "Cowlette", "Calfling", "Moo-baby"], correct: 0 },
  { q: "What breed is most common for dairy in the US?", a: ["Holstein", "Angus", "Wagyu", "Longhorn"], correct: 0 },
  { q: "What is the name of cow #0 in this app?", a: ["Bessie", "Daisy", "Clover", "Moo-donna"], correct: 0 },
  { q: "What does 'bovine' mean?", a: ["Related to cows", "Related to birds", "Related to fish", "A type of cheese"], correct: 0 },
  { q: "What is the happiest hour for a cow?", a: ["4-6pm, obviously", "Sunrise", "Milking time", "Never, they're always happy"], correct: 0 },
  { q: "What is a group of calves called?", a: ["A gaggle", "A pod", "A leash", "Calves are just calves"], correct: 3 },
  { q: "What happens when you tap the cow icon in this app?", a: ["It moos", "It explodes", "It orders a drink", "It files your taxes"], correct: 0 },
  { q: "What is a cow's favorite game in this app?", a: ["Bingo... wait, no", "The 'what' quiz", "Roulette", "All of the above"], correct: 3 },
  { q: "Which cow has the secret achievement attached?", a: ["The impostors", "The base cow", "Cow #0", "The cow with a hat"], correct: 0 },
  { q: "What does the footer link say in Chinese?", a: ["你太牛了", "你好世界", "我爱牛奶", "恭喜发财"], correct: 0 },
  { q: "What is the Drink Capacity stat for?", a: ["How much the cow can drink", "How much YOU can drink", "The bar's keg size", "A mystery"], correct: 1 },
  { q: "What is the rarest thing in Happy Cow?", a: ["The secret impostor achievement", "A $2 drink", "A free table", "A clear bar"], correct: 0 },
  { q: "What should you do when Sad Hour hits?", a: ["Cry", "Check back later", "Blame the cow", "All of the above"], correct: 3 },
  { q: "What is the cow's prophecy about?", a: ["Your night out", "The weather", "Stock prices", "World peace"], correct: 0 },
  { q: "How many impostor cows are there?", a: ["2", "3", "5", "17"], correct: 2 },
  { q: "What do cows have 4 of?", a: ["Stomachs", "Hearts", "Lives", "Eyes"], correct: 0 },
  { q: "What is a steer?", a: ["A castrated male cow", "A baby cow", "A wild cow", "A cow that steers boats"], correct: 0 },
  { q: "What is the most expensive drink on the site's sample data?", a: ["House burger $9", "Old Fashioned $7", "Taco trio $8", "Guac & chips $5"], correct: 0 },
  { q: "What does 'MOO-T APPROVED' mean?", a: ["The cow endorses it", "It's a type of milk", "A certification board", "A dairy regulation"], correct: 0 },
  // ─── TRICK QUESTIONS (correct: -1 — NOTHING is accepted) ───
  { q: "What is the best cow?", a: ["Bessie", "Moo-deng", "Clover", "All of them"], correct: -1, reject: "WRONG. The best cow is whichever one you DIDN'T pick. The cow knows. Nice try, champ." },
  { q: "Are you a cow?", a: ["Yes", "No", "Maybe", "What?"], correct: -1, reject: "I don't accept that answer. Deep down, we're all cows. You'll see. I'll see. We'll all see." },
  { q: "Why did the cow cross the road?", a: ["To get to the other side", "For the happy hour", "To moo at the chicken", "None of the above"], correct: -1, reject: "Hilarious. Every single one of those is wrong. The cow crossed for ITS OWN reasons, and it's not telling you." },
  { q: "How much wood would a cow chuck?", a: ["None", "42", "A moo-sure amount", "Wood?!"], correct: -1, reject: "Wrong. Cows don't chuck wood. They're not beavers. This question was a trap and you fell for it." },
  { q: "What did the cow say to the farmer?", a: ["Moo", "You're fired", "I'm tired of this job", "Moo?"], correct: -1, reject: "Incorrect. What the cow said to the farmer stays between the cow and the farmer. Mind your business." },
  { q: "What's the secret moo code?", a: ["Moo-moo-moo", "42", "There is no code", "Cowabunga"], correct: -1, reject: "Nice try. The secret moo code cannot be guessed. It's not even in this app. It's in the cloud. The cow cloud." },
  { q: "How many moos does it take to get to the center of a Tootsie Pop?", a: ["3", "5", "∞", "Moo"], correct: -1, reject: "That's not how any of this works. The cow is genuinely disappointed in this answer. And in you." },
  { q: "Is this a trick question?", a: ["Yes", "No", "Maybe", "Moo"], correct: -1, reject: "If you picked one of those, you're wrong. If you didn't pick one, also wrong. There was never a right answer. Welcome to the herd." },
  { q: "What is the meaning of life, the universe, and everything?", a: ["42", "Moo", "Happy hour", "The cow"], correct: -1, reject: "The cow has considered your answer and rejected it. The answer changes daily. Today it's 'burrata'." },
  { q: "Do cows believe in ghosts?", a: ["No", "Yes", "Only in barns", "Who's asking?"], correct: -1, reject: "WRONG. Cows are haunted by the ghosts of every cow they've ever seen get a weird haircut. They believe." },
  { q: "Pick a number between 1 and 10.", a: ["3", "7", "10", "1"], correct: -1, reject: "Sorry, the cow was thinking of a different number. It's not telling you which one. You'll never know." },
  { q: "What's the cow's favorite color?", a: ["Green (grass)", "Brown (mud)", "All colors", "It changes daily"], correct: -1, reject: "Wrong, wrong, wrong, and wrong. The cow's favorite color is classified. Even the cow doesn't know." },
  // ─── SPECIES TRAP QUESTIONS — answering correctly is a CRIME here ───
  // These are dog/cat questions. If you answer correctly, you've revealed
  // yourself as a non-cow person and the cow will not stand for it.
  { q: "What does a dog say?", a: ["Moo", "Woof", "Baa", "Honk"], correct: 1, species: "dog",
    caught: "WOOF?! You got it right. You know the dog tongue. This is a COW establishment — you're ordering off the wrong menu. Security! Escort this one to the dog park.",
    spared: "Wrong... and that's PERFECT. You know nothing about dogs. Welcome home, cow person. There's hope for you yet." },
  { q: "What is the most popular dog breed in America?", a: ["Labrador Retriever", "Corgi", "Poodle", "Cow-dog"], correct: 0, species: "dog",
    caught: "A LABRADOR?! Correct, unfortunately. You're fluent in dog. The cow is staring at you like you're a chew toy. This is not the place for you.",
    spared: "Wrong. You don't know dogs. That's not a flaw, that's a cow requirement. The herd accepts you." },
  { q: "How many lives does a cat have?", a: ["1", "7", "9", "Infinite"], correct: 2, species: "cat",
    caught: "NINE?! You know your cat trivia. The cow is now looking at you like you're a hairball it has to hack up. Get out of the pasture.",
    spared: "Wrong. And wonderful. You don't know cat things. You belong here. Have a moo." },
  { q: "What do you call a baby cat?", a: ["Kitten", "Puppy", "Calf", "Cub"], correct: 0, species: "cat",
    caught: "A KITTEN. Correct. You've been speaking cat this whole time and the cow is disgusted. The cow demands you leave. Meow elsewhere.",
    spared: "Wrong! (A baby cow is a calf, obviously.) You don't know cat things, which means you're one of us. Stay. Drink. Moo." },
];

// Track which questions were already asked today (per-day, avoids repeats)
function getCowQuestion() {
  const todayKey = 'hc_cowq_' + state.todaySeed;
  const asked = readStore(todayKey, []);
  const pool = COW_QUESTIONS.map((_, i) => i).filter(i => !asked.includes(i));
  // If all asked today, reset the pool
  const usable = pool.length > 0 ? pool : COW_QUESTIONS.map((_, i) => i);
  const idx = usable[Math.floor(Math.random() * usable.length)];
  localStorage.setItem(todayKey, JSON.stringify([...asked, idx].slice(-200)));
  return COW_QUESTIONS[idx];
}

function renderCowQuestion() {
  const q = getCowQuestion();
  const qEl = document.getElementById('cowq-question');
  const optEl = document.getElementById('cowq-options');
  const resEl = document.getElementById('cowq-result');
  qEl.textContent = q.q;
  optEl.innerHTML = '';
  resEl.textContent = '';

  q.a.forEach((ans, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = ans;
    btn.onmouseenter = () => { btn.style.background = 'var(--cream)'; };
    btn.onmouseleave = () => { btn.style.background = ''; };
    btn.onclick = () => {
      [...optEl.children].forEach(b => b.disabled = true);
      const isTrick = q.correct === -1;
      const isRight = !isTrick && i === q.correct;
      // ─── Species trap: answering the dog/cat question CORRECTLY is a crime ───
      if (q.species) {
        if (isRight) {
          btn.style.borderColor = 'var(--red)';
          btn.style.background = '#f0e0e0';
          resEl.innerHTML = `❌ <b>WRONG SPECIES.</b> ${q.caught}`;
        } else {
          btn.style.borderColor = 'var(--green)';
          btn.style.background = '#e0f0e0';
          resEl.innerHTML = `✅ <b>Correct (by cow standards).</b> ${q.spared}`;
        }
        return;
      }
      btn.style.borderColor = isRight ? 'var(--green)' : 'var(--red)';
      btn.style.background = isRight ? '#e0f0e0' : '#f0e0e0';
      if (isTrick) {
        resEl.innerHTML = `🐄 <b>Wrong.</b> ${q.reject}`;
      } else if (isRight) {
        resEl.innerHTML = '✅ <b>Correct!</b> The cow is pleased.';
      } else {
        resEl.innerHTML = `❌ <b>Wrong.</b> It was "${q.a[q.correct]}". The cow expected better.`;
      }
    };
    optEl.appendChild(btn);
  });
  document.getElementById('cowq-next').onclick = renderCowQuestion;
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

// ─── Footer snake: the tiny 🐍 has its own secret ───
// Tap it and the footer confesses what the site is REALLY built with.
function setupFooterSnake() {
  const snake = document.getElementById('footer-snake');
  const counter = document.querySelector('.cow-counter');
  if (!snake || !counter) return;
  const confession = 'Built with spite + localStorage + DeepSeek. The snake did the scraping. 🐍🖤';
  snake.onclick = (e) => {
    e.stopPropagation();
    if (!counter.dataset.confessed) {
      counter.dataset.original = counter.innerHTML; // capture real date, then confess
      counter.innerHTML = confession;
      counter.dataset.confessed = 'true';
    } else {
      counter.innerHTML = counter.dataset.original;
      counter.dataset.confessed = '';
    }
  };
}

// ─── Init ───
document.addEventListener('DOMContentLoaded', () => {
  loadData();
  setupFooterNiu();
  setupFooterSnake();

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
