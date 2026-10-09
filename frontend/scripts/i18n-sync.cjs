#!/usr/bin/env node
/**
 * Keep src/i18n/locales/{rw,fr}.json in step with en.json.
 * - Keys new in English are added as "TODO: translate" (never machine-translated).
 * - Keys no longer in English are removed and listed.
 * - Keys follow the English order, so files diff cleanly.
 * Usage: npm run i18n:sync
 */
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname, '..', 'src', 'i18n', 'locales');
const TODO = 'TODO: translate';
const read = (name) => {
  const file = path.join(dir, `${name}.json`);
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
};

const en = read('en');

for (const locale of ['rw', 'fr']) {
  const current = read(locale);
  const next = {};
  let added = 0;
  for (const key of Object.keys(en)) {
    if (key in current) {
      next[key] = current[key];
    } else {
      next[key] = TODO;
      added += 1;
    }
  }
  const removed = Object.keys(current).filter((k) => !(k in en));
  const todo = Object.values(next).filter((v) => v === TODO).length;
  fs.writeFileSync(path.join(dir, `${locale}.json`), `${JSON.stringify(next, null, 2)}\n`);
  console.log(`${locale}: ${added} added, ${removed.length} removed, ${todo} to translate`);
  if (removed.length) console.log(`  removed: ${removed.join(', ')}`);
}
