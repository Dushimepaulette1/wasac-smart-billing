// Compatibility and page speed on a local build. Writes tools/e2e/out/compatibility.md.
//   node compat_check.mjs http://localhost:3000
// Each browser engine at phone and desktop sizes: the page loads, shows its heading, has no sideways
// scroll and no page errors. Chromium also runs with simulated slow 3G and a 4x slower CPU.
import { chromium, firefox, webkit } from 'playwright-core';
import { mkdirSync, writeFileSync } from 'node:fs';

const APP = process.argv[2] || 'http://localhost:3000';
if (!/^https?:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/.test(APP)) {
  console.error('Local builds only.');
  process.exit(2);
}
const ENGINES = { chromium, firefox, webkit };
const SIZES = [['small phone', 360, 640], ['phone', 390, 844], ['tablet', 768, 1024], ['laptop', 1366, 768]];
const PAGES = ['/', '/sign-in', '/staff/sign-in'];
const NETWORKS = {
  'no limit': null,
  'slow 3G, 4x slower CPU': { latency: 400, down: (400 * 1024) / 8, up: (400 * 1024) / 8, cpu: 4 },
  'fast 3G, 4x slower CPU': { latency: 150, down: (1600 * 1024) / 8, up: (750 * 1024) / 8, cpu: 4 },
};

const rows = [];
for (const [name, engine] of Object.entries(ENGINES)) {
  let browser;
  try { browser = await engine.launch(); } catch (e) {
    rows.push(`| ${name} | all | all | not run: ${String(e).split('\n')[0].slice(0, 70)} |`);
    continue;
  }
  for (const [label, width, height] of SIZES) {
    const context = await browser.newContext({ viewport: { width, height } });
    await context.addInitScript(() => localStorage.setItem('wasac.locale', 'en'));
    for (const path of PAGES) {
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', (e) => errors.push(e.message));
      const started = Date.now();
      await page.goto(APP + path, { waitUntil: 'load' });
      await page.getByRole('heading').first().waitFor({ timeout: 15000 });
      const ms = Date.now() - started;
      const sideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      const ok = !sideways && errors.length === 0;
      rows.push(`| ${name} ${browser.version()} | ${label} (${width}x${height}) | ${path} | ${ok ? 'pass' : `FAIL ${sideways ? 'sideways scroll ' : ''}${errors[0] ?? ''}`} | ${ms} |`);
      await page.close();
    }
    await context.close();
  }
  await browser.close();
}

const speed = [];
const browser = await chromium.launch();
for (const [label, net] of Object.entries(NETWORKS)) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });
  if (net) {
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: net.latency, downloadThroughput: net.down, uploadThroughput: net.up });
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: net.cpu });
  }
  await page.goto(APP + '/', { waitUntil: 'load', timeout: 120000 });
  await page.getByRole('heading').first().waitFor({ timeout: 60000 });
  await page.waitForTimeout(1000);
  const m = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const paint = performance.getEntriesByName('first-contentful-paint')[0];
    const bytes = performance.getEntriesByType('resource').reduce((sum, r) => sum + (r.transferSize || 0), nav.transferSize || 0);
    return { fcp: Math.round(paint?.startTime ?? 0), load: Math.round(nav.loadEventEnd), kb: Math.round(bytes / 1024) };
  });
  speed.push(`| ${label} | ${m.fcp} | ${m.load} | ${m.kb} |`);
  await context.close();
}
await browser.close();

mkdirSync(new URL('./out/', import.meta.url), { recursive: true });
writeFileSync(new URL('./out/compatibility.md', import.meta.url), `# Compatibility and page speed

Made by \`tools/e2e/compat_check.mjs\` on ${new Date().toISOString().slice(0, 10)} against a local build. Browser engines
and device sizes are real engines at simulated sizes, and the slow networks and CPU are simulated, not real phones.

## Browsers and screen sizes

| Browser | Size | Page | Result | Load (ms) |
|---|---|---|---|---|
${rows.join('\n')}

## Landing page speed, phone size, no cache

| Conditions | First paint (ms) | Page loaded (ms) | Downloaded (KB) |
|---|---|---|---|
${speed.join('\n')}
`);
console.log(rows.join('\n') + '\n' + speed.join('\n'));
