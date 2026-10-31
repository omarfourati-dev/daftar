// Platzhalter-Screenshots: einfarbige Fläche in der echten Pixelgröße, beschriftet mit Dateiname, Ansicht und dem
// Zustand, der später zu sehen sein muss. Echte Aufnahmen (capture.mjs) werden nie überschrieben – außer mit --force.
// placeholders.json im Zielordner merkt sich den SHA-1 jedes Platzhalters; so erkennt build.mjs bzw. render.mjs,
// welche Bilder noch Platzhalter sind.

import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { pixelSize } from './shots.mjs';
import { fileUrl, sha1, SHARED } from './lib.mjs';

const TONE = {
  desktop: { bg: '#d9f0ec', ink: '#134e4a', tag: '#0f766e' },
  mobile: { bg: '#fdecc8', ink: '#78350f', tag: '#b45309' },
  tv: { bg: '#1e293b', ink: '#e2e8f0', tag: '#f59e0b' },
};

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

function html(shot, lang, { width, height, css }) {
  const t = TONE[shot.view];
  const manual = shot.mode === 'manual';
  return `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="${fileUrl(join(SHARED, 'fonts.css'))}">
<style>
  html,body{margin:0}
  body{width:${css[0]}px;height:${css[1]}px;background:${t.bg};color:${t.ink};font-family:"Plex Arabic",sans-serif;
    display:flex;flex-direction:column;justify-content:center;gap:${Math.max(6, css[1] * 0.02)}px;padding:0 ${css[0] * 0.07}px;box-sizing:border-box;overflow:hidden}
  .tag{align-self:flex-start;background:${t.tag};color:#fff;font-weight:700;border-radius:999px;padding:2px 12px;font-size:${Math.max(11, css[0] / 60)}px;letter-spacing:.04em}
  .id{font-weight:700;font-size:${Math.max(16, css[0] / 22)}px;line-height:1.15}
  .state{font-size:${Math.max(11, css[0] / 52)}px;line-height:1.45;max-width:${css[0] * 0.86}px}
  .meta{font-size:${Math.max(10, css[0] / 75)}px;opacity:.75}
</style></head><body>
<span class="tag">${manual ? 'PLATZHALTER · VON HAND AUFNEHMEN' : 'PLATZHALTER · capture.mjs'}</span>
<div class="id">${esc(shot.id)}-${lang}.png</div>
<div class="state">${esc(shot.state)}</div>
<div class="meta">${esc(shot.view)} · ${esc(shot.crop)} · ${width} × ${height} px · Sprache ${lang.toUpperCase()}</div>
</body></html>`;
}

/** Erzeugt fehlende Platzhalter; gibt die Liste der neu geschriebenen Dateien zurück. */
export async function makePlaceholders(browser, { shots, dir, langs = ['fr', 'ar'], force = false }) {
  mkdirSync(dir, { recursive: true });
  const recordFile = join(dir, 'placeholders.json');
  const record = existsSync(recordFile) ? JSON.parse(readFileSync(recordFile, 'utf8')) : {};
  const written = [];
  for (const shot of shots) {
    for (const lang of langs) {
      const name = `${shot.id}-${lang}.png`;
      const file = join(dir, name);
      const isPlaceholder = existsSync(file) && record[name] === sha1(file);
      if (existsSync(file) && !isPlaceholder && !force) continue; // echte Aufnahme behalten
      if (existsSync(file) && isPlaceholder && !force) continue;
      const size = pixelSize(shot);
      const page = await browser.newPage({ viewport: { width: size.css[0], height: size.css[1] }, deviceScaleFactor: size.width / size.css[0] });
      await page.goto(fileUrl(join(SHARED, 'blank.html')));
      await page.setContent(html(shot, lang, size), { waitUntil: 'load' });
      await page.evaluate(async () => { await document.fonts.ready; });
      await page.screenshot({ path: file });
      await page.close();
      record[name] = sha1(file);
      written.push(name);
    }
  }
  writeFileSync(recordFile, JSON.stringify(record, null, 2) + '\n');
  return written;
}

/** Welche Dateien eines Ordners sind (noch) Platzhalter? */
export function placeholderStatus(dir, names) {
  const recordFile = join(dir, 'placeholders.json');
  const record = existsSync(recordFile) ? JSON.parse(readFileSync(recordFile, 'utf8')) : {};
  const missing = [];
  const placeholders = [];
  const real = [];
  for (const name of names) {
    const file = join(dir, name);
    if (!existsSync(file)) missing.push(name);
    else if (record[name] && record[name] === sha1(file)) placeholders.push(name);
    else real.push(name);
  }
  return { missing, placeholders, real };
}
