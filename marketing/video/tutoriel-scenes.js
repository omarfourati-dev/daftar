/* Tutorial-Video Daftar: baut Intro, Kapiteltafeln, Schritte und Outro aus tutoriel.js und stellt eine Zeitleiste
   bereit (gleiche Schnittstelle wie scenes.js, damit render.mjs beide Filme gleich behandelt).
   tutoriel.html?lang=fr|ar               → Bühne 1920 x 1080 (render.mjs nimmt Bild für Bild auf)
   …&preview=1                            → im Browser abspielen (Leertaste = Pause, Pfeile = ±1 s), …&t=60 → Standbild
   Zeitplan: window.DAFTAR_PLAN (aus den echten Sprechdauern) oder geschätzt aus der Textlänge (timing.js).
   Kamera: je Satz mit Fokus fährt das Bild sanft auf die Stelle (Zoom + Verschieben), ein Rahmen hebt sie hervor;
   dazu ein leichtes Heranfahren über die ganze Szene. Untertitel = gesprochener Text des laufenden Satzes. */
(function () {
  'use strict';
  const q = new URLSearchParams(location.search);
  const LANG = q.get('lang') === 'ar' ? 'ar' : 'fr';
  const RTL = LANG === 'ar';
  const W = 1920, H = 1080, FADE = 0.45;
  const TUT = window.DAFTAR_TUTORIEL;
  const LIB = window.DAFTAR_TIMING_LIB;
  const SCENES = TUT.scenes;
  const PLAN = window.DAFTAR_PLAN || LIB.plan(SCENES, {
    defaults: TUT.timing,
    seconds: (i, k) => LIB.estimate(SCENES[i].say[k][LANG], LANG, TUT.rate),
  });
  const MAXZOOM = { page: 2.3, dialog: 1.55, section: 1.6, mobile: 1.9, tv: 1.25 };

  const html = document.documentElement;
  html.lang = LANG;
  html.dir = RTL ? 'rtl' : 'ltr';
  if (q.has('preview')) html.classList.add('preview');
  const stage = document.getElementById('stage');

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
  const tx = (t) => (!t ? '' : LANG === 'fr' ? t.fr.replace(/ ([:;?!])/g, ' $1') : t.ar);
  const ease = (p) => 1 - Math.pow(1 - p, 3);
  const easeInOut = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
  const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
  const mirror = (r) => (r && RTL ? Object.assign({}, r, { x: 1 - r.x - r.w }) : r);
  const ICON = {
    android: '<svg viewBox="0 0 24 24" fill="#0f766e"><path d="M7 9h10v8a1 1 0 0 1-1 1h-1v3h-2v-3h-2v3H9v-3H8a1 1 0 0 1-1-1zM4.5 9.5a1.2 1.2 0 0 1 2.4 0v5a1.2 1.2 0 0 1-2.4 0zm12.6 0a1.2 1.2 0 0 1 2.4 0v5a1.2 1.2 0 0 1-2.4 0zM7.2 8a4.8 4.8 0 0 1 9.6 0zM9.5 6a.6.6 0 1 0 0 .01zm5 0a.6.6 0 1 0 0 .01z"/></svg>',
    apple: '<svg viewBox="0 0 24 24" fill="#0f766e"><path d="M16.5 12.6c0-2.3 1.9-3.4 2-3.5a4.3 4.3 0 0 0-3.4-1.8c-1.4-.2-2.8.8-3.5.8s-1.8-.8-3-.8a4.5 4.5 0 0 0-3.8 2.3c-1.6 2.8-.4 7 1.2 9.3.8 1.1 1.7 2.4 2.9 2.3 1.2 0 1.6-.7 3-.7s1.8.7 3 .7 2-1.1 2.8-2.3a9.6 9.6 0 0 0 1.3-2.6 4 4 0 0 1-2.5-3.7zM14.2 5.8a4 4 0 0 0 .9-2.9 4.1 4.1 0 0 0-2.7 1.4 3.8 3.8 0 0 0-1 2.8 3.4 3.4 0 0 0 2.8-1.3z"/></svg>',
    pc: '<svg viewBox="0 0 24 24" fill="none" stroke="#0f766e" stroke-width="2" stroke-linecap="round"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4M12 7v5M9.5 9.8 12 12.3l2.5-2.5"/></svg>',
  };

  const scenes = [];
  let current = null;
  function A(node, type, at, dur, extra) {
    node.classList.add('anim');
    current.anims.push(Object.assign({ node, type, at, dur: dur || 0.6, dist: 40 }, extra || {}));
    return node;
  }

  function qrBlock(caption) {
    return el('div', 'qr-block', {}, [
      el('div', 'qr-card', {}, [el('img', '', { src: 'img/qr-daftar.svg', alt: 'QR code : ' + TUT.ui.url })]),
      el('p', 'cap', { text: tx(caption) }),
      el('p', 'url', { text: TUT.ui.url }),
    ]);
  }
  const price = () => el('p', 'price', {}, [el('strong', '', { text: tx(TUT.ui.price) }), el('span', '', { text: tx(TUT.ui.priceRest) })]);

  const BUILD = {
    intro(s, root) {
      root.append(el('div', 'bg bg-dark'));
      const big = el('div', 'big');
      big.append(A(el('img', 'logo', { src: '../shared/brand/logo-inverse.svg', alt: 'Daftar' }), 'up', 0.1, 0.8));
      big.append(A(el('h1', '', { text: tx(TUT.ui.title) }), 'up', 0.4, 0.8));
      big.append(A(el('p', '', { text: tx(TUT.ui.sub) }), 'up', 0.7, 0.8));
      root.append(big, A(qrBlock(TUT.ui.demo), 'pop', 1.0, 0.7));
      current.dark = true;
    },

    chapter(s, root) {
      root.append(el('div', 'bg bg-dark'));
      const c = s.chapter;
      const card = el('div', 'chapter-card');
      card.append(A(el('div', 'no', { text: String(c.no) }), 'pop', 0.05, 0.5));
      card.append(A(el('div', 'lbl', { text: `${tx(TUT.ui.chapter)} ${c.no}` }), 'up', 0.15, 0.6));
      card.append(A(el('h1', '', { text: tx(c.title) }), 'up', 0.25, 0.7));
      card.append(A(el('p', 'who', { text: tx(c.who) }), 'up', 0.45, 0.7));
      root.append(card);
      current.dark = true;
    },

    step(s, root, timing) {
      root.append(el('div', 'bg bg-light'));
      const c = s.chapter;
      const head = el('div', 'head', {}, [
        el('span', 'chip', { text: `${tx(TUT.ui.chapter)} ${c.no} · ${tx(c.title)}` }),
        el('h2', '', {}, [el('span', 'num', { text: `${c.no}.${s.n}` }), document.createTextNode(tx(s.title))]),
      ]);
      root.append(head, el('img', 'mini-logo', { src: '../shared/brand/logo.svg', alt: 'Daftar' }));
      const vp = el('div', 'vp');
      const frame = el('div', 'frame ' + s.view);
      const wrap = el('div', 'shot-wrap');
      const img = el('img', 'shot', { src: `../tutorial/shots/${s.shot}-${LANG}.png`, alt: '' });
      wrap.append(img);
      if (s.view === 'page') frame.append(el('div', 'bar', {}, [el('i'), el('i'), el('i'), el('span', '', { text: 'cabinet-ben-salah.daftar.omarfourati.de/app' })]));
      frame.append(wrap);
      vp.append(frame);
      root.append(vp);
      // je Satz ein Rahmen um die Fokusstelle
      const rings = s.say.map((b) => {
        if (!b.focus) return null;
        const f = mirror(b.focus);
        const r = el('div', 'ring', { style: `left:${(f.x * 100).toFixed(2)}%; top:${(f.y * 100).toFixed(2)}%; width:${(f.w * 100).toFixed(2)}%; height:${(f.h * 100).toFixed(2)}%` });
        wrap.append(r);
        return r;
      });
      if (s.panel) {
        const p = el('div', 'panel');
        const ico = el('div', 'ico'); ico.innerHTML = ICON[s.panel.icon]; // feste SVG-Symbole aus dieser Datei
        p.append(ico, el('ol', '', {}, (LANG === 'fr' ? s.panel.lines.fr : s.panel.lines.ar).map((l) => el('li', '', { text: l }))));
        root.append(A(p, 'pop', 0.5, 0.5));
      }
      current.cam = { vp, frame, wrap, img, view: s.view, rings, beats: timing.beats };
    },

    outro(s, root) {
      root.append(el('div', 'bg bg-dark'));
      const big = el('div', 'big');
      big.append(A(el('img', 'logo', { src: '../shared/brand/logo-inverse.svg', alt: 'Daftar' }), 'up', 0.1, 0.7));
      big.append(A(el('h1', '', { text: tx(TUT.ui.question) }), 'up', 0.3, 0.7));
      big.append(A(el('p', '', { text: tx(TUT.ui.feedback) }), 'up', 0.55, 0.7));
      big.append(A(el('p', 'mail', { text: TUT.ui.mail }), 'up', 0.8, 0.7));
      big.append(A(price(), 'up', 1.05, 0.7));
      root.append(big, A(qrBlock(TUT.ui.demo), 'pop', 0.9, 0.7));
      current.dark = true;
    },
  };

  // ---------- Aufbau ----------
  SCENES.forEach((s, index) => {
    const timing = PLAN.scenes[index];
    const root = el('section', 'scene scene-' + s.kind, { 'data-index': index });
    current = { index, start: timing.start, dur: timing.dur, beats: timing.beats, node: root, anims: [], data: s, shown: false, dark: false };
    BUILD[s.kind](s, root, timing);
    stage.append(root);
    scenes.push(current);
  });
  const duration = PLAN.total;

  // Untertitel und Fortschritt liegen über allen Szenen
  const subs = el('div', 'subs');
  const subBox = el('div', 'box');
  subs.append(subBox);
  const progress = el('div', 'progress');
  stage.append(subs, progress);
  const cues = [];
  scenes.forEach((s) => s.beats.forEach((b, k) => {
    cues.push({ from: s.start + b.at - 0.12, to: s.start + b.at + b.dur + 0.25, text: LIB.display(s.data.say[k][LANG]), dark: s.dark, id: `${s.index}.${k}` });
  }));
  cues.forEach((c, i) => { if (cues[i + 1] && c.to > cues[i + 1].from) c.to = cues[i + 1].from; });

  // ---------- Kamera ----------
  /** Grundlage nach dem Laden: Rahmen so groß wie möglich ins Bildfenster, zentriert */
  function layout() {
    for (const s of scenes) {
      const c = s.cam;
      if (!c || !c.img.naturalWidth) continue;
      const VW = c.vp.clientWidth, VH = c.vp.clientHeight;
      const nw = c.img.naturalWidth, nh = c.img.naturalHeight;
      const padX = c.view === 'mobile' ? 28 : c.view === 'tv' ? 36 : 0;
      const bar = c.view === 'page' ? 41 : 0;
      const margin = c.view === 'page' || c.view === 'tv' ? 34 : 44;
      let k = Math.min((VW - 2 * margin - padX) / nw, (VH - 2 * margin - padX - bar) / nh);
      if (c.view === 'dialog' || c.view === 'section') k = Math.min(k, 1.35);
      const sw = nw * k, sh = nh * k;
      c.frame.style.width = (sw + padX) + 'px';
      c.wrap.style.height = sh + 'px';
      const FW = sw + padX, FH = sh + padX + bar;
      c.base = { VW, VH, FW, FH, x0: (VW - FW) / 2, y0: (VH - FH) / 2, ox: padX / 2, oy: padX / 2 + bar, sw, sh };
      // Kamerastellung je Satz
      let prev = { S: 1, tx: 0, ty: 0 };
      c.keys = c.beats.map((b, i) => {
        const f = s.data.say[i].focus ? mirror(s.data.say[i].focus) : null;
        if (!f) return Object.assign({}, prev, { focus: false });
        const fw = f.w * sw, fh = f.h * sh;
        const S = clamp(Math.min((VW * 0.78) / fw, (VH * 0.72) / fh), 1, MAXZOOM[c.view]);
        const cx = c.base.ox + (f.x + f.w / 2) * sw, cy = c.base.oy + (f.y + f.h / 2) * sh;
        const fit = (V, F, x0, center) => (F * S <= V ? (V - F * S) / 2 - x0 : clamp(V / 2 - x0 - center * S, V - F * S - x0, -x0));
        prev = { S, tx: fit(VW, FW, c.base.x0, cx), ty: fit(VH, FH, c.base.y0, cy) };
        return Object.assign({}, prev, { focus: true });
      });
    }
  }

  function camera(s, local) {
    const c = s.cam;
    if (!c || !c.base) return '';
    let from = { S: 1, tx: 0, ty: 0 }, cur = from;
    let ringOn = -1, ringP = 0;
    for (let i = 0; i < c.keys.length; i++) {
      const key = c.keys[i];
      const t0 = Math.max(0.15, c.beats[i].at - 0.3);
      if (local < t0) break;
      const p = easeInOut(clamp((local - t0) / 1.0));
      cur = { S: from.S + (key.S - from.S) * p, tx: from.tx + (key.tx - from.tx) * p, ty: from.ty + (key.ty - from.ty) * p };
      if (key.focus) { ringOn = i; ringP = clamp((local - t0 - 0.75) / 0.35); }
      else ringOn = -1;
      from = { S: key.S, tx: key.tx, ty: key.ty };
    }
    // leichtes Heranfahren über die ganze Szene (um die Bildmitte)
    const drift = 1 + 0.025 * clamp(local / s.dur);
    const S = cur.S * drift;
    const B = c.base;
    const cx = B.VW / 2, cy = B.VH / 2;
    const x = cx + (B.x0 + cur.tx - cx) * drift, y = cy + (B.y0 + cur.ty - cy) * drift;
    c.frame.style.transform = `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px) scale(${S.toFixed(4)})`;
    c.rings.forEach((r, i) => {
      if (!r) return;
      const on = i === ringOn ? ringP : 0;
      r.style.opacity = on.toFixed(3);
      r.style.borderWidth = (5 / S).toFixed(2) + 'px';
      r.style.borderRadius = (12 / S).toFixed(2) + 'px';
    });
    return `${S.toFixed(4)}:${x.toFixed(1)}:${y.toFixed(1)}:${ringOn}:${ringP.toFixed(2)}`;
  }

  function apply(a, p) {
    const st = a.node.style;
    if (a.type === 'fade') st.opacity = p;
    else if (a.type === 'up') { st.opacity = p; st.transform = `translateY(${((1 - p) * a.dist).toFixed(2)}px)`; }
    else if (a.type === 'pop') { st.opacity = p; st.transform = `scale(${(0.88 + 0.12 * p).toFixed(4)})`; }
  }

  let lastCue = null;
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
      key += camera(s, local) + ';';
    }
    // Untertitel
    const cue = cues.find((c) => t >= c.from && t < c.to) || null;
    if (cue !== lastCue) {
      subBox.textContent = cue ? cue.text : '';
      subs.classList.toggle('on-dark', !!(cue && cue.dark));
      lastCue = cue;
    }
    let so = 0;
    if (cue) so = Math.min(clamp((t - cue.from) / 0.15), clamp((cue.to - t) / 0.12));
    subs.style.opacity = so.toFixed(3);
    subs.style.visibility = cue ? 'visible' : 'hidden';
    key += 'S' + (cue ? cue.id : '-') + so.toFixed(2);
    // Fortschritt (in 0,5-%-Schritten, damit ruhige Bilder ruhig bleiben)
    const pr = Math.round(clamp(t / duration) * 200) / 2;
    progress.style.width = pr + '%';
    key += 'P' + pr;
    return key;
  }

  const imgs = [...stage.querySelectorAll('img')];
  const ready = Promise.all([
    document.fonts.ready,
    ...imgs.map((i) => (i.complete ? Promise.resolve() : new Promise((r) => { i.onload = r; i.onerror = r; }))),
  ]).then(() => Promise.all(imgs.map((i) => (i.naturalWidth ? i.decode().catch(() => {}) : null)))).then(layout);

  window.timeline = {
    format: 'h', lang: LANG, width: W, height: H, duration, seek, ready, plan: PLAN,
    get missing() { return imgs.filter((i) => !i.naturalWidth).map((i) => i.getAttribute('src')); },
    scenes: scenes.map((s) => ({ index: s.index, start: s.start, dur: s.dur, kind: s.data.kind, shot: s.data.shot || null })),
    marks: scenes.map((s) => ({ t: +(s.start + Math.max(0.5, s.dur - 0.4)).toFixed(3), scene: s.index, label: s.data.kind === 'step' ? `${s.data.chapter.no}-${s.data.n}-${s.data.shot}` : s.data.kind + (s.data.chapter ? '-' + s.data.chapter.no : '') })),
  };

  ready.then(() => seek(Number(q.get('t')) || 0));
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
