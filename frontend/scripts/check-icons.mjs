// Fails when the icons in the build are missing, malformed or not linked
// from index.html. favicon.ico is parsed (header, directory, each entry's
// image), not just matched on its first bytes.
// Run after `ng build`: node scripts/check-icons.mjs [build dir]
// (or on the sources: node scripts/check-icons.mjs public; the link check
// then reads src/index.html)
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const buildDir = process.argv[2] ?? 'dist/signal-forge/browser';
const ICO_SIZES = [16, 32, 48];
const APPLE_SIZE = 180;
// Small icons; a jump past these means something went wrong in generation.
const MAX_BYTES = { 'favicon.ico': 16 * 1024, 'favicon.svg': 2 * 1024, 'apple-touch-icon.png': 32 * 1024 };
const PNG_SIGNATURE = '89504e470d0a1a0a';

const errors = [];

function read(name) {
  const path = join(buildDir, name);
  if (!existsSync(path)) {
    errors.push(`${path} not found; it belongs in frontend/public/`);
    return undefined;
  }
  const data = readFileSync(path);
  if (data.length > MAX_BYTES[name]) errors.push(`${name} is ${data.length} bytes, over ${MAX_BYTES[name]}`);
  return data;
}

/** Width and height of a PNG from its IHDR chunk, or undefined if it is not a PNG. */
function pngSize(buf) {
  if (buf.length < 24 || buf.subarray(0, 8).toString('hex') !== PNG_SIGNATURE) return undefined;
  if (buf.subarray(12, 16).toString('latin1') !== 'IHDR') return undefined;
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

/** Width and height of an ICO entry's image: PNG, or a BMP DIB (height doubled for the mask). */
function entryImageSize(img) {
  const png = pngSize(img);
  if (png) return png;
  if (img.length >= 40 && img.readUInt32LE(0) === 40) {
    return { width: img.readInt32LE(4), height: img.readInt32LE(8) / 2 };
  }
  return undefined;
}

function checkIco(buf) {
  if (buf.length < 6) return errors.push('favicon.ico is shorter than its header');
  if (buf.readUInt16LE(0) !== 0 || buf.readUInt16LE(2) !== 1) {
    return errors.push('favicon.ico header is not an icon (reserved 0, type 1)');
  }
  const count = buf.readUInt16LE(4);
  if (buf.length < 6 + 16 * count) return errors.push('favicon.ico directory is truncated');
  const found = [];
  const ranges = [];
  for (let i = 0; i < count; i++) {
    const at = 6 + 16 * i;
    const width = buf.readUInt8(at) || 256;
    const height = buf.readUInt8(at + 1) || 256;
    const length = buf.readUInt32LE(at + 8);
    const offset = buf.readUInt32LE(at + 12);
    if (width !== height) errors.push(`favicon.ico entry ${i} is not square (${width}x${height})`);
    if (offset < 6 + 16 * count || offset + length > buf.length) {
      errors.push(`favicon.ico entry ${i} (${width}px) points outside the file`);
      continue;
    }
    ranges.push([offset, offset + length]);
    const size = entryImageSize(buf.subarray(offset, offset + length));
    if (!size) errors.push(`favicon.ico entry ${i} (${width}px) is neither a PNG nor a BMP`);
    else if (size.width !== width || size.height !== height) {
      errors.push(`favicon.ico entry ${i} says ${width}x${height}, its image is ${size.width}x${size.height}`);
    }
    found.push(width);
  }
  ranges.sort((a, b) => a[0] - b[0]);
  for (let i = 1; i < ranges.length; i++) {
    if (ranges[i][0] < ranges[i - 1][1]) errors.push('favicon.ico entries overlap');
  }
  for (const size of ICO_SIZES) {
    if (!found.includes(size)) errors.push(`favicon.ico has no ${size}x${size} entry`);
  }
}

function checkSvg(buf) {
  const text = buf.toString('utf8');
  if (!/^\s*<svg\b[^>]*\bxmlns="http:\/\/www\.w3\.org\/2000\/svg"/.test(text)) {
    errors.push('favicon.svg does not start with an <svg> element in the SVG namespace');
  }
  if (!/\bviewBox="/.test(text)) errors.push('favicon.svg has no viewBox');
  // Served same-origin under the SPA CSP; keep it a static picture.
  if (/<script\b|<foreignObject\b|\bon[a-z]+\s*=|href\s*=/i.test(text)) {
    errors.push('favicon.svg must not contain scripts, event handlers, foreignObject or links');
  }
}

function checkApple(buf) {
  const size = pngSize(buf);
  if (!size) errors.push('apple-touch-icon.png is not a PNG');
  else if (size.width !== APPLE_SIZE || size.height !== APPLE_SIZE) {
    errors.push(`apple-touch-icon.png is ${size.width}x${size.height}, expected ${APPLE_SIZE}x${APPLE_SIZE}`);
  }
}

function checkLinks() {
  const indexPath = existsSync(join(buildDir, 'index.html')) ? join(buildDir, 'index.html') : 'src/index.html';
  if (!existsSync(indexPath)) return errors.push(`${indexPath} not found`);
  const links = readFileSync(indexPath, 'utf8').match(/<link\b[^>]*>/gi) ?? [];
  const attr = (tag, name) => tag.match(new RegExp(`\\b${name}\\s*=\\s*"([^"]*)"`, 'i'))?.[1];
  const has = (rel, href, type) => links.some(tag =>
    attr(tag, 'rel') === rel && attr(tag, 'href') === href && (type === undefined || attr(tag, 'type') === type));
  if (!has('icon', 'favicon.ico')) errors.push(`${indexPath}: no <link rel="icon" href="favicon.ico">`);
  if (!has('icon', 'favicon.svg', 'image/svg+xml')) {
    errors.push(`${indexPath}: no <link rel="icon" type="image/svg+xml" href="favicon.svg">`);
  }
  if (!has('apple-touch-icon', 'apple-touch-icon.png')) {
    errors.push(`${indexPath}: no <link rel="apple-touch-icon" href="apple-touch-icon.png">`);
  }
}

const icoFile = read('favicon.ico');
if (icoFile) checkIco(icoFile);
const svgFile = read('favicon.svg');
if (svgFile) checkSvg(svgFile);
const appleFile = read('apple-touch-icon.png');
if (appleFile) checkApple(appleFile);
checkLinks();

if (errors.length) {
  console.error('check-icons failed:\n- ' + errors.join('\n- '));
  process.exit(1);
}
console.log(`check-icons: favicon.ico (${ICO_SIZES.join(', ')}), favicon.svg, apple-touch-icon.png and links OK in ${buildDir}`);
