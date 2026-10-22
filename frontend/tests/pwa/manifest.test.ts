import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const PUBLIC = resolve(__dirname, '../../public');
const manifest = JSON.parse(readFileSync(resolve(PUBLIC, 'manifest.webmanifest'), 'utf8')) as {
  name: string;
  short_name: string;
  start_url: string;
  scope: string;
  display: string;
  icons: { src: string; sizes: string; type: string; purpose: string }[];
  shortcuts: { url: string }[];
};

/** Width and height from a PNG's header. */
function pngSize(file: string): string {
  const bytes = readFileSync(resolve(PUBLIC, file.replace(/^\//, '')));
  return `${bytes.readUInt32BE(16)}x${bytes.readUInt32BE(20)}`;
}

describe('the web app manifest', () => {
  it('when a phone installs the app, should have the fields browsers need', () => {
    expect(manifest.name).toBeTruthy();
    expect(manifest.short_name.length).toBeLessThanOrEqual(12); // fits under the home-screen icon
    expect(manifest.display).toBe('standalone');
    expect(manifest.start_url.startsWith(manifest.scope)).toBe(true);
  });

  it('when listing icons, should point at files of the stated size, with a maskable one', () => {
    for (const icon of manifest.icons) {
      expect(existsSync(resolve(PUBLIC, icon.src.replace(/^\//, '')))).toBe(true);
      if (icon.type === 'image/png') expect(pngSize(icon.src)).toBe(icon.sizes);
    }
    expect(manifest.icons.some((i) => i.purpose === 'maskable' && i.sizes === '512x512')).toBe(true);
    expect(manifest.icons.some((i) => i.sizes === '192x192')).toBe(true);
  });

  it('when adding shortcuts, should only point inside the app', () => {
    for (const s of manifest.shortcuts) expect(s.url.startsWith('/')).toBe(true);
  });
});

describe('the service worker', () => {
  const sw = readFileSync(resolve(PUBLIC, 'sw.js'), 'utf8');

  it('when it installs, should only pre-save files that exist', () => {
    const list = /const PRECACHE = \[([^\]]*)\]/.exec(sw)?.[1] ?? '';
    const files = [...list.matchAll(/'([^']+)'/g)].map((m) => m[1] ?? '');
    expect(files.length).toBeGreaterThan(0);
    for (const f of files) if (f !== '/') expect(existsSync(resolve(PUBLIC, f.replace(/^\//, '')))).toBe(true);
  });

  it('when the app asks for data, should never store it (bills, readings, sign-in)', () => {
    for (const path of ['/auth', '/household', '/customers', '/confirm-reading', '/submit-photo', '/api/']) {
      expect(sw).toContain(`'${path}'`);
    }
    expect(sw).toMatch(/url\.origin !== self\.location\.origin\) return/);
  });
});
