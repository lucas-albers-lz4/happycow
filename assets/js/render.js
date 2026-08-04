// assets/js/render.js — pure venue-row HTML builder (014 dense format).
// Loaded BEFORE app.js. Depends on: hours.js (HappyCowHours), format.js (HappyCowFormat).
//
// renderVenueCardHtml(venue, helpers, now) -> HTML string
//   venue   — site venue record
//   helpers — { esc, specialPriceLabel } from HappyCowFormat
//   now     — injectable Date (defaults to new Date()) for deterministic tests
//
// DOM wiring (toggle listeners, panel expand, scrolling) stays in app.js.
(function (global) {
  'use strict';

  function dealHeadline(venue, specialPriceLabel) {
    const s = (venue.specials || [])[0];
    if (!s) return 'Tap for specials';
    const price = specialPriceLabel(s);
    if (price === '—' || price === 'FREE') return s.item;
    return `${s.item} · ${price}`;
  }

  function placeLabel(venue) {
    if (!venue.address) return '';
    return String(venue.address).split(',')[0].trim();
  }

  function whenLabel(st, now) {
    const d = now || new Date();
    if (st.kind === 'live' && st.endMin != null) {
      const left = global.HappyCowHours.timeUntil(st.endMin, d);
      return left || 'now';
    }
    if (st.kind === 'soon' && st.nextStartMin != null) {
      return global.HappyCowHours.timeUntil(st.nextStartMin, d) || 'soon';
    }
    if (st.kind === 'closed') return '—';
    return '';
  }

  function renderVenueCardHtml(venue, helpers, now) {
    const { esc, specialPriceLabel } = helpers;
    const clock = now || new Date();
    const st = global.HappyCowHours.hhStatus(venue.hours, venue.business_hours, clock);
    const status = st.kind === 'unknown' ? 'closed' : st.kind;
    const when = whenLabel(st, clock);
    const deal = dealHeadline(venue, specialPriceLabel);
    const place = placeLabel(venue);
    const meta = [venue.hours, place].filter(Boolean).join(' · ');

    const specialsId = `specials-${venue.id}`;
    const hoursId = `hours-${venue.id}`;
    const bizHoursId = `biz-hours-${venue.id}`;

    return `
    <button type="button" class="venue-toggle" aria-expanded="false" aria-controls="${specialsId}" data-venue-id="${esc(venue.id)}">
      <div class="venue-row-main">
        <div class="venue-row-l1">
          <h3 class="venue-name">${esc(venue.name)}</h3>
          <span class="venue-when">${esc(when)}</span>
        </div>
        <div class="venue-deal">${esc(deal)}</div>
        <div class="venue-detail">${esc(meta)}</div>
      </div>
    </button>
    <div class="venue-specials" id="${specialsId}" hidden>
      ${(venue.specials || []).map(s => `
        <div class="special-row">
          <div>
            <div>${esc(s.item)}</div>
            <div class="special-desc">${esc(s.description)}</div>
          </div>
          <div class="special-price">${specialPriceLabel(s)}</div>
        </div>
      `).join('')}
      ${!venue.hours && venue.notes ? `<div class="hours-notes">${esc(venue.notes)}</div>` : ''}
      <div class="venue-actions">
        <a href="${venue.maps}" target="_blank" rel="noopener" class="venue-link">📍 Directions</a>
        ${venue.website ? `<a href="${venue.website}" target="_blank" rel="noopener" class="venue-link">🔗 Website</a>` : ''}
        ${venue.hours ? `<button type="button" class="venue-link hours-toggle" aria-expanded="false" aria-controls="${hoursId}">🕐 Hours</button>` : ''}
        ${venue.business_hours ? `<button type="button" class="venue-link biz-hours-toggle" aria-expanded="false" aria-controls="${bizHoursId}">🏪 Biz Hours</button>` : ''}
      </div>
      ${venue.hours ? `
      <div class="hours-panel" id="${hoursId}" hidden>
        <div class="hours-title">Happy Hour</div>
        <div class="hours-value">${esc(venue.hours)}</div>
        ${venue.notes ? `<div class="hours-notes">${esc(venue.notes)}</div>` : ''}
      </div>` : ''}
      ${venue.business_hours ? `
      <div class="hours-panel" id="${bizHoursId}" hidden>
        <div class="hours-title">Business Hours</div>
        <div class="hours-value">${esc(venue.business_hours)}</div>
      </div>` : ''}
    </div>
  `;
  }

  global.HappyCowRender = { renderVenueCardHtml, dealHeadline, placeLabel };
})(typeof window !== 'undefined' ? window : globalThis);
