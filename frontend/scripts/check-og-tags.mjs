// Fails when the built index.html lacks the link-preview tags, or when the
// preview image is missing from the build. Link-preview crawlers (LinkedIn,
// Slack, X) do not run JavaScript, so the tags must be in the static HTML.
// Run after `ng build`: node scripts/check-og-tags.mjs [build dir]
import { existsSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const ORIGIN = 'https://signalforge-api-ah1q.onrender.com';
const IMAGE = 'og-image.png';
const buildDir = process.argv[2] ?? 'dist/signal-forge/browser';

const REQUIRED = [
  ['name', 'description'],
  ['property', 'og:type'],
  ['property', 'og:title'],
  ['property', 'og:description'],
  ['property', 'og:url'],
  ['property', 'og:image'],
  ['property', 'og:image:width'],
  ['property', 'og:image:height'],
  ['property', 'og:image:alt'],
  ['name', 'twitter:card'],
  ['name', 'twitter:title'],
  ['name', 'twitter:description'],
  ['name', 'twitter:image'],
];

const errors = [];
const indexPath = join(buildDir, 'index.html');
if (!existsSync(indexPath)) {
  console.error(`check-og-tags: ${indexPath} not found; run ng build first`);
  process.exit(1);
}
const html = readFileSync(indexPath, 'utf8');

/** The content of the first meta tag with attr="key", in either attribute order. */
function metaContent(attr, key) {
  for (const tag of html.match(/<meta\b[^>]*>/gi) ?? []) {
    const keyMatch = tag.match(new RegExp(`\\b${attr}\\s*=\\s*["']?([^"'\\s>]+)`, 'i'));
    if (keyMatch?.[1] !== key) continue;
    const content = tag.match(/\bcontent\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i);
    return content ? (content[1] ?? content[2] ?? content[3]) : '';
  }
  return undefined;
}

const values = {};
for (const [attr, key] of REQUIRED) {
  const value = metaContent(attr, key);
  if (value === undefined) errors.push(`missing <meta ${attr}="${key}">`);
  else if (!value.trim()) errors.push(`empty content for ${key}`);
  else values[key] = value;
}

const imageUrl = `${ORIGIN}/${IMAGE}`;
for (const key of ['og:image', 'twitter:image']) {
  if (values[key] && values[key] !== imageUrl) errors.push(`${key} is ${values[key]}, expected ${imageUrl}`);
}
if (values['og:url'] && !values['og:url'].startsWith(`${ORIGIN}/`)) {
  errors.push(`og:url must start with ${ORIGIN}/`);
}
if (values['twitter:card'] && values['twitter:card'] !== 'summary_large_image') {
  errors.push('twitter:card must be summary_large_image');
}
for (const key of ['og:image:width', 'og:image:height']) {
  if (values[key] && !/^[1-9]\d*$/.test(values[key])) errors.push(`${key} must be a positive integer`);
}

const imagePath = join(buildDir, IMAGE);
if (!existsSync(imagePath)) {
  errors.push(`${imagePath} not found; it belongs in frontend/public/`);
} else {
  // LinkedIn rejects images over 5 MB.
  if (statSync(imagePath).size > 5 * 1024 * 1024) errors.push(`${IMAGE} is over 5 MB`);
  const png = readFileSync(imagePath);
  const signature = '89504e470d0a1a0a';
  if (png.subarray(0, 8).toString('hex') !== signature) {
    errors.push(`${IMAGE} is not a PNG`);
  } else {
    // IHDR width and height, big-endian, at bytes 16-23.
    const width = png.readUInt32BE(16);
    const height = png.readUInt32BE(20);
    if (values['og:image:width'] && Number(values['og:image:width']) !== width) {
      errors.push(`og:image:width is ${values['og:image:width']}, the image is ${width} wide`);
    }
    if (values['og:image:height'] && Number(values['og:image:height']) !== height) {
      errors.push(`og:image:height is ${values['og:image:height']}, the image is ${height} high`);
    }
  }
}

if (errors.length) {
  console.error('check-og-tags failed:\n- ' + errors.join('\n- '));
  process.exit(1);
}
console.log(`check-og-tags: ${REQUIRED.length} tags and ${IMAGE} OK in ${buildDir}`);
