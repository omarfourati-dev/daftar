// Tutorial Daftar (FR + AR) → A4-PDF, mit Prüfungen. Gleiche Technik wie flyer/build.mjs: HTML/CSS in Chromium
// (Playwright, headless), page.pdf mit CSS-Seitengröße, kein Netz.
//
// Aufruf (im Ordner tutorial):
//   node build.mjs                 Platzhalter für fehlende Bilder anlegen, prüfen, PDFs schreiben
//   node build.mjs --lang ar       nur eine Sprache
//   node build.mjs --placeholders --force   alle Platzhalter neu zeichnen (überschreibt auch echte Bilder!)
//   node build.mjs --strict        Fehler (Exit-Code 1), solange noch Platzhalter im Tutorial stecken – vor dem Versand
//
// Ablauf
//  1. QR-Code https://daftar.omarfourati.de als Vektor (img/qr-daftar.svg)
//  2. fehlende Screenshots als Platzhalter (shots/<id>-<lang>.png, Liste in ../shared/shots.mjs)
//  3. tutorial-<lang>.html laden: Schriften, alle Bilder geladen, jede Bild-id steht in der Liste und umgekehrt,
//     keine externe Anfrage, QR-Code aus der gerenderten Seite lesbar
//  4. PDF A4 (tutorial-daftar-<lang>.pdf) mit Seitenzahlen, Metadaten; Vorschau der Titelseite (preview-<lang>.png)
//  5. Bericht: echte Bilder / Platzhalter / von Hand aufzunehmen

import { readFileSync, writeFileSync, statSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { args, fileUrl, kb, need, offlineOnly, qrSvg, readQr } from '../shared/lib.mjs';
import { TUTORIAL_SHOTS, LANGS } from '../shared/shots.mjs';
import { makePlaceholders, placeholderStatus } from '../shared/placeholders.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const opt = args();
const langs = opt.lang ? [opt.lang] : LANGS;
const URL_DAFTAR = 'https://daftar.omarfourati.de';
const TITLE = { fr: 'Daftar – Guide de prise en main', ar: 'دفتر – دليل الاستعمال' };
const SUBJECT = {
  fr: 'Daftar pas à pas : installer, premiers réglages, rendez-vous, salle d’attente, caisse, rappels, import Excel, réservation en ligne',
  ar: 'دفتر خطوة بخطوة: التثبيت، الإعدادات الأولى، المواعيد، قاعة الانتظار، الصندوق، التذكيرات، استيراد Excel، الحجز عبر الإنترنت',
};

const { chromium } = need('playwright');
const { PDFDocument } = need('pdf-lib');
const problems = [];

// ---------- 1. QR ----------
mkdirSync(join(here, 'img'), { recursive: true });
writeFileSync(join(here, 'img', 'qr-daftar.svg'), qrSvg(URL_DAFTAR, { ecl: 'Q', color: '#134e4a' }));

const browser = await chromium.launch();

// ---------- 2. Platzhalter ----------
const made = await makePlaceholders(browser, { shots: TUTORIAL_SHOTS, dir: join(here, 'shots'), langs, force: !!(opt.placeholders && opt.force) });
if (made.length) console.log(`Platzhalter neu: ${made.length}`);

const ids = new Set(TUTORIAL_SHOTS.map((s) => s.id));
for (const lang of langs) {
  // ---------- 3. Laden und prüfen ----------
  const page = await browser.newPage({ viewport: { width: 794, height: 1123 }, deviceScaleFactor: 2 });
  page.on('console', (m) => { if (m.type() === 'error') problems.push(`${lang}: Browser: ${m.text()}`); });
  page.on('requestfailed', (r) => { if (!/^https?:/.test(r.url())) problems.push(`${lang}: nicht geladen ${r.url()}`); });
  await offlineOnly(page, (...a) => problems.push(`${lang}: ${a.join(' ')}`));
  await page.goto(fileUrl(join(here, `tutorial-${lang}.html`)), { waitUntil: 'load' });
  await page.evaluate(async () => { await document.fonts.ready; });

  const report = await page.evaluate(() => {
    const imgs = [...document.querySelectorAll('img')].map((i) => ({ src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0, alt: i.alt }));
    const fonts = [...document.fonts].filter((f) => f.status === 'loaded').map((f) => `${f.family} ${f.weight}`);
    const dir = document.documentElement.dir;
    const steps = document.querySelectorAll('.step').length;
    const stepsWithoutShot = [...document.querySelectorAll('.step')].filter((s) => !s.querySelector('figure img')).map((s) => s.querySelector('h3')?.textContent);
    return { imgs, fonts: [...new Set(fonts)], dir, steps, stepsWithoutShot };
  });
  const used = report.imgs.map((i) => i.src.match(/^shots\/(.+)-(fr|ar)\.png$/)).filter(Boolean);
  for (const i of report.imgs) {
    if (!i.ok) problems.push(`${lang}: Bild nicht geladen: ${i.src}`);
    if (!i.alt) problems.push(`${lang}: Bild ohne Alternativtext: ${i.src}`);
  }
  for (const [, id, l] of used) {
    if (!ids.has(id)) problems.push(`${lang}: Bild ${id} fehlt in shared/shots.mjs`);
    if (l !== lang) problems.push(`${lang}: Bild der falschen Sprache: ${id}-${l}.png`);
  }
  const usedIds = new Set(used.map((u) => u[1]));
  for (const id of ids) if (!usedIds.has(id)) problems.push(`${lang}: Bild ${id} aus shared/shots.mjs wird nicht verwendet`);
  if (report.stepsWithoutShot.length) problems.push(`${lang}: Schritte ohne Bild: ${report.stepsWithoutShot.join(', ')}`);
  if (report.dir !== (lang === 'ar' ? 'rtl' : 'ltr')) problems.push(`${lang}: dir=${report.dir}`);
  console.log(`\n[${lang}] ${report.steps} Schritte, ${used.length} Screenshots, Schriften: ${report.fonts.join(', ')}`);

  // QR-Code aus der gerenderten Seite lesen
  const qrPng = await page.locator('.end .qr').screenshot();
  const qrText = readQr(qrPng);
  console.log(`[${lang}] QR-Prüfung: ${qrText ?? 'nicht lesbar'} ${qrText === URL_DAFTAR ? 'OK' : 'FEHLER'}`);
  if (qrText !== URL_DAFTAR) problems.push(`${lang}: QR-Code liefert nicht ${URL_DAFTAR}`);

  // ---------- 4. PDF ----------
  // Fotos, die von Hand entstehen (Browser-Menüs) und noch fehlen, nicht als Platzhalter verschicken: der Schritt
  // bleibt als Text stehen, nur das Bild entfällt (mit echtem Foto in shots/ erscheint es beim nächsten Build).
  const manualOpen = TUTORIAL_SHOTS.filter((s) => s.mode === 'manual').map((s) => `${s.id}-${lang}.png`)
    .filter((n) => placeholderStatus(join(here, 'shots'), [n]).placeholders.length);
  await page.evaluate((files) => {
    for (const img of document.querySelectorAll('figure img')) {
      if (files.includes((img.getAttribute('src') || '').replace(/^shots\//, ''))) img.closest('figure').remove();
    }
  }, manualOpen);
  await page.emulateMedia({ media: 'print' });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: join(here, `preview-${lang}.png`), fullPage: true, clip: { x: 0, y: 0, width: 794, height: 1123 } });
  const pdfBytes = await page.pdf({ printBackground: true, preferCSSPageSize: true, tagged: true, outline: true });
  const doc = await PDFDocument.load(pdfBytes);
  doc.setTitle(TITLE[lang]);
  doc.setAuthor('Omar Fourati');
  doc.setSubject(SUBJECT[lang]);
  doc.setLanguage(lang === 'ar' ? 'ar-TN' : 'fr-TN');
  doc.setCreator('HTML/CSS + Playwright/Chromium (tutorial/build.mjs)');
  const out = join(here, `tutorial-daftar-${lang}.pdf`);
  writeFileSync(out, await doc.save());
  const sizes = doc.getPages().map((p) => p.getSize());
  const a4 = sizes.every((s) => Math.abs(s.width - 595.28) < 1 && Math.abs(s.height - 841.89) < 1);
  if (!a4) problems.push(`${lang}: PDF-Seiten nicht A4`);
  console.log(`[${lang}] PDF ${out.split(/[\\/]/).pop()}: ${sizes.length} Seiten A4${a4 ? '' : ' (FEHLER)'}, ${kb(statSync(out).size)}`);
  await page.close();

  // ---------- 5. Bericht ----------
  const names = TUTORIAL_SHOTS.map((s) => `${s.id}-${lang}.png`);
  const st = placeholderStatus(join(here, 'shots'), names);
  const manual = TUTORIAL_SHOTS.filter((s) => s.mode === 'manual').map((s) => `${s.id}-${lang}.png`);
  console.log(`[${lang}] Screenshots: ${st.real.length} echt, ${st.placeholders.length} Platzhalter, ${st.missing.length} fehlen`);
  const openManual = manual.filter((n) => st.placeholders.includes(n));
  if (openManual.length) console.log(`[${lang}] von Hand aufzunehmen: ${openManual.join(', ')}`);
  if (st.missing.length) problems.push(`${lang}: fehlende Bilder ${st.missing.join(', ')}`);
  if (opt.strict && st.placeholders.length) problems.push(`${lang}: noch ${st.placeholders.length} Platzhalter (--strict)`);
}

await browser.close();
if (problems.length) {
  console.error('\nPROBLEME:\n  ' + problems.join('\n  '));
  process.exitCode = 1;
} else {
  console.log('\nAlle Prüfungen bestanden.');
}
