// Schreibt storyboard.md aus story.js (Aufruf: node render.mjs --storyboard). Texte, Dauern und Bilder kommen nur
// aus story.js und shared/shots.mjs – so bleibt das Storyboard immer gleich mit dem, was gerendert wird.

import { writeFileSync } from 'node:fs';
import { VIDEO_SHOTS, TUTORIAL_SHOTS } from '../shared/shots.mjs';

const fmt = (s) => {
  const m = Math.floor(s / 60);
  const sec = +(s - m * 60).toFixed(1);
  return `${m}:${sec < 10 ? '0' : ''}${sec}`;
};
const cell = (t) => String(t ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ');
const KIND = {
  cahier: 'Aufhänger: Heft', double: 'Problem: Doppelbuchung', salle: 'Problem: Wartezimmer', absent: 'Problem: Nichterscheinen',
  brand: 'Wende: Daftar', feature: 'Lösung', langs: 'FR + AR', cta: 'Aufforderung',
};

export function writeStoryboard(story, file) {
  const shotState = Object.fromEntries(VIDEO_SHOTS.map((s) => [s.id, s]));
  const out = [];
  const total = (f) => story[f].reduce((a, s) => a + s.dur, 0);
  out.push(`# Daftar – Werbevideo: Storyboard

> Erzeugt aus \`story.js\` mit \`node render.mjs --storyboard\` – Änderungen bitte dort, nicht hier.

**Ziel:** Ärztinnen und Ärzte in Tunesien (alle Fachrichtungen) sehen in einer Minute, was Daftar am Empfang ändert,
und probieren die Demo aus. Versand per WhatsApp (Status, Chat) und E-Mail, dazu YouTube/LinkedIn.

**Fassungen**

| Fassung | Größe | Länge | Für |
|---|---|---|---|
| vertikal | 1080 × 1920 | ${fmt(total('v'))} | WhatsApp-Status, Reels, Chat (bleibt unter 60 s) |
| quer | 1920 × 1080 | ${fmt(total('h'))} | YouTube, LinkedIn, Link in der E-Mail |

Jede Fassung auf Französisch und Arabisch (Arabisch: ganzes Bild von rechts nach links, Namen in arabischer Schrift).

**Gestaltung:** ohne Sprecher und ohne Musik – alles steht als große Texttafel im Bild, weil die meisten das Video
stumm ansehen. Ruhige Bewegung: Texte und Geräte gleiten in 0,7–1 s ins Bild und stehen dann still; Szenen blenden
in 0,5 s über. Farben, Schrift (IBM Plex Sans Arabic) und Logo wie die Landing; das karierte Heft (Seyès, roter
Rand) ist das Motiv des Aufhängers. Am Ende QR-Code zu https://daftar.omarfourati.de (wird beim Export aus dem
fertigen Video gelesen und geprüft).

**Aufhänger:** das Papierheft der Praxis – Doppelbuchungen, volle Wartezone, Nichterscheinen und offene Beträge, die
im Rand verloren gehen → „Daftar remplace le cahier.“ → fünf bis sieben Funktionen mit echten Screenshots der
Demo-Praxis → Demo ausprobieren.
`);

  for (const f of ['v', 'h']) {
    out.push(`\n## ${f === 'v' ? 'Vertikal 1080 × 1920' : 'Quer 1920 × 1080'} – ${fmt(total(f))}\n`);
    out.push('| # | Zeit | Art | Bild | Text FR | Text AR | Screenshot |');
    out.push('|---|---|---|---|---|---|---|');
    let t = 0;
    story[f].forEach((s, i) => {
      const text = (l) => [s.title ? `**${s.title[l]}**` : '', s.sub ? s.sub[l] : '', s.kind === 'cta' ? `${s.url} · ${s.price[l]} – ${s.priceRest[l]}` : ''].filter(Boolean).join('<br>');
      const fr = text('fr');
      const ar = text('ar');
      const shots = (s.shots ?? []).map((sh) => `\`${sh.id}-${sh.lang === 'other' ? '‹andere›' : '‹lang›'}.png\``).join('<br>') || (s.kind === 'cta' ? 'QR-Code (erzeugt)' : 'gezeichnet');
      out.push(`| ${i + 1} | ${fmt(t)}–${fmt(t + s.dur)} | ${KIND[s.kind]} | ${cell(s.note)} | ${cell(fr)} | <span dir="rtl">${cell(ar)}</span> | ${shots} |`);
      t += s.dur;
    });
  }

  out.push(`\n## Screenshots für das Video

Ordner \`video/shots/\`, je Sprache eine Datei (\`<id>-fr.png\`, \`<id>-ar.png\`). Bis zur Aufnahme stehen dort beschriftete
Platzhalter. \`capture.mjs\` nimmt alle auf (Demo-Praxis, über die Landing gestartet).

| id | Ansicht | Was zu sehen sein muss |
|---|---|---|`);
  for (const s of VIDEO_SHOTS) out.push(`| \`${s.id}\` | ${s.view} | ${cell(s.state)} |`);

  out.push(`\n## Nach dem Deploy: aufnehmen und exportieren

\`\`\`powershell
cd "C:\\Users\\ABUS Dev\\daftar\\marketing\\video"
# 1. Screenshots der Live-App (Demo-Praxis, FR und AR, Desktop und Handy) – ca. 5–10 Minuten
$env:BASE = "https://app.daftar.omarfourati.de"; node capture.mjs
#    nur einzelne Bilder wiederholen:  node capture.mjs --only 18-agenda-jour,v01-agenda-desktop --lang ar
# 2. Video: alle vier Fassungen (FR/AR × vertikal/quer) nach out\\, mit Prüfung – ca. 25–35 Minuten
node render.mjs --strict
# 3. Tutorial-PDFs (FR und AR) – vorher die drei Fotos 04–06 vom Handy/PC in ..\\tutorial\\shots\\ legen
cd ..\\tutorial; node build.mjs --strict
\`\`\`

Ergebnis: \`video/out/daftar-vertical-fr.mp4\`, \`…-vertical-ar.mp4\`, \`…-horizontal-fr.mp4\`, \`…-horizontal-ar.mp4\`
(H.264 High, 30 Bilder/s, MP4 mit \`moov\` vorne, ohne Tonspur) und \`tutorial/tutorial-daftar-fr.pdf\`, \`…-ar.pdf\`.
Vor dem Versand die Datei \`*-letztes-bild.png\` neben jedem Video ansehen (letztes Bild aus dem dekodierten Video, QR-Code
wird daraus gelesen) und \`node render.mjs --stills\` für je ein Standbild pro Szene (\`out/stills/\`).

Von Hand (Browser-Menüs kann Playwright nicht zeigen): ${TUTORIAL_SHOTS.filter((s) => s.mode === 'manual').map((s) => `\`${s.id}\``).join(', ')}
– Zustand siehe Platzhalterbild bzw. \`shared/shots.mjs\`.
`);
  writeFileSync(file, out.join('\n') + '\n');
}
