/* Daftar-Werbevideo: baut die Szenen aus story.js und stellt eine Zeitleiste bereit.
   scenes.html?format=v|h&lang=fr|ar          → Bühne in Videogröße (render.mjs nimmt Bild für Bild auf)
   …&preview=1                                → im Browser abspielen (verkleinert, Leertaste = Pause, Pfeile = ±1 s)
   …&t=12.5                                   → Standbild bei 12,5 s
   Zeitplan: window.DAFTAR_PLAN (von render.mjs aus den echten Sprechdauern) oder – in der Vorschau – geschätzt aus
   der Textlänge (timing.js). Jede Szene dauert so lange wie ihr Sprechtext plus Pausen.
   window.timeline = { duration, ready, missing, seek(t) → Zustandsschlüssel, scenes, marks, plan }
   seek(t) ist eine reine Funktion der Zeit: gleiche Zeit → gleiches Bild; gleicher Schlüssel → Bild unverändert. */
(function () {
  'use strict';
  const q = new URLSearchParams(location.search);
  const FORMAT = q.get('format') === 'h' ? 'h' : 'v';
  const LANG = q.get('lang') === 'ar' ? 'ar' : 'fr';
  const OTHER = LANG === 'ar' ? 'fr' : 'ar';
  const RTL = LANG === 'ar';
  const W = FORMAT === 'v' ? 1080 : 1920;
  const H = FORMAT === 'v' ? 1920 : 1080;
  const FADE = 0.5;
  const STORY = window.DAFTAR_STORY;
  const LIB = window.DAFTAR_TIMING_LIB;
  const SCENES = STORY[FORMAT];
  const PLAN = window.DAFTAR_PLAN || LIB.plan(SCENES, {
    defaults: (STORY.timing || {})[FORMAT],
    seconds: (i, k) => LIB.estimate(SCENES[i].say[k][LANG], LANG, (STORY.rate || {})[FORMAT]),
  });

  const html = document.documentElement;
  html.lang = LANG;
  html.dir = RTL ? 'rtl' : 'ltr';
  html.classList.add('fmt-' + FORMAT);
  if (q.has('preview')) html.classList.add('preview');
  const stage = document.getElementById('stage');

  // ---------- kleine Helfer ----------
  function el(tag, cls, attrs, children) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'text') n.textContent = v;
      else if (k === 'style') n.style.cssText = v;
      else n.setAttribute(k, v);
    }
    for (const c of children || []) if (c) n.append(c);
    return n;
  }
  /** Text der Sprache; im Französischen geschütztes Leerzeichen vor : ; ? ! (Typografie) */
  const tx = (t) => (!t ? '' : LANG === 'fr' ? t.fr.replace(/ ([:;?!])/g, ' $1') : t.ar);
  /** x in Lese-Richtung: Abstand vom Zeilenanfang → absolute x-Koordinate der Bühne */
  const X = (fromStart) => (RTL ? W - fromStart : fromStart);
  const ease = (p) => 1 - Math.pow(1 - p, 3);
  const easeInOut = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
  const clamp = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);
  /** Rechteck in Bildanteilen; für Arabisch (RTL-Oberfläche) horizontal gespiegelt */
  const mirror = (r) => (r && RTL ? Object.assign({}, r, { x: 1 - r.x - r.w }) : r);

  const scenes = [];
  let current = null;
  let OFFSET = 0;  // Startzeit der Phase innerhalb der Szene
  let SPEED = 1;   // < 1: Bewegungen der Phase gestaucht (kurze Phase)
  function A(node, type, at, dur, extra) {
    node.classList.add('anim');
    current.anims.push(Object.assign({ node, type, at: OFFSET + at * SPEED, dur: (dur || 0.7) * SPEED, base: '', dist: 50 }, extra || {}));
    return node;
  }

  function tag(kind, t) { return el('span', 'tag tag-' + kind, { text: tx(t) }); }

  function textBlock(s, opts) {
    const o = opts || {};
    const box = el('div', 'text' + (o.card ? ' card' : '') + (o.dark ? ' on-dark' : ''));
    const at = o.at ?? 0.15;
    if (s.tag) box.append(A(tag(s.tag, STORY.who[s.tag]), 'up', Math.max(0, at - 0.1), 0.6));
    box.append(A(el('h1', 'title', { text: tx(s.title) }), 'up', at, 0.8));
    if (s.sub) box.append(A(el('p', 'sub', { text: tx(s.sub) }), 'up', at + 0.35, 0.8));
    return box;
  }

  /** Bildquelle: „t:<id>“ = Tutorial-Aufnahme, sonst Video-Aufnahme; lang: 'other' = andere Sprache */
  function shotSrc(shot) {
    const lang = shot.lang === 'other' ? OTHER : shot.lang || LANG;
    return shot.id.startsWith('t:') ? `../tutorial/shots/${shot.id.slice(2)}-${lang}.png` : `shots/${shot.id}-${lang}.png`;
  }

  /** Bildschirminhalt mit optionalem Ausschnitt (crop) und Hervorhebung (mark), beide in Bildanteilen */
  function screen(shot, at) {
    const wrap = el('div', 'screen-wrap');
    const img = el('img', 'screen', { src: shotSrc(shot), alt: '' });
    wrap.append(img);
    const c = shot.crop ? mirror(shot.crop) : { x: 0, y: 0, w: 1, h: 1 };
    if (shot.crop) {
      wrap.classList.add('cropped');
      wrap.dataset.crop = JSON.stringify(c);
      img.style.cssText = `position:absolute; width:${(100 / c.w).toFixed(3)}%; left:${(-c.x / c.w * 100).toFixed(3)}%; top:${(-c.y / c.h * 100).toFixed(3)}%`;
    }
    if (shot.mark) {
      const m = mirror(shot.mark);
      const pad = 0.012;
      const box = { x: (m.x - pad - c.x) / c.w, y: (m.y - pad - c.y) / c.h, w: (m.w + 2 * pad) / c.w, h: (m.h + 2 * pad) / c.h };
      const mark = el('div', 'mark', { style: `left:${(box.x * 100).toFixed(2)}%; top:${(box.y * 100).toFixed(2)}%; width:${(box.w * 100).toFixed(2)}%; height:${(box.h * 100).toFixed(2)}%` });
      wrap.append(A(mark, 'pop', at + 1.0, 0.45));
    }
    return wrap;
  }

  function device(shot, at) {
    const slot = shot.slot;
    const view = /^card/.test(slot) ? 'card' : /^tv/.test(slot) ? 'tv' : /^(phone|pair)/.test(slot) ? 'phone' : 'browser';
    let node;
    if (view === 'browser') {
      node = el('div', 'device browser slot-' + slot, {}, [
        el('div', 'bar', {}, [el('i'), el('i'), el('i'), el('span', 'url', { text: shot.url || 'app.daftar.omarfourati.de/app' })]),
        screen(shot, at),
      ]);
    } else {
      node = el('div', 'device ' + view + ' slot-' + slot, {}, [screen(shot, at)]);
    }
    const tilt = slot === 'pair-a' ? (RTL ? 'rotate(3deg)' : 'rotate(-3deg)') : slot === 'pair-b' ? (RTL ? 'rotate(-3deg)' : 'rotate(3deg)') : '';
    return A(node, 'rise', at, 1.0, { base: tilt });
  }

  function svg(tag, attrs, children) {
    const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    for (const c of children || []) if (c) n.append(c);
    return n;
  }
  function stext(x, y, text, attrs) {
    const t = svg('text', Object.assign({ x, y, 'font-family': '"Plex Arabic", sans-serif' }, attrs || {}));
    t.textContent = text;
    if (/[؀-ۿ]/.test(text)) t.setAttribute('direction', 'rtl');
    return t;
  }
  /** Bühne für SVG-Illustrationen (viewBox 1000 x 900) auf der Leseend-Seite (h) bzw. unter der Tafel (v) */
  function artBox(root, cls) {
    const box = el('div', 'art ' + (cls || ''));
    const s = svg('svg', { viewBox: '0 0 1000 900', preserveAspectRatio: 'xMidYMid meet' });
    box.append(s);
    root.append(box);
    return s;
  }
  function entryRow(time, who, top, rot, cls, start) {
    const pos = start != null ? ` inset-inline-start:${start}px;` : '';
    return el('div', 'entry' + (cls ? ' ' + cls : ''), { style: `top:${top}px;${pos} transform: rotate(${rot}deg)` }, [
      el('span', 'time', { text: time }), el('span', 'who', { text: who })]);
  }
  const price = (s) => el('p', 'price', {}, [el('strong', '', { text: tx(s.price) }), el('span', '', { text: tx(s.priceRest) })]);

  const ICON = {
    phone: '<svg viewBox="0 0 120 120"><path d="M28 18c6-6 14-6 18 2l9 18c3 6 1 12-4 16l-7 5c5 12 15 22 27 27l5-7c4-5 10-7 16-4l18 9c8 4 8 12 2 18l-9 9c-8 8-24 9-44-5-22-15-38-37-42-54-3-13 1-22 8-29z" fill="#0f766e"/></svg>',
    steth: '<svg viewBox="0 0 120 120" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round"><path d="M30 14v30c0 18 12 30 26 30s26-12 26-30V14"/><path d="M56 74v10c0 14 10 22 22 22s20-8 20-20V66"/><circle cx="98" cy="58" r="10"/><path d="M22 14h16M74 14h16"/></svg>',
    lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><rect x="4" y="10" width="16" height="11" rx="2.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>',
  };
  const iconEl = (name, cls) => { const d = el('div', cls); d.innerHTML = ICON[name]; return d; };

  // ---------- Szenenarten (Probleme: Bildschirm-Illustrationen) ----------
  const BUILD = {
    cahier(s, root) {
      root.append(el('div', 'bg bg-paper'));
      const list = el('div', 'entries');
      const step = FORMAT === 'v' ? 120 : 110;
      STORY.entries[LANG].forEach(([time, who], i) => list.append(A(entryRow(time, who, i * step, RTL ? 1 : -1), 'wipe', 0.35 + i * 0.32, 0.55)));
      root.append(list, textBlock(s, { card: true }));
    },

    /** Telefon klingelt, im Heft wird gesucht, radiert, neu geschrieben */
    phone(s, root) {
      root.append(el('div', 'bg bg-paper'));
      const list = el('div', 'entries');
      const step = FORMAT === 'v' ? 120 : 110;
      const rows = STORY.entries[LANG].slice(0, 6);
      rows.forEach(([time, who], i) => {
        const e = entryRow(time, who, i * step, RTL ? 1 : -1);
        if (i === 1 || i === 3) {
          e.append(A(el('i', 'strike'), 'wipe', 1.0 + (i === 3 ? 0.7 : 0), 0.4));
        }
        list.append(A(e, 'fade', 0, 0.01));
      });
      // radiert und daneben neu geschrieben
      const [t1] = rows[1], [t3] = rows[3];
      const side = FORMAT === 'v' ? 440 : 470;
      list.append(A(el('div', 'smudge', { style: `top:${1 * step - 10}px` }), 'fade', 1.35, 0.4));
      list.append(A(entryRow(t1, rows[4][1], 1 * step - 26, RTL ? 4 : -4, 'second rewrite', side), 'wipe', 1.5, 0.6));
      list.append(A(entryRow(t3, rows[0][1], 3 * step - 26, RTL ? 4 : -4, 'second rewrite', side), 'wipe', 2.2, 0.6));
      root.append(list);
      const ph = iconEl('phone', 'ringing');
      for (let k = 0; k < 3; k++) ph.append(A(el('i', 'wave w' + k), 'pulse', 0.2 + k * 0.12, 0.6, { period: 0.9 }));
      root.append(A(ph, 'ring', 0.2, 0.01, { freq: 9, amp: 9 }));
      root.append(textBlock(s, { card: true }));
    },

    double(s, root) {
      root.append(el('div', 'bg bg-paper'));
      const list = el('div', 'entries');
      const step = FORMAT === 'v' ? 150 : 135;
      const rows = STORY.entries[LANG].slice(1, 5);
      rows.forEach(([time, who], i) => {
        const e = entryRow(time, who, i * step, RTL ? 1 : -1);
        list.append(i === 2 ? e : A(e, 'fade', 0, 0.01));
      });
      // zweiter Name in derselben Zeile, eng darunter gequetscht
      const d = STORY.double;
      list.append(A(entryRow(d.time, d[LANG], 2 * step + (FORMAT === 'v' ? 72 : 64), RTL ? 2 : -2, 'second'), 'wipe', 0.7, 0.7));
      root.append(list);

      // roter Kreis um beide Einträge (Bühnenkoordinaten, in Leserichtung gespiegelt)
      const top0 = FORMAT === 'v' ? 760 : 200;
      const box = FORMAT === 'v' ? { x0: 160, x1: 1030, y0: top0 + 2 * step - 30, y1: top0 + 2 * step + 170 } : { x0: 980, x1: 1840, y0: top0 + 2 * step - 30, y1: top0 + 2 * step + 160 };
      const cx = (box.x0 + box.x1) / 2, cy = (box.y0 + box.y1) / 2, rx = (box.x1 - box.x0) / 2, ry = (box.y1 - box.y0) / 2;
      const ring = svg('svg', { class: 'ring', viewBox: `0 0 ${W} ${H}`, width: W, height: H, style: 'left:0;top:0' });
      const pts = [];
      for (let k = 0; k <= 64; k++) {
        const a = -Math.PI * 0.95 + (k / 64) * Math.PI * 2.12;
        const wobble = 1 + 0.025 * Math.sin(k * 0.9);
        pts.push([X(cx + Math.cos(a) * rx * wobble), cy + Math.sin(a) * ry * wobble]);
      }
      const path = svg('path', { d: 'M' + pts.map((p) => p.map((v) => v.toFixed(1)).join(' ')).join(' L') });
      ring.append(path);
      root.append(ring);
      current.anims.push({ node: path, type: 'draw', at: OFFSET + 1.5 * SPEED, dur: 0.9 * SPEED, len: null });
      root.append(A(el('div', 'bang', { text: '!', style: `left:${X(box.x1 - 30) - 60}px; top:${box.y0 - 110}px` }), 'pop', 2.4, 0.4));
      root.append(textBlock(s, { card: true }));
    },

    salle(s, root) {
      root.append(el('div', 'bg bg-light'));
      const room = el('div', 'room');
      const vb = FORMAT === 'v' ? [960, 900] : [1000, 800];
      const sv = svg('svg', { viewBox: `0 0 ${vb[0]} ${vb[1]}`, preserveAspectRatio: 'xMidYMid meet' });
      const g0 = svg('g');
      g0.append(svg('rect', { x: 0, y: vb[1] - 120, width: vb[0], height: 120, rx: 24, fill: '#ccfbf1' }));
      g0.append(svg('circle', { cx: vb[0] - 120, cy: 90, r: 58, fill: '#fff', stroke: '#134e4a', 'stroke-width': 8 }));
      g0.append(svg('path', { d: `M${vb[0] - 120} 90 V55 M${vb[0] - 120} 90 L${vb[0] - 95} 108`, stroke: '#134e4a', 'stroke-width': 8, 'stroke-linecap': 'round' }));
      sv.append(g0);
      const colors = ['#64748b', '#94a3b8', '#0f766e', '#a8a29e', '#475569', '#5eead4', '#78716c', '#334155', '#99f6e4', '#94a3b8', '#57534e', '#14b8a6'];
      const rowsY = FORMAT === 'v' ? [430, 720] : [370, 640];
      const per = 6;
      let n = 0;
      rowsY.forEach((y) => {
        for (let i = 0; i < per; i++) {
          const x = 90 + i * ((vb[0] - 180) / (per - 1));
          sv.append(svg('rect', { x: x - 58, y: y - 40, width: 116, height: 120, rx: 18, fill: '#e2e8f0' }));
          const p = svg('g', { style: 'transform-box: fill-box; transform-origin: 50% 100%' });
          const c = colors[n % colors.length];
          p.append(svg('rect', { x: x - 46, y: y - 110, width: 92, height: 130, rx: 44, fill: c }));
          p.append(svg('circle', { cx: x, cy: y - 150, r: 38, fill: c }));
          sv.append(p);
          A(p, 'pop', 0.25 + n * 0.11, 0.45);
          n++;
        }
      });
      room.append(sv);
      root.append(room);
      root.append(A(el('div', 'bubble', { text: tx(STORY.bubble) }), 'pop', 1.9, 0.5));
      root.append(A(el('div', 'bubble bubble-2', { text: tx(STORY.bubble2) }), 'pop', 2.5, 0.5));
      root.append(textBlock(s, { card: true }));
    },

    /** Rückrufe am Vorabend: Liste mit Nummern wird abtelefoniert, Uhr läuft */
    calls(s, root) {
      root.append(el('div', 'bg bg-paper'));
      const list = el('div', 'entries calls');
      const step = FORMAT === 'v' ? 118 : 104;
      STORY.entries[LANG].slice(0, 6).forEach(([, who], i) => {
        const e = entryRow(`+216 00 000 0${11 + i * 7}`, who, i * step, RTL ? 0.6 : -0.6, 'num');
        e.querySelector('.time').setAttribute('dir', 'ltr');
        list.append(A(e, 'fade', 0, 0.01));
        list.append(A(el('span', 'tick', { text: '✓', style: `top:${i * step - 6}px` }), 'pop', 0.7 + i * 0.42, 0.3));
      });
      list.append(A(el('div', 'bubble small', { text: tx(STORY.art.calls), style: FORMAT === 'v' ? `top:${6 * step + 10}px` : `top:${-step * 1.05}px` }), 'pop', 0.45, 0.4));
      root.append(list);
      // Uhr mit laufenden Zeigern
      const clock = el('div', 'clock');
      const cs = svg('svg', { viewBox: '0 0 200 200' });
      cs.append(svg('circle', { cx: 100, cy: 100, r: 88, fill: '#fff', stroke: '#134e4a', 'stroke-width': 10 }));
      for (let k = 0; k < 12; k++) {
        const a = (k / 12) * Math.PI * 2;
        cs.append(svg('line', { x1: 100 + Math.sin(a) * 70, y1: 100 - Math.cos(a) * 70, x2: 100 + Math.sin(a) * 78, y2: 100 - Math.cos(a) * 78, stroke: '#134e4a', 'stroke-width': 5, 'stroke-linecap': 'round' }));
      }
      const hour = svg('line', { x1: 100, y1: 100, x2: 100, y2: 58, stroke: '#134e4a', 'stroke-width': 9, 'stroke-linecap': 'round', style: 'transform-origin: 100px 100px' });
      const min = svg('line', { x1: 100, y1: 100, x2: 100, y2: 30, stroke: '#be123c', 'stroke-width': 6, 'stroke-linecap': 'round', style: 'transform-origin: 100px 100px' });
      cs.append(hour, min, svg('circle', { cx: 100, cy: 100, r: 8, fill: '#134e4a' }));
      clock.append(cs);
      current.anims.push({ node: hour, type: 'spin', at: OFFSET, dur: 0.01, deg: 50 / Math.max(SPEED, 0.6), from: 150 });
      current.anims.push({ node: min, type: 'spin', at: OFFSET, dur: 0.01, deg: 600 / Math.max(SPEED, 0.6), from: 0 });
      root.append(A(clock, 'pop', 0.1, 0.5));
      root.append(textBlock(s, { card: true }));
    },

    /** Restbeträge auf Zetteln, abends Kasse von Hand */
    notes(s, root) {
      root.append(el('div', 'bg bg-paper'));
      const box = el('div', 'notes');
      const texts = STORY.art.notes[LANG];
      const pos = FORMAT === 'v'
        ? [[40, 0, -6], [500, 30, 5], [120, 300, 4], [560, 320, -4]]
        : [[0, 0, -6], [420, 20, 5], [60, 250, 4], [470, 270, -5]];
      texts.forEach((t, i) => {
        const [x, y, r] = pos[i];
        box.append(A(el('div', 'note n' + i, { text: t, style: `inset-inline-start:${x}px; top:${y}px` }), 'pop', 0.25 + i * 0.35, 0.4, { base: `rotate(${RTL ? -r : r}deg)` }));
      });
      const cash = el('div', 'cash');
      const cv = svg('svg', { viewBox: '0 0 360 200' });
      for (let k = 0; k < 4; k++) cv.append(svg('rect', { x: 20 + k * 10, y: 70 - k * 12, width: 200, height: 96, rx: 10, fill: ['#86efac', '#4ade80', '#a7f3d0', '#6ee7b7'][k], stroke: '#166534', 'stroke-width': 3 }));
      for (let k = 0; k < 5; k++) cv.append(svg('ellipse', { cx: 290, cy: 170 - k * 16, rx: 48, ry: 14, fill: '#fcd34d', stroke: '#a16207', 'stroke-width': 3 }));
      cash.append(cv);
      box.append(A(cash, 'pop', 1.7, 0.45));
      box.append(A(el('div', 'sum', {}, [el('bdi', '', { text: tx(STORY.art.sum), dir: 'ltr' })]), 'wipe', 2.1, 0.8));
      root.append(box, textBlock(s, { card: true }));
    },

    absent(s, root) {
      root.append(el('div', 'bg bg-paper'));
      const list = el('div', 'entries');
      const step = FORMAT === 'v' ? 170 : 150;
      const [who, word] = STORY.absent[LANG];
      ['12/10', '19/10', '26/10'].forEach((date, i) => {
        list.append(A(entryRow(date, who, i * step, RTL ? 1 : -1), 'fade', 0.1 + i * 0.1, 0.4));
        const stamp = el('div', 'stamp', { text: word, style: `top:${i * step - 6}px; inset-inline-start:${FORMAT === 'v' ? 580 : 540}px` });
        list.append(A(stamp, 'stamp', 0.8 + i * 0.6, 0.35, { base: 'rotate(-8deg)' }));
      });
      const debt = el('div', 'debt', { text: tx(STORY.absent.debt), style: `top:${3 * step + 20}px; inset-inline-start:${FORMAT === 'v' ? 160 : 140}px` });
      list.append(A(debt, 'wipe', 2.9, 0.7));
      root.append(list, textBlock(s, { card: true }));
    },

    /** Kein Überblick: Kacheln mit Fragezeichen */
    overview(s, root) {
      root.append(el('div', 'bg bg-light'));
      const tiles = el('div', 'tiles');
      STORY.art.overview[LANG].forEach((label, i) => {
        const t = el('div', 'tile', {}, [el('span', 'label', { text: label }), A(el('b', 'qm', { text: '?' }), 'pop', 0.9 + i * 0.4, 0.4)]);
        tiles.append(A(t, 'up', 0.2 + i * 0.2, 0.6));
      });
      root.append(tiles, textBlock(s, { card: true }));
    },

    /** Zu lange Wartezeit: Uhr läuft, zwei Patienten stehen auf und gehen */
    leave(s, root) {
      root.append(el('div', 'bg bg-light'));
      const sv = artBox(root, 'leave');
      sv.append(svg('rect', { x: 0, y: 760, width: 1000, height: 140, rx: 24, fill: '#ccfbf1' }));
      // Tür auf der Leseend-Seite
      const doorX = RTL ? 40 : 800;
      sv.append(svg('rect', { x: doorX, y: 330, width: 160, height: 430, rx: 10, fill: '#e2e8f0', stroke: '#94a3b8', 'stroke-width': 6 }));
      sv.append(svg('circle', { cx: RTL ? doorX + 135 : doorX + 25, cy: 560, r: 9, fill: '#64748b' }));
      // Uhr
      sv.append(svg('circle', { cx: 500, cy: 140, r: 90, fill: '#fff', stroke: '#134e4a', 'stroke-width': 10 }));
      const hh = svg('line', { x1: 500, y1: 140, x2: 500, y2: 92, stroke: '#134e4a', 'stroke-width': 10, 'stroke-linecap': 'round', style: 'transform-origin: 500px 140px' });
      const mm = svg('line', { x1: 500, y1: 140, x2: 500, y2: 70, stroke: '#be123c', 'stroke-width': 7, 'stroke-linecap': 'round', style: 'transform-origin: 500px 140px' });
      sv.append(hh, mm, svg('circle', { cx: 500, cy: 140, r: 9, fill: '#134e4a' }));
      current.anims.push({ node: hh, type: 'spin', at: OFFSET, dur: 0.01, deg: 60 / Math.max(SPEED, 0.6), from: 60 });
      current.anims.push({ node: mm, type: 'spin', at: OFFSET, dur: 0.01, deg: 720 / Math.max(SPEED, 0.6), from: 0 });
      sv.append(A(stext(500, 290, tx(STORY.art.wait), { 'text-anchor': 'middle', 'font-size': 56, 'font-weight': 700, fill: '#be123c' }), 'pop', 0.8, 0.4));
      const colors = ['#64748b', '#0f766e', '#a8a29e', '#475569', '#14b8a6'];
      const xs = RTL ? [880, 740, 600, 460, 320] : [120, 260, 400, 540, 680];
      xs.forEach((x, i) => {
        sv.append(svg('rect', { x: x - 55, y: 600, width: 110, height: 130, rx: 18, fill: '#e2e8f0' }));
        const p = svg('g', { style: 'transform-box: fill-box; transform-origin: 50% 100%' }, [
          svg('rect', { x: x - 44, y: 520, width: 88, height: 130, rx: 42, fill: colors[i] }),
          svg('circle', { cx: x, cy: 480, r: 36, fill: colors[i] })]);
        sv.append(p);
        if (i === 3 || i === 4) {
          const dist = (RTL ? doorX + 80 - x : doorX + 80 - x);
          A(p, 'walk', 1.3 + (4 - i) * 0.45, 1.6, { dx: dist });
        } else A(p, 'pop', 0.2 + i * 0.12, 0.4);
      });
      root.append(textBlock(s, { card: true }));
    },

    /** Das Heft geht verloren: es fällt, Seiten fliegen weg, zurück bleibt ein Umriss */
    lost(s, root) {
      root.append(el('div', 'bg bg-paper'));
      const sv = artBox(root, 'lost');
      sv.append(A(svg('rect', { x: 290, y: 190, width: 420, height: 540, rx: 26, fill: 'none', stroke: '#94a3b8', 'stroke-width': 6, 'stroke-dasharray': '22 16' }), 'fade', 1.6, 0.6));
      sv.append(A(stext(500, 520, '?', { 'text-anchor': 'middle', 'font-size': 260, 'font-weight': 700, fill: '#be123c' }), 'pop', 2.1, 0.45));
      for (let k = 0; k < 6; k++) {
        const ang = (k / 6) * Math.PI * 2 + 0.4;
        const pg = svg('rect', { x: 330, y: 230, width: 340, height: 460, rx: 10, fill: '#fffdf7', stroke: '#cbd5e1', 'stroke-width': 4, style: 'transform-box: fill-box; transform-origin: 50% 50%' });
        sv.append(A(pg, 'scatter', 0.7 + k * 0.06, 1.3, { dx: Math.cos(ang) * 520, dy: Math.sin(ang) * 420, rot: (k % 2 ? 1 : -1) * (40 + k * 12) }));
      }
      const book = svg('g', { style: 'transform-box: fill-box; transform-origin: 50% 50%' });
      book.append(svg('rect', { x: 290, y: 190, width: 420, height: 540, rx: 26, fill: '#1e3a8a' }));
      book.append(svg('rect', { x: 330, y: 300, width: 340, height: 110, rx: 14, fill: '#fff' }));
      book.append(stext(500, 372, tx(STORY.art.lost), { 'text-anchor': 'middle', 'font-size': 52, 'font-weight': 700, fill: '#1e3a8a' }));
      for (let k = 0; k < 9; k++) book.append(svg('circle', { cx: 290, cy: 230 + k * 58, r: 12, fill: '#cbd5e1' }));
      sv.append(A(book, 'fall', 0.5, 1.2));
      root.append(textBlock(s, { card: true }));
    },

    // ---------- Lösung, Wechsel, Abschluss ----------
    feature(s, root) {
      root.append(el('div', 'bg bg-light'));
      (s.shots || []).forEach((shot, i) => root.append(device(shot, 0.3 + i * 0.3)));
      if (s.badge) {
        const b = el('div', 'badge', {}, [iconEl('lock', 'ico'), el('span', '', { text: tx(s.badge) })]);
        root.append(A(b, 'pop', 1.3, 0.45));
      }
      root.append(textBlock(s, { card: FORMAT === 'v', at: 0.1 }));
    },

    pair(s, root, timing) {
      const tB = Math.max(1.2, (timing.beats[1] ? timing.beats[1].at : timing.dur * 0.45) - 0.35);
      const painS = Object.assign({}, s.pain, { tag: s.pain.who });
      const fixS = Object.assign({}, s.fix, { tag: 'daftar' });
      // Phase A: das Problem
      const a = el('div', 'phase phase-a scene-' + s.pain.art);
      SPEED = Math.max(0.5, Math.min(1, tB / 3.3));
      BUILD[s.pain.art](painS, a);
      SPEED = 1;
      root.append(a);
      // Phase B: mit Daftar
      const b = el('div', 'phase phase-b');
      OFFSET = tB;
      A(b, 'fade', 0, 0.55);
      BUILD.feature(fixS, b);
      OFFSET = 0;
      root.append(b);
      current.marks.push({ t: tB - 0.05, label: 'vorher' }, { t: timing.dur - 0.05, label: 'mit-daftar' });
    },

    persona(s, root) {
      root.append(el('div', 'bg bg-dark'));
      const block = el('div', 'brand-block persona');
      block.append(A(iconEl('steth', 'persona-icon'), 'pop', 0.05, 0.5));
      block.append(A(el('h1', 'title', { text: tx(s.title) }), 'up', 0.2, 0.6));
      root.append(block);
    },

    brand(s, root) {
      root.append(el('div', 'bg bg-dark'));
      const block = el('div', 'brand-block');
      block.append(A(el('img', 'brand-logo', { src: '../shared/brand/logo-inverse.svg', alt: 'Daftar' }), 'pop', 0.1, 0.8));
      block.append(A(el('h1', 'title', { text: tx(s.title) }), 'up', 0.8, 0.8));
      if (s.sub) block.append(A(el('p', 'sub', { text: tx(s.sub) }), 'up', 1.2, 0.8));
      root.append(block);
    },

    cta(s, root) {
      root.append(el('div', 'bg bg-dark'));
      const box = el('div', 'cta on-dark');
      box.append(A(el('img', 'brand-logo', { src: '../shared/brand/logo-inverse.svg', alt: 'Daftar' }), 'up', 0.1, 0.7));
      box.append(A(el('h1', 'title', { text: tx(s.title) }), 'up', 0.35, 0.8));
      box.append(A(el('p', 'sub', { text: tx(s.sub) }), 'up', 0.65, 0.8));
      const qr = el('div', 'qr-card', {}, [el('img', '', { src: 'img/qr-daftar.svg', alt: 'QR code : ' + s.url })]);
      if (FORMAT === 'v') {
        box.append(A(qr, 'pop', 0.95, 0.6));
        box.append(A(el('p', 'cta-url', { text: s.url }), 'up', 1.2, 0.7));
        box.append(A(price(s), 'up', 1.5, 0.7));
        root.append(box);
      } else {
        box.append(A(el('p', 'cta-url', { text: s.url }), 'up', 0.95, 0.7));
        box.append(A(price(s), 'up', 1.25, 0.7));
        root.append(box, A(qr, 'pop', 0.8, 0.6), A(el('p', 'qr-caption', { text: 'https://' + s.url }), 'fade', 1.2, 0.6));
      }
    },
  };

  // ---------- Aufbau ----------
  SCENES.forEach((s, index) => {
    const timing = PLAN.scenes[index];
    const root = el('section', 'scene scene-' + s.kind, { 'data-index': index });
    current = { index, start: timing.start, dur: timing.dur, beats: timing.beats, node: root, anims: [], marks: [], data: s, shown: false };
    BUILD[s.kind](s, root, timing);
    if (!current.marks.length) current.marks.push({ t: timing.dur - 0.05, label: s.kind });
    stage.append(root);
    scenes.push(current);
  });
  const duration = PLAN.total;

  function apply(a, p, local) {
    const st = a.node.style;
    switch (a.type) {
      case 'fade': st.opacity = p; break;
      case 'up': st.opacity = p; st.transform = `translateY(${((1 - p) * a.dist).toFixed(2)}px)`; break;
      case 'rise': st.opacity = Math.min(1, p * 1.6); st.transform = `${a.base} translateY(${((1 - p) * 160).toFixed(2)}px)`; break;
      case 'pop': st.opacity = p; st.transform = `${a.base} scale(${(0.86 + 0.14 * p).toFixed(4)})`; break;
      case 'stamp': st.opacity = Math.min(1, p * 2); st.transform = `${a.base} scale(${(1.7 - 0.7 * p).toFixed(4)})`; break;
      case 'wipe': {
        const r = ((1 - p) * 100).toFixed(2);
        st.clipPath = RTL ? `inset(-20% 0 -20% ${r}%)` : `inset(-20% ${r}% -20% 0)`;
        break;
      }
      case 'draw':
        if (a.len === null) { a.len = a.node.getTotalLength(); a.node.style.strokeDasharray = a.len; }
        st.strokeDashoffset = (a.len * (1 - p)).toFixed(2);
        st.opacity = p > 0 ? 1 : 0;
        break;
      case 'ring': { // Telefon wackelt in Stößen
        const t = Math.max(0, local - a.at);
        const burst = (t % 1.2) < 0.7 ? 1 : 0;
        st.transform = `rotate(${(Math.sin(t * Math.PI * 2 * a.freq) * a.amp * burst).toFixed(2)}deg)`;
        st.opacity = local >= a.at ? 1 : 0;
        break;
      }
      case 'pulse': {
        const t = local - a.at;
        const ph = t < 0 ? 0 : (t % a.period) / a.period;
        st.opacity = t < 0 ? 0 : (1 - ph).toFixed(3);
        st.transform = `scale(${(0.7 + ph * 0.6).toFixed(3)})`;
        break;
      }
      case 'spin': st.transform = `rotate(${(a.from + Math.max(0, local - a.at) * a.deg).toFixed(2)}deg)`; break;
      case 'walk': {
        const bob = p > 0 && p < 1 ? Math.abs(Math.sin(p * Math.PI * 6)) * -10 : 0;
        st.transform = `translate(${(a.dx * p).toFixed(1)}px, ${(bob - (p > 0 ? 24 : 0)).toFixed(1)}px)`;
        st.opacity = p > 0.85 ? ((1 - p) / 0.15).toFixed(3) : 1;
        break;
      }
      case 'fall':
        st.transform = `translate(0, ${(p * 380).toFixed(1)}px) rotate(${(p * 28).toFixed(2)}deg) scale(${(1 - 0.25 * p).toFixed(3)})`;
        st.opacity = (1 - p).toFixed(3);
        break;
      case 'scatter':
        st.transform = `translate(${(a.dx * p).toFixed(1)}px, ${(a.dy * p).toFixed(1)}px) rotate(${(a.rot * p).toFixed(1)}deg)`;
        st.opacity = p <= 0 ? 0 : (1 - p).toFixed(3);
        break;
    }
  }
  const CONTINUOUS = new Set(['ring', 'pulse', 'spin']);

  function seek(t) {
    let key = '';
    for (const s of scenes) {
      const local = t - s.start;
      const last = s.index === scenes.length - 1;
      const visible = local >= 0 && (last || local < s.dur + FADE);
      if (!visible) {
        if (s.shown) { s.node.style.visibility = 'hidden'; s.shown = false; }
        continue;
      }
      if (!s.shown) { s.node.style.visibility = 'visible'; s.shown = true; }
      const o = s.index === 0 ? 1 : easeInOut(clamp(local / FADE));
      s.node.style.opacity = o;
      key += s.index + ':' + o.toFixed(3) + '|';
      for (const a of s.anims) {
        const p = ease(clamp((local - a.at) / a.dur));
        apply(a, p, local);
        key += (CONTINUOUS.has(a.type) && local >= a.at ? local.toFixed(3) : p.toFixed(3)) + ',';
      }
    }
    return key;
  }

  /** Hochformat: Geräte unter die Texttafel der jeweiligen Phase setzen (Höhe hängt von Sprache und Text ab). */
  function layout() {
    for (const w of stage.querySelectorAll('.screen-wrap.cropped')) {
      const img = w.querySelector('img');
      const c = JSON.parse(w.dataset.crop);
      if (img.naturalWidth) w.style.aspectRatio = `${(img.naturalWidth * c.w).toFixed(1)} / ${(img.naturalHeight * c.h).toFixed(1)}`;
    }
    if (FORMAT !== 'v') return;
    for (const box of stage.querySelectorAll('.scene, .phase')) {
      const card = [...box.children].find((c) => c.classList.contains('text') && c.classList.contains('card'));
      if (!card) continue;
      const bottom = card.offsetTop + card.offsetHeight;
      for (const d of box.querySelectorAll(':scope > .device')) {
        if (/slot-(card-front|tv-front|phone-front)/.test(d.className)) continue; // unten verankert
        const base = d.classList.contains('slot-pair-b') ? 60 : 0;
        d.style.top = Math.max(d.offsetTop, bottom + 70 + base) + 'px';
      }
    }
  }

  const imgs = [...stage.querySelectorAll('img')];
  const ready = Promise.all([
    document.fonts.ready,
    ...imgs.map((i) => (i.complete ? Promise.resolve() : new Promise((r) => { i.onload = r; i.onerror = r; }))),
  ]).then(() => Promise.all(imgs.map((i) => (i.naturalWidth ? i.decode().catch(() => {}) : null)))).then(layout);

  window.timeline = {
    format: FORMAT, lang: LANG, width: W, height: H, duration, seek, ready, plan: PLAN,
    get missing() { return imgs.filter((i) => !i.naturalWidth).map((i) => i.getAttribute('src')); },
    scenes: scenes.map((s) => ({ index: s.index, start: s.start, dur: s.dur, kind: s.data.kind, art: s.data.pain ? s.data.pain.art : null })),
    marks: scenes.flatMap((s) => s.marks.map((m) => ({ t: +(s.start + m.t).toFixed(3), scene: s.index, label: m.label }))),
  };

  // ---------- Vorschau im Browser ----------
  seek(Number(q.get('t')) || 0);
  if (q.has('preview')) {
    const fit = () => { const k = Math.min(innerWidth / W, innerHeight / H); stage.style.transform = `scale(${k})`; };
    addEventListener('resize', fit); fit();
    let t0 = performance.now(), base = Number(q.get('t')) || 0, paused = false, now = base;
    addEventListener('keydown', (e) => {
      if (e.key === ' ') { paused = !paused; base = now; t0 = performance.now(); }
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { base = Math.max(0, now + (e.key === 'ArrowRight' ? 1 : -1)); t0 = performance.now(); seek(base); now = base; }
    });
    const loop = () => { if (!paused) { now = (base + (performance.now() - t0) / 1000) % duration; seek(now); } requestAnimationFrame(loop); };
    ready.then(() => requestAnimationFrame(loop));
  }
})();
