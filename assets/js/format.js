// assets/js/format.js — HTML escape + special price labels.
// Phase A of issue #42. Loaded BEFORE app.js.
//
// Shared by the browser (script tag) and Node unit tests (eval IIFE).
(function (global) {
  'use strict';

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

  global.HappyCowFormat = { esc, specialPriceLabel };
})(typeof window !== 'undefined' ? window : globalThis);
