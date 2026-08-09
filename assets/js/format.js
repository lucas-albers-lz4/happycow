// assets/js/format.js — HTML escape + special price labels + day-special match.
// Phase A of issue #42. Loaded BEFORE app.js.
//
// Shared by the browser (script tag) and Node unit tests (eval IIFE).
(function (global) {
  'use strict';

  const FULL_DAYS = {
    monday: 1, tuesday: 2, wednesday: 3, thursday: 4,
    friday: 5, saturday: 6, sunday: 7
  };
  const ABBR_DAYS = { mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6, sun: 7 };

  // Escape pipeline-sourced text (scraped pages / LLM output) before
  // interpolating into innerHTML — venue data is not trusted input.
  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  // A special's price cell. price 0 is ambiguous: it can mean genuinely free,
  // or a discount-only deal ("$1 off") with no base price in the data. The old
  // renderer printed FREE for both, which mislabeled "$1.00 off well drinks"
  // as a free drink. Any deal/pricing wording in `description` → dash; only
  // descriptions with no pricing signal at all read as genuinely free.
  function specialPriceLabel(s) {
    if (s.price > 0) return '$' + s.price.toFixed(2);
    if (s.description && /\$|cents|%|off|discount|half|bogo|special|deal|price|happy\s*hour|2\s*for\s*1|2-4-1|one\s*free/i.test(s.description)) return '—';
    return 'FREE';
  }

  // 1=Mon … 7=Sun — single definition lives in hours.js (loaded first).
  function dayOfDate(d) {
    return global.HappyCowHours.dayOfDate(d);
  }

  // Park-Miller LCG — shared by nicknames (app.js) and tall tales (tales.js).
  function seededRandom(seed) {
    let s = seed % 2147483647;
    if (s <= 0) s += 2147483646;
    return function () {
      s = (s * 16807) % 2147483647;
      return (s - 1) / 2147483646;
    };
  }

  function hashStr(s) {
    let h = 0;
    const str = String(s || '');
    for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0;
    return Math.abs(h);
  }

  // Collect weekday numbers mentioned in free-text (item + description).
  // Word boundaries so "fri" ≠ "fries". Full names accept trailing "s"
  // (Wednesdays). Hyphenated ranges (Mon-Fri) expand to every day in range
  // (wrap-aware). Slash pairs like "Tue/Thu" stay as separate endpoint tokens.
  function daysMentionedInSpecial(special) {
    const text = `${special?.item || ''} ${special?.description || ''}`.toLowerCase();
    const days = new Set();

    const rangeRe = /\b(mon|tue|wed|thu|fri|sat|sun)-(mon|tue|wed|thu|fri|sat|sun)\b/g;
    let m;
    while ((m = rangeRe.exec(text)) !== null) {
      const start = ABBR_DAYS[m[1]];
      const end = ABBR_DAYS[m[2]];
      if (!start || !end) continue;
      if (end >= start) {
        for (let d = start; d <= end; d++) days.add(d);
      } else {
        // Wrap: Fri-Mon → Fri,Sat,Sun,Mon
        for (let d = start; d <= 7; d++) days.add(d);
        for (let d = 1; d <= end; d++) days.add(d);
      }
    }

    for (const [name, n] of Object.entries(FULL_DAYS)) {
      if (new RegExp('\\b' + name + 's?\\b').test(text)) days.add(n);
    }
    for (const [name, n] of Object.entries(ABBR_DAYS)) {
      if (new RegExp('\\b' + name + '\\b').test(text)) days.add(n);
    }
    return days;
  }

  // True only when the special names specific weekdays AND today is one of them.
  // Always-on specials (no day tokens) return false — not highlighted as "today".
  function specialAppliesToday(special, now) {
    const days = daysMentionedInSpecial(special);
    if (!days.size) return false;
    return days.has(dayOfDate(now || new Date()));
  }

  global.HappyCowFormat = {
    esc,
    specialPriceLabel,
    specialAppliesToday,
    daysMentionedInSpecial,
    dayOfDate,
    seededRandom,
    hashStr
  };
})(typeof window !== 'undefined' ? window : globalThis);
