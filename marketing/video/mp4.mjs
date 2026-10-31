// Minimaler MP4-Muxer (ISO BMFF) für einen H.264-Videostrom aus WebCodecs (avc-Format, Längenpräfix) und ein
// Prüfer, der die fertige Datei wieder einliest. Kein ffmpeg nötig.
//
//   muxMp4({ width, height, timescale, avcC, samples: [{ data, key, duration }] }) → Buffer
//   inspectMp4(buffer) → { brands, durationS, width, height, codec, profile, level, samples, keyframes, mdatBytes, faststart }
//
// Aufbau: ftyp · moov (mvhd, trak: tkhd, mdia: mdhd, hdlr, minf: vmhd, dinf, stbl: stsd/avc1/avcC+pasp, stts, stss,
// stsc, stsz, stco) · mdat. moov steht vor mdat („faststart“): Wiedergabe beginnt sofort, auch in WhatsApp/Browsern.
// Annahme: Ausgabe in Anzeigereihenfolge ohne B-Frames (prüft render.mjs an den Zeitstempeln).

const u8 = (n) => Buffer.from([n & 0xff]);
const u16 = (n) => { const b = Buffer.alloc(2); b.writeUInt16BE(n & 0xffff); return b; };
const u32 = (n) => { const b = Buffer.alloc(4); b.writeUInt32BE(n >>> 0); return b; };
const zeros = (n) => Buffer.alloc(n);
const str = (s) => Buffer.from(s, 'latin1');

function box(type, ...parts) {
  const body = Buffer.concat(parts.flat());
  return Buffer.concat([u32(8 + body.length), str(type), body]);
}
const full = (type, version, flags, ...parts) => box(type, u32(((version & 0xff) << 24) | (flags & 0xffffff)), ...parts);
const MATRIX = Buffer.concat([0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000].map(u32));

export function muxMp4({ width, height, timescale, avcC, samples, compressor = 'Daftar render.mjs' }) {
  if (!samples.length) throw new Error('keine Bilder');
  if (!samples[0].key) throw new Error('erstes Bild ist kein Schlüsselbild');
  const ticks = samples.reduce((a, s) => a + s.duration, 0);
  const movieScale = 1000;
  const movieDuration = Math.round((ticks * movieScale) / timescale);

  // stts: Läufe gleicher Dauer
  const runs = [];
  for (const s of samples) {
    const last = runs[runs.length - 1];
    if (last && last[1] === s.duration) last[0]++;
    else runs.push([1, s.duration]);
  }
  const keyIdx = samples.map((s, i) => (s.key ? i + 1 : 0)).filter(Boolean);
  const name = Buffer.alloc(32);
  const cname = str(compressor.slice(0, 31));
  name[0] = cname.length;
  cname.copy(name, 1);

  const build = (chunkOffset) => {
    const avc1 = box('avc1',
      zeros(6), u16(1),               // reserved, data_reference_index
      zeros(16),                      // pre_defined, reserved, pre_defined[3]
      u16(width), u16(height),
      u32(0x00480000), u32(0x00480000), // 72 dpi
      u32(0), u16(1), name, u16(0x0018), u16(0xffff),
      box('avcC', avcC),
      box('pasp', u32(1), u32(1)));
    const stbl = box('stbl',
      full('stsd', 0, 0, u32(1), avc1),
      full('stts', 0, 0, u32(runs.length), ...runs.map(([c, d]) => Buffer.concat([u32(c), u32(d)]))),
      full('stss', 0, 0, u32(keyIdx.length), ...keyIdx.map(u32)),
      full('stsc', 0, 0, u32(1), u32(1), u32(samples.length), u32(1)),
      full('stsz', 0, 0, u32(0), u32(samples.length), ...samples.map((s) => u32(s.data.length))),
      full('stco', 0, 0, u32(1), u32(chunkOffset)));
    const minf = box('minf',
      full('vmhd', 0, 1, u16(0), zeros(6)),
      box('dinf', full('dref', 0, 0, u32(1), full('url ', 0, 1))),
      stbl);
    const mdia = box('mdia',
      full('mdhd', 0, 0, u32(0), u32(0), u32(timescale), u32(ticks), u16(0x55c4), u16(0)),
      full('hdlr', 0, 0, u32(0), str('vide'), zeros(12), str('VideoHandler\0')),
      minf);
    const tkhd = full('tkhd', 0, 3, u32(0), u32(0), u32(1), u32(0), u32(movieDuration), zeros(8),
      u16(0), u16(0), u16(0), u16(0), MATRIX, u32(width << 16), u32(height << 16));
    const mvhd = full('mvhd', 0, 0, u32(0), u32(0), u32(movieScale), u32(movieDuration), u32(0x00010000), u16(0x0100),
      zeros(10), MATRIX, zeros(24), u32(2));
    return box('moov', mvhd, box('trak', tkhd, mdia));
  };

  const ftyp = box('ftyp', str('isom'), u32(0x200), str('isom'), str('iso2'), str('avc1'), str('mp41'));
  const probe = build(0);
  const offset = ftyp.length + probe.length + 8;
  const moov = build(offset);
  const payload = Buffer.concat(samples.map((s) => s.data));
  const mdat = Buffer.concat([u32(8 + payload.length), str('mdat'), payload]);
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

export function inspectMp4(buf) {
  const out = { order: [] };
  const walk = (start, end, depth) => {
    for (const b of boxes(buf, start, end)) {
      if (depth === 0) out.order.push(b.type);
      if (CONTAINERS.has(b.type)) { walk(b.body, b.end, depth + 1); continue; }
      const v = b.body;
      switch (b.type) {
        case 'ftyp': {
          out.brands = [buf.toString('latin1', v, v + 4)];
          for (let p = v + 8; p < b.end; p += 4) out.brands.push(buf.toString('latin1', p, p + 4));
          break;
        }
        case 'mvhd': out.movieScale = buf.readUInt32BE(v + 12); out.movieDuration = buf.readUInt32BE(v + 16); break;
        case 'tkhd': out.width = buf.readUInt32BE(v + 76) >>> 16; out.height = buf.readUInt32BE(v + 80) >>> 16; break;
        case 'mdhd': out.timescale = buf.readUInt32BE(v + 12); out.ticks = buf.readUInt32BE(v + 16); break;
        case 'stsd': {
          const entry = v + 8;
          out.codec = buf.toString('latin1', entry + 4, entry + 8);
          for (const c of boxes(buf, entry + 8 + 78, buf.readUInt32BE(entry) + entry)) {
            if (c.type === 'avcC') { out.profile = buf[c.body + 1]; out.level = buf[c.body + 3]; }
          }
          break;
        }
        case 'stts': {
          let n = 0, ticks = 0;
          for (let i = 0, k = buf.readUInt32BE(v + 4); i < k; i++) { const c = buf.readUInt32BE(v + 8 + i * 8); n += c; ticks += c * buf.readUInt32BE(v + 12 + i * 8); }
          out.sttsSamples = n; out.sttsTicks = ticks;
          break;
        }
        case 'stss': out.keyframes = buf.readUInt32BE(v + 4); break;
        case 'stsz': {
          out.samples = buf.readUInt32BE(v + 8);
          let sum = 0;
          for (let i = 0; i < out.samples; i++) sum += buf.readUInt32BE(v + 12 + i * 4);
          out.sampleBytes = sum;
          break;
        }
        case 'stco': out.chunkOffset = buf.readUInt32BE(v + 8); break;
        case 'mdat': out.mdatStart = b.body; out.mdatBytes = b.end - b.body; break;
      }
    }
  };
  walk(0, buf.length, 0);
  out.durationS = out.ticks / out.timescale;
  out.faststart = out.order.indexOf('moov') < out.order.indexOf('mdat');
  const PROFILES = { 66: 'Baseline', 77: 'Main', 100: 'High' };
  out.profileName = PROFILES[out.profile] ?? String(out.profile);
  out.levelName = out.level ? (out.level / 10).toFixed(1) : '?';
  const problems = [];
  if (out.codec !== 'avc1') problems.push(`Codec ${out.codec}`);
  if (out.samples !== out.sttsSamples) problems.push('stsz/stts ungleich');
  if (out.sampleBytes !== out.mdatBytes) problems.push('mdat-Größe passt nicht zu stsz');
  if (out.chunkOffset !== out.mdatStart) problems.push('stco zeigt nicht auf mdat');
  out.problems = problems;
  return out;
}
