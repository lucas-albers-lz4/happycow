// assets/js/render.js — pure venue-card HTML builder.
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

  const CLOSED_LABEL = 'Done';

  function renderVenueCardHtml(venue, helpers, now) {
    const { esc, specialPriceLabel } = helpers;
    const st = global.HappyCowHours.hhStatus(venue.hours, venue.business_hours, now || new Date());
    const status = st.kind;
    const expanded = false; // card HTML is always initially collapsed; app.js manages state

    const statusText = status === 'live' ? '● Live now' :
                       status === 'soon' ? `▲ Opens in ${global.HappyCowHours.timeUntil(st.nextStartMin, now || new Date())}` :
                       status === 'closed' ? `○ ${CLOSED_LABEL}` :
                       '';
    const statusBadge = statusText ? `<div class="hh-status ${status}">${statusText}</div>` : '';
    const nSpecials = (venue.specials || []).length;
    const specialsChip = nSpecials
      ? `<div class="hh-status specials">🍸 ${nSpecials} special${nSpecials === 1 ? '' : 's'}</div>` : '';
    const badges = (statusBadge || specialsChip)
      ? `<div class="venue-badges">${statusBadge}${specialsChip}</div>` : '';

    const specialsId = `specials-${venue.id}`;
    const hoursId = `hours-${venue.id}`;
    const bizHoursId = `biz-hours-${venue.id}`;

    return `
    <button type="button" class="venue-toggle" aria-expanded="false" aria-controls="${specialsId}" data-venue-id="${esc(venue.id)}">
      <div class="venue-header">
        <div>
          <h3 class="venue-name">${esc(venue.name)}</h3>
          <div class="venue-detail">${esc([venue.hours, venue.address].filter(Boolean).join(' · '))}</div>
          <div class="venue-tags">${(venue.tags || []).map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>
        </div>
        ${badges}
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

  global.HappyCowRender = { renderVenueCardHtml };
})(typeof window !== 'undefined' ? window : globalThis);
