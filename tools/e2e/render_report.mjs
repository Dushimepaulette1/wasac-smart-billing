// Render the report from its version-controlled HTML. Run after installing Playwright Chromium.
import { chromium } from 'playwright-core';
import { fileURLToPath } from 'node:url';

const source = new URL('../../docs/report/technical_report.html', import.meta.url);
const target = fileURLToPath(new URL('../../docs/report/Mubazi_Technical_Report.pdf', import.meta.url));
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
try {
  const page = await browser.newPage();
  await page.goto(source.href, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({ path: target, preferCSSPageSize: true, printBackground: true });
  console.log(`Report written to ${target}`);
} finally {
  await browser.close();
}
