// Rebuilds the raster icons from public/favicon.svg, the source of truth:
//   public/favicon.ico           16, 32 and 48 px, PNG entries, transparent corners
//   public/apple-touch-icon.png  180 px, opaque (iOS fills transparency with black)
//
// Run by hand after changing favicon.svg, then commit the results:
//   cd frontend && node scripts/generate-icons.mjs && node scripts/check-icons.mjs
//
// Not part of the build or CI: the generated files are committed. It uses
// the Chromium that Playwright already installs for the e2e tests
// (npx playwright install chromium); no image library is needed.
import { chromium } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const publicDir = resolve(dirname(fileURLToPath(import.meta.url)), '../public');
const svg = readFileSync(resolve(publicDir, 'favicon.svg'), 'utf8');
// The tile colour in favicon.svg; the apple icon's square corners use it too.
const TILE = '#0b0f14';
const ICO_SIZES = [16, 32, 48];
const APPLE_SIZE = 180;

/** One PNG of the SVG at size x size; transparent unless a background is given. */
async function render(page, size, background) {
  await page.setViewportSize({ width: size, height: size });
  const src = `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;
  await page.setContent(
    `<html><body style="margin:0;background:${background ?? 'transparent'}">` +
    `<img src="${src}" width="${size}" height="${size}" style="display:block"></body></html>`,
  );
  await page.locator('img').evaluate(img => img.decode());
  return page.screenshot({ omitBackground: !background, clip: { x: 0, y: 0, width: size, height: size } });
}

/** An ICO file with one PNG entry per size (supported by every current browser). */
function ico(images) {
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);             // reserved
  header.writeUInt16LE(1, 2);             // type: icon
  header.writeUInt16LE(images.length, 4);
  const entries = [];
  let offset = 6 + 16 * images.length;
  for (const { size, png } of images) {
    const entry = Buffer.alloc(16);
    entry.writeUInt8(size >= 256 ? 0 : size, 0);  // width (0 means 256)
    entry.writeUInt8(size >= 256 ? 0 : size, 1);  // height
    entry.writeUInt8(0, 2);                        // no palette
    entry.writeUInt8(0, 3);                        // reserved
    entry.writeUInt16LE(1, 4);                     // colour planes
    entry.writeUInt16LE(32, 6);                    // bits per pixel
    entry.writeUInt32LE(png.length, 8);
    entry.writeUInt32LE(offset, 12);
    entries.push(entry);
    offset += png.length;
  }
  return Buffer.concat([header, ...entries, ...images.map(i => i.png)]);
}

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  const images = [];
  for (const size of ICO_SIZES) images.push({ size, png: await render(page, size) });
  writeFileSync(resolve(publicDir, 'favicon.ico'), ico(images));
  writeFileSync(resolve(publicDir, 'apple-touch-icon.png'), await render(page, APPLE_SIZE, TILE));
} finally {
  await browser.close();
}
console.log(`generate-icons: favicon.ico (${ICO_SIZES.join(', ')}) and apple-touch-icon.png (${APPLE_SIZE}) written`);
