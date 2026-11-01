// Daftar-Videos → MP4 (H.264 + AAC), ohne ffmpeg und ohne Download.
//
// Filme
//   pub       Werbevideo „Vorher → mit Daftar“ (story.js, scenes.html): v = 1080x1920 (≤ 60 s, < 16 MB), h = 1920x1080
//   tutoriel  Tutorial-Gesamtvideo (tutoriel.js, tutoriel.html): 1920x1080, Kapitel, Schritte, Untertitel
// Stimme: Azure Neural TTS über ../voice/tts.py (der Schlüssel bleibt dort). Die Szenendauer ergibt sich aus der Länge
// der gesprochenen Sätze (timing.js); ist eine Fassung zu lang, wird das Sprechtempo stufenweise erhöht (rateSteps).
//
// Technik: Die Szenen-Seite läuft in Chromium (Playwright, headless); timeline.seek(t) setzt jedes Bild, Playwright
// fotografiert es, eine zweite Seite kodiert Bild (VideoEncoder, avc1) und Ton (AudioEncoder, mp4a.40.2 = AAC-LC) mit
// WebCodecs. mp4.mjs packt beides in eine MP4-Datei (moov vorne, Bild und Ton verschränkt).
// Prüfungen je Datei (Bericht out/<name>.pruefung.json): Datei wieder einlesen (beide Spuren, Codec, Dauer, mdat),
// Wiedergabe im Browser (Bild, Ton wird dekodiert), Tonpegel nicht leer, Ton synchron (Einsätze der Sätze im
// dekodierten Ton gegen den Zeitplan) und Bild synchron (dekodierte Bilder gegen die gerenderten), QR im letzten Bild.
//
// Aufruf (im Ordner video):
//   node render.mjs --check-voice                  Azure-Zugang prüfen (tts.py --check): „OK“ oder „Azure-Schlüssel fehlt/ungültig“
//   node render.mjs                                alle Fassungen mit Stimme: pub v/h × fr/ar und tutoriel fr/ar
//   node render.mjs --film pub --format v --lang fr   eine Fassung
//   node render.mjs --stills                       Standbilder an den Wechselpunkten → out/standbilder/ (Stimme aus dem Cache, sonst geschätzt)
//   node render.mjs --sprechtexte                  sprechtexte.md schreiben (Dauern aus dem Cache, sonst geschätzt)
//   node render.mjs --storyboard                   storyboard.md aus story.js neu schreiben
//   node render.mjs --test-tone …                  Tonkette prüfen ohne Azure: Prüfsignal statt Stimme → out/probe-ton-*.mp4
//   node render.mjs --no-voice …                   ohne Ton, Dauern geschätzt → out/ohne-ton-*.mp4 (nur Vorschau)
//   node render.mjs --probe …                      nur Anfang (8 s) und Schluss (6 s) → out/probe-*.mp4
//   node render.mjs --check-only …                 vorhandene Dateien in out/ nur prüfen (gleiche Optionen wie beim Export)
//   Optionen: --fps, --bitrate (Mbit/s), --quality (JPEG der Zwischenbilder), --channel msedge|chrome

import { readFileSync, writeFileSync, mkdirSync, statSync, existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { args, fileUrl, mb, need, qrSvg, readQr, SHARED } from '../shared/lib.mjs';
import { VIDEO_SHOTS, TUTORIAL_SHOTS, LANGS } from '../shared/shots.mjs';
import { placeholderStatus } from '../shared/placeholders.mjs';
import { muxMp4, inspectMp4 } from './mp4.mjs';
import { TTS_PY, jobsFor, synthesize, readWav, trimSilence, mix, testTone, onsets, levels } from './voice.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const opt = args();
const URL_DAFTAR = 'https://daftar.omarfourati.de';
const FORMATS = { v: { name: 'vertical', width: 1080, height: 1920 }, h: { name: 'horizontal', width: 1920, height: 1080 } };
const SR = 48000;
const AUDIO_BITRATE = 128000;
const jpegQuality = Number(opt.quality ?? 90);

function load(file, global) {
  const ctx = { window: {} };
  vm.runInNewContext(readFileSync(join(here, 'timing.js'), 'utf8') + '\n' + readFileSync(join(here, file), 'utf8'), ctx);
  return { lib: ctx.window.DAFTAR_TIMING_LIB, data: ctx.window[global] };
}
const { lib: LIB, data: STORY } = load('story.js', 'DAFTAR_STORY');
const { data: TUT } = load('tutoriel.js', 'DAFTAR_TUTORIEL');

const FILMS = {
  pub: {
    key: 'pub', page: 'scenes.html', data: STORY, formats: ['v', 'h'], fps: 30,
    scenes: (f) => STORY[f], rate: (f) => STORY.rate[f], steps: (f) => STORY.rateSteps[f] || [], timing: (f) => STORY.timing[f],
    limits: (f) => STORY.limits[f], bitrate: { v: 1.9e6, h: 4e6 }, qr: '.scene-cta .qr-card',
    out: (f, lang) => `daftar-${FORMATS[f].name}-${lang}.mp4`,
  },
  tutoriel: {
    key: 'tutoriel', page: 'tutoriel.html', data: TUT, formats: ['h'], fps: 25,
    scenes: () => TUT.scenes, rate: () => TUT.rate, steps: () => TUT.rateSteps || [], timing: () => TUT.timing,
    limits: () => TUT.limits, bitrate: { h: 1.6e6 }, qr: '.scene-outro .qr-card',
    out: (f, lang) => `daftar-tutoriel-${lang}.mp4`,
  },
};

// ---------- reine Textaufgaben ----------
if (opt['check-voice']) {
  const r = spawnSync(process.env.PYTHON || 'python', [TTS_PY, '--check'], { stdio: 'inherit' });
  process.exit(r.status ?? 1);
}
if (opt.storyboard) {
  const { writeStoryboard } = await import('./storyboard.mjs');
  writeStoryboard(STORY, LIB, join(here, 'storyboard.md'));
  console.log('storyboard.md geschrieben.');
  process.exit(0);
}

const voiceMode = opt['no-voice'] ? 'none' : opt['test-tone'] ? 'tone' : (opt.stills || opt.sprechtexte) ? 'offline' : 'azure';
const films = opt.film ? [opt.film] : ['pub', 'tutoriel'];
const langs = opt.lang ? [opt.lang] : LANGS;
for (const f of films) if (!FILMS[f]) throw new Error(`unbekannter Film ${f} (pub | tutoriel)`);

// Sprechtexte prüfen (nur erlaubte SSML-Tags) und Bild-ids gegen shared/shots.mjs
const problems = [];
for (const fk of films) for (const f of FILMS[fk].formats) for (const s of FILMS[fk].scenes(f)) {
  for (const b of s.say || []) for (const l of LANGS) for (const p of LIB.checkSsml(b[l])) problems.push(`${fk}/${f}: Sprechtext ${l}: ${p}: ${b[l].slice(0, 50)}`);
}
const knownVideo = new Set(VIDEO_SHOTS.map((s) => s.id)), knownTut = new Set(TUTORIAL_SHOTS.map((s) => s.id));
for (const f of ['v', 'h']) for (const s of STORY[f]) for (const sh of (s.fix?.shots ?? s.shots ?? [])) {
  const ok = sh.id.startsWith('t:') ? knownTut.has(sh.id.slice(2)) : knownVideo.has(sh.id);
  if (!ok) problems.push(`story.js: Bild ${sh.id} fehlt in shared/shots.mjs`);
}
for (const s of TUT.scenes) if (s.shot && !knownTut.has(s.shot)) problems.push(`tutoriel.js: Bild ${s.shot} fehlt in shared/shots.mjs`);
if (problems.length) { console.error('PROBLEME in den Daten:\n  ' + problems.join('\n  ')); process.exit(1); }

/** Zeitplan und Tonstücke einer Fassung. mode: azure | offline | tone | none */
function prepare(film, f, lang, mode) {
  const scenes = film.scenes(f);
  const limits = film.limits(f) || {};
  const rates = [film.rate(f), ...film.steps(f)];
  let last = null;
  for (const rate of rates) {
    const clips = scenes.map((s) => (s.say || []).map(() => null));
    let estimated = 0;
    if (mode === 'azure' || mode === 'offline') {
      const jobs = jobsFor(scenes, film.data.voices, lang, rate, `${film.key}-${f}`);
      const res = synthesize(jobs, { offline: mode === 'offline', tag: `${film.key}-${f}-${lang}` });
      if (res.code === 2) { const e = new Error('Azure-Schlüssel fehlt/ungültig'); e.code = 'KEY'; throw e; }
      if (res.code !== 0) throw new Error(`voice/tts.py beendet mit Code ${res.code}`);
      for (const j of jobs) {
        const e = res.entries.get(j.id);
        if (e && e.wav) {
          const w = readWav(e.wav);
          if (w.sampleRate !== SR) throw new Error(`WAV ${e.wav}: ${w.sampleRate} Hz statt ${SR}`);
          clips[j.scene][j.beat] = trimSilence(w.pcm, SR);
        }
      }
    }
    const seconds = (i, k) => {
      if (clips[i][k]) return clips[i][k].length / SR;
      estimated++;
      const sec = LIB.estimate(scenes[i].say[k][lang], lang, rate);
      if (mode === 'tone') clips[i][k] = testTone(sec, SR);
      return sec;
    };
    const plan = LIB.plan(scenes, { defaults: film.timing(f), seconds });
    last = { plan, clips: mode === 'none' ? null : clips, rate, estimated, total: plan.total };
    if (!limits.maxS || plan.total <= limits.maxS - 0.1) break;
    console.log(`[${film.key}-${f}-${lang}] ${plan.total.toFixed(1)} s bei Tempo ${rate} ist länger als ${limits.maxS} s – nächste Tempostufe`);
  }
  return last;
}

// ---------- Nur Sprechtexte ----------
if (opt.sprechtexte) {
  const { writeSprechtexte } = await import('./sprechtexte.mjs');
  const plans = {};
  for (const fk of ['pub', 'tutoriel']) for (const f of FILMS[fk].formats) for (const lang of LANGS) {
    plans[`${fk}-${f}-${lang}`] = prepare(FILMS[fk], f, lang, 'offline');
  }
  writeSprechtexte({ STORY, TUT, LIB, plans, file: join(here, 'sprechtexte.md') });
  console.log('sprechtexte.md geschrieben.');
  process.exit(0);
}

// ---------- Azure zuerst prüfen ----------
if (voiceMode === 'azure') {
  const r = spawnSync(process.env.PYTHON || 'python', [TTS_PY, '--check'], { encoding: 'utf8' });
  const msg = (r.stdout || '').trim();
  if (r.status !== 0) {
    console.error(`\nStimme nicht verfügbar: ${msg || 'tts.py --check fehlgeschlagen'}${r.stderr ? '\n' + r.stderr.trim() : ''}`);
    console.error('Kein Video mit Stimme erzeugt. Schlüssel in ~/.claude/dp/tokens-for-scripts.json unter "azure" (token, region) eintragen,');
    console.error('dann erneut: node render.mjs   (Vorschau ohne Azure: --test-tone oder --no-voice, Standbilder: --stills)');
    process.exit(2);
  }
  console.log(`Azure TTS: ${msg}`);
}

mkdirSync(join(here, 'img'), { recursive: true });
mkdirSync(join(here, 'out'), { recursive: true });
writeFileSync(join(here, 'img', 'qr-daftar.svg'), qrSvg(URL_DAFTAR, { ecl: 'Q', color: '#134e4a' }));

const { chromium } = need('playwright');
const browser = await chromium.launch({ ...(opt.channel ? { channel: opt.channel } : {}), args: ['--autoplay-policy=no-user-gesture-required'] });

// ---------- Encoder-Seite (WebCodecs braucht einen sicheren Kontext: file://) ----------
const ENCODER = String.raw`
function toB64(u8) { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); }
window.enc = {
  async start(cfg) {
    this.chunks = []; this.description = null; this.error = null; this.last = null; this.fps = cfg.fps;
    for (const codec of cfg.codecs) {
      const c = { codec, width: cfg.width, height: cfg.height, bitrate: cfg.bitrate, framerate: cfg.fps, bitrateMode: 'variable', latencyMode: 'quality', avc: { format: 'avc' } };
      if (!(await VideoEncoder.isConfigSupported(c)).supported) continue;
      this.encoder = new VideoEncoder({
        output: (chunk, meta) => {
          const data = new Uint8Array(chunk.byteLength); chunk.copyTo(data);
          if (meta && meta.decoderConfig && meta.decoderConfig.description) this.description = new Uint8Array(meta.decoderConfig.description);
          this.chunks.push({ data, key: chunk.type === 'key', ts: chunk.timestamp });
        },
        error: (e) => { this.error = String(e); },
      });
      this.encoder.configure(c);
      return codec;
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
    return this.chunks.splice(0).map((c) => ({ b64: toB64(c.data), key: c.key, ts: c.ts }));
  },
  async finish() {
    await this.encoder.flush();
    const rest = this.chunks.splice(0).map((c) => ({ b64: toB64(c.data), key: c.key, ts: c.ts }));
    this.encoder.close();
    return { rest, description: this.description ? toB64(this.description) : null, error: this.error };
  },
};
window.aenc = {
  async start(cfg) {
    this.chunks = []; this.asc = null; this.error = null; this.sr = cfg.sampleRate; this.pos = 0;
    const c = { codec: 'mp4a.40.2', sampleRate: cfg.sampleRate, numberOfChannels: 1, bitrate: cfg.bitrate };
    if (!(await AudioEncoder.isConfigSupported(c)).supported) throw new Error('Kein AAC-Encoder (mp4a.40.2) in diesem Browser');
    this.encoder = new AudioEncoder({
      output: (chunk, meta) => {
        const d = new Uint8Array(chunk.byteLength); chunk.copyTo(d); this.chunks.push(d);
        if (meta && meta.decoderConfig && meta.decoderConfig.description) this.asc = new Uint8Array(meta.decoderConfig.description);
      },
      error: (e) => { this.error = String(e); },
    });
    this.encoder.configure(c);
  },
  async push(b64) {
    if (this.error) throw new Error(this.error);
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const i16 = new Int16Array(bytes.buffer);
    const f = new Float32Array(i16.length);
    for (let i = 0; i < i16.length; i++) f[i] = i16[i] / 32768;
    for (let o = 0; o < f.length; o += 4800) {
      const n = Math.min(4800, f.length - o);
      const ad = new AudioData({ format: 'f32-planar', sampleRate: this.sr, numberOfFrames: n, numberOfChannels: 1, timestamp: Math.round(((this.pos + o) * 1e6) / this.sr), data: f.slice(o, o + n) });
      this.encoder.encode(ad); ad.close();
    }
    this.pos += f.length;
    while (this.encoder.encodeQueueSize > 8) await new Promise((r) => setTimeout(r, 2));
  },
  async finish() {
    await this.encoder.flush();
    this.encoder.close();
    return { chunks: this.chunks.map(toB64), asc: this.asc ? toB64(this.asc) : null, error: this.error };
  },
};
`;

const summary = [];
for (const fk of films) {
  const film = FILMS[fk];
  const formats = opt.format ? [opt.format].filter((f) => film.formats.includes(f)) : film.formats;
  for (const f of formats) for (const lang of langs) {
    const label = `${fk}-${f}-${lang}`;
    const F = FORMATS[f];
    const fps = Number(opt.fps ?? film.fps);
    let prep;
    try {
      prep = prepare(film, f, lang, voiceMode);
    } catch (e) {
      if (e.code === 'KEY') { console.error(`[${label}] Azure-Schlüssel fehlt/ungültig – abgebrochen.`); await browser.close(); process.exit(2); }
      throw e;
    }
    const { plan, clips } = prep;
    console.log(`[${label}] Zeitplan ${plan.total.toFixed(2)} s, Tempo ${prep.rate}${prep.estimated ? `, ${prep.estimated} Dauern geschätzt` : ''}`);

    // ---------- Szenen-Seite ----------
    const scene = await browser.newPage({ viewport: { width: F.width, height: F.height }, deviceScaleFactor: 1 });
    scene.on('pageerror', (e) => problems.push(`${label}: ${e.message}`));
    await scene.route(/^https?:/, (r) => { problems.push(`${label}: externe Anfrage ${r.request().url()}`); return r.abort(); });
    await scene.addInitScript((p) => { window.DAFTAR_PLAN = p; }, plan);
    await scene.goto(fileUrl(join(here, film.page)) + `?format=${f}&lang=${lang}`);
    await scene.evaluate(() => window.timeline.ready);
    const tl = await scene.evaluate(() => ({ duration: window.timeline.duration, missing: window.timeline.missing, scenes: window.timeline.scenes, marks: window.timeline.marks }));
    if (tl.missing.length) problems.push(`${label}: Bilder fehlen: ${tl.missing.join(', ')}`);
    if (Math.abs(tl.duration - plan.total) > 0.001) problems.push(`${label}: Seite nutzt nicht den Zeitplan (${tl.duration} statt ${plan.total})`);

    // Platzhalter im Bild?
    const usedShots = fk === 'pub'
      ? [...new Set(STORY[f].flatMap((s) => (s.fix?.shots ?? s.shots ?? []).filter((sh) => !sh.id.startsWith('t:')).map((sh) => `${sh.id}-${sh.lang === 'other' ? (lang === 'ar' ? 'fr' : 'ar') : lang}.png`)))]
      : [];
    if (usedShots.length) {
      const st = placeholderStatus(join(here, 'shots'), usedShots);
      if (st.placeholders.length) problems.push(`${label}: ${st.placeholders.length} Video-Screenshots sind Platzhalter`);
    }
    const tutShots = fk === 'tutoriel' ? [...new Set(TUT.scenes.filter((s) => s.shot).map((s) => `${s.shot}-${lang}.png`))]
      : [...new Set(STORY[f].flatMap((s) => (s.fix?.shots ?? []).filter((sh) => sh.id.startsWith('t:')).map((sh) => `${sh.id.slice(2)}-${lang}.png`)))];
    if (tutShots.length) {
      const st = placeholderStatus(join(here, '..', 'tutorial', 'shots'), tutShots);
      if (st.placeholders.length) problems.push(`${label}: Tutorial-Platzhalter im Bild: ${st.placeholders.join(', ')}`);
    }

    // QR-Code der Schlusstafel aus dem gerenderten Bild lesen
    await scene.evaluate((t) => window.timeline.seek(t), tl.duration - 0.05);
    const qrText = readQr(await scene.locator(film.qr).screenshot());
    if (qrText !== URL_DAFTAR) problems.push(`${label}: QR-Code der Schlusstafel liefert ${qrText}`);

    // ---------- Standbilder ----------
    if (opt.stills) {
      const dir = join(here, 'out', 'standbilder');
      mkdirSync(dir, { recursive: true });
      for (const m of tl.marks) {
        await scene.evaluate((t) => window.timeline.seek(t), m.t);
        await scene.screenshot({ path: join(dir, `${label}-${String(m.scene).padStart(2, '0')}-${m.label}.jpg`), type: 'jpeg', quality: 82 });
      }
      console.log(`[${label}] ${tl.marks.length} Standbilder in out/standbilder/ (QR ${qrText === URL_DAFTAR ? 'lesbar' : 'FEHLER'})`);
      await scene.close();
      continue;
    }

    // ---------- Zeitbereiche ----------
    let ranges = [[Number(opt.from ?? 0), Math.min(Number(opt.to ?? tl.duration), tl.duration)]];
    if (opt.probe) ranges = [[0, Math.min(8, tl.duration)], [Math.max(0, tl.duration - 6), tl.duration]];
    const partial = !!(opt.probe || opt.from || opt.to);
    const base = film.out(f, lang);
    const outName = (voiceMode === 'tone' ? 'probe-ton-' : voiceMode === 'none' ? 'ohne-ton-' : '') + (partial ? 'probe-' : '') + base;
    const file = join(here, 'out', outName);

    // Ton: Sätze auf die Zeitleiste legen
    let audio = null;
    if (clips) {
      const items = [];
      plan.scenes.forEach((s, i) => s.beats.forEach((b, k) => { if (clips[i][k]) items.push({ t: s.start + b.at, pcm: clips[i][k], scene: i, beat: k }); }));
      const mixed = mix(items, plan.total, SR);
      // erwartete Einsätze (nur Sätze mit ≥ 0,2 s Stille davor), aus dem gemischten Signal selbst
      const cand = items.filter((it, n) => n === 0 || it.t - (items[n - 1].t + items[n - 1].pcm.length / SR) >= 0.2);
      const exp = onsets(mixed.pcm, SR, cand.map((it) => it.t), { before: 0.02, after: 0.4 });
      audio = { mixed, expected: exp.filter((t) => t != null) };
    }

    if (!opt['check-only']) {
      let bitrate = Number(opt.bitrate ?? 0) * 1e6 || film.bitrate[f];
      for (let attempt = 0; attempt < 3; attempt++) {
        const result = await encodeAndMux({ label, scene, F, fps, ranges, bitrate, audio, partial, file });
        const lim = film.limits(f) || {};
        if (!partial && lim.maxBytes && result.size >= lim.maxBytes && attempt < 2) {
          bitrate = Math.round(bitrate * 0.72);
          console.log(`[${label}] ${mb(result.size)} ≥ ${(lim.maxBytes / 1e6).toFixed(0)} MB – neu kodieren mit ${(bitrate / 1e6).toFixed(2)} Mbit/s`);
          continue;
        }
        break;
      }
    } else if (!existsSync(file)) {
      problems.push(`${label}: ${outName} fehlt (--check-only prüft nur vorhandene Dateien)`);
      await scene.close();
      continue;
    }
    // Bezugsbilder für die Bild-Synchronprüfung: Mitte einiger Szenen, frisch aus der Szenen-Seite (seek ist eine reine
    // Funktion der Zeit, also dasselbe Bild wie beim Kodieren)
    const refs = [];
    if (!partial) {
      const pick = tl.scenes.filter((s) => s.dur > 2).filter((_, i, a) => i % Math.max(1, Math.floor(a.length / 6)) === 0).slice(0, 7);
      for (const s of pick) {
        const fi = Math.floor((s.start + s.dur * 0.62) * fps);
        await scene.evaluate((tt) => window.timeline.seek(tt), fi / fps);
        refs.push({ t: (fi + 0.5) / fps, jpeg: (await scene.screenshot({ type: 'jpeg', quality: jpegQuality })).toString('base64') });
      }
    }
    await scene.close();

    // ---------- Prüfen ----------
    const report = await check({ label, file, F, fps, plan, audio, partial, limits: film.limits(f) || {}, refs, voiceMode, rate: prep.rate, estimated: prep.estimated, qrPage: qrText });
    writeFileSync(file.replace(/\.mp4$/, '.pruefung.json'), JSON.stringify(report, null, 1));
    problems.push(...report.problems.map((p) => `${label}: ${p}`));
    summary.push(report);
    console.log(`[${label}] ${outName}: ${report.sizeMB} MB, ${report.width}x${report.height}, ${report.durationS} s, ` +
      `Spuren ${report.tracks.join('+')}, ${report.mbitPerS} Mbit/s, Wiedergabe ${report.playback.ok ? 'OK' : 'FEHLER'}, ` +
      `Ton ${report.audio ? `${report.audio.voicedRmsDb} dBFS (Sprache), Spitze ${report.audio.peakDb} dBFS` : '–'}, ` +
      `Sync ${report.sync ? `Ton max ${report.sync.maxMs} ms / Bild ${report.frames.maxDiff}` : '–'}, QR ${report.qrVideo === URL_DAFTAR ? 'lesbar' : 'FEHLER'}`);
  }
}

await browser.close();
if (problems.length) {
  console.error('\nPROBLEME:\n  ' + problems.join('\n  '));
  process.exitCode = 1;
} else if (!opt.stills) {
  console.log('\nAlle Prüfungen bestanden.');
}

// =====================================================================================================================

/** Bilder fotografieren und kodieren, Ton kodieren, MP4 schreiben. */
async function encodeAndMux({ label, scene, F, fps, ranges, bitrate, audio, partial, file }) {
  const encoder = await browser.newPage();
  encoder.on('pageerror', (e) => problems.push(`${label} (Encoder): ${e.message}`));
  await encoder.goto(fileUrl(join(SHARED, 'blank.html')));
  await encoder.evaluate(`(() => { ${ENCODER} })()`);
  const codec = await encoder.evaluate((cfg) => window.enc.start(cfg), {
    width: F.width, height: F.height, fps, bitrate, codecs: ['avc1.640028', 'avc1.4d0028', 'avc1.42e028'],
  });
  const chunks = [];
  let prevKey = null, shots = 0, frames = 0;
  const t0 = Date.now();
  const totalFrames = Math.round(ranges.reduce((a, [s, e]) => a + (e - s), 0) * fps);
  for (const [from, to] of ranges) {
    const n = Math.round((to - from) * fps);
    for (let i = 0; i < n; i++) {
      const fi = Math.round(from * fps) + i;
      const t = fi / fps;
      const key = await scene.evaluate((tt) => window.timeline.seek(tt), t);
      let b64 = null;
      if (key !== prevKey) {
        b64 = (await scene.screenshot({ type: 'jpeg', quality: jpegQuality })).toString('base64');
        shots++; prevKey = key;
      }
      const out = await encoder.evaluate(([b, ts, k]) => window.enc.frame(b, ts, k), [b64, Math.round((frames * 1e6) / fps), frames % (fps * 2) === 0]);
      chunks.push(...out);
      frames++;
      if (frames % (fps * 10) === 0) process.stdout.write(`\r[${label}] ${frames}/${totalFrames} Bilder (${shots} fotografiert)   `);
    }
  }
  const { rest, description, error } = await encoder.evaluate(() => window.enc.finish());
  chunks.push(...rest);
  process.stdout.write(`\r[${label}] ${frames}/${totalFrames} Bilder (${shots} fotografiert), ${((Date.now() - t0) / 1000).toFixed(0)} s, ${codec}, Ziel ${(bitrate / 1e6).toFixed(2)} Mbit/s\n`);
  if (error) problems.push(`${label}: Video-Encoder: ${error}`);
  if (!description) throw new Error(`${label}: Encoder lieferte keine avcC-Beschreibung`);
  if (chunks.length !== frames) problems.push(`${label}: ${chunks.length} kodierte Bilder statt ${frames}`);
  for (let i = 1; i < chunks.length; i++) {
    if (chunks[i].ts <= chunks[i - 1].ts) { problems.push(`${label}: Zeitstempel nicht aufsteigend (B-Frames?) bei Bild ${i}`); break; }
  }

  // ---------- Ton ----------
  let aac = null;
  const videoS = frames / fps;
  if (audio) {
    // bei Teilbereichen (Probe) die passenden Stücke aneinanderhängen
    let pcm = audio.mixed.pcm;
    if (partial) {
      const parts = ranges.map(([a, z]) => pcm.subarray(Math.round(a * SR), Math.round(z * SR)));
      const all = new Float32Array(parts.reduce((s, p) => s + p.length, 0));
      let o = 0; for (const p of parts) { all.set(p, o); o += p.length; }
      pcm = all;
    }
    const need = Math.ceil(videoS * SR);
    if (pcm.length < need) { const p2 = new Float32Array(need); p2.set(pcm); pcm = p2; } else pcm = pcm.subarray(0, need);
    await encoder.evaluate((cfg) => window.aenc.start(cfg), { sampleRate: SR, bitrate: AUDIO_BITRATE });
    const step = SR * 2;
    for (let o = 0; o < pcm.length; o += step) {
      const part = pcm.subarray(o, Math.min(pcm.length, o + step));
      const i16 = new Int16Array(part.length);
      for (let i = 0; i < part.length; i++) i16[i] = Math.max(-32768, Math.min(32767, Math.round(part[i] * 32767)));
      await encoder.evaluate((b) => window.aenc.push(b), Buffer.from(i16.buffer).toString('base64'));
    }
    const res = await encoder.evaluate(() => window.aenc.finish());
    if (res.error) problems.push(`${label}: Audio-Encoder: ${res.error}`);
    if (!res.asc) throw new Error(`${label}: AAC-Encoder lieferte keine AudioSpecificConfig`);
    aac = { sampleRate: SR, channels: 1, asc: Buffer.from(res.asc, 'base64'), samples: res.chunks.map((b) => ({ data: Buffer.from(b, 'base64') })), durationS: videoS, bitrate: AUDIO_BITRATE };
  }
  await encoder.close();

  const mp4 = muxMp4({
    width: F.width, height: F.height, timescale: fps * 1000,
    avcC: Buffer.from(description, 'base64'),
    samples: chunks.map((c) => ({ data: Buffer.from(c.b64, 'base64'), key: c.key, duration: 1000 })),
    audio: aac,
  });
  writeFileSync(file, mp4);
  return { size: statSync(file).size };
}

/** Fertige Datei prüfen: Container, Dauer, Grenzen, Wiedergabe, Ton (Pegel, Synchronität), Bild-Synchronität, QR. */
async function check({ label, file, F, fps, plan, audio, partial, limits, refs, voiceMode, rate, estimated, qrPage }) {
  const p = [];
  const bytes = readFileSync(file);
  const info = inspectMp4(bytes);
  p.push(...info.problems);
  const tracks = info.tracks.map((t) => t.handler);
  const expectS = partial ? info.durationS : plan.total;
  if (!info.video) p.push('keine Videospur');
  if (audio && !info.audio) p.push('keine Tonspur');
  if (!partial && Math.abs(info.durationS - Math.round(plan.total * fps) / fps) > 1.01 / fps) p.push(`Videodauer ${info.durationS.toFixed(3)} s statt ${plan.total.toFixed(3)} s`);
  if (info.audio && Math.abs(info.audio.playS - info.durationS) > 0.05) p.push(`Tondauer ${info.audio.playS.toFixed(3)} s, Video ${info.durationS.toFixed(3)} s`);
  if (!partial && limits.maxS && info.durationS > limits.maxS) p.push(`länger als ${limits.maxS} s (${info.durationS.toFixed(2)} s)`);
  if (!partial && limits.maxBytes && bytes.length >= limits.maxBytes) p.push(`Datei ${mb(bytes.length)} nicht unter ${(limits.maxBytes / 1e6).toFixed(0)} MB`);
  const warnings = [];
  if (!partial && limits.minS && info.durationS < limits.minS) warnings.push(`kürzer als ${limits.minS} s (${info.durationS.toFixed(1)} s)`);

  const play = await playCheck(bytes, F, expectS, { expected: audio && !partial ? audio.expected : [], refs: partial ? [] : refs });
  if (!play.ok) p.push(`Wiedergabe im Browser: ${play.reason}`);
  let qrVideo = null;
  if (play.last) {
    const png = Buffer.from(play.last, 'base64');
    writeFileSync(file.replace(/\.mp4$/, '-letztes-bild.png'), png);
    qrVideo = readQr(png);
    // nur wenn die Datei bis zur Schlusstafel reicht (ganze Fassung oder --probe), nicht bei --from/--to-Ausschnitten
    const endsWithCta = !partial || !!opt.probe || Number(opt.to ?? Infinity) >= plan.total;
    if (endsWithCta && qrVideo !== URL_DAFTAR) p.push(`QR-Code im dekodierten letzten Bild nicht lesbar (${qrVideo})`);
  }
  let sync = null;
  if (audio && play.audio) {
    const lv = play.audio.levels;
    if (!(lv.voicedRatio > 0.25 && lv.voicedRmsDb > -35 && lv.peakDb > -12)) p.push(`Tonpegel zu niedrig/leer (${JSON.stringify(lv)})`);
    if (!partial) {
      const diffs = play.audio.diffs.filter((d) => d != null);
      const missing = play.audio.diffs.length - diffs.length;
      const maxMs = diffs.length ? Math.round(Math.max(...diffs.map(Math.abs)) * 1000) : null;
      const medMs = diffs.length ? Math.round(diffs.map(Math.abs).sort((a, b) => a - b)[Math.floor(diffs.length / 2)] * 1000) : null;
      sync = { onsets: play.audio.diffs.length, found: diffs.length, maxMs, medianMs: medMs };
      if (missing) p.push(`Synchronprüfung Ton: ${missing} Satzanfänge nicht gefunden`);
      if (maxMs == null || maxMs > 40) p.push(`Ton nicht synchron: größte Abweichung ${maxMs} ms`);
    }
  }
  const frames = play.frames || { checked: 0, maxDiff: null };
  if (!partial && refs.length && !(frames.checked === refs.length && frames.maxDiff <= 12)) p.push(`Bild nicht synchron zum Zeitplan (${JSON.stringify(frames)})`);
  if (audio && !(play.audioPlayback > 0)) p.push('Ton wird bei der Wiedergabe im Browser nicht dekodiert');

  return {
    datei: file, voiceMode, rate, estimatedDurations: estimated, plannedS: plan.total,
    sizeBytes: bytes.length, sizeMB: +(bytes.length / 1024 / 1024).toFixed(2), width: info.width, height: info.height,
    durationS: +info.durationS.toFixed(3), tracks, faststart: info.faststart,
    video: { codec: info.codec, profile: info.profileName, level: info.levelName, frames: info.samples, keyframes: info.keyframes },
    audioTrack: info.audio ? { codec: info.audio.codec, sampleRate: info.audio.sampleRate, channels: info.audio.channels, playS: +info.audio.playS.toFixed(3) } : null,
    mbitPerS: +((bytes.length * 8) / info.durationS / 1e6).toFixed(2),
    playback: { ok: play.ok, detail: play.detail, audioDecodedBytes: play.audioPlayback },
    audio: play.audio ? play.audio.levels : null, sync, frames, qrPage, qrVideo, warnings, problems: p,
  };
}

/** Im Browser: abspielen (Bild, Ton), Ton dekodieren (Pegel, Satzanfänge), Bilder mit den gerenderten vergleichen. */
async function playCheck(bytes, F, expected, { expected: onsetsExpected, refs }) {
  // Eigener Ursprung statt file://, damit das Videobild in ein Canvas gelesen werden darf. Kleiner HTTP-Server nur auf
  // 127.0.0.1 (kein Netz nach außen); große Dateien (Tutorial > 100 MB) gehen so nicht durch das Playwright-Protokoll.
  const server = createServer((req, res) => {
    if (!req.url.endsWith('.mp4')) { res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); res.end('<!doctype html><title>Prüfung</title>'); return; }
    const m = /bytes=(\d+)-(\d*)/.exec(req.headers.range || '');
    if (!m) { res.writeHead(200, { 'Content-Type': 'video/mp4', 'Content-Length': bytes.length, 'Accept-Ranges': 'bytes' }); res.end(bytes); return; }
    const from = Number(m[1]), to = m[2] ? Math.min(Number(m[2]), bytes.length - 1) : bytes.length - 1;
    res.writeHead(206, { 'Content-Type': 'video/mp4', 'Content-Length': to - from + 1, 'Accept-Ranges': 'bytes', 'Content-Range': `bytes ${from}-${to}/${bytes.length}` });
    res.end(bytes.subarray(from, to + 1));
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const page = await browser.newPage();
  try {
    await page.goto(origin + '/');
    return await page.evaluate(async ({ src, w, h, expected, onsetsExpected, refs }) => {
      const out = { ok: false };
      const v = document.createElement('video');
      v.preload = 'auto'; v.src = src;
      document.body.append(v);
      const can = v.canPlayType('video/mp4; codecs="avc1.640028, mp4a.40.2"');
      await new Promise((res, rej) => { v.onloadeddata = res; v.onerror = () => rej(new Error('Fehler ' + (v.error && v.error.code))); setTimeout(() => rej(new Error('Zeitüberschreitung')), 20000); });
      if (v.videoWidth !== w || v.videoHeight !== h) return { ok: false, reason: `Größe ${v.videoWidth}x${v.videoHeight}` };
      if (Math.abs(v.duration - expected) > 0.2) return { ok: false, reason: `Dauer ${v.duration}` };
      // abspielen mit Ton (Autoplay ist für diesen Browser freigeschaltet)
      v.muted = false; v.volume = 1;
      const t0 = v.currentTime;
      const w0 = performance.now();
      await v.play();
      // spielen lassen, bis 1 s Video gelaufen ist (Pufferung am Anfang; höchstens 8 s warten)
      while (v.currentTime - t0 < 1.0 && performance.now() - w0 < 8000) await new Promise((r) => setTimeout(r, 100));
      v.pause();
      out.audioPlayback = v.webkitAudioDecodedByteCount || 0;
      const advanced = v.currentTime - t0;
      const wall = (performance.now() - w0) / 1000;
      const c = document.createElement('canvas'); c.width = 64; c.height = 64;
      const g = c.getContext('2d', { willReadFrequently: true });
      const seekTo = (t) => new Promise((res) => { v.onseeked = res; v.currentTime = t; });
      const means = [];
      for (const t of [0.5, v.duration / 2, v.duration - 0.3]) {
        await seekTo(t);
        g.drawImage(v, 0, 0, 64, 64);
        const d = g.getImageData(0, 0, 64, 64).data;
        let s = 0; for (let i = 0; i < d.length; i += 4) s += d[i] + d[i + 1] + d[i + 2];
        means.push(Math.round(s / (d.length / 4) / 3));
      }
      if (means.some((m) => m < 8)) return { ok: false, reason: `schwarzes Bild (${means.join('/')})` };
      if (!(advanced >= 1.0)) return { ok: false, reason: `Wiedergabe läuft nicht (${advanced.toFixed(2)} s in ${wall.toFixed(1)} s)`, audioPlayback: out.audioPlayback };
      // Bild-Synchronität: dekodierte Bilder gegen die gerenderten Bezugsbilder
      const cw = 96, ch = Math.round((96 * h) / w);
      const gray = (src) => { const cc = document.createElement('canvas'); cc.width = cw; cc.height = ch; const gg = cc.getContext('2d', { willReadFrequently: true }); gg.drawImage(src, 0, 0, cw, ch); const d = gg.getImageData(0, 0, cw, ch).data; const o = new Float32Array(cw * ch); for (let i = 0; i < o.length; i++) o[i] = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2]; return o; };
      const diffs = [];
      for (const r of refs) {
        const img = new Image(); img.src = 'data:image/jpeg;base64,' + r.jpeg; await img.decode();
        await seekTo(r.t);
        const a = gray(img), b = gray(v);
        let s = 0; for (let i = 0; i < a.length; i++) s += Math.abs(a[i] - b[i]);
        diffs.push(+(s / a.length).toFixed(2));
      }
      out.frames = { checked: diffs.length, maxDiff: diffs.length ? Math.max(...diffs) : null, diffs };
      // Ton dekodieren: Pegel und Satzanfänge
      const buf = await (await fetch(src)).arrayBuffer();
      let audio = null;
      try {
        const ctx = new OfflineAudioContext(1, 48000, 48000);
        const ab = await ctx.decodeAudioData(buf);
        const pcm = ab.getChannelData(0), sr = ab.sampleRate;
        const win = Math.round(0.05 * sr);
        let peak = 0, voiced = 0, windows = 0, sum = 0;
        for (let i = 0; i < pcm.length; i++) peak = Math.max(peak, Math.abs(pcm[i]));
        for (let a = 0; a + win <= pcm.length; a += win) { let s = 0; for (let i = a; i < a + win; i++) s += pcm[i] * pcm[i]; const rms = Math.sqrt(s / win); windows++; if (rms > 0.01) { voiced++; sum += rms * rms; } }
        const db = (x) => (x > 0 ? +(20 * Math.log10(x)).toFixed(1) : -999);
        const ds = onsetsExpected.map((t) => {
          const a = Math.max(0, Math.floor((t - 0.2) * sr)), z = Math.min(pcm.length, Math.ceil((t + 0.4) * sr));
          for (let i = a; i < z; i++) if (Math.abs(pcm[i]) >= 0.03) return +(i / sr - t).toFixed(4);
          return null;
        });
        audio = { durationS: +(pcm.length / sr).toFixed(3), levels: { peakDb: db(peak), voicedRmsDb: voiced ? db(Math.sqrt(sum / voiced)) : -999, voicedRatio: windows ? +(voiced / windows).toFixed(3) : 0 }, diffs: ds };
      } catch (e) { audio = null; out.audioError = String(e); }
      out.audio = audio;
      // letztes Bild (Schlusstafel mit QR-Code) in voller Größe
      await seekTo(v.duration - 0.2);
      const big = document.createElement('canvas'); big.width = w; big.height = h;
      big.getContext('2d').drawImage(v, 0, 0, w, h);
      out.last = big.toDataURL('image/png').split(',')[1];
      out.ok = true;
      out.detail = `canPlayType=${can || "leer"}, Helligkeit ${means.join("/")}, ${advanced.toFixed(2)} s in ${wall.toFixed(1)} s abgespielt`;
      return out;
    }, { src: origin + '/video.mp4', w: F.width, h: F.height, expected, onsetsExpected, refs });
  } catch (e) {
    return { ok: false, reason: e.message };
  } finally {
    await page.close().catch(() => {});
    server.close();
  }
}
