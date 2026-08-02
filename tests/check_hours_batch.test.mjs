// check_hours_batch.mjs — issue #41. Run: node --test
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const SCRIPT = fileURLToPath(new URL('../scripts/scraper/check_hours_batch.mjs', import.meta.url));

function checkBatch(items) {
  const proc = spawnSync(process.execPath, [SCRIPT], {
    input: JSON.stringify(items),
    encoding: 'utf8',
  });
  assert.equal(proc.status, 0, proc.stderr || proc.stdout);
  return JSON.parse(proc.stdout.trim());
}

test('check_hours_batch: good hours pass', () => {
  const out = checkBatch([
    { id: 'a', hours: 'Daily 4-6pm' },
    { id: 'b', hours: 'Daily 3-5pm & 8-9pm' },
    { id: 'c', hours: 'Mon-Fri 3-5pm, Sun all day' },
  ]);
  assert.deepEqual(out.bad, []);
});

test('check_hours_batch: unparseable flagged; empty skipped', () => {
  const out = checkBatch([
    { id: 'ok', hours: 'Mon-Fri 4-6pm' },
    { id: 'bad', hours: 'from 4 until 6 in the evening' },
    { id: 'empty', hours: '' },
    { id: 'also-bad', hours: 'Weekdays afternoons' },
  ]);
  assert.deepEqual(out.bad, ['bad', 'also-bad']);
});

test('check_hours_batch: empty stdin -> empty bad', () => {
  const proc = spawnSync(process.execPath, [SCRIPT], {
    input: '',
    encoding: 'utf8',
  });
  assert.equal(proc.status, 0);
  assert.deepEqual(JSON.parse(proc.stdout.trim()), { bad: [] });
});
