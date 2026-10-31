// End-to-end in a real browser, as real people use it:
//   household signs in, reads the meter (real photo), checks it (check-first), is held for
//   checking, cannot send another; officer accepts it; household sees the bill, pays it, gets the
//   confirmation. With a second phone: that household is rejected, and sees the reason.
//
//   node live_e2e.mjs <app url> <meter photo> <staff password> <demo phone> [chrome path]
//
//   E2E_STAFF_USER   the staff username (default dushime)
//   E2E_READING      8 digits to type on the confirm page (default: what the reader read)
//   E2E_REJECT_PHONE a second demo household, for the reject path
//   E2E_NO_MODELS=1  the models are not installed, so the officer has no photo to see
//   E2E_ALLOW_LIVE=1 needed for anything but localhost: this script changes data
//
// Use a demo household that has no reading waiting and none in the last 25 days. Prints each step
// and every problem (failed requests, page errors, console errors); screenshots go to ./out/.
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';
import { homedir } from 'node:os';

const [APP, PHOTO, STAFF_PW, PHONE, CHROME] = process.argv.slice(2);
const TX = 'E2E' + Date.now(); // a made-up MoMo transaction ID; staff confirm it below
if (!APP || !PHOTO || !STAFF_PW || !PHONE) {
  console.error('usage: node live_e2e.mjs <app url> <meter photo> <staff password> <demo phone> [chrome path]');
  process.exit(2);
}
if (!/^https?:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/.test(APP) && process.env.E2E_ALLOW_LIVE !== '1') {
  console.error('Refusing to run against ' + APP + ': this script changes data. Set E2E_ALLOW_LIVE=1 only if you mean it.');
  process.exit(2);
}
const STAFF_USER = process.env.E2E_STAFF_USER || 'dushime';
const READING = process.env.E2E_READING;
const REJECT_PHONE = process.env.E2E_REJECT_PHONE;
const householdName = (phone) => 'DEMO Household ' + phone.replace(/\D/g, '').slice(-3);
const HOUSEHOLD = householdName(PHONE);
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
/** Type a reading on the meter counter (needed when the reader could not read the photo). */
async function typeReading(page, digits) {
  await page.locator('main input').first().focus(); // one real input lies over the wheels
  await page.keyboard.type(digits);
}

/** "Confirm reading" checks first. A reading that needs review offers the two choices: send it. */
async function confirmAndSend(page) {
  log('     confirm page says:', (await page.locator('main').innerText()).replace(/\s+/g, ' ').slice(0, 160));
  await page.getByRole('button', { name: 'Confirm reading' }).click();
  const review = page.getByRole('button', { name: 'Send for review' });
  const done = page.waitForURL(/submit\/held|\/bill/, { timeout: 60000 });
  await Promise.race([done, review.waitFor({ timeout: 60000 })]);
  if (await review.isVisible().catch(() => false)) {
    log('     check says:', (await page.getByRole('status').first().innerText()).replace(/\s+/g, ' ').slice(0, 160));
    if (!(await page.getByRole('button', { name: 'Check the digits' }).isVisible())) throw new Error('no Check the digits choice');
    await review.click();
  }
  await done;
  log('     went to', new URL(page.url()).pathname);
}

async function signIn(page, phone) {
  await page.goto(APP + '/sign-in');
  await page.getByLabel('Your phone number').fill(phone);
  await page.getByRole('button', { name: 'Send me a code' }).click();
  await page.getByText('Demo account', { exact: true }).waitFor({ timeout: 30000 });
  const code = ((await page.locator('main').innerText()).match(/Your code is\s*(\d{6})/) || [])[1];
  if (!code) throw new Error('no demo code on screen');
  await page.getByLabel('6-digit code').fill(code);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL(/\/home/, { timeout: 30000 });
  await page.getByText('Your meter', { exact: true }).waitFor({ timeout: 30000 });
}

async function readMeter(page) {
  await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Read' }).click();
  await page.waitForURL(/submit\/camera/);
  await page.locator('video').waitFor({ timeout: 30000 });
  await page.locator('input[type=file]').setInputFiles(PHOTO);
  for (let i = 0; i < 60 && !/submit\/confirm/.test(page.url()); i++) {
    const anyway = page.getByRole('button', { name: 'Use this photo anyway' });
    const type = page.getByRole('button', { name: 'Type the numbers instead' });
    if (await anyway.isVisible().catch(() => false)) await anyway.click();
    else if (await page.getByText('We could not read the numbers').isVisible().catch(() => false) && await type.isVisible()) await type.click();
    await page.waitForTimeout(1000);
  }
  if (!/submit\/confirm/.test(page.url())) throw new Error('never reached the confirm page');
  if (READING) await typeReading(page, READING);
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
await step('02 sign in with code', p, () => signIn(p, PHONE));
await step('03-04 read the meter', p, () => readMeter(p));
await step('05 check first, then send', p, () => confirmAndSend(p));
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
  await s.getByLabel('Username').fill(STAFF_USER);
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
  if (process.env.E2E_NO_MODELS === '1') log('     no models here: no photo is kept, not checked');
  else {
    await s.getByRole('img', { name: /Meter photo sent by/ }).waitFor({ timeout: 20000 });
    log('     photo shown to the officer; reader read:', /Photo reader read/.test(pane));
  }
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
await step('11b households upload: preview only, saves nothing', s, async () => {
  await s.getByRole('button', { name: 'Upload list' }).click();
  await s.getByLabel('Choose a CSV file').setInputFiles({ name: 'check.csv', mimeType: 'text/csv',
    buffer: Buffer.from('name,phone,meter_number,sector\nPreview Check,0788 000 000,E2E-PREVIEW-1,Remera\n') });
  await s.getByText('Preview of check.csv').waitFor({ timeout: 30000 });
  log('     preview:', (await s.locator('#staff-main ul').filter({ hasText: 'new' }).first().innerText()).replace(/\s+/g, ' '));
  await s.getByRole('button', { name: 'Cancel' }).click();
});
await step('12 sent SMS page lists messages', s, async () => {
  await s.goto(APP + '/staff/sms');
  await s.locator('#staff-main table, #staff-main section p').first().waitFor({ timeout: 30000 });
  log('     sms rows:', await s.locator('tbody tr').count());
});
await step('13 staff accounts page', s, async () => {
  await s.goto(APP + '/staff/accounts');
  await s.getByText(STAFF_USER).first().waitFor({ timeout: 30000 });
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
  await p.getByRole('heading', { name: 'Pay with MoMo Pay' }).waitFor({ timeout: 60000 });
  const dial = p.locator('main a[href^="tel:"]');
  log('     code to dial:', (await dial.count()) ? (await dial.first().innerText()).trim() : 'none (MOMO_PAY_CODE not set)');
  await p.getByLabel('2. Enter the transaction ID').fill(TX);
  await p.getByRole('button', { name: 'Send for checking' }).click();
  await p.getByRole('heading', { name: "We're checking your payment" }).waitFor({ timeout: 30000 });
});
await step('15b staff confirm the payment', s, async () => {
  await s.goto(APP + '/staff/payments');
  const row = s.locator('#staff-main tr', { hasText: TX });
  await row.getByRole('button', { name: 'Found: confirm' }).click();
  await s.getByText(/The bill is paid/).waitFor({ timeout: 30000 });
});
await step('15c household sees it paid', p, async () => {
  await p.reload();
  await p.getByRole('heading', { name: 'Paid' }).waitFor({ timeout: 60000 });
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
await step('17b delete a message', p, async () => {
  const before = await p.getByRole('button', { name: 'Delete' }).count();
  if (!before) throw new Error('no message could be deleted');
  await p.getByRole('button', { name: 'Delete' }).first().click();
  await p.waitForFunction((n) => [...document.querySelectorAll('main button')]
    .filter((b) => b.textContent.trim() === 'Delete').length < n, before, { timeout: 30000 });
});
await step('18 a new reading waits for the next period', p, async () => {
  await p.goto(APP + '/submit/camera');
  await p.getByText(/next one opens|next reading from/).waitFor({ timeout: 30000 });
});

// ---- A second household: rejected, with the reason ----------------------------
if (REJECT_PHONE) {
  const name = householdName(REJECT_PHONE);
  const rh = await browser.newContext({ viewport: { width: 390, height: 844 }, permissions: ['camera', 'geolocation'], geolocation: { latitude: -1.95, longitude: 30.07, accuracy: 15 } });
  await rh.addInitScript(() => localStorage.setItem('wasac.locale', 'en'));
  const q = await rh.newPage(); watch(q, 'household 2');
  await step('19 second household sends a reading', q, async () => {
    await signIn(q, REJECT_PHONE);
    await readMeter(q);
    await confirmAndSend(q);
  });
  await step('20 officer rejects it, with a reason', s, async () => {
    await s.goto(APP + '/staff/review');
    const item = s.getByRole('button', { name: new RegExp(name) }).first();
    await item.waitFor({ timeout: 30000 });
    await item.click();
    await s.getByRole('button', { name: 'Reject, ask for a new photo' }).click();
    await s.getByLabel('Why are you rejecting this reading?').selectOption('digits');
    await s.getByRole('button', { name: 'Reject the reading' }).click();
    await s.waitForTimeout(8000); // 5 s undo window, then the request
  });
  await step('21 household sees why', q, async () => {
    await q.goto(APP + '/messages');
    await q.getByText(/The numbers did not match the photo/).first().waitFor({ timeout: 30000 });
  });
  await step('22 activity keeps the reason', s, async () => {
    await s.goto(APP + '/staff/activity');
    await s.getByText(/do not match the photo/).first().waitFor({ timeout: 30000 });
  });
}

console.log('\n==== PROBLEMS (' + problems.length + ') ====');
for (const x of problems) console.log(' -', x);
await browser.close();
process.exit(problems.length ? 1 : 0);
