// End-to-end on the LIVE site, as real people use it:
//   household signs in, reads the meter (real photo), is held for checking, cannot send another;
//   officer accepts it; household sees the bill, pays it, gets the confirmation.
//
//   node live_e2e.mjs <app url> <meter photo> <staff password> <demo phone> [chrome path]
//
// Use a demo household that has no reading waiting and none in the last 25 days. Prints each step
// and every problem (failed requests, page errors, console errors); screenshots go to ./out/.
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';
import { homedir } from 'node:os';

const [APP, PHOTO, STAFF_PW, PHONE, CHROME] = process.argv.slice(2);
if (!APP || !PHOTO || !STAFF_PW || !PHONE) {
  console.error('usage: node live_e2e.mjs <app url> <meter photo> <staff password> <demo phone> [chrome path]');
  process.exit(2);
}
const HOUSEHOLD = 'DEMO Household ' + PHONE.replace(/\D/g, '').slice(-3);
const OUT = 'out';
mkdirSync(OUT, { recursive: true });
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const problems = [];
const browser = await chromium.launch({
  executablePath: CHROME || `${homedir()}/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell`,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
});

function watch(page, who) {
  page.on('pageerror', (e) => problems.push(`${who} page error: ${e}`));
  page.on('console', (m) => { if (m.type() === 'error') problems.push(`${who} console: ${m.text().slice(0, 200)}`); });
  page.on('response', (r) => {
    const u = r.url();
    if (r.status() >= 400 && !u.includes('/guide-frame')) problems.push(`${who} HTTP ${r.status()} ${r.request().method()} ${u.replace(/^https?:\/\/[^/]+/, '')}`);
  });
}
async function step(name, page, fn) {
  try { await fn(); log('OK  ', name); }
  catch (e) { problems.push(`STEP FAILED: ${name}: ${String(e).split('\n')[0]}`); log('FAIL', name, String(e).split('\n')[0]); }
  await page.screenshot({ path: `${OUT}/${name.replace(/\W+/g, '_')}.png` }).catch(() => {});
}

// ---- Household ---------------------------------------------------------------
const hh = await browser.newContext({ viewport: { width: 390, height: 844 }, permissions: ['camera', 'geolocation'], geolocation: { latitude: -1.95, longitude: 30.07, accuracy: 15 } });
await hh.addInitScript(() => localStorage.setItem('wasac.locale', 'en'));
const p = await hh.newPage(); watch(p, 'household');
await step('01 landing loads', p, async () => { await p.goto(APP + '/', { waitUntil: 'networkidle' }); await p.getByRole('heading', { level: 1 }).waitFor(); });
await step('02 sign in with code', p, async () => {
  await p.goto(APP + '/sign-in');
  await p.getByLabel('Your phone number').fill(PHONE);
  await p.getByRole('button', { name: 'Send me a code' }).click();
  await p.getByText('Demo account', { exact: true }).waitFor({ timeout: 30000 });
  const code = ((await p.locator('main').innerText()).match(/Your code is\s*(\d{6})/) || [])[1];
  if (!code) throw new Error('no demo code on screen');
  await p.getByLabel('6-digit code').fill(code);
  await p.getByRole('button', { name: 'Sign in' }).click();
  await p.waitForURL(/\/home/, { timeout: 30000 });
  await p.getByText('Your meter', { exact: true }).waitFor({ timeout: 30000 });
});
await step('03 open the camera', p, async () => {
  await p.getByRole('button', { name: 'Read your meter' }).click();
  await p.waitForURL(/submit\/camera/);
  await p.locator('video').waitFor({ timeout: 30000 });
});
await step('04 upload a meter photo', p, async () => {
  await p.locator('input[type=file]').setInputFiles(PHOTO);
  for (let i = 0; i < 60 && !/submit\/confirm/.test(p.url()); i++) {
    const anyway = p.getByRole('button', { name: 'Use this photo anyway' });
    const type = p.getByRole('button', { name: 'Type the numbers instead' });
    if (await anyway.isVisible().catch(() => false)) await anyway.click();
    else if (await p.getByText('We could not read the numbers').isVisible().catch(() => false) && await type.isVisible()) await type.click();
    await p.waitForTimeout(1000);
  }
  if (!/submit\/confirm/.test(p.url())) throw new Error('never reached the confirm page');
});
await step('05 confirm the reading', p, async () => {
  log('     confirm page says:', (await p.locator('main').innerText()).replace(/\s+/g, ' ').slice(0, 160));
  await p.getByRole('button', { name: 'Confirm reading' }).click();
  await p.waitForURL(/submit\/held|\/bill/, { timeout: 60000 });
  log('     went to', new URL(p.url()).pathname);
});
await step('06 messages explain the check', p, async () => {
  await p.goto(APP + '/messages');
  await p.locator('article').first().waitFor({ timeout: 30000 });
  log('     first message:', (await p.locator('article').first().innerText()).replace(/\s+/g, ' ').slice(0, 140));
});
await step('07 a second reading is refused while checking', p, async () => {
  await p.goto(APP + '/submit/camera');
  await p.getByText(/after the decision/).waitFor({ timeout: 30000 });
});

// ---- Staff -------------------------------------------------------------------
const st = await browser.newContext({ viewport: { width: 1366, height: 860 } });
await st.addInitScript(() => localStorage.setItem('wasac.locale', 'en'));
const s = await st.newPage(); watch(s, 'staff');
await step('08 staff sign in', s, async () => {
  await s.goto(APP + '/staff/sign-in');
  await s.getByLabel('Username').fill('dushime');
  await s.getByLabel('Password').fill(STAFF_PW);
  await s.getByRole('button', { name: 'Sign in' }).click();
  await s.waitForURL(/\/staff\/?$/, { timeout: 30000 });
});
await step('09 review queue: see the photo, accept our reading', s, async () => {
  await s.goto(APP + '/staff/review');
  const item = s.getByRole('button', { name: new RegExp(HOUSEHOLD) }).first();
  await item.waitFor({ timeout: 30000 });
  await item.click();
  const pane = (await s.locator('main').innerText()).replace(/\s+/g, ' ');
  log('     decision pane mentions location:', /Where the photo was taken/.test(pane), '| map link:', await s.getByRole('link', { name: 'Open in map' }).count());
  // The officer sees the photo the household sent (kept by /submit-photo, linked on confirm).
  await s.getByRole('img', { name: /Meter photo sent by/ }).waitFor({ timeout: 20000 });
  log('     photo shown to the officer; reader read:', /Photo reader read/.test(pane));
  await s.getByRole('button', { name: 'Accept reading' }).click();
  await s.waitForTimeout(8000); // 5 s undo window, then the request
});
await step('10 activity shows the decision', s, async () => {
  await s.goto(APP + '/staff/activity');
  await s.getByRole('cell', { name: 'Accepted a reading' }).first().waitFor({ timeout: 30000 });
  log('     newest decision:', (await s.locator('tbody tr').first().innerText()).replace(/\s+/g, ' '));
});
await step('11 households page shows the unpaid bill', s, async () => {
  await s.goto(APP + '/staff/households');
  const row = s.locator('tr', { hasText: HOUSEHOLD });
  await row.waitFor({ timeout: 30000 });
  const text = (await row.innerText()).replace(/\s+/g, ' ');
  log('     row:', text);
  if (!/RWF/.test(text)) throw new Error('no unpaid amount shown for ' + HOUSEHOLD);
});
await step('12 sent SMS page lists messages', s, async () => {
  await s.goto(APP + '/staff/sms');
  await s.locator('#staff-main table, #staff-main section p').first().waitFor({ timeout: 30000 });
  log('     sms rows:', await s.locator('tbody tr').count());
});
await step('13 staff accounts page', s, async () => {
  await s.goto(APP + '/staff/accounts');
  await s.getByText('dushime').first().waitFor({ timeout: 30000 });
});

// ---- Household again: the bill and payment ----------------------------------
await step('14 home shows the bill', p, async () => {
  await p.goto(APP + '/home');
  await p.getByRole('button', { name: /^Pay RWF/ }).waitFor({ timeout: 30000 });
});
await step('15 pay the bill', p, async () => {
  await p.getByRole('button', { name: /^Pay RWF/ }).click();
  await p.waitForURL(/payment/);
  await p.getByRole('button', { name: /^Pay RWF/ }).click();
  await p.getByRole('heading', { name: 'Paid' }).waitFor({ timeout: 150000 }); // MoMo: waits for the PIN
  log('     receipt:', (await p.locator('main').innerText()).replace(/\s+/g, ' ').slice(0, 200));
});
await step('16 bills list shows it paid', p, async () => {
  await p.goto(APP + '/history');
  await p.locator('main li, main a').first().waitFor({ timeout: 30000 });
  log('     bills page:', (await p.locator('main').innerText()).replace(/\s+/g, ' ').slice(0, 160));
});
await step('17 messages show the confirmation', p, async () => {
  await p.goto(APP + '/messages');
  await p.getByText(/Checked and confirmed/).first().waitFor({ timeout: 30000 });
});
await step('18 a new reading waits for the next period', p, async () => {
  await p.goto(APP + '/submit/camera');
  await p.getByText(/next one opens|next reading from/).waitFor({ timeout: 30000 });
});

console.log('\n==== PROBLEMS (' + problems.length + ') ====');
for (const x of problems) console.log(' -', x);
await browser.close();
process.exit(problems.length ? 1 : 0);
