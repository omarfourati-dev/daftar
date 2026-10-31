// Daftar-Werbevideo → MP4 (H.264), ohne ffmpeg und ohne Download.
//
// Technik: scenes.html (HTML/CSS) läuft in Chromium (Playwright, headless). Für jedes Bild setzt timeline.seek(t)
// den Zustand, Playwright macht einen Screenshot, eine zweite Seite kodiert ihn mit WebCodecs (VideoEncoder, avc1)
// – der H.264-Encoder steckt im Browser. mp4.mjs packt den Strom in eine MP4-Datei (moov vorne) und prüft sie.
// Unveränderte Bilder (Standbilder zwischen den Bewegungen) werden nicht neu fotografiert, nur neu kodiert.
// Zum Schluss: Datei wieder einlesen (Boxen, Codec, Dauer), im Browser abspielen (Bild nicht schwarz) und den
// QR-Code der Schlusstafel aus dem gerenderten Bild lesen.
//
// Aufruf (im Ordner video):
//   node render.mjs                         alle vier Fassungen: out/daftar-vertical-fr.mp4 … out/daftar-horizontal-ar.mp4
//   node render.mjs --format v --lang fr    eine Fassung (v = 1080x1920, h = 1920x1080)
//   node render.mjs --probe                 Probe: Anfang (0–8 s) + Schluss (letzte 6 s) → out/probe-*.mp4
//   node render.mjs --from 20 --to 30       Ausschnitt
//   node render.mjs --stills                Standbild aus jeder Szene → out/stills/ (zum Ansehen, ohne Video)
//   node render.mjs --storyboard            storyboard.md aus story.js neu schreiben
//   node render.mjs --placeholders --force  Platzhalter der Video-Screenshots neu zeichnen
//   Optionen: --fps 30, --bitrate 6 (Mbit/s, Obergrenze), --quality 92 (JPEG der Zwischenbilder), --strict
//             (Fehler, solange noch Platzhalter im Bild sind), --channel msedge|chrome (anderer Browser)

import { readFileSync, writeFileSync, mkdirSync, statSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { args, fileUrl, mb, need, qrSvg, readQr, SHARED } from '../shared/lib.mjs';
import { VIDEO_SHOTS, LANGS } from '../shared/shots.mjs';
import { makePlaceholders, placeholderStatus } from '../shared/placeholders.mjs';
import { muxMp4, inspectMp4 } from './mp4.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const opt = args();
const URL_DAFTAR = 'https://daftar.omarfourati.de';
const FORMATS = { v: { name: 'vertical', width: 1080, height: 1920 }, h: { name: 'horizontal', width: 1920, height: 1080 } };
const fps = Number(opt.fps ?? 30);
const maxBitrate = Number(opt.bitrate ?? 6) * 1e6;
const jpegQuality = Number(opt.quality ?? 92);

const story = (() => {
  const ctx = { window: {} };
  vm.runInNewContext(readFileSync(join(here, 'story.js'), 'utf8'), ctx);
  return ctx.window.DAFTAR_STORY;
})();

if (opt.storyboard) {
  const { writeStoryboard } = await import('./storyboard.mjs');
  writeStoryboard(story, join(here, 'storyboard.md'));
  console.log('storyboard.md geschrieben.');
  process.exit(0);
}

// Bild-ids aus story.js müssen in shared/shots.mjs stehen
const known = new Set(VIDEO_SHOTS.map((s) => s.id));
for (const f of ['v', 'h']) for (const s of story[f]) for (const sh of s.shots ?? []) {
  if (!known.has(sh.id)) throw new Error(`story.js: Bild ${sh.id} fehlt in shared/shots.mjs (VIDEO_SHOTS)`);
}

mkdirSync(join(here, 'img'), { recursive: true });
mkdirSync(join(here, 'out'), { recursive: true });
writeFileSync(join(here, 'img', 'qr-daftar.svg'), qrSvg(URL_DAFTAR, { ecl: 'Q', color: '#134e4a' }));

const { chromium } = need('playwright');
const browser = await chromium.launch(opt.channel ? { channel: opt.channel } : {});
const made = await makePlaceholders(browser, { shots: VIDEO_SHOTS, dir: join(here, 'shots'), force: !!(opt.placeholders && opt.force) });
if (made.length) console.log(`Platzhalter neu: ${made.length}`);
if (opt.placeholders) { await browser.close(); process.exit(0); }

const formats = opt.format ? [opt.format] : ['v', 'h'];
const langs = opt.lang ? [opt.lang] : LANGS;
const problems = [];

// ---------- Encoder-Seite (WebCodecs braucht einen sicheren Kontext: file://) ----------
const ENCODER = String.raw`
window.enc = {
  async start(cfg) {
    this.chunks = []; this.description = null; this.error = null; this.last = null; this.fps = cfg.fps;
    const tries = cfg.codecs.map((codec) => ({ codec, width: cfg.width, height: cfg.height, bitrate: cfg.bitrate, framerate: cfg.fps,
      bitrateMode: 'variable', latencyMode: 'quality', avc: { format: 'avc' } }));
    for (const c of tries) {
      const s = await VideoEncoder.isConfigSupported(c);
      if (!s.supported) continue;
      this.encoder = new VideoEncoder({
        output: (chunk, meta) => {
          const data = new Uint8Array(chunk.byteLength); chunk.copyTo(data);
          if (meta && meta.decoderConfig && meta.decoderConfig.description) this.description = new Uint8Array(meta.decoderConfig.description);
          this.chunks.push({ data, key: chunk.type === 'key', ts: chunk.timestamp });
        },
        error: (e) => { this.error = String(e); },
      });
      this.encoder.configure(c);
      this.config = c;
      return c.codec;
    }
    throw new Error('Kein H.264-Encoder (avc1) in diesem Browser');
  },
  async frame(b64, ts, key) {
    if (this.error) throw new Error(this.error);
    if (b64) {
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const bmp = await createImageBitmap(new Blob([bytes], { type: 'image/jpeg' }));
      if (this.last) this.last.close();
      this.last = bmp;
    }
    const f = new VideoFrame(this.last, { timestamp: ts, duration: Math.round(1e6 / this.fps) });
    this.encoder.encode(f, { keyFrame: key });
    f.close();
    while (this.encoder.encodeQueueSize > 4) await new Promise((r) => setTimeout(r, 2));
    return this.drain();
  },
  drain() {
    const out = this.chunks.splice(0).map((c) => ({ b64: toB64(c.data), key: c.key, ts: c.ts }));
    return out;
  },
  async finish() {
    await this.encoder.flush();
    const rest = this.drain();
    this.encoder.close();
    return { rest, description: this.description ? toB64(this.description) : null, error: this.error };
  },
};
function toB64(u8) { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); }
`;

for (const f of formats) {
  const F = FORMATS[f];
  for (const lang of langs) {
    const label = `${F.name}-${lang}`;
    const scene = await browser.newPage({ viewport: { width: F.width, height: F.height }, deviceScaleFactor: 1 });
    scene.on('pageerror', (e) => problems.push(`${label}: ${e.message}`));
    await scene.route(/^https?:/, (r) => { problems.push(`${label}: externe Anfrage ${r.request().url()}`); return r.abort(); });
    await scene.goto(fileUrl(join(here, 'scenes.html')) + `?format=${f}&lang=${lang}`);
    await scene.evaluate(() => window.timeline.ready);
    const tl = await scene.evaluate(() => ({ duration: window.timeline.duration, missing: window.timeline.missing, scenes: window.timeline.scenes }));
    if (tl.missing.length) problems.push(`${label}: Bilder fehlen: ${tl.missing.join(', ')}`);

    // Platzhalter im Bild?
    const used = [...new Set(story[f].flatMap((s) => (s.shots ?? []).map((sh) => `${sh.id}-${sh.lang === 'other' ? (lang === 'ar' ? 'fr' : 'ar') : lang}.png`)))];
    const st = placeholderStatus(join(here, 'shots'), used);
    if (st.placeholders.length) {
      console.log(`[${label}] ${st.placeholders.length} von ${used.length} Screenshots sind noch Platzhalter`);
      if (opt.strict) problems.push(`${label}: Platzhalter im Video (--strict)`);
    }

    // QR-Code der Schlusstafel aus dem gerenderten Bild lesen
    await scene.evaluate((t) => window.timeline.seek(t), tl.duration - 0.05);
    const qrText = readQr(await scene.locator('.scene-cta .qr-card').screenshot());
    console.log(`[${label}] QR-Prüfung: ${qrText ?? 'nicht lesbar'} ${qrText === URL_DAFTAR ? 'OK' : 'FEHLER'}`);
    if (qrText !== URL_DAFTAR) problems.push(`${label}: QR-Code liefert nicht ${URL_DAFTAR}`);

    // Standbilder je Szene
    if (opt.stills) {
      mkdirSync(join(here, 'out', 'stills'), { recursive: true });
      for (const s of tl.scenes) {
        await scene.evaluate((t) => window.timeline.seek(t), s.start + s.dur - 0.3);
        await scene.screenshot({ path: join(here, 'out', 'stills', `${label}-${String(s.index + 1).padStart(2, '0')}-${s.kind}.jpg`), type: 'jpeg', quality: 80 });
      }
      console.log(`[${label}] ${tl.scenes.length} Standbilder in out/stills/`);
      await scene.close();
      continue;
    }

    // Zeitbereiche
    let ranges = [[Number(opt.from ?? 0), Math.min(Number(opt.to ?? tl.duration), tl.duration)]];
    if (opt.probe) ranges = [[0, Math.min(8, tl.duration)], [Math.max(0, tl.duration - 6), tl.duration]];
    const outName = opt.probe || opt.from || opt.to ? `probe-daftar-${label}.mp4` : `daftar-${label}.mp4`;

    // ---------- Kodieren ----------
    const encoder = await browser.newPage();
    encoder.on('pageerror', (e) => problems.push(`${label} (Encoder): ${e.message}`));
    await encoder.goto(fileUrl(join(SHARED, 'blank.html')));
    await encoder.evaluate(ENCODER);
    const codec = await encoder.evaluate((cfg) => window.enc.start(cfg), {
      width: F.width, height: F.height, fps, bitrate: maxBitrate,
      codecs: ['avc1.640028', 'avc1.4d0028', 'avc1.42e028'],
    });
    const chunks = [];
    let prevKey = null, shots = 0, frames = 0;
    const t0 = Date.now();
    const total = Math.round(ranges.reduce((a, [s, e]) => a + (e - s), 0) * fps);
    for (const [from, to] of ranges) {
      const n = Math.round((to - from) * fps);
      for (let i = 0; i < n; i++) {
        const t = from + i / fps;
        const key = await scene.evaluate((tt) => window.timeline.seek(tt), t);
        let b64 = null;
        if (key !== prevKey) {
          b64 = (await scene.screenshot({ type: 'jpeg', quality: jpegQuality })).toString('base64');
          shots++;
          prevKey = key;
        }
        const out = await encoder.evaluate(([b, ts, k]) => window.enc.frame(b, ts, k), [b64, Math.round((frames * 1e6) / fps), frames % (fps * 2) === 0]);
        chunks.push(...out);
        frames++;
        if (frames % (fps * 5) === 0) process.stdout.write(`\r[${label}] ${frames}/${total} Bilder (${shots} fotografiert)   `);
      }
    }
    const { rest, description, error } = await encoder.evaluate(() => window.enc.finish());
    chunks.push(...rest);
    await encoder.close();
    process.stdout.write(`\r[${label}] ${frames}/${total} Bilder (${shots} fotografiert), ${((Date.now() - t0) / 1000).toFixed(0)} s, Codec ${codec}\n`);
    if (error) problems.push(`${label}: Encoder: ${error}`);
    if (!description) { problems.push(`${label}: Encoder lieferte keine avcC-Beschreibung`); await scene.close(); continue; }
    if (chunks.length !== frames) problems.push(`${label}: ${chunks.length} kodierte Bilder statt ${frames}`);
    for (let i = 1; i < chunks.length; i++) {
      if (chunks[i].ts <= chunks[i - 1].ts) { problems.push(`${label}: Zeitstempel nicht aufsteigend (B-Frames?) bei Bild ${i}`); break; }
    }

    const timescale = fps * 1000;
    const mp4 = muxMp4({
      width: F.width, height: F.height, timescale,
      avcC: Buffer.from(description, 'base64'),
      samples: chunks.map((c) => ({ data: Buffer.from(c.b64, 'base64'), key: c.key, duration: 1000 })),
    });
    const file = join(here, 'out', outName);
    writeFileSync(file, mp4);

    // ---------- Prüfen ----------
    const info = inspectMp4(readFileSync(file));
    problems.push(...info.problems.map((p) => `${label}: ${p}`));
    const play = await playCheck(browser, file, F, info.durationS);
    if (!play.ok) problems.push(`${label}: Wiedergabe im Browser: ${play.reason}`);
    let videoQr = null;
    if (play.last) {
      const png = Buffer.from(play.last, 'base64');
      writeFileSync(file.replace(/\.mp4$/, '-letztes-bild.png'), png);
      videoQr = readQr(png);
      if (videoQr !== URL_DAFTAR) problems.push(`${label}: QR-Code im dekodierten Video nicht lesbar (${videoQr})`);
    }
    const size = statSync(file).size;
    console.log(`[${label}] ${outName}: ${mb(size)}, ${info.width}x${info.height}, ${info.durationS.toFixed(2)} s, ${info.samples} Bilder (${info.keyframes} Schlüsselbilder), ` +
      `H.264 ${info.profileName}@${info.levelName}, Container ${info.brands.join('/')}, moov vor mdat: ${info.faststart ? 'ja' : 'nein'}, ` +
      `${((size * 8) / info.durationS / 1e6).toFixed(2)} Mbit/s, Wiedergabe im Browser: ${play.ok ? `OK (${play.detail})` : 'FEHLER'}, QR im Video: ${videoQr === URL_DAFTAR ? 'lesbar' : 'FEHLER'}`);
    await scene.close();
  }
}

await browser.close();
if (problems.length) {
  console.error('\nPROBLEME:\n  ' + problems.join('\n  '));
  process.exitCode = 1;
} else if (!opt.stills) {
  console.log('\nAlle Prüfungen bestanden.');
}

/** Datei in einem <video> abspielen: Metadaten, Größe, Dauer, und an drei Stellen ein Bild, das nicht schwarz ist. */
async function playCheck(browser, file, F, expected) {
  const page = await browser.newPage();
  try {
    // eigener Ursprung statt file://, damit das Videobild in ein Canvas gelesen werden darf
    const bytes = readFileSync(file);
    await page.route('http://render.local/**', (route) => {
      if (!route.request().url().endsWith('.mp4')) return route.fulfill({ body: '<!doctype html><title>Prüfung</title>', contentType: 'text/html' });
      const m = /bytes=(\d+)-(\d*)/.exec(route.request().headers().range || '');
      if (!m) return route.fulfill({ body: bytes, contentType: 'video/mp4', headers: { 'Accept-Ranges': 'bytes' } });
      const from = Number(m[1]), to = m[2] ? Number(m[2]) : bytes.length - 1;
      return route.fulfill({ status: 206, body: bytes.subarray(from, to + 1), contentType: 'video/mp4',
        headers: { 'Accept-Ranges': 'bytes', 'Content-Range': `bytes ${from}-${to}/${bytes.length}` } });
    });
    await page.goto('http://render.local/');
    return await page.evaluate(async ({ src, w, h, expected }) => {
      const v = document.createElement('video');
      v.muted = true; v.preload = 'auto'; v.src = src;
      document.body.append(v);
      const can = v.canPlayType('video/mp4; codecs="avc1.640028"');
      await new Promise((res, rej) => { v.onloadeddata = res; v.onerror = () => rej(new Error('Fehler ' + (v.error && v.error.code))); setTimeout(() => rej(new Error('Zeitüberschreitung')), 15000); });
      if (v.videoWidth !== w || v.videoHeight !== h) return { ok: false, reason: `Größe ${v.videoWidth}x${v.videoHeight}` };
      if (Math.abs(v.duration - expected) > 0.2) return { ok: false, reason: `Dauer ${v.duration}` };
      const c = document.createElement('canvas'); c.width = 64; c.height = 64;
      const g = c.getContext('2d', { willReadFrequently: true });
      const means = [];
      for (const t of [0.5, v.duration / 2, v.duration - 0.3]) {
        await new Promise((res) => { v.onseeked = res; v.currentTime = t; });
        g.drawImage(v, 0, 0, 64, 64);
        const d = g.getImageData(0, 0, 64, 64).data;
        let s = 0; for (let i = 0; i < d.length; i += 4) s += d[i] + d[i + 1] + d[i + 2];
        means.push(Math.round(s / (d.length / 4) / 3));
      }
      if (means.some((m) => m < 8)) return { ok: false, reason: `schwarzes Bild (${means.join('/')})` };
      // letztes Bild (Schlusstafel mit QR-Code) in voller Größe zurückgeben
      await new Promise((res) => { v.onseeked = res; v.currentTime = v.duration - 0.2; });
      const big = document.createElement('canvas'); big.width = w; big.height = h;
      big.getContext('2d').drawImage(v, 0, 0, w, h);
      return { ok: true, detail: `canPlayType=${can || 'leer'}, Helligkeit ${means.join('/')}`, last: big.toDataURL('image/png').split(',')[1] };
    }, { src: 'http://render.local/video.mp4', w: F.width, h: F.height, expected });
  } catch (e) {
    return { ok: false, reason: e.message };
  } finally {
    await page.close();
  }
}
