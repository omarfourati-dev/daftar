// Druckfertiger Flyer aus HTML/CSS: PDF mit Beschnitt + PNG-Vorschauen + Druckprüfungen.
//
// Aufruf (im Flyer-Ordner):  npm install  &&  node build.mjs
//
// Ablauf
//  1. QR-Codes aus flyer.config.json als Vektor-SVG erzeugen (qr/*.svg, Ruhezone 4 Module)
//  2. Aquarell-Illustrationen (SVG mit Filtern) einmalig in Druckauflösung rastern (img/*.png)
//  3. flyer.html in Chromium öffnen, Schriften abwarten, Druckregeln prüfen:
//     Schriftgröße >= 8 pt, nichts Wichtiges näher als 5 mm an der Schnittkante,
//     Textkontrast (WCAG AA), QR-Symbol >= 25 mm
//  4. page.pdf in Endformat + 3 mm Beschnitt, danach TrimBox/BleedBox setzen (pdf-lib)
//  5. PNG-Vorschau je Seite (beschnitten auf das Endformat)
//  6. Jeden QR-Code aus der gerenderten Vorschau mit jsQR dekodieren und mit der Soll-URL vergleichen
//
// Gleiche Datei in cabinet-bellaaj/flyer und daftar/marketing/flyer; der Unterschied steckt nur in flyer.config.json.

import { chromium } from 'playwright';
import QRCode from 'qrcode';
import { PDFDocument, PDFDict, PDFName, PDFArray } from 'pdf-lib';
import jsQR from 'jsqr';
import { PNG } from 'pngjs';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const cfg = JSON.parse(readFileSync(join(here, 'flyer.config.json'), 'utf8'));

const MM = 96 / 25.4;          // CSS-Pixel je mm
const PT_PER_MM = 72 / 25.4;   // PDF-Punkte je mm
const { trimW, trimH, bleed } = cfg.format;
const sheetW = trimW + 2 * bleed;
const sheetH = trimH + 2 * bleed;

// ---------- 1. QR-Codes als Vektor ----------
function qrSvg(text, { ecl, version, color, symbolMm, margin = 4 }) {
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
  const outerMm = Math.round((symbolMm * total / n) * 100) / 100;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${total} ${total}" width="${outerMm}mm" height="${outerMm}mm" shape-rendering="crispEdges">` +
    `<title>${text}</title><rect width="${total}" height="${total}" fill="#fff"/><path fill="${color}" d="${path}"/></svg>\n`;
  return { svg, version: qr.version, modules: n, outerMm };
}

const qrInfo = [];
for (const q of cfg.qr) {
  const r = qrSvg(q.url, q);
  writeFileSync(join(here, q.file), r.svg);
  qrInfo.push({ ...q, ...r });
  console.log(`QR ${q.file}: Version ${r.version}, ${r.modules} Module, Fehlerkorrektur ${q.ecl}, Symbol ${q.symbolMm} mm (mit Ruhezone ${r.outerMm} mm)`);
}

const browser = await chromium.launch();

// ---------- 2. Illustrationen rastern ----------
for (const il of cfg.raster ?? []) {
  const out = join(here, il.out);
  if (existsSync(out) && !process.argv.includes('--raster')) continue;
  const src = readFileSync(join(here, il.src), 'utf8');
  const [, , vw, vh] = src.match(/viewBox="([\d.\s-]+)"/)[1].trim().split(/\s+/).map(Number);
  const scale = il.widthPx / vw;
  const page = await browser.newPage({ viewport: { width: vw, height: vh }, deviceScaleFactor: scale });
  await page.goto(pathToFileURL(join(here, il.src)).href);
  await page.screenshot({ path: out, omitBackground: true });
  await page.close();
  console.log(`Illustration ${il.out}: ${Math.round(vw * scale)} x ${Math.round(vh * scale)} px`);
}

// ---------- 3. Seite laden und prüfen ----------
const page = await browser.newPage({
  viewport: { width: Math.ceil(sheetW * MM), height: Math.ceil(sheetH * MM) },
  deviceScaleFactor: cfg.preview.scale,
});
page.on('console', (m) => { if (m.type() === 'error') console.error('Browser:', m.text()); });
page.on('requestfailed', (r) => console.error('Nicht geladen:', r.url()));
await page.route(/^https?:/, (r) => { console.error('Externe Anfrage blockiert:', r.request().url()); return r.abort(); });
await page.goto(pathToFileURL(join(here, cfg.html)).href, { waitUntil: 'load' });
await page.evaluate(async () => { await document.fonts.ready; });

const report = await page.evaluate(({ MM, bleed, trimW, trimH, safeMm, minPt, qrSel }) => {
  const out = { fonts: [], small: [], unsafe: [], contrast: [], qr: [], overflow: [] };
  for (const f of document.fonts) if (f.status === 'loaded') out.fonts.push(`${f.family} ${f.weight}`);
  const lum = (c) => {
    const m = c.match(/[\d.]+/g).map(Number);
    const [r, g, b] = m.slice(0, 3).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const alpha = (c) => { const m = c.match(/[\d.]+/g); return m.length > 3 ? Number(m[3]) : 1; };
  const bgOf = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const bg = getComputedStyle(e).backgroundColor;
      if (bg && alpha(bg) > 0.5) return bg;
    }
    return 'rgb(255, 255, 255)';
  };
  for (const sheet of document.querySelectorAll('.sheet')) {
    const s = sheet.getBoundingClientRect();
    const trim = { l: s.left + bleed * MM, t: s.top + bleed * MM, r: s.left + (bleed + trimW) * MM, b: s.top + (bleed + trimH) * MM };
    const side = sheet.getAttribute('lang');
    const walker = document.createTreeWalker(sheet, NodeFilter.SHOW_TEXT);
    const seen = new Set();
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (!n.textContent.trim()) continue;
      const el = n.parentElement;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none') continue;
      const range = document.createRange(); range.selectNodeContents(n);
      for (const r of range.getClientRects()) {
        if (r.width < 1) continue;
        const d = Math.min(r.left - trim.l, r.top - trim.t, trim.r - r.right, trim.b - r.bottom) / MM;
        if (d < safeMm) out.unsafe.push(`${side}: "${n.textContent.trim().slice(0, 40)}" ${d.toFixed(1)} mm vom Rand`);
      }
      if (seen.has(el)) continue;
      seen.add(el);
      const pt = parseFloat(cs.fontSize) * 72 / 96;
      if (pt < minPt - 0.01) out.small.push(`${side}: "${n.textContent.trim().slice(0, 40)}" ${pt.toFixed(2)} pt`);
      const fg = cs.color; const bg = bgOf(el);
      const L1 = lum(fg), L2 = lum(bg);
      const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
      const large = pt >= 18 || (pt >= 14 && Number(cs.fontWeight) >= 600);
      out.contrast.push({ side, text: n.textContent.trim().slice(0, 30), ratio: Math.round(ratio * 100) / 100, need: large ? 3 : 4.5 });
      if (el.scrollWidth > el.clientWidth + 1 && cs.overflow !== 'visible') out.overflow.push(`${side}: ${el.className}`);
    }
    for (const img of sheet.querySelectorAll(qrSel)) {
      const r = img.getBoundingClientRect();
      const d = Math.min(r.left - trim.l, r.top - trim.t, trim.r - r.right, trim.b - r.bottom) / MM;
      out.qr.push({
        side, src: img.getAttribute('src'),
        xMm: (r.left - s.left) / MM, yMm: (r.top - s.top) / MM, wMm: r.width / MM, hMm: r.height / MM,
        sheetIndex: [...document.querySelectorAll('.sheet')].indexOf(sheet), edgeMm: d,
      });
    }
  }
  return out;
}, { MM, bleed, trimW, trimH, safeMm: cfg.checks.safeMm, minPt: cfg.checks.minPt, qrSel: 'img.qr' });

console.log('Schriften geladen:', [...new Set(report.fonts)].join(', '));
const problems = [];
if (report.small.length) problems.push('Zu kleine Schrift:\n  ' + report.small.join('\n  '));
if (report.unsafe.length) problems.push('Text im 5-mm-Randbereich:\n  ' + report.unsafe.join('\n  '));
if (report.overflow.length) problems.push('Überlauf:\n  ' + report.overflow.join('\n  '));
const weak = report.contrast.filter((c) => c.ratio < c.need);
if (weak.length) problems.push('Kontrast unter WCAG AA:\n  ' + weak.map((c) => `${c.side}: "${c.text}" ${c.ratio}:1 (nötig ${c.need}:1)`).join('\n  '));
const minRatio = Math.min(...report.contrast.map((c) => c.ratio));
console.log(`Kontrast: kleinster Wert ${minRatio}:1 bei ${report.contrast.length} Textelementen`);
for (const q of report.qr) {
  const info = qrInfo.find((i) => i.file === q.src);
  const symbolMm = q.wMm * info.modules / (info.modules + 8);
  console.log(`QR ${q.side} ${q.src}: ${q.wMm.toFixed(1)} mm gesamt, Symbol ${symbolMm.toFixed(1)} mm, ${q.edgeMm.toFixed(1)} mm vom Rand`);
  if (symbolMm < 25) problems.push(`QR ${q.src} (${q.side}) kleiner als 25 mm`);
  if (q.edgeMm < cfg.checks.safeMm) problems.push(`QR ${q.src} (${q.side}) im Randbereich`);
}

// ---------- 4. PDF mit Beschnitt ----------
// Chromium rundet die Papiergröße (auf 1/100 Zoll); darum wird etwas größer gedruckt (@page in flyer.css)
// und danach MediaBox/CropBox/BleedBox exakt auf Endformat + Beschnitt gesetzt, oben links verankert.
const pdfBytes = await page.pdf({ printBackground: true, preferCSSPageSize: true, margin: { top: 0, right: 0, bottom: 0, left: 0 }, tagged: true });
const doc = await PDFDocument.load(pdfBytes);
const b = bleed * PT_PER_MM;
const W = sheetW * PT_PER_MM;
const H = sheetH * PT_PER_MM;
for (const p of doc.getPages()) {
  const m = p.getMediaBox();
  if (m.width < W || m.height < H) problems.push(`PDF-Seite zu klein: ${m.width} x ${m.height} pt`);
  // Inhalt so verschieben, dass die obere linke Ecke des Bogens erhalten bleibt und die Boxen bei 0,0 beginnen
  const dx = -m.x;
  const dy = -(m.y + m.height - H);
  p.translateContent(dx, dy);
  const annots = p.node.Annots();
  if (annots) {
    for (let i = 0; i < annots.size(); i++) {
      const a = annots.lookup(i, PDFDict);
      const rect = a.lookup(PDFName.of('Rect'), PDFArray);
      const v = rect.asArray().map((n) => n.asNumber());
      a.set(PDFName.of('Rect'), doc.context.obj([v[0] + dx, v[1] + dy, v[2] + dx, v[3] + dy]));
    }
  }
  p.setMediaBox(0, 0, W, H);
  p.setCropBox(0, 0, W, H);
  p.setBleedBox(0, 0, W, H);
  p.setTrimBox(b, b, W - 2 * b, H - 2 * b);
}
doc.setTitle(cfg.title);
doc.setAuthor(cfg.author);
doc.setSubject(cfg.subject);
doc.setCreator('HTML/CSS + Playwright/Chromium (build.mjs)');
const pdfOut = join(here, cfg.pdf);
writeFileSync(pdfOut, await doc.save());
const pages = doc.getPages().map((p) => { const m = p.getMediaBox(); return `${(m.width / PT_PER_MM).toFixed(2)} x ${(m.height / PT_PER_MM).toFixed(2)} mm`; });
console.log(`PDF ${cfg.pdf}: ${pages.length} Seiten (${pages.join(', ')}), TrimBox ${trimW} x ${trimH} mm, Beschnitt ${bleed} mm`);
if (pages.length !== cfg.previews.length) problems.push(`PDF hat ${pages.length} Seiten statt ${cfg.previews.length}`);

// ---------- 5. Vorschauen (Endformat) ----------
const sheets = await page.$$('.sheet');
for (const [i, name] of cfg.previews.entries()) {
  const box = await sheets[i].boundingBox();
  await page.screenshot({
    path: join(here, name),
    fullPage: true,
    clip: { x: box.x + bleed * MM, y: box.y + bleed * MM, width: trimW * MM, height: trimH * MM },
  });
  console.log(`Vorschau ${name}: ${Math.round(trimW * MM * cfg.preview.scale)} x ${Math.round(trimH * MM * cfg.preview.scale)} px`);
}

// ---------- 6. QR-Codes aus der gerenderten Vorschau dekodieren ----------
for (const q of report.qr) {
  const info = qrInfo.find((i) => i.file === q.src);
  const box = await sheets[q.sheetIndex].boundingBox();
  const pad = 2 * MM;
  const png = PNG.sync.read(await page.screenshot({
    fullPage: true,
    clip: { x: box.x + q.xMm * MM - pad, y: box.y + q.yMm * MM - pad, width: q.wMm * MM + 2 * pad, height: q.hMm * MM + 2 * pad },
  }));
  const res = jsQR(new Uint8ClampedArray(png.data), png.width, png.height);
  const ok = res && res.data === info.url;
  console.log(`QR-Prüfung ${q.side} ${q.src}: ${res ? res.data : 'nicht lesbar'} ${ok ? 'OK' : 'FEHLER'}`);
  if (!ok) problems.push(`QR ${q.src} (${q.side}) liefert nicht ${info.url}`);
}
writeFileSync(join(here, 'qr-positionen.json'), JSON.stringify(report.qr.map((q) => ({ ...q, url: qrInfo.find((i) => i.file === q.src).url })), null, 2) + '\n');

await browser.close();
if (problems.length) {
  console.error('\nPROBLEME:\n' + problems.join('\n'));
  process.exitCode = 1;
} else {
  console.log('\nAlle Prüfungen bestanden.');
}
