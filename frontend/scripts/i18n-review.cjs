#!/usr/bin/env node
/**
 * Kinyarwanda review sheet (CSV, opens in Excel / Google Sheets).
 *
 *   npm run i18n:review                    write docs/i18n/kinyarwanda_review.csv from en.json + rw.json
 *   npm run i18n:review -- new <name> <keys...|prefix.*>
 *                                          write docs/i18n/kinyarwanda_review_<name>.csv with only those
 *                                          strings (added later, so the main sheet is not overwritten)
 *   npm run i18n:review -- apply           copy every filled "correction" cell, from every
 *                                          docs/i18n/kinyarwanda_review*.csv, into rw.json
 *
 * Columns: key, screen, english, kinyarwanda (current), correction (empty: fill in to change),
 * placeholders. A correction must keep the same {placeholders} as the English text, or it is refused.
 */
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const localeDir = path.join(root, 'src', 'i18n', 'locales');
const sheetDir = path.join(root, '..', 'docs', 'i18n');
const sheet = path.join(sheetDir, 'kinyarwanda_review.csv');
const read = (name) => JSON.parse(fs.readFileSync(path.join(localeDir, `${name}.json`), 'utf8'));

const SCREENS = {
  app: 'Everywhere', action: 'Buttons', status: 'Loading', error: 'Error messages', counter: 'Meter counter',
  language: 'Language picker', month: 'Month names', pay: 'Payment', nav: 'Bottom menu', flow: 'Reading steps',
  camera: 'Camera', guidance: 'Camera tips', confirm: 'Check the numbers', held: 'Reading being checked',
  bill: 'Bill', history: 'Bills list', home: 'Home', messages: 'Messages', msg: 'Messages', brand: 'Header',
  landing: 'Public start page', theme: 'Light/dark switch', demo: 'Demo label', signin: 'Staff sign-in',
  staff: 'Staff dashboard', issue: 'Staff dashboard', notFound: 'Page not found',
};
const placeholders = (text) => (text.match(/\{\w+\}/g) || []).sort().join(' ');
const cell = (value) => `"${String(value).replace(/"/g, '""')}"`;

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i += 1; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n') { row.push(field.replace(/\r$/, '')); rows.push(row); row = []; field = ''; }
    else field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  return rows;
}

const en = read('en');
const rw = read('rw');

function writeSheet(file, keys) {
  const lines = [['key', 'screen', 'english', 'kinyarwanda', 'correction', 'placeholders'].join(',')];
  for (const key of keys) {
    const english = en[key];
    const screen = SCREENS[key.split('.')[0]] || '';
    lines.push([key, screen, english, rw[key] || '', '', placeholders(english)].map(cell).join(','));
  }
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `﻿${lines.join('\n')}\n`); // BOM so Excel reads UTF-8
  console.log(`Wrote ${lines.length - 1} strings to ${path.relative(path.join(root, '..'), file)}`);
}

if (process.argv[2] === 'apply') {
  const sheets = fs.readdirSync(sheetDir).filter((f) => /^kinyarwanda_review.*\.csv$/.test(f));
  const rows = [];
  let header = [];
  for (const f of sheets) {
    const [h, ...r] = parseCsv(fs.readFileSync(path.join(sheetDir, f), 'utf8').replace(/^﻿/, ''));
    header = h;
    rows.push(...r);
  }
  const col = (name) => header.indexOf(name);
  let changed = 0;
  const refused = [];
  for (const r of rows) {
    const key = r[col('key')];
    const correction = (r[col('correction')] || '').trim();
    if (!key || !correction || !(key in en)) continue;
    if (placeholders(correction) !== placeholders(en[key])) { refused.push(key); continue; }
    if (rw[key] !== correction) { rw[key] = correction; changed += 1; }
  }
  fs.writeFileSync(path.join(localeDir, 'rw.json'), `${JSON.stringify(rw, null, 2)}\n`);
  console.log(`${changed} corrections applied to rw.json.`);
  if (refused.length) console.log(`Refused (placeholders differ from English): ${refused.join(', ')}`);
} else if (process.argv[2] === 'new') {
  const [name, ...patterns] = process.argv.slice(3);
  if (!name || !/^[a-z0-9_-]+$/.test(name) || patterns.length === 0) {
    console.error('Usage: npm run i18n:review -- new <name> <key|prefix.*> ...');
    process.exit(1);
  }
  const wanted = (key) => patterns.some((p) => (p.endsWith('*') ? key.startsWith(p.slice(0, -1)) : key === p));
  writeSheet(path.join(sheetDir, `kinyarwanda_review_${name}.csv`), Object.keys(en).filter(wanted));
} else {
  writeSheet(sheet, Object.keys(en));
}
