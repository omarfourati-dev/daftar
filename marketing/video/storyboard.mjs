// Schreibt storyboard.md aus story.js (Aufruf: node render.mjs --storyboard). Texte, Bilder und (geschätzte) Dauern
// kommen nur aus story.js, timing.js und shared/shots.mjs – so bleibt das Storyboard gleich mit dem, was gerendert wird.
// Die genauen Dauern hängen von der Sprechdauer ab (Azure TTS) und stehen nach dem Lauf in sprechtexte.md.

import { writeFileSync } from 'node:fs';
import { VIDEO_SHOTS } from '../shared/shots.mjs';

const fmt = (s) => {
  const m = Math.floor(s / 60);
  const sec = +(s - m * 60).toFixed(1);
  return `${m}:${sec < 10 ? '0' : ''}${String(sec).replace('.', ',')}`;
};
const cell = (t) => String(t ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ');
const ART = {
  phone: 'Telefon klingelt, im Heft wird radiert und neu geschrieben', double: 'Doppelbuchung im Heft, roter Kreis',
  salle: 'volles Wartezimmer, „C’est quand mon tour ?“, Streit um die Reihenfolge', calls: 'Liste mit Telefonnummern wird abtelefoniert, Uhr rast',
  notes: 'Zettel mit Restbeträgen, Geld, Summe „= ?“', absent: 'Stempel „absent“ an drei Tagen, „reste 120 DT ?“',
  overview: 'Kacheln „Encaissé / Montants dus / Absences“ mit roten Fragezeichen', leave: 'Uhr läuft, zwei Patienten stehen auf und gehen',
  lost: 'Heft fällt, Seiten fliegen weg, leerer Umriss mit „?“',
};

export function writeStoryboard(story, LIB, file) {
  const plan = (f, lang) => LIB.plan(story[f], { defaults: story.timing[f], seconds: (i, k) => LIB.estimate(story[f][i].say[k][lang], lang, story.rate[f]) });
  const out = [];
  out.push(`# Daftar – Werbevideo „Vorher → mit Daftar“: Storyboard

> Erzeugt aus \`story.js\` mit \`node render.mjs --storyboard\` – Änderungen bitte dort, nicht hier.
> Dauern hier geschätzt; die echten Dauern ergeben sich aus der Sprechdauer (Azure TTS) und stehen in \`sprechtexte.md\`.

**Ziel:** Sekretariat und Ärztin/Arzt einer Praxis in Tunesien (alle Fachrichtungen) erkennen ihre Alltagsprobleme
wieder und sehen zu jedem Problem, was Daftar konkret ändert – mit echten Screenshots der Demo-Praxis. Danach: Demo.

**Fassungen** (je FR und AR, mit Stimme: FR \`${story.voices.fr.voice}\`, AR \`${story.voices.ar.voice}\` in tunesischem Derja)

| Fassung | Größe | Länge (geschätzt FR/AR) | Grenze | Für |
|---|---|---|---|---|
| vertikal | 1080 × 1920 | ${fmt(plan('v', 'fr').total)} / ${fmt(plan('v', 'ar').total)} | ≤ 60 s, < 16 MB | WhatsApp (Chat, Status), Reels |
| quer | 1920 × 1080 | ${fmt(plan('h', 'fr').total)} / ${fmt(plan('h', 'ar').total)} | etwa 90–120 s | YouTube, LinkedIn, E-Mail |

**Aufbau:** Aufhänger (Heft) → je Schmerzpunkt eine Szene in zwei Phasen: *vorher* (gezeichnete Szene, Etikett
„À l’accueil“ bzw. „Pour le médecin“) und *mit Daftar* (echte Aufnahmen, Etikett „Avec Daftar“, wichtige Stelle gelb
umrandet). Der Wechsel kommt genau dann, wenn die Stimme auf „Avec Daftar …“ wechselt. → Schluss mit QR-Code zu
https://daftar.omarfourati.de und Preis wie auf der Landing.

**Versprechen geprüft** gegen die Spezifikation und die Landing: Rappels öffnen WhatsApp/SMS mit fertigem Text (kein
automatischer Versand); Doppelbuchungen lehnt die Datenbank ab; Daten auf einem Server bei IONOS in Deutschland,
Verbindung HTTPS; Online-Buchung rund um die Uhr auf der Praxisseite; Kasse mit Tagesabschluss und offenen Beträgen.
`);

  for (const f of ['v', 'h']) {
    const pf = plan(f, 'fr');
    out.push(`\n## ${f === 'v' ? 'Vertikal 1080 × 1920' : 'Quer 1920 × 1080'} – ≈ ${fmt(pf.total)} (FR)\n`);
    out.push('| # | Zeit (FR, ≈) | Szene | Bild | Bildtext FR | Bildtext AR | Aufnahmen |');
    out.push('|---|---|---|---|---|---|---|');
    story[f].forEach((s, i) => {
      const t = pf.scenes[i];
      const time = `${fmt(t.start)}–${fmt(t.start + t.dur)}`;
      if (s.kind === 'pair') {
        const fr = `vorher: **${s.pain.title.fr}**<br>mit Daftar: **${s.fix.title.fr}**`;
        const ar = `قبل: **${s.pain.title.ar}**<br>مع دفتر: **${s.fix.title.ar}**`;
        const shots = s.fix.shots.map((sh) => `\`${sh.id}\`${sh.mark ? ' (markiert)' : ''}`).join('<br>');
        out.push(`| ${i + 1} | ${time} | vorher → mit Daftar (${s.pain.who === 'accueil' ? 'Sekretariat' : 'Ärztin/Arzt'}) | ${cell(ART[s.pain.art])} | ${cell(fr)} | <span dir="rtl">${cell(ar)}</span> | ${shots} |`);
      } else {
        const text = (l) => [s.title ? `**${s.title[l]}**` : '', s.sub ? s.sub[l] : '', s.kind === 'cta' ? `${s.url} · ${s.price[l]} – ${s.priceRest[l]}` : ''].filter(Boolean).join('<br>');
        out.push(`| ${i + 1} | ${time} | ${s.kind} | ${cell(s.note || '')} | ${cell(text('fr'))} | <span dir="rtl">${cell(text('ar'))}</span> | ${s.kind === 'cta' ? 'QR-Code (erzeugt, geprüft)' : 'gezeichnet'} |`);
      }
    });
  }

  out.push(`\n## Screenshots

Video-Aufnahmen in \`video/shots/<id>-<fr|ar>.png\` (\`capture.mjs\`), dazu Aufnahmen aus dem Tutorial (\`t:<id>\` →
\`tutorial/shots/<id>-<fr|ar>.png\`), teils als Ausschnitt.

| id | Ansicht | Was zu sehen ist |
|---|---|---|`);
  for (const s of VIDEO_SHOTS) out.push(`| \`${s.id}\` | ${s.view} | ${cell(s.state)} |`);

  out.push(`\n## Export

\`\`\`powershell
cd "C:\\Users\\ABUS Dev\\daftar\\marketing\\video"
node render.mjs --check-voice      # Azure-Zugang prüfen
node render.mjs                    # alle Fassungen mit Stimme + Tutorial, mit Prüfung (out\\*.pruefung.json)
node render.mjs --sprechtexte      # sprechtexte.md mit gemessenen Dauern
\`\`\`
`);
  writeFileSync(file, out.join('\n') + '\n');
}
