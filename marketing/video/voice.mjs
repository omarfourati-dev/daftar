// Stimme für die Daftar-Videos: Sprechtexte → Aufträge für voice/tts.py (Azure Neural TTS) → WAV → gekürzt,
// gemischt auf die Zeitleiste. Der Azure-Schlüssel bleibt in tts.py; dieses Modul sieht ihn nie.
//
//   jobsFor(scenes, voices, lang, rate, prefix)    → [{ id, voice, lang, body, rate, scene, beat }]
//   synthesize(jobs, { offline })                   → { code, entries: Map(id → { wav, seconds }) }  (code 2 = Schlüssel)
//   readWav(path)                                    → { sampleRate, pcm: Float32Array (mono) }
//   trimSilence(pcm, sampleRate)                     → Float32Array ohne Stille am Anfang/Ende (25 ms Rand)
//   mix(items: [{ t, pcm }], totalS, sampleRate)     → { pcm: Float32Array, gain } auf −1 dBFS Spitze normiert
//   testTone(seconds, sampleRate)                    → sprachähnliches Prüfsignal (nur für --test-tone)
//   onsets(pcm, sampleRate, times)                   → erster Einsatz über Schwelle nahe jeder Zeit (Synchronprüfung)
//   levels(pcm, sampleRate)                          → { peakDb, voicedRmsDb, voicedRatio }

import { spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { MARKETING } from '../shared/lib.mjs';

export const TTS_PY = join(MARKETING, 'voice', 'tts.py');
const WORK = join(MARKETING, 'voice', 'cache');

export function jobsFor(scenes, voices, lang, rate, prefix) {
  const v = voices[lang];
  const jobs = [];
  scenes.forEach((s, i) => (s.say || []).forEach((b, k) => {
    jobs.push({ id: `${prefix}-${lang}-${i}-${k}`, voice: v.voice, lang: v.lang, body: b[lang], rate, scene: i, beat: k });
  }));
  return jobs;
}

/** tts.py ausführen (Schlüssel bleibt dort). offline: nur Cache lesen, kein Netz. */
export function synthesize(jobs, { offline = false, tag = 'jobs' } = {}) {
  mkdirSync(WORK, { recursive: true });
  const jf = join(WORK, `${tag}.jobs.json`);
  const of = join(WORK, `${tag}.manifest.json`);
  writeFileSync(jf, JSON.stringify(jobs.map(({ id, voice, lang, body, rate }) => ({ id, voice, lang, body, rate })), null, 1));
  const args = [TTS_PY, '--jobs', jf, '--out', of];
  if (offline) args.push('--offline');
  const r = spawnSync(process.env.PYTHON || 'python', args, { stdio: ['ignore', 'inherit', 'inherit'], encoding: 'utf8' });
  const code = r.status ?? 1;
  const entries = new Map();
  if (code === 0) for (const e of JSON.parse(readFileSync(of, 'utf8'))) entries.set(e.id, e);
  return { code, entries };
}

export function readWav(path) {
  const b = readFileSync(path);
  if (b.toString('latin1', 0, 4) !== 'RIFF' || b.toString('latin1', 8, 12) !== 'WAVE') throw new Error(`keine WAV-Datei: ${path}`);
  let p = 12, fmt = null, data = null;
  while (p + 8 <= b.length) {
    const id = b.toString('latin1', p, p + 4), len = b.readUInt32LE(p + 4);
    if (id === 'fmt ') fmt = { format: b.readUInt16LE(p + 8), channels: b.readUInt16LE(p + 10), sampleRate: b.readUInt32LE(p + 12), bits: b.readUInt16LE(p + 22) };
    if (id === 'data') { data = b.subarray(p + 8, Math.min(b.length, p + 8 + len)); break; }
    p += 8 + len + (len & 1);
  }
  if (!fmt || !data || fmt.format !== 1 || fmt.bits !== 16) throw new Error(`WAV nicht PCM 16 bit: ${path}`);
  const n = Math.floor(data.length / 2 / fmt.channels);
  const pcm = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    let s = 0;
    for (let c = 0; c < fmt.channels; c++) s += data.readInt16LE((i * fmt.channels + c) * 2);
    pcm[i] = s / fmt.channels / 32768;
  }
  return { sampleRate: fmt.sampleRate, pcm };
}

export function trimSilence(pcm, sampleRate, { threshold = 0.004, keepMs = 25 } = {}) {
  let a = 0, z = pcm.length - 1;
  while (a < pcm.length && Math.abs(pcm[a]) < threshold) a++;
  while (z > a && Math.abs(pcm[z]) < threshold) z--;
  const keep = Math.round((keepMs / 1000) * sampleRate);
  return pcm.slice(Math.max(0, a - keep), Math.min(pcm.length, z + 1 + keep * 2));
}

export function mix(items, totalS, sampleRate, { peak = 0.89 } = {}) {
  const out = new Float32Array(Math.ceil(totalS * sampleRate));
  const fade = Math.round(0.006 * sampleRate);
  for (const { t, pcm } of items) {
    const o = Math.round(t * sampleRate);
    for (let i = 0; i < pcm.length && o + i < out.length; i++) {
      const g = Math.min(1, i / fade, (pcm.length - 1 - i) / fade);
      out[o + i] += pcm[i] * g;
    }
  }
  let m = 0;
  for (let i = 0; i < out.length; i++) m = Math.max(m, Math.abs(out[i]));
  const gain = m > 0 ? peak / m : 1;
  for (let i = 0; i < out.length; i++) out[i] *= gain;
  return { pcm: out, gain };
}

/** Sprachähnliches Prüfsignal (nur zum Testen der Tonkette ohne Azure): Grundton mit Obertönen, Silben-Hüllkurve. */
export function testTone(seconds, sampleRate) {
  const n = Math.max(1, Math.round(seconds * sampleRate));
  const pcm = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const t = i / sampleRate;
    const f0 = 190 + 25 * Math.sin(2 * Math.PI * 0.7 * t);
    const env = 0.55 + 0.45 * Math.abs(Math.sin(2 * Math.PI * 2.2 * t));
    pcm[i] = 0.32 * env * (Math.sin(2 * Math.PI * f0 * t) + 0.5 * Math.sin(4 * Math.PI * f0 * t) + 0.25 * Math.sin(6 * Math.PI * f0 * t));
  }
  return pcm;
}

/** Erster Einsatz über `threshold` im Fenster [t − before, t + after] je erwarteter Zeit (in Sekunden, null = keiner) */
export function onsets(pcm, sampleRate, times, { threshold = 0.03, before = 0.2, after = 0.4 } = {}) {
  return times.map((t) => {
    const a = Math.max(0, Math.floor((t - before) * sampleRate)), z = Math.min(pcm.length, Math.ceil((t + after) * sampleRate));
    for (let i = a; i < z; i++) if (Math.abs(pcm[i]) >= threshold) return i / sampleRate;
    return null;
  });
}

export function levels(pcm, sampleRate) {
  const win = Math.round(0.05 * sampleRate);
  let peak = 0, voiced = 0, windows = 0, sum = 0;
  for (let i = 0; i < pcm.length; i++) peak = Math.max(peak, Math.abs(pcm[i]));
  for (let a = 0; a + win <= pcm.length; a += win) {
    let s = 0;
    for (let i = a; i < a + win; i++) s += pcm[i] * pcm[i];
    const rms = Math.sqrt(s / win);
    windows++;
    if (rms > 0.01) { voiced++; sum += rms * rms; }
  }
  const db = (x) => (x > 0 ? 20 * Math.log10(x) : -Infinity);
  return { peakDb: +db(peak).toFixed(1), voicedRmsDb: voiced ? +db(Math.sqrt(sum / voiced)).toFixed(1) : -Infinity, voicedRatio: windows ? +(voiced / windows).toFixed(3) : 0 };
}
