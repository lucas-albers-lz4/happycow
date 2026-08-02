// Validates that every non-empty `hours` string in the data parses under the
// canonical parser (assets/js/hours.js — the SINGLE source of truth; no Python
// re-implementation, per the architecture MCR, issue #30).
//
// Usage: node scripts/validate_hours.mjs data/happy_hour_data.json
// Exit 0 = pass, 1 = any unparseable hours string.
import { readFileSync } from 'node:fs';

const hoursJs = readFileSync(new URL('../assets/js/hours.js', import.meta.url), 'utf8');
eval(hoursJs); // IIFE attaches to globalThis in Node
const { parseHours } = globalThis.HappyCowHours;

const dataPath = process.argv[2];
if (!dataPath) {
  console.error('usage: node scripts/validate_hours.mjs <data.json>');
  process.exit(2);
}
const data = JSON.parse(readFileSync(dataPath, 'utf8'));

let fail = 0;
for (const v of data.venues || []) {
  const h = (v.hours || '').trim();
  if (!h) continue; // no hours is legitimate (specials-only venues)
  const windows = parseHours(h);
  if (windows.length === 0) {
    console.error(`UNPARSEABLE hours: ${v.id} — "${h}"`);
    fail++;
  }
}
if (fail) {
  console.error(`${fail} venue(s) with unparseable hours`);
  process.exit(1);
}
console.log(`hours OK: all non-empty hours strings in ${dataPath} parse (${data.venues.length} venues)`);
