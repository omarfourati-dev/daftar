/* Zeitplan der Daftar-Videos: Die Szenendauer richtet sich nach der Länge des Sprechtexts.
   Gemeinsam für scenes.html / tutoriel.html (Browser) und render.mjs (Node, über vm).

   Sprechtexte: einfache Zeichenketten mit wenigen SSML-Tags (sub, say-as, break). Für die Stimme gehen sie als
   SSML an voice/tts.py, für Untertitel zeigt display() den geschriebenen Text, für die Schätzung (ohne Azure)
   zählt spoken() die gesprochene Form.

   plan(scenes, { seconds(sceneIndex, beatIndex) }) → { scenes: [{ start, dur, beats: [{ at, dur }] }], total }
   – lead: Stille am Szenenanfang, gap: Pause zwischen zwei Sätzen (switch: true → längere Pause für den
     Bildwechsel „vorher → mit Daftar“), tail: Ausklang, minDur: Mindestdauer. Werte je Szene überschreibbar. */
(function (root) {
  'use strict';
  const ALLOWED = /^(sub|say-as|break|emphasis|lang|prosody)$/;
  const DEFAULTS = { lead: 0.35, gap: 0.3, switchGap: 0.6, tail: 0.5, minDur: 0 };
  // Zeichen je Sekunde bei Sprechtempo +0 % (Azure Neural, gemessen an ähnlichen Texten; nur für Schätzungen)
  const CPS = { fr: 16.5, ar: 13.5 };

  function spoken(t) {
    return String(t || '')
      .replace(/<sub\s+alias="([^"]*)"\s*>[\s\S]*?<\/sub>/g, '$1')
      .replace(/<break[^>]*\/>/g, ' ')
      .replace(/<[^>]+>/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }
  function display(t) {
    return String(t || '')
      .replace(/<sub\s+alias="[^"]*"\s*>([\s\S]*?)<\/sub>/g, '$1')
      .replace(/<break[^>]*\/>/g, ' ')
      .replace(/<[^>]+>/g, '')
      .replace(/\s+/g, ' ')
      .replace(/\s+([,.،])/g, '$1')
      .trim();
  }
  /** Tags prüfen: nur erlaubte SSML-Elemente, kein & oder < außerhalb von Tags. */
  function checkSsml(t) {
    const problems = [];
    const s = String(t || '');
    for (const m of s.matchAll(/<\/?([a-zA-Z-]+)/g)) if (!ALLOWED.test(m[1])) problems.push(`Tag <${m[1]}> nicht erlaubt`);
    if (/&(?!amp;|lt;|gt;|quot;|apos;)/.test(s)) problems.push('& ohne Maskierung');
    const opened = (s.match(/<(sub|say-as|emphasis|lang|prosody)\b[^>]*[^/]>/g) || []).length;
    const closed = (s.match(/<\/(sub|say-as|emphasis|lang|prosody)>/g) || []).length;
    if (opened !== closed) problems.push('Tags nicht geschlossen');
    return problems;
  }
  function rateFactor(rate) {
    const m = /^([+-]?\d+(?:\.\d+)?)%$/.exec(String(rate || '0%'));
    return 1 + (m ? Number(m[1]) : 0) / 100;
  }
  /** geschätzte Sprechdauer in Sekunden */
  function estimate(text, lang, rate) {
    const s = spoken(text);
    const ends = (s.match(/[.!?؟…:]/g) || []).length;
    const commas = (s.match(/[,،;؛]/g) || []).length;
    return (s.length / (CPS[lang] || 15)) / rateFactor(rate) + 0.2 + 0.22 * ends + 0.1 * commas;
  }

  function plan(scenes, opts) {
    const o = opts || {};
    const out = [];
    let start = 0;
    scenes.forEach((s, i) => {
      const p = Object.assign({}, DEFAULTS, o.defaults || {}, s.timing || {});
      const beats = [];
      let t = i === 0 && p.firstLead != null ? p.firstLead : p.lead;
      (s.say || []).forEach((b, k) => {
        if (k > 0) t += b && b.switch ? p.switchGap : (p.gaps && p.gaps[k - 1] != null ? p.gaps[k - 1] : p.gap);
        const d = o.seconds(i, k);
        beats.push({ at: +t.toFixed(3), dur: +d.toFixed(3) });
        t += d;
      });
      const dur = Math.max(p.minDur, t + p.tail);
      out.push({ index: i, start: +start.toFixed(3), dur: +dur.toFixed(3), beats });
      start += dur;
    });
    return { scenes: out, total: +start.toFixed(3) };
  }

  root.DAFTAR_TIMING_LIB = { spoken, display, checkSsml, estimate, plan, rateFactor, DEFAULTS, CPS };
})(typeof window !== 'undefined' ? window : globalThis);
