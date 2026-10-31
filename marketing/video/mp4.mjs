// Minimaler MP4-Muxer (ISO BMFF) für einen H.264-Videostrom und optional eine AAC-Tonspur aus WebCodecs, und ein
// Prüfer, der die fertige Datei wieder einliest. Kein ffmpeg nötig.
//
//   muxMp4({ width, height, timescale, avcC, samples: [{ data, key, duration }],
//            audio?: { sampleRate, channels, asc, samples: [{ data }], durationS?, bitrate? } }) → Buffer
//   inspectMp4(buffer) → { brands, durationS, width, height, codec, profile, level, samples, keyframes, faststart,
//                          tracks: [{ handler, codec, durationS, playS, samples, … }], video, audio, problems }
//
// Aufbau: ftyp · moov (mvhd, trak Video: tkhd, mdia: mdhd, hdlr, minf: vmhd, dinf, stbl: stsd/avc1/avcC+pasp, stts,
// stss, stsc, stsz, stco · trak Ton: tkhd, edts/elst, mdia: mdhd, hdlr soun, minf: smhd, dinf, stbl: stsd/mp4a/esds,
// stts, stsc, stsz, stco) · mdat. moov steht vor mdat („faststart“), Bild und Ton liegen in mdat verschränkt in
// Blöcken von etwa einer Sekunde – so beginnt die Wiedergabe sofort, auch in WhatsApp und im Browser.
// Annahmen: Video in Anzeigereihenfolge ohne B-Frames (prüft render.mjs an den Zeitstempeln); AAC-LC mit 1024
// Abtastwerten je Block. Die Tonspur bekommt eine Edit-Liste auf die gewünschte Länge (letzter AAC-Block ist aufgefüllt).

const u8 = (n) => Buffer.from([n & 0xff]);
const u16 = (n) => { const b = Buffer.alloc(2); b.writeUInt16BE(n & 0xffff); return b; };
const u24 = (n) => Buffer.from([(n >>> 16) & 0xff, (n >>> 8) & 0xff, n & 0xff]);
const u32 = (n) => { const b = Buffer.alloc(4); b.writeUInt32BE(n >>> 0); return b; };
const zeros = (n) => Buffer.alloc(n);
const str = (s) => Buffer.from(s, 'latin1');

function box(type, ...parts) {
  const body = Buffer.concat(parts.flat());
  return Buffer.concat([u32(8 + body.length), str(type), body]);
}
const full = (type, version, flags, ...parts) => box(type, u32(((version & 0xff) << 24) | (flags & 0xffffff)), ...parts);
const MATRIX = Buffer.concat([0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000].map(u32));
export const AAC_FRAME = 1024;

/** MPEG-4-Deskriptor (ES_Descriptor usw.) mit 4-Byte-Längenfeld. */
function desc(tag, ...parts) {
  const body = Buffer.concat(parts.flat());
  const n = body.length;
  return Buffer.concat([u8(tag), Buffer.from([0x80 | ((n >> 21) & 0x7f), 0x80 | ((n >> 14) & 0x7f), 0x80 | ((n >> 7) & 0x7f), n & 0x7f]), body]);
}

/** Läufe gleicher Werte: [[anzahl, wert], …] */
function runs(values) {
  const out = [];
  for (const v of values) {
    const last = out[out.length - 1];
    if (last && last[1] === v) last[0]++;
    else out.push([1, v]);
  }
  return out;
}

/** Abtastwerte in Blöcke zu je `perChunk` teilen → [[erster, anzahl], …] */
function chunking(count, perChunk) {
  const out = [];
  for (let i = 0; i < count; i += perChunk) out.push([i, Math.min(perChunk, count - i)]);
  return out;
}

function stscFor(chunks) {
  const entries = [];
  chunks.forEach(([, n], i) => {
    const last = entries[entries.length - 1];
    if (!last || last[1] !== n) entries.push([i + 1, n]);
  });
  return full('stsc', 0, 0, u32(entries.length), ...entries.map(([first, n]) => Buffer.concat([u32(first), u32(n), u32(1)])));
}

export function muxMp4({ width, height, timescale, avcC, samples, audio = null, compressor = 'Daftar render.mjs' }) {
  if (!samples.length) throw new Error('keine Bilder');
  if (!samples[0].key) throw new Error('erstes Bild ist kein Schlüsselbild');
  const ticks = samples.reduce((a, s) => a + s.duration, 0);
  const movieScale = 1000;
  const movieDuration = Math.round((ticks * movieScale) / timescale);

  // ---------- Blöcke (Chunks), verschränkt nach Zeit ----------
  const fps = Math.max(1, Math.round(timescale / (samples[0].duration || 1)));
  const vChunks = chunking(samples.length, fps); // ≈ 1 s je Block
  let aChunks = [];
  let aMediaTicks = 0, aKeepTicks = 0;
  if (audio) {
    if (!audio.samples.length) throw new Error('Tonspur ohne Blöcke');
    if (!audio.asc || audio.asc.length < 2) throw new Error('Tonspur ohne AudioSpecificConfig');
    aChunks = chunking(audio.samples.length, Math.max(1, Math.round(audio.sampleRate / AAC_FRAME)));
    aMediaTicks = audio.samples.length * AAC_FRAME;
    aKeepTicks = Math.min(aMediaTicks, Math.round((audio.durationS ?? aMediaTicks / audio.sampleRate) * audio.sampleRate));
  }
  // Reihenfolge in mdat: nach Startzeit, bei Gleichstand Video zuerst
  const order = [];
  vChunks.forEach(([first], i) => order.push({ t: (first * samples[0].duration) / timescale, track: 'v', i }));
  aChunks.forEach(([first], i) => order.push({ t: (first * AAC_FRAME) / audio.sampleRate, track: 'a', i }));
  order.sort((a, b) => a.t - b.t || (a.track === 'v' ? -1 : 1));

  const vData = samples.map((s) => s.data);
  const aData = audio ? audio.samples.map((s) => s.data) : [];
  const chunkBytes = (track, i) => {
    const [first, n] = track === 'v' ? vChunks[i] : aChunks[i];
    const src = track === 'v' ? vData : aData;
    let sum = 0;
    for (let k = first; k < first + n; k++) sum += src[k].length;
    return sum;
  };

  const name = Buffer.alloc(32);
  const cname = str(compressor.slice(0, 31));
  name[0] = cname.length;
  cname.copy(name, 1);

  const build = (vOffsets, aOffsets) => {
    // ----- Video -----
    const keyIdx = samples.map((s, i) => (s.key ? i + 1 : 0)).filter(Boolean);
    const avc1 = box('avc1',
      zeros(6), u16(1),               // reserved, data_reference_index
      zeros(16),                      // pre_defined, reserved, pre_defined[3]
      u16(width), u16(height),
      u32(0x00480000), u32(0x00480000), // 72 dpi
      u32(0), u16(1), name, u16(0x0018), u16(0xffff),
      box('avcC', avcC),
      box('pasp', u32(1), u32(1)));
    const vRuns = runs(samples.map((s) => s.duration));
    const vStbl = box('stbl',
      full('stsd', 0, 0, u32(1), avc1),
      full('stts', 0, 0, u32(vRuns.length), ...vRuns.map(([c, d]) => Buffer.concat([u32(c), u32(d)]))),
      full('stss', 0, 0, u32(keyIdx.length), ...keyIdx.map(u32)),
      stscFor(vChunks),
      full('stsz', 0, 0, u32(0), u32(samples.length), ...samples.map((s) => u32(s.data.length))),
      full('stco', 0, 0, u32(vOffsets.length), ...vOffsets.map(u32)));
    const vMdia = box('mdia',
      full('mdhd', 0, 0, u32(0), u32(0), u32(timescale), u32(ticks), u16(0x55c4), u16(0)),
      full('hdlr', 0, 0, u32(0), str('vide'), zeros(12), str('VideoHandler\0')),
      box('minf',
        full('vmhd', 0, 1, u16(0), zeros(6)),
        box('dinf', full('dref', 0, 0, u32(1), full('url ', 0, 1))),
        vStbl));
    const vTkhd = full('tkhd', 0, 3, u32(0), u32(0), u32(1), u32(0), u32(movieDuration), zeros(8),
      u16(0), u16(0), u16(0), u16(0), MATRIX, u32(width << 16), u32(height << 16));
    const traks = [box('trak', vTkhd, vMdia)];

    // ----- Ton -----
    let audioMovieDuration = 0;
    if (audio) {
      const sr = audio.sampleRate;
      audioMovieDuration = Math.round((aKeepTicks / sr) * movieScale);
      const br = audio.bitrate ?? 128000;
      const maxFrame = Math.max(...aData.map((d) => d.length));
      const esds = full('esds', 0, 0, desc(0x03, u16(0), u8(0),
        desc(0x04, u8(0x40), u8(0x15), u24(maxFrame), u32(br), u32(br), desc(0x05, audio.asc)),
        desc(0x06, u8(0x02))));
      const mp4a = box('mp4a', zeros(6), u16(1), zeros(8), u16(audio.channels), u16(16), u16(0), u16(0), u32(sr * 65536), esds);
      const aStbl = box('stbl',
        full('stsd', 0, 0, u32(1), mp4a),
        full('stts', 0, 0, u32(1), u32(aData.length), u32(AAC_FRAME)),
        stscFor(aChunks),
        full('stsz', 0, 0, u32(0), u32(aData.length), ...aData.map((d) => u32(d.length))),
        full('stco', 0, 0, u32(aOffsets.length), ...aOffsets.map(u32)));
      const aMdia = box('mdia',
        full('mdhd', 0, 0, u32(0), u32(0), u32(sr), u32(aMediaTicks), u16(0x55c4), u16(0)),
        full('hdlr', 0, 0, u32(0), str('soun'), zeros(12), str('SoundHandler\0')),
        box('minf',
          full('smhd', 0, 0, u16(0), u16(0)),
          box('dinf', full('dref', 0, 0, u32(1), full('url ', 0, 1))),
          aStbl));
      const aTkhd = full('tkhd', 0, 3, u32(0), u32(0), u32(2), u32(0), u32(audioMovieDuration), zeros(8),
        u16(0), u16(1), u16(0x0100), u16(0), MATRIX, u32(0), u32(0));
      // Edit-Liste: Ton ab 0, genau so lang wie gewünscht (der letzte AAC-Block ist mit Stille aufgefüllt)
      const edts = box('edts', full('elst', 0, 0, u32(1), u32(audioMovieDuration), u32(0), u16(1), u16(0)));
      traks.push(box('trak', aTkhd, edts, aMdia));
    }
    const mvhd = full('mvhd', 0, 0, u32(0), u32(0), u32(movieScale), u32(Math.max(movieDuration, audioMovieDuration)), u32(0x00010000), u16(0x0100),
      zeros(10), MATRIX, zeros(24), u32(audio ? 3 : 2));
    return box('moov', mvhd, ...traks);
  };

  const ftyp = box('ftyp', str('isom'), u32(0x200), str('isom'), str('iso2'), str('avc1'), str('mp41'));
  const probe = build(vChunks.map(() => 0), aChunks.map(() => 0));
  let pos = ftyp.length + probe.length + 8;
  const vOffsets = new Array(vChunks.length), aOffsets = new Array(aChunks.length);
  for (const o of order) {
    (o.track === 'v' ? vOffsets : aOffsets)[o.i] = pos;
    pos += chunkBytes(o.track, o.i);
  }
  if (pos > 0xffffffff) throw new Error('Datei größer als 4 GB – co64 nicht umgesetzt');
  const moov = build(vOffsets, aOffsets);
  if (moov.length !== probe.length) throw new Error('moov-Größe hat sich geändert');
  const payload = [];
  for (const o of order) {
    const [first, n] = o.track === 'v' ? vChunks[o.i] : aChunks[o.i];
    const src = o.track === 'v' ? vData : aData;
    for (let k = first; k < first + n; k++) payload.push(src[k]);
  }
  const body = Buffer.concat(payload);
  const mdat = Buffer.concat([u32(8 + body.length), str('mdat'), body]);
  return Buffer.concat([ftyp, moov, mdat]);
}

// ---------- Prüfen ----------
const CONTAINERS = new Set(['moov', 'trak', 'mdia', 'minf', 'stbl', 'dinf', 'edts', 'udta']);

function* boxes(buf, start, end) {
  let p = start;
  while (p + 8 <= end) {
    let size = buf.readUInt32BE(p);
    const type = buf.toString('latin1', p + 4, p + 8);
    let header = 8;
    if (size === 1) { size = Number(buf.readBigUInt64BE(p + 8)); header = 16; }
    if (size === 0) size = end - p;
    if (size < header || p + size > end) throw new Error(`kaputte Box ${type} bei ${p}`);
    yield { type, start: p, body: p + header, end: p + size };
    p += size;
  }
}

/** Deskriptor in esds lesen: { tag, body, end } */
function readDesc(buf, p) {
  const tag = buf[p];
  let len = 0, q = p + 1;
  for (let k = 0; k < 4; k++) { const b = buf[q++]; len = (len << 7) | (b & 0x7f); if (!(b & 0x80)) break; }
  return { tag, body: q, end: q + len };
}

export function inspectMp4(buf) {
  const out = { order: [], tracks: [] };
  let t = null;
  const walk = (start, end, depth) => {
    for (const b of boxes(buf, start, end)) {
      if (depth === 0) out.order.push(b.type);
      if (b.type === 'trak') { t = {}; out.tracks.push(t); walk(b.body, b.end, depth + 1); t = null; continue; }
      if (CONTAINERS.has(b.type)) { walk(b.body, b.end, depth + 1); continue; }
      const v = b.body;
      switch (b.type) {
        case 'ftyp': {
          out.brands = [buf.toString('latin1', v, v + 4)];
          for (let p = v + 8; p < b.end; p += 4) out.brands.push(buf.toString('latin1', p, p + 4));
          break;
        }
        case 'mvhd': out.movieScale = buf.readUInt32BE(v + 12); out.movieDuration = buf.readUInt32BE(v + 16); out.nextTrackId = buf.readUInt32BE(v + 96); break;
        case 'tkhd': t.id = buf.readUInt32BE(v + 12); t.tkhdDuration = buf.readUInt32BE(v + 20); t.volume = buf.readUInt16BE(v + 36); t.width = buf.readUInt32BE(v + 76) >>> 16; t.height = buf.readUInt32BE(v + 80) >>> 16; break;
        case 'elst': {
          t.elst = [];
          for (let i = 0, n = buf.readUInt32BE(v + 4); i < n; i++) t.elst.push({ segment: buf.readUInt32BE(v + 8 + i * 12), mediaTime: buf.readInt32BE(v + 12 + i * 12) });
          break;
        }
        case 'mdhd': t.timescale = buf.readUInt32BE(v + 12); t.ticks = buf.readUInt32BE(v + 16); break;
        case 'hdlr': t.handler = buf.toString('latin1', v + 8, v + 12); break;
        case 'stsd': {
          const entry = v + 8;
          const entryEnd = entry + buf.readUInt32BE(entry);
          t.codec = buf.toString('latin1', entry + 4, entry + 8);
          if (t.codec === 'avc1') {
            for (const c of boxes(buf, entry + 8 + 78, entryEnd)) {
              if (c.type === 'avcC') { t.profile = buf[c.body + 1]; t.level = buf[c.body + 3]; }
            }
          } else if (t.codec === 'mp4a') {
            t.channels = buf.readUInt16BE(entry + 8 + 16);
            t.sampleRate = buf.readUInt32BE(entry + 8 + 24) >>> 16;
            for (const c of boxes(buf, entry + 8 + 28, entryEnd)) {
              if (c.type !== 'esds') continue;
              const es = readDesc(buf, c.body + 4);
              for (let p = es.body + 3; p < es.end;) {
                const d = readDesc(buf, p);
                if (d.tag === 0x04) {
                  t.objectType = buf[d.body];
                  const dsi = readDesc(buf, d.body + 13);
                  if (dsi.tag === 0x05) t.asc = [...buf.subarray(dsi.body, dsi.end)];
                }
                p = d.end;
              }
            }
          }
          break;
        }
        case 'stts': {
          let n = 0, ticks = 0;
          for (let i = 0, k = buf.readUInt32BE(v + 4); i < k; i++) { const c = buf.readUInt32BE(v + 8 + i * 8); n += c; ticks += c * buf.readUInt32BE(v + 12 + i * 8); }
          t.sttsSamples = n; t.sttsTicks = ticks;
          break;
        }
        case 'stss': t.keyframes = buf.readUInt32BE(v + 4); break;
        case 'stsc': {
          t.stsc = [];
          for (let i = 0, k = buf.readUInt32BE(v + 4); i < k; i++) t.stsc.push([buf.readUInt32BE(v + 8 + i * 12), buf.readUInt32BE(v + 12 + i * 12)]);
          break;
        }
        case 'stsz': {
          t.samples = buf.readUInt32BE(v + 8);
          t.sizes = [];
          for (let i = 0; i < t.samples; i++) t.sizes.push(buf.readUInt32BE(v + 12 + i * 4));
          t.sampleBytes = t.sizes.reduce((a, s) => a + s, 0);
          break;
        }
        case 'stco': {
          t.offsets = [];
          for (let i = 0, k = buf.readUInt32BE(v + 4); i < k; i++) t.offsets.push(buf.readUInt32BE(v + 8 + i * 4));
          break;
        }
        case 'mdat': out.mdatStart = b.body; out.mdatBytes = b.end - b.body; break;
      }
    }
  };
  walk(0, buf.length, 0);
  out.faststart = out.order.indexOf('moov') < out.order.indexOf('mdat');

  const problems = [];
  const spans = [];
  for (const tr of out.tracks) {
    tr.durationS = tr.ticks / tr.timescale;
    tr.playS = tr.elst?.length && out.movieScale ? tr.elst.reduce((a, e) => a + e.segment, 0) / out.movieScale : tr.durationS;
    if (tr.samples !== tr.sttsSamples) problems.push(`${tr.handler}: stsz/stts ungleich`);
    // Lage jedes Abtastwerts aus stsc/stco/stsz
    if (tr.offsets && tr.stsc && tr.sizes) {
      let sample = 0;
      for (let c = 0; c < tr.offsets.length; c++) {
        let per = 0;
        for (const [first, n] of tr.stsc) if (first <= c + 1) per = n;
        let p = tr.offsets[c];
        for (let k = 0; k < per && sample < tr.sizes.length; k++, sample++) { spans.push([p, tr.sizes[sample]]); p += tr.sizes[sample]; }
      }
      if (sample !== tr.sizes.length) problems.push(`${tr.handler}: stsc/stco decken nicht alle Abtastwerte ab (${sample}/${tr.sizes.length})`);
    }
    delete tr.sizes;
  }
  // Alle Abtastwerte lückenlos und überschneidungsfrei in mdat
  spans.sort((a, b) => a[0] - b[0]);
  let cursor = out.mdatStart;
  for (const [p, n] of spans) {
    if (p !== cursor) { problems.push(`mdat: Lücke oder Überschneidung bei Byte ${p}`); break; }
    cursor += n;
  }
  if (cursor !== out.mdatStart + out.mdatBytes) problems.push('mdat-Größe passt nicht zu den Abtastwerten');

  const video = out.tracks.find((tr) => tr.handler === 'vide');
  const audio = out.tracks.find((tr) => tr.handler === 'soun');
  out.video = video; out.audio = audio;
  if (!video) problems.push('keine Videospur');
  else {
    if (video.codec !== 'avc1') problems.push(`Codec ${video.codec}`);
    Object.assign(out, {
      width: video.width, height: video.height, timescale: video.timescale, ticks: video.ticks, durationS: video.durationS,
      codec: video.codec, profile: video.profile, level: video.level, samples: video.samples, keyframes: video.keyframes,
    });
    const PROFILES = { 66: 'Baseline', 77: 'Main', 100: 'High' };
    out.profileName = PROFILES[video.profile] ?? String(video.profile);
    out.levelName = video.level ? (video.level / 10).toFixed(1) : '?';
  }
  if (audio) {
    if (audio.codec !== 'mp4a' || audio.objectType !== 0x40) problems.push(`Ton: Codec ${audio.codec}/${audio.objectType}`);
    if (!audio.asc) problems.push('Ton: AudioSpecificConfig fehlt');
  }
  out.problems = problems;
  return out;
}
