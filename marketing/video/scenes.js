/* Daftar-Video: baut die Szenen aus story.js und stellt eine Zeitleiste bereit.
   scenes.html?format=v|h&lang=fr|ar          → Bühne in Videogröße (render.mjs nimmt Bild für Bild auf)
   …&preview=1                                → im Browser abspielen (verkleinert, Leertaste = Pause, Pfeile = ±1 s)
   …&t=12.5                                   → Standbild bei 12,5 s
   window.timeline = { duration, ready, missing, seek(t) → Zustandsschlüssel, scenes }
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
  const tx = (t) => (!t ? '' : LANG === 'fr' ? t.fr.replace(/ ([:;?!])/g, '\u00a0$1') : t.ar);
  /** x in Lese-Richtung: Abstand vom Zeilenanfang → absolute x-Koordinate der Bühne */
  const X = (fromStart) => (RTL ? W - fromStart : fromStart);
  const ease = (p) => 1 - Math.pow(1 - p, 3);
  const easeInOut = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
  const clamp = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);

  const scenes = [];
  let current = null;
  function A(node, type, at, dur, extra) {
    node.classList.add('anim');
    current.anims.push(Object.assign({ node, type, at, dur: dur || 0.7, base: '', dist: 50 }, extra || {}));
    return node;
  }

  function textBlock(s, opts) {
    const o = opts || {};
    const box = el('div', 'text' + (o.card ? ' card' : '') + (o.dark ? ' on-dark' : ''));
    const title = el('h1', 'title', { text: tx(s.title) });
    box.append(A(title, 'up', o.at ?? 0.15, 0.8));
    if (s.sub) box.append(A(el('p', 'sub', { text: tx(s.sub) }), 'up', (o.at ?? 0.15) + 0.35, 0.8));
    return box;
  }

  function shotSrc(shot) {
    const lang = shot.lang === 'other' ? OTHER : shot.lang || LANG;
    return `shots/${shot.id}-${lang}.png`;
  }

  function device(shot, at) {
    const view = /-tv$/.test(shot.id) ? 'tv' : /-mobile$/.test(shot.id) ? 'phone' : 'browser';
    const img = el('img', 'screen', { src: shotSrc(shot), alt: '' });
    let node;
    if (view === 'browser') {
      node = el('div', 'device browser slot-' + shot.slot, {}, [
        el('div', 'bar', {}, [el('i'), el('i'), el('i'), el('span', 'url', { text: shot.url || 'app.daftar.omarfourati.de/app' })]),
        img,
      ]);
    } else {
      node = el('div', 'device ' + view + ' slot-' + shot.slot, {}, [img]);
    }
    const tilt = shot.slot === 'pair-a' ? (RTL ? 'rotate(3deg)' : 'rotate(-3deg)') : shot.slot === 'pair-b' ? (RTL ? 'rotate(-3deg)' : 'rotate(3deg)') : '';
    return A(node, 'rise', at, 1.0, { base: tilt });
  }

  function svg(tag, attrs) {
    const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    return n;
  }

  const price = (s) => el('p', 'price', {}, [el('strong', '', { text: tx(s.price) }), el('span', '', { text: tx(s.priceRest) })]);

  // ---------- Szenenarten ----------
  const BUILD = {
    cahier(s, root) {
      root.append(el('div', 'bg bg-paper'));
      const list = el('div', 'entries');
      const step = FORMAT === 'v' ? 120 : 110;
      STORY.entries[LANG].forEach(([time, who], i) => {
        const e = el('div', 'entry', { style: `top:${i * step}px; transform: rotate(${RTL ? 1 : -1}deg)` }, [
          el('span', 'time', { text: time }), el('span', 'who', { text: who })]);
        list.append(A(e, 'wipe', 0.35 + i * 0.32, 0.55));
      });
      root.append(list, textBlock(s, { card: true }));
    },

    double(s, root) {
      root.append(el('div', 'bg bg-paper'));
      const list = el('div', 'entries');
      const step = FORMAT === 'v' ? 150 : 135;
      const rows = STORY.entries[LANG].slice(1, 5);
      rows.forEach(([time, who], i) => {
        const e = el('div', 'entry', { style: `top:${i * step}px; transform: rotate(${RTL ? 1 : -1}deg)` }, [
          el('span', 'time', { text: time }), el('span', 'who', { text: who })]);
        list.append(i === 2 ? e : A(e, 'fade', 0, 0.01));
      });
      // zweiter Name in derselben Zeile, eng darunter gequetscht
      const d = STORY.double;
      const second = el('div', 'entry second', { style: `top:${2 * step + (FORMAT === 'v' ? 72 : 64)}px; transform: rotate(${RTL ? 2 : -2}deg)` }, [
        el('span', 'time', { text: d.time }), el('span', 'who', { text: d[LANG] })]);
      list.append(A(second, 'wipe', 0.7, 0.7));
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
      current.anims.push({ node: path, type: 'draw', at: 1.5, dur: 0.9, len: null });
      const bang = el('div', 'bang', { text: '!', style: `left:${X(box.x1 - 30) - 60}px; top:${box.y0 - 110}px` });
      root.append(A(bang, 'pop', 2.4, 0.4));
      root.append(textBlock(s, { card: true }));
    },

    salle(s, root) {
      root.append(el('div', 'bg bg-light'));
      const room = el('div', 'room');
      const vb = FORMAT === 'v' ? [960, 900] : [1000, 800];
      const sv = svg('svg', { viewBox: `0 0 ${vb[0]} ${vb[1]}`, preserveAspectRatio: 'xMidYMid meet' });
      const g0 = svg('g');
      // Boden und Wand
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
          const chair = svg('rect', { x: x - 58, y: y - 40, width: 116, height: 120, rx: 18, fill: '#e2e8f0' });
          sv.append(chair);
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
      root.append(textBlock(s, { card: true }));
    },

    absent(s, root) {
      root.append(el('div', 'bg bg-paper'));
      const list = el('div', 'entries');
      const step = FORMAT === 'v' ? 170 : 150;
      const [who, word] = STORY.absent[LANG];
      ['12/10', '19/10', '26/10'].forEach((date, i) => {
        const e = el('div', 'entry', { style: `top:${i * step}px; transform: rotate(${RTL ? 1 : -1}deg)` }, [
          el('span', 'time', { text: date }), el('span', 'who', { text: who })]);
        list.append(A(e, 'fade', 0.1 + i * 0.1, 0.4));
        const stamp = el('div', 'stamp', { text: word, style: `top:${i * step - 6}px; inset-inline-start:${FORMAT === 'v' ? 580 : 540}px` });
        list.append(A(stamp, 'stamp', 0.8 + i * 0.6, 0.35, { base: 'rotate(-8deg)' }));
      });
      const debt = el('div', 'debt', { text: tx(STORY.absent.debt), style: `top:${3 * step + 20}px; inset-inline-start:${FORMAT === 'v' ? 160 : 140}px` });
      list.append(A(debt, 'wipe', 2.9, 0.7));
      root.append(list, textBlock(s, { card: true }));
    },

    brand(s, root) {
      root.append(el('div', 'bg bg-dark'));
      const block = el('div', 'brand-block');
      block.append(A(el('img', 'brand-logo', { src: '../shared/brand/logo-inverse.svg', alt: 'Daftar' }), 'pop', 0.1, 0.8));
      block.append(A(el('h1', 'title', { text: tx(s.title) }), 'up', 0.8, 0.8));
      if (s.sub) block.append(A(el('p', 'sub', { text: tx(s.sub) }), 'up', 1.2, 0.8));
      root.append(block);
    },

    feature(s, root) {
      root.append(el('div', 'bg bg-light'));
      (s.shots || []).forEach((shot, i) => root.append(device(shot, 0.35 + i * 0.35)));
      root.append(textBlock(s, { card: FORMAT === 'v' }));
    },

    langs(s, root) {
      BUILD.feature(s, root);
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
  let start = 0;
  STORY[FORMAT].forEach((s, index) => {
    const root = el('section', 'scene scene-' + s.kind, { 'data-index': index });
    current = { index, start, dur: s.dur, node: root, anims: [], data: s, shown: false };
    BUILD[s.kind](s, root);
    stage.append(root);
    scenes.push(current);
    start += s.dur;
  });
  const duration = start;

  function apply(a, p) {
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
    }
  }

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
        apply(a, p);
        key += p.toFixed(3) + ',';
      }
    }
    return key;
  }

  /** Hochformat: Geräte unter die Texttafel setzen (Höhe der Tafel hängt von Sprache und Text ab). */
  function layout() {
    if (FORMAT !== 'v') return;
    for (const s of scenes) {
      const card = s.node.querySelector('.text.card');
      if (!card) continue;
      const bottom = card.offsetTop + card.offsetHeight;
      for (const d of s.node.querySelectorAll('.device')) {
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
    format: FORMAT, lang: LANG, width: W, height: H, duration, seek, ready,
    get missing() { return imgs.filter((i) => !i.naturalWidth).map((i) => i.getAttribute('src')); },
    scenes: scenes.map((s) => ({ index: s.index, start: s.start, dur: s.dur, kind: s.data.kind })),
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
