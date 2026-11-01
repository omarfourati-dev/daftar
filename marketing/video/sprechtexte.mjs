// Schreibt sprechtexte.md (Aufruf: node render.mjs --sprechtexte): alle Sprechtexte FR und tunesisches Derja mit
// Szene, Start und Dauer – zum Gegenlesen. Dauern aus dem TTS-Cache (gemessen) oder geschätzt (≈).

import { writeFileSync } from 'node:fs';

const KIND = {
  cahier: 'Aufhänger', persona: 'Wechsel: Ärztin/Arzt', cta: 'Schluss (QR, Preis)',
  intro: 'Intro (QR)', outro: 'Outro (QR, Preis)', chapter: 'Kapiteltafel',
};
const ART = {
  phone: 'Telefon klingelt, Heft radieren', double: 'Doppelbuchung', salle: 'volles Wartezimmer', calls: 'Erinnerungen am Telefon',
  notes: 'Restbeträge auf Zetteln, Kasse von Hand', absent: 'Nichterscheinen', overview: 'kein Überblick über Einnahmen/offene Beträge',
  leave: 'Patienten wechseln wegen Wartezeit', lost: 'Heft verloren',
};
const WHO = { accueil: 'Sekretariat', medecin: 'Ärztin/Arzt' };

const sec = (s) => s.toFixed(1).replace('.', ',');
const clock = (s) => { const m = Math.floor(s / 60); const r = s - m * 60; return `${m}:${r < 10 ? '0' : ''}${r.toFixed(1).replace('.', ',')}`; };
const q = (t) => (t ? `„${t}“` : '–');

function spokenNote(LIB, text) {
  const d = LIB.display(text), s = LIB.spoken(text);
  return d === s ? '' : ` _(gesprochen: ${s})_`;
}

function line(LIB, label, text, dur, estimated) {
  return `- **${label}** (${estimated ? '≈ ' : ''}${sec(dur)} s): ${LIB.display(text)}${spokenNote(LIB, text)}`;
}

function pubSection(out, LIB, STORY, f, plans) {
  const pf = plans[`pub-${f}-fr`], pa = plans[`pub-${f}-ar`];
  STORY[f].forEach((s, i) => {
    const fr = pf.plan.scenes[i], ar = pa.plan.scenes[i];
    const title = s.kind === 'pair' ? `Vorher → mit Daftar: ${ART[s.pain.art]} (${WHO[s.pain.who]})` : KIND[s.kind] || s.kind;
    out.push(`### ${i + 1} · ${title}`);
    out.push(`FR ${clock(fr.start)}–${clock(fr.start + fr.dur)} (${sec(fr.dur)} s) · AR ${clock(ar.start)}–${clock(ar.start + ar.dur)} (${sec(ar.dur)} s)\n`);
    if (s.kind === 'pair') {
      out.push(`Bild vorher: ${q(s.pain.title.fr)} / ${q(s.pain.title.ar)}  `);
      out.push(`Bild mit Daftar: ${q(s.fix.title.fr)} / ${q(s.fix.title.ar)} – Aufnahmen: ${s.fix.shots.map((x) => '`' + x.id + '`').join(', ')}\n`);
    } else if (s.title) {
      out.push(`Bild: ${q(s.title.fr)} / ${q(s.title.ar)}\n`);
    }
    s.say.forEach((b, k) => {
      const tag = s.kind === 'pair' ? (k === 0 ? ' vorher' : ' mit Daftar') : '';
      out.push(line(LIB, `FR${tag}`, b.fr, fr.beats[k].dur, pf.estimatedSet.has(`${i}.${k}`)));
    });
    s.say.forEach((b, k) => {
      const tag = s.kind === 'pair' ? (k === 0 ? ' vorher' : ' mit Daftar') : '';
      out.push(line(LIB, `Derja${tag}`, b.ar, ar.beats[k].dur, pa.estimatedSet.has(`${i}.${k}`)));
    });
    out.push('');
  });
}

export function writeSprechtexte({ STORY, TUT, LIB, plans, file }) {
  // welche Dauern sind geschätzt? (Clip fehlt im Cache)
  for (const p of Object.values(plans)) {
    p.estimatedSet = new Set();
    (p.clips || []).forEach((row, i) => row.forEach((c, k) => { if (!c) p.estimatedSet.add(`${i}.${k}`); }));
  }
  const anyEstimated = Object.values(plans).some((p) => p.estimatedSet.size);
  const out = [];
  out.push(`# Daftar – Sprechtexte der Videos (FR / tunesisches Derja)

> Erzeugt mit \`node render.mjs --sprechtexte\` aus \`story.js\` (Werbevideo) und \`tutoriel.js\` (Tutorial) –
> Änderungen bitte dort, nicht hier.

**Zum Gegenlesen:** Das Arabische ist der Sprechtext in tunesischem Derja (arabische Schrift), so wie die Stimme ihn
spricht und wie er im Tutorial als Untertitel erscheint. Die Texte im Bild bleiben Hocharabisch (hier je Szene als
„Bild“ angegeben). Kurze Sätze, Zahlen ausgeschrieben; wo die Schrift von der Aussprache abweicht, steht die
gesprochene Form dahinter (SSML \`<sub>\`).

**Stimmen (Azure Neural TTS, \`voice/tts.py\`):** FR \`${STORY.voices.fr.voice}\` · AR \`${STORY.voices.ar.voice}\` – je Sprache
durchgängig dieselbe Stimme, in Werbevideo und Tutorial.

**Dauern:** ${anyEstimated ? '„≈“ = geschätzt aus der Textlänge, weil noch keine Azure-Aufnahme im Cache liegt. Nach dem ersten Lauf mit Stimme neu erzeugen, dann stehen hier die gemessenen Längen.' : 'gemessene Längen der Azure-Aufnahmen (Stille am Anfang/Ende entfernt).'}
Die Szenendauer = Sprechdauer + Pausen (Anfang, zwischen den Sätzen, Ausklang).
`);
  out.push('## Übersicht\n');
  out.push('| Fassung | Tempo FR / AR | Dauer FR | Dauer AR | Ziel |');
  out.push('|---|---|---|---|---|');
  const row = (name, key, goal) => {
    const fr = plans[`${key}-fr`], ar = plans[`${key}-ar`];
    const est = (p) => (p.estimatedSet.size ? '≈ ' : '');
    out.push(`| ${name} | ${fr.rate} / ${ar.rate} | ${est(fr)}${clock(fr.plan.total)} | ${est(ar)}${clock(ar.plan.total)} | ${goal} |`);
  };
  row('Werbevideo hochkant 1080×1920', 'pub-v', '≤ 1:00, < 16 MB');
  row('Werbevideo quer 1920×1080', 'pub-h', 'etwa 1:30–2:00');
  row('Tutorial 1920×1080', 'tutoriel-h', 'etwa 8–10 min');
  out.push('');

  out.push('## 1. Werbevideo hochkant (1080 × 1920, WhatsApp)\n');
  pubSection(out, LIB, STORY, 'v', plans);
  out.push('## 2. Werbevideo quer (1920 × 1080)\n');
  pubSection(out, LIB, STORY, 'h', plans);

  out.push('## 3. Tutorial-Gesamtvideo (1920 × 1080)\n');
  out.push('Untertitel = Sprechtext. Kapitel und Schritte wie im Tutorial-PDF; je Schritt der echte Screenshot.\n');
  const tf = plans['tutoriel-h-fr'], ta = plans['tutoriel-h-ar'];
  TUT.scenes.forEach((s, i) => {
    const fr = tf.plan.scenes[i], ar = ta.plan.scenes[i];
    let head;
    if (s.kind === 'step') head = `#### ${s.chapter.no}.${s.n} ${s.title.fr} · ${s.title.ar}`;
    else if (s.kind === 'chapter') head = `### Kapitel ${s.chapter.no} – ${s.chapter.title.fr} · ${s.chapter.title.ar}`;
    else head = `### ${KIND[s.kind]}`;
    out.push(head);
    out.push(`FR ${clock(fr.start)} (${sec(fr.dur)} s) · AR ${clock(ar.start)} (${sec(ar.dur)} s)${s.shot ? ` · Bild \`${s.shot}\` (${s.view})${s.panel ? ' mit Merkkarte' : ''}` : ''}\n`);
    s.say.forEach((b, k) => out.push(line(LIB, 'FR', b.fr, fr.beats[k].dur, tf.estimatedSet.has(`${i}.${k}`))));
    s.say.forEach((b, k) => out.push(line(LIB, 'Derja', b.ar, ar.beats[k].dur, ta.estimatedSet.has(`${i}.${k}`))));
    out.push('');
  });
  out.push(`## Hinweise zum Derja

- Schreibweise wie man in Tunesien im Chat schreibt (z. B. توّا، برشا، متاع، باش، كان = „wenn/nur“, ولا = „oder“,
  مبعد = „danach“, نومرو، تيكي، الكاسة، الخلاص، السوم، لوّج، فسخ، يحلّ = „öffnen“, ورّى = „zeigen“).
- Knopf- und Menünamen stehen in «…» genau wie in der arabischen Oberfläche (Hocharabisch), damit man sie wiedererkennt.
- Fachwörter aus dem Französischen, wie man sie in der Praxis sagt: الديمو، أونلاين، البي سي، التابلات، الواتساب، الإس إم إس، سيرفور.
- Die Stimme ar-TN spricht tunesisch gefärbt; ob jedes Derja-Wort natürlich klingt, bitte nach dem ersten Lauf anhören
  (Cache: \`marketing/voice/cache/\`, je Satz eine WAV-Datei).
`);
  writeFileSync(file, out.join('\n'));
}
