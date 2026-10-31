// Gemeinsame Helfer für tutorial/build.mjs, video/render.mjs und video/capture.mjs.
//
// Keine neuen Downloads: Playwright, qrcode, jsQR und pngjs werden aus vorhandenen node_modules geladen –
// zuerst aus dem eigenen Ordner, dann aus marketing/flyer (Flyer-Werkzeug) und daftar/web (Web-Projekt).

import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const SHARED = dirname(fileURLToPath(import.meta.url));
export const MARKETING = resolve(SHARED, '..');
export const DAFTAR = resolve(MARKETING, '..');

const SEARCH = [
  join(MARKETING, 'tutorial', 'node_modules'),
  join(MARKETING, 'video', 'node_modules'),
  join(MARKETING, 'flyer', 'node_modules'),
  join(DAFTAR, 'web', 'node_modules'),
];

/** `require` eines Pakets aus der ersten node_modules-Liste, die es enthält. */
export function need(name) {
  for (const dir of SEARCH) {
    if (existsSync(join(dir, name, 'package.json'))) return createRequire(join(dir, 'noop.js'))(name);
  }
  throw new Error(`Paket "${name}" nicht gefunden in:\n  ${SEARCH.join('\n  ')}\n(npm install im Flyer-Ordner oder in daftar/web)`);
}

export const fileUrl = (path) => pathToFileURL(path).href;
export const sha1 = (path) => createHash('sha1').update(readFileSync(path)).digest('hex');

/** QR-Code als Vektor-SVG (gleiches Verfahren wie flyer/build.mjs), Ruhezone 4 Module. */
export function qrSvg(text, { ecl = 'Q', version, color = '#134e4a', background = '#fff', margin = 4 } = {}) {
  const QRCode = need('qrcode');
  const qr = QRCode.create(text, { errorCorrectionLevel: ecl, version });
  const n = qr.modules.size;
  const d = qr.modules.data;
  const total = n + 2 * margin;
  let path = '';
  for (let y = 0; y < n; y++) {
    let x = 0;
    while (x < n) {
      if (!d[y * n + x]) { x++; continue; }
      const s = x;
      while (x < n && d[y * n + x]) x++;
      path += `M${s + margin} ${y + margin}h${x - s}v1h-${x - s}z`;
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${total} ${total}" shape-rendering="crispEdges">` +
    `<title>${text}</title><rect width="${total}" height="${total}" fill="${background}"/><path fill="${color}" d="${path}"/></svg>\n`;
}

/** QR-Code in einem PNG-Puffer lesen (jsQR); null, wenn nichts lesbar ist. */
export function readQr(pngBuffer) {
  const jsQR = need('jsqr');
  const { PNG } = need('pngjs');
  const png = PNG.sync.read(pngBuffer);
  const res = jsQR(new Uint8ClampedArray(png.data), png.width, png.height);
  return res ? res.data : null;
}

/** Externe Anfragen hart blocken (Druck/Video laufen nur mit lokalen Dateien). */
export async function offlineOnly(page, log = console.error) {
  await page.route(/^https?:/, (r) => { log('Externe Anfrage blockiert:', r.request().url()); return r.abort(); });
}

export function args(argv = process.argv.slice(2)) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) { out._.push(a); continue; }
    const [k, v] = a.slice(2).split('=');
    if (v !== undefined) out[k] = v;
    else if (argv[i + 1] && !argv[i + 1].startsWith('--')) out[k] = argv[++i];
    else out[k] = true;
  }
  return out;
}

export const kb = (bytes) => `${(bytes / 1024).toFixed(0)} KB`;
export const mb = (bytes) => `${(bytes / 1024 / 1024).toFixed(2)} MB`;
