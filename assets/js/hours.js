// assets/js/hours.js — canonical happy-hour + business-hours parsing.
// Phase 1 of issue #30 (architecture refactor). Loaded BEFORE app.js.
//
// Pure functions with an injectable `now` so the logic is unit-testable.
// Grammar covered (all 22 distinct strings in the live data):
//   Daily 3-5pm · Mon-Fri 4-7pm · Fri 12-8pm · Mon 3-close · Daily 2:30-4pm
//   Daily 3-5pm & 8-9pm            (multi-window, same day range)
//   Daily 3-6pm, Fri-Sat 10pm-12am (secondary window with its own days)
//   Mon-Fri 3-5pm, Sun all day     (all-day terminal)
//   Fri-Sat 11am-2am               (midnight crossing -> spansNextDay)
//   Mon-Sun 4pm-10pm               (business hours, for `close` resolution)
(function (global) {
  'use strict';

  const DAY_ORDER = { mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6, sun: 7 };
  const MIN = 60;
  const DAY_MIN = 1440;
  const FALLBACK_CLOSE = 23 * 60 + 59; // 11:59pm when business hours unparseable

  function dayNum(token) {
    return DAY_ORDER[String(token).toLowerCase().slice(0, 3)];
  }

  // "Daily" | "Mon-Fri" | "Fri" | "Sun" | "Thu-Sat" -> {startDay, endDay} (1=Mon..7=Sun)
  function parseDayRange(token) {
    if (!token) return null;
    if (/^daily$/i.test(token)) return { startDay: 1, endDay: 7 };
    const m = String(token).match(/^(mon|tue|wed|thu|fri|sat|sun)(?:-(mon|tue|wed|thu|fri|sat|sun))?$/i);
    if (!m) return null;
    return { startDay: dayNum(m[1]), endDay: dayNum(m[2] || m[1]) };
  }

  function toMin(hour, min, ampm) {
    let h = hour;
    const a = String(ampm || '').toLowerCase();
    if (a === 'am') { if (h === 12) h = 0; }
    else if (a === 'pm') { if (h !== 12) h += 12; }
    return h * MIN + (min || 0);
  }

  // "4-6pm" | "2:30-4pm" | "11am-2am" | "3-close" | "all day"
  // Returns null when unparseable. `close` windows get FALLBACK_CLOSE here;
  // hhStatus re-resolves them against business hours.
  function parseTimeRange(tok) {
    const t = String(tok || '').trim().toLowerCase();
    if (t === 'all day') return { startMin: 0, endMin: DAY_MIN - 1, allDay: true, spansNextDay: false, close: false };
    const m = t.match(/^(\d{1,2})(?::(\d{2}))?(am|pm)?\s*-\s*(close|(\d{1,2})(?::(\d{2}))?(am|pm)?)$/);
    if (!m) return null;
    const sH = +m[1], sMin = +(m[2] || 0), sA = m[3];
    const startMin = toMin(sH, sMin, sA || 'pm');
    let endMin, close = false;
    if (m[4] === 'close') {
      close = true;
      endMin = FALLBACK_CLOSE;
    } else {
      endMin = toMin(+m[5], +(m[6] || 0), m[7] || sA || 'pm');
    }
    let spansNextDay = false;
    if (endMin <= startMin) { endMin += DAY_MIN; spansNextDay = true; }
    return { startMin, endMin, spansNextDay, close, allDay: false };
  }

  // "Daily 3-5pm & 8-9pm" | "Daily 3-6pm, Fri-Sat 10pm-12am" | "Mon-Fri 3-5pm, Sun all day"
  // Segments without a day token inherit the previous segment's day range.
  function parseHours(hoursStr) {
    if (!hoursStr || !String(hoursStr).trim()) return [];
    const windows = [];
    let lastRange = null;
    for (const seg of String(hoursStr).split(/[&,]/)) {
      const tokens = seg.trim().split(/\s+/).filter(Boolean);
      if (!tokens.length) continue;
      let dayRange = parseDayRange(tokens[0]);
      let timeTok;
      if (dayRange) {
        timeTok = tokens.slice(1).join(' ');
      } else {
        dayRange = lastRange;
        timeTok = tokens.join(' ');
      }
      if (!dayRange || !timeTok) continue;
      lastRange = dayRange;
      const tr = parseTimeRange(timeTok);
      if (!tr) continue;
      windows.push({ startDay: dayRange.startDay, endDay: dayRange.endDay, ...tr });
    }
    return windows;
  }

  // Best-effort: "Mon-Sun 4pm-10pm" | "Mon Closed, Tue-Sat 10am-6pm" | "Fri-Sat 4pm-Midnight (…)"
  // Returns { day(1-7): closeMin } for parseable days only; missing days fall back
  // to FALLBACK_CLOSE in hhStatus. "Midnight" -> 1440 (24:00).
  function parseBusinessHours(str) {
    const out = {};
    if (!str) return out;
    for (const seg of String(str).split(',')) {
      const m = seg.trim().match(/^(daily|(?:mon|tue|wed|thu|fri|sat|sun)(?:-(?:mon|tue|wed|thu|fri|sat|sun))?)\s+(.+)$/i);
      if (!m) continue;
      const rng = parseDayRange(m[1]);
      if (!rng) continue;
      const body = m[2].trim();
      if (/^closed/i.test(body)) continue;
      const t = body.match(/(\d{1,2})(?::(\d{2}))?(am|pm)?\s*-\s*(midnight|close|(\d{1,2})(?::(\d{2}))?(am|pm)?)/i);
      if (!t) continue;
      let endMin;
      if (/^midnight$/i.test(t[4])) endMin = DAY_MIN;
      else endMin = toMin(+t[5], +(t[6] || 0), t[7] || t[3] || 'pm');
      for (let d = rng.startDay; ; d = d === 7 ? 1 : d + 1) {
        out[d] = endMin;
        if (d === rng.endDay) break;
      }
    }
    return out;
  }

  function dayOfDate(d) { return (d.getDay() + 6) % 7 + 1; } // 1=Mon..7=Sun
  function prevDay(d) { return d === 1 ? 7 : d - 1; }

  // Is `day` inside [startDay, endDay] with wrap (Thu-Sat, Sun-Thu)?
  function dayInRange(day, startDay, endDay) {
    if (endDay >= startDay) return day >= startDay && day <= endDay;
    return day >= startDay || day <= endDay;
  }

  // A window with endMin > 1440 spills into the next day. Active at (day, min)
  // if the day is in range and the minute falls in the window, or if the
  // PREVIOUS day was in range and the minute falls in the spilled tail.
  function windowActive(w, day, min) {
    const inRange = dayInRange(day, w.startDay, w.endDay);
    if (inRange && min >= w.startMin && min < Math.min(w.endMin, DAY_MIN)) return true;
    if (w.endMin > DAY_MIN && dayInRange(prevDay(day), w.startDay, w.endDay) && min < w.endMin - DAY_MIN) return true;
    return false;
  }

  // hhStatus(hoursStr, bizHoursStr, now) -> {kind, nextStartMin}
  // kind: 'live' | 'soon' | 'closed' | 'unknown'. `soon` = next same-day window
  // start within 120 minutes (mirrors the old behaviour, now multi-window aware).
  function hhStatus(hoursStr, bizHoursStr, now) {
    const windows = parseHours(hoursStr);
    if (!windows.length) return { kind: 'unknown', nextStartMin: null };
    const d = now || new Date();
    const day = dayOfDate(d);
    const min = d.getHours() * MIN + d.getMinutes();
    const biz = parseBusinessHours(bizHoursStr);

    for (const w of windows) {
      if (w.close && biz[day] != null) {
        const rw = { ...w, endMin: biz[day], spansNextDay: biz[day] <= w.startMin };
        if (windowActive(rw, day, min)) return { kind: 'live', nextStartMin: null };
      } else if (windowActive(w, day, min)) {
        return { kind: 'live', nextStartMin: null };
      }
    }

    let best = null;
    for (const w of windows) {
      const endMin = w.close && biz[day] != null ? biz[day] : w.endMin;
      if (dayInRange(day, w.startDay, w.endDay) && min < w.startMin) {
        const delta = w.startMin - min;
        if (delta <= 120 && (best === null || delta < best.delta)) {
          best = { delta, startMin: w.startMin };
        }
      }
      if (w.close && endMin > DAY_MIN) {
        // close lands after midnight: a same-day start still applies today
        if (dayInRange(day, w.startDay, w.endDay) && min < w.startMin && (best === null || w.startMin - min < best.delta)) {
          best = { delta: w.startMin - min, startMin: w.startMin };
        }
      }
    }
    if (best) return { kind: 'soon', nextStartMin: best.startMin };
    return { kind: 'closed', nextStartMin: null };
  }

  function timeUntil(startMin, now) {
    const d = now || new Date();
    const diff = startMin - (d.getHours() * MIN + d.getMinutes());
    if (diff <= 0) return '';
    const h = Math.floor(diff / MIN);
    const m = diff % MIN;
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  }

  const api = { parseHours, parseBusinessHours, hhStatus, timeUntil };
  global.HappyCowHours = api;
  // Back-compat wrappers so app.js call sites keep working during the migration.
  global.isHHLive = function isHHLive(hoursStr, bizHoursStr) {
    return hhStatus(hoursStr, bizHoursStr, new Date()).kind;
  };
  global.timeUntil = function timeUntilCompat(startMin) {
    return timeUntil(startMin, new Date());
  };
  global.getStartMinutes = function getStartMinutes(hoursStr) {
    return hhStatus(hoursStr, '', new Date()).nextStartMin || 0;
  };
})(typeof window !== 'undefined' ? window : globalThis);
