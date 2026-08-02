// Batch-check hours strings with ONE Node process (issue #41).
// Reads JSON from stdin: [{"id":"...","hours":"..."}, ...]
// Prints JSON: {"bad":["id",...]} — ids whose non-empty hours do not parse
// under assets/js/hours.js (same parseHours as validate_hours.mjs).
import { readFileSync } from 'node:fs';

const hoursJs = readFileSync(new URL('../../assets/js/hours.js', import.meta.url), 'utf8');
eval(hoursJs); // IIFE attaches to globalThis in Node
const { parseHours } = globalThis.HappyCowHours;

const raw = readFileSync(0, 'utf8').trim();
if (!raw) {
  console.log(JSON.stringify({ bad: [] }));
  process.exit(0);
}

let items;
try {
  items = JSON.parse(raw);
} catch (e) {
  console.error('check_hours_batch: invalid JSON on stdin');
  process.exit(2);
}

if (!Array.isArray(items)) {
  console.error('check_hours_batch: stdin must be a JSON array');
  process.exit(2);
}

const bad = [];
for (const item of items) {
  if (!item || typeof item !== 'object') continue;
  const id = item.id;
  const h = String(item.hours || '').trim();
  if (!h) continue; // empty hours is legitimate
  const windows = parseHours(h);
  if (windows.length === 0) bad.push(id);
}

console.log(JSON.stringify({ bad }));
