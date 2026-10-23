// Render the app icons (frontend/icons/*.svg) to the PNGs in frontend/public/, with headless
// Chromium (playwright-core). Usage, from the repository root:
//   node tools/e2e/render_icons.mjs <path to chrome or chrome-headless-shell>
import { chromium } from 'playwright-core';
import { copyFileSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'frontend');
const jobs = [
  ['icon.svg', 'icon-192.png', 192],
  ['icon.svg', 'icon-512.png', 512],
  ['icon-maskable.svg', 'icon-maskable-512.png', 512],
  ['icon-full.svg', 'apple-touch-icon.png', 180],
  ['favicon.svg', 'favicon-32.png', 32],
];

const browser = await chromium.launch({ executablePath: process.argv[2] });
const page = await browser.newPage();
for (const [source, target, size] of jobs) {
  const svg = readFileSync(join(root, 'icons', source), 'utf8').replace(/width="\d+" height="\d+"/, `width="${size}" height="${size}"`);
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
  await page.screenshot({ path: join(root, 'public', target), omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
  console.log('rendered', target);
}
await browser.close();
copyFileSync(join(root, 'icons', 'favicon.svg'), join(root, 'public', 'favicon.svg'));
console.log('copied favicon.svg');
