// Comeni hybrid identity: Friendly's legibility + Observatory's precision + the shared family core.
import { writeFileSync } from 'node:fs';
const D = new URL('.', import.meta.url).pathname;
const MONO = "'Geist Mono', ui-monospace, monospace";
const UI = "'Lexend', system-ui, sans-serif";

const T = {
  light: { name: 'light', bg: '#F4F5F8', surface: '#FFFFFF', canvas: '#F8F9FB', grid: 'rgba(40,60,110,.055)', grid2: 'rgba(40,60,110,.028)',
    border: '#E1E4EC', border2: '#C9CEDB', ink: '#171A26', ink2: '#474D63', ink3: '#666C84', rail: '#B3B9CA',
    line: '#0F9D7A', lineSoft: '#DDF3EC', sel: '#2F6FEB', selSoft: '#E6EEFD', meas: '#9A5B00', measBar: '#D08A10', measSoft: '#FBF0DC',
    open: '#C92F36', openSoft: '#FCE5E6', settled: '#474D63', exon: '#ECEFF5',
    btn: '#0B7F63', btnInk: '#FFFFFF', btnSh: '#075C48', float: '0 6px 18px -10px rgba(23,26,38,.25)' },
  dark: { name: 'dark', bg: '#12141B', surface: '#1A1D27', canvas: '#161820', grid: 'rgba(140,170,255,.06)', grid2: 'rgba(140,170,255,.03)',
    border: '#282C3A', border2: '#3A3F52', ink: '#E8EAF2', ink2: '#B0B5C8', ink3: '#8C92A8', rail: '#4A5068',
    line: '#2FC79B', lineSoft: '#113529', sel: '#6EA2FF', selSoft: '#172642', meas: '#F0B840', measBar: '#F0B840', measSoft: '#35290F',
    open: '#FF6E73', openSoft: '#3A1B20', settled: '#B0B5C8', exon: '#232736',
    btn: '#2FC79B', btnInk: '#06201A', btnSh: '#1E8C6C', float: '0 8px 22px -12px rgba(0,0,0,.7)' },
};

const head = (c) => `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Lexend:wght@400;500;600;700&amp;family=Geist+Mono:wght@400;500&amp;display=swap">
  <style>
    body { margin: 0; background: ${c.bg}; }
    a { color: ${c.sel}; text-decoration: none; } a:hover { color: ${c.ink}; }
  </style>
</helmet>`;
const foot = `</x-dc>
</body>
</html>
`;

// ── shared pieces ──────────────────────────────────────────────
const logo = (c, name) => `<div style="display:flex;align-items:center;gap:10px">
  <svg width="30" height="16" viewBox="0 0 30 16"><line x1="3" y1="8" x2="27" y2="8" style="stroke:${c.line};stroke-width:4;stroke-linecap:round"></line><circle cx="4" cy="8" r="3.5" style="fill:${c.surface};stroke:${c.ink};stroke-width:2"></circle><circle cx="15" cy="8" r="3.5" style="fill:${c.surface};stroke:${c.ink};stroke-width:2"></circle><circle cx="26" cy="8" r="3.5" style="fill:${c.surface};stroke:${c.ink};stroke-width:2"></circle></svg>
  <span style="font-size:17px;font-weight:700;letter-spacing:-.01em">${name}</span></div>`;
const navItem = (c, s, on) => on
  ? `<span style="padding:6px 14px;border-radius:8px;background:${c.surface};border:1px solid ${c.border};color:${c.ink};font-weight:600">${s}</span>`
  : `<span style="padding:6px 12px;border:1px solid transparent;color:${c.ink2}">${s}</span>`;
const chip = (c, txt, col, soft) => `<span style="display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;background:${soft};color:${col};font-size:12.5px;font-weight:500"><span style="width:7px;height:7px;border-radius:50%;background:${col}"></span>${txt}</span>`;
const primary = (c, label, icon) => `<span style="display:inline-flex;align-items:center;gap:8px;padding:10px 26px;border-radius:10px;background:${c.btn};color:${c.btnInk};font-size:14.5px;font-weight:600;box-shadow:0 3px 0 ${c.btnSh}">${icon || ''}${label}</span>`;
const secondary = (c, s, col) => `<span style="display:inline-flex;align-items:center;gap:6px;padding:7px 13px;border-radius:9px;background:${c.surface};border:1px solid ${c.border2};color:${col || c.ink};font-size:13px;font-weight:500">${s}</span>`;
const panel = (c) => `background:${c.surface};border:1px solid ${c.border};border-radius:14px`;
const label = (c) => `font-size:12px;font-weight:500;color:${c.ink3}`;
const seg = (c, items, onIdx) => `<div style="display:flex;padding:3px;border-radius:10px;background:${c.bg};border:1px solid ${c.border}">${items.map((s, i) => `<span style="padding:5px 13px;border-radius:7px;font-size:12.5px;${i === onIdx ? `background:${c.surface};color:${c.ink};font-weight:600;box-shadow:0 1px 2px rgba(0,0,0,.08)` : `color:${c.ink2}`}">${s}</span>`).join('')}</div>`;
const gridBg = (c) => `background-color:${c.canvas};background-image:linear-gradient(${c.grid} 1px, transparent 1px),linear-gradient(90deg, ${c.grid} 1px, transparent 1px),linear-gradient(${c.grid2} 1px, transparent 1px),linear-gradient(90deg, ${c.grid2} 1px, transparent 1px);background-size:80px 80px,80px 80px,16px 16px,16px 16px`;

// ── Labs: builder ───────────────────────────────────────────────
function labs(c) {
  const port = (dir, name) => `<div style="display:flex;align-items:center;gap:7px;height:19px;font-family:${MONO};font-size:10.5px;color:${dir === 'in' ? c.ink2 : c.ink3}">
      <svg width="10" height="10" viewBox="0 0 10 10"><path d="${dir === 'in' ? 'M7 2 L3 5 L7 8' : 'M3 2 L7 5 L3 8'}" style="fill:none;stroke:${c.ink3};stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round"></path></svg>${name}</div>`;
  const pdot = (side, y, on) => `<span style="position:absolute;${side}:-5px;top:${y}px;width:8px;height:8px;border-radius:2px;background:${on ? c.sel : c.surface};border:1.5px solid ${on ? c.sel : c.border2}"></span>`;
  const node = (x, y, name, ins, outs, footTxt, kind) => {
    const edgeStyle = kind === 'sel' ? `border:1.5px solid ${c.sel};box-shadow:0 0 0 3px ${c.selSoft}` : `border:1px solid ${c.border2}`;
    const badge = kind === 'sel' ? `<span style="margin-left:auto;padding:1px 7px;border-radius:999px;background:${c.measSoft};color:${c.meas};font-size:10.5px;font-weight:600">measured</span>`
      : kind === 'open' ? `<span style="margin-left:auto;padding:1px 7px;border-radius:999px;background:${c.openSoft};color:${c.open};font-size:10.5px;font-weight:600">2 need you</span>` : '';
    return `<div style="position:absolute;left:${x}px;top:${y}px;width:172px;border-radius:10px;background:${c.surface};${edgeStyle};display:flex;flex-direction:column">
      ${pdot('left', 51, kind === 'sel')}${ins.length > 1 ? pdot('left', 70, kind === 'sel') : ''}${pdot('right', 51, kind === 'sel')}
      <div style="display:flex;align-items:center;gap:6px;height:32px;padding:0 11px;border-bottom:1px solid ${c.border}">
        <span style="font-family:${MONO};font-size:11.5px;font-weight:500;color:${c.ink}">${name}</span>${badge}
      </div>
      <div style="padding:5px 11px;display:flex;flex-direction:column">${ins.map(p => port('in', p)).join('')}${outs.map(p => port('out', p)).join('')}</div>
      <div style="padding:5px 11px 8px;border-top:1px solid ${c.border};font-size:11.5px;color:${c.ink3}">${footTxt}</div>
    </div>`;
  };
  const src = (x, y, name, type) => `<div style="position:absolute;left:${x}px;top:${y}px;width:128px;height:80px;border-radius:10px;background:${c.selSoft};border:1.5px dashed ${c.sel};display:flex;flex-direction:column;justify-content:center;gap:2px;padding:0 11px">
      ${pdot('right', 36, false)}
      <span style="font-size:11.5px;font-weight:600;color:${c.sel}">Input</span>
      <span style="font-family:${MONO};font-size:12px;color:${c.ink}">${name}</span>
      <span style="font-family:${MONO};font-size:10px;color:${c.ink2}">${type}</span></div>`;
  const plus = (x, y) => `<div style="position:absolute;left:${x}px;top:${y}px;width:22px;height:22px;border-radius:6px;background:${c.surface};border:1px solid ${c.border2};color:${c.sel};display:flex;align-items:center;justify-content:center;font-size:15px;line-height:1">+</div>`;
  // right-angled routing with small rounded bends
  const edge = (x1, y1, x2, y2, mx, on) => {
    const st = `fill:none;stroke:${on ? c.sel : c.rail};stroke-width:2;stroke-linejoin:round`;
    if (y1 === y2) return `<path d="M${x1} ${y1} H${x2}" style="${st}"></path>`;
    const r = 7, s = y2 > y1 ? 1 : -1;
    return `<path d="M${x1} ${y1} H${mx - r} Q${mx} ${y1} ${mx} ${y1 + s * r} V${y2 - s * r} Q${mx} ${y2} ${mx + r} ${y2} H${x2}" style="${st}"></path>`;
  };

  return `${head(c)}
<div style="width:1400px;height:880px;display:flex;flex-direction:column;background:${c.bg};color:${c.ink};font-family:${UI};overflow:hidden">
  <header style="height:60px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 28px;border-bottom:1px solid ${c.border}">
    <div style="display:flex;align-items:center;gap:28px">
      ${logo(c, 'Comeni Labs')}
      <nav style="display:flex;align-items:center;gap:4px;font-size:14px">${navItem(c, 'Builder', true)}${navItem(c, 'Runs')}${navItem(c, 'Registry')}</nav>
    </div>
    <div style="display:flex;align-items:center;gap:18px;font-size:13px;color:${c.ink2}">
      <span>Learn in Code</span>
      <span style="display:inline-flex;align-items:center;gap:8px;padding:4px 12px 4px 4px;border-radius:999px;border:1px solid ${c.border};background:${c.surface};color:${c.ink}">
        <span style="width:24px;height:24px;border-radius:50%;background:${c.selSoft};color:${c.sel};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600">FL</span>Ferreira lab</span>
    </div>
  </header>

  <div style="height:74px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 28px">
    <div style="display:flex;align-items:center;gap:14px">
      <span style="font-size:26px;font-weight:600;letter-spacing:-.02em">rnaseq-counts</span>
      <span style="font-size:12.5px;color:${c.ink3}">Saved 4s ago</span>
      ${chip(c, 'Valid', c.line, c.lineSoft)}${chip(c, '2 values need you', c.open, c.openSoft)}
    </div>
    <div style="display:flex;align-items:center;gap:14px">
      ${seg(c, ['Canvas', 'Artifact'], 0)}
      ${primary(c, 'Run', '<svg width="11" height="11" viewBox="0 0 12 12"><path d="M3 1.5 L10 6 L3 10.5 Z" style="fill:currentColor"></path></svg>')}
    </div>
  </div>

  <main style="flex:1;display:grid;grid-template-columns:minmax(0, 1fr) 320px;gap:18px;padding:0 28px 24px;min-height:0">
    <section style="position:relative;border-radius:14px;${gridBg(c)};border:1px solid ${c.border};overflow:hidden">
      <div style="position:absolute;left:16px;top:14px;right:16px;display:flex;justify-content:space-between;align-items:center">
        <span style="${label(c)}">5 steps · 2 inputs</span>
        ${seg(c, ['Comfortable', 'Compact'], 0)}
      </div>
      <svg style="position:absolute;left:0;top:0" width="1020" height="700">
        ${edge(148, 208, 170, 208)}
        ${edge(148, 208, 170, 378, 159)}
        ${edge(342, 208, 372, 208, 0, true)}
        ${edge(148, 480, 372, 227, 360, true)}
        ${edge(544, 208, 574, 208, 0, true)}
        ${edge(746, 208, 776, 208)}
      </svg>
      ${src(20, 168, 'reads', 'fastq.reads[paired]')}
      ${src(20, 440, 'reference', 'genome.index.star')}
      ${node(170, 152, 'TRIMGALORE', ['fastq.reads'], ['fastq.reads[trimmed]'], '9 settled')}
      ${node(170, 322, 'FASTQC', ['fastq.reads'], ['qc.report'], '4 settled')}
      ${plus(352, 367)}
      ${node(372, 152, 'STAR_ALIGN', ['fastq.reads[trimmed]', 'genome.index.star'], ['alignment.bam'], '14 settled', 'sel')}
      ${node(574, 152, 'SAMTOOLS_SORT', ['alignment.bam'], ['alignment.bam[sorted]'], '6 settled')}
      ${node(776, 152, 'FEATURECOUNTS', ['alignment.bam[sorted]'], ['counts.matrix'], '<span style="color:' + c.open + ';font-weight:500">2 need you</span> · 11 settled', 'open')}
      ${plus(956, 197)}
      <div style="position:absolute;left:16px;bottom:16px;display:flex;gap:8px">
        ${secondary(c, 'Fit')}${secondary(c, '+ Add step', c.sel)}
      </div>
      <div style="position:absolute;right:16px;bottom:16px;width:150px;height:60px;border-radius:10px;background:${c.surface};border:1px solid ${c.border};box-shadow:${c.float}">
        ${[[10, 16, 12, c.border2], [10, 36, 12, c.border2], [32, 16, 18, c.border2], [32, 30, 18, c.border2], [60, 16, 18, c.sel], [88, 16, 18, c.border2], [116, 16, 18, c.open]].map(([x, y, w, col]) => `<span style="position:absolute;left:${x}px;top:${y}px;width:${w}px;height:7px;border-radius:2px;border:1.5px solid ${col}"></span>`).join('')}
      </div>
    </section>

    <aside style="${panel(c)};display:flex;flex-direction:column;gap:16px;padding:14px 18px;min-height:0">
      ${seg(c, ['Assistant', 'Step'], 1).replace('display:flex;', 'display:flex;align-self:flex-start;')}
      <div style="display:flex;flex-direction:column;gap:3px">
        <span style="font-family:${MONO};font-size:16px;font-weight:500">STAR_ALIGN</span>
        <span style="font-family:${MONO};font-size:11px;color:${c.ink3}">nf-core/star/align@2.7.11a</span>
      </div>
      <div style="display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;align-items:center;justify-content:space-between">
          <span style="font-size:13px;font-weight:600">Why this tool</span>
          <span style="padding:1px 8px;border-radius:999px;background:${c.measSoft};color:${c.meas};font-size:11px;font-weight:600">measured</span>
        </div>
        <span style="font-size:13.5px;line-height:1.55;color:${c.ink2};padding-left:12px;border-left:2px solid ${c.measBar}">Read length is <span style="font-family:${MONO};color:${c.ink}">151 bp</span>, measured from your files, not assumed. Rule <span style="font-family:${MONO};color:${c.ink}">R04</span>.</span>
      </div>
      ${secondary(c, 'Swap for something else').replace('display:inline-flex;', 'display:inline-flex;align-self:flex-start;')}
      <div style="display:flex;flex-direction:column;gap:6px;padding-top:14px;border-top:1px solid ${c.border}">
        <span style="font-size:13px;font-weight:600">Values</span>
        <div style="display:flex;align-items:center;gap:8px;font-size:13.5px;color:${c.ink2}">
          <svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 8.5l3 3 7-7" style="fill:none;stroke:${c.ink2};stroke-width:2;stroke-linecap:round;stroke-linejoin:round"></path></svg>14 settings, all settled</div>
        <a style="font-size:13px;font-weight:500">Open on the node</a>
      </div>
      <div style="margin-top:auto;display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:10px;background:${c.bg};border:1px solid ${c.border}">
        <svg width="44" height="14" viewBox="0 0 44 14"><line x1="3" y1="7" x2="41" y2="7" style="stroke:${c.line};stroke-width:4;stroke-linecap:round"></line><circle cx="7" cy="7" r="4" style="fill:${c.settled}"></circle><circle cx="22" cy="7" r="5" style="fill:${c.selSoft};stroke:${c.sel};stroke-width:2"></circle><circle cx="37" cy="7" r="4" style="fill:${c.surface};stroke:${c.ink3};stroke-width:1.5"></circle></svg>
        <div style="display:flex;flex-direction:column;min-width:0">
          <span style="${label(c)}">Not sure why? Learn it in Code</span>
          <span style="font-size:13.5px;font-weight:600">Splice-aware alignment · 25 min</span>
        </div>
      </div>
    </aside>
  </main>
</div>
${foot}`;
}

// ── Code: a lesson step + Today ─────────────────────────────────
function code(c) {
  const M = MONO;
  const letters = (s, x0, y, fill) => [...s].map((ch, i) => `<text x="${x0 + 8 + i * 16}" y="${y}" text-anchor="middle" style="font-family:${M};font-size:14px;fill:${fill}">${ch}</text>`).join('');
  const figure = `<svg viewBox="0 0 640 170" width="100%" style="display:block">
    <text x="0" y="30" style="font-family:${M};font-size:10.5px;fill:${c.ink3}">genome</text>
    ${letters('ACGTTAGC', 56, 30, c.ink)}
    <text x="330" y="30" text-anchor="middle" style="font-family:${M};font-size:11px;fill:${c.ink3}">GTAAGT · · · 228 nt · · · TTTCAG</text>
    ${letters('CTAGGAT', 474, 30, c.ink)}
    <line x1="184" y1="52" x2="474" y2="52" style="stroke:${c.rail};stroke-width:2"></line>
    <path d="M300 47 l6 5 l-6 5 M350 47 l6 5 l-6 5" style="fill:none;stroke:${c.rail};stroke-width:1.5"></path>
    <rect x="56" y="44" width="128" height="16" rx="3" style="fill:${c.exon};stroke:${c.ink2};stroke-width:1"></rect>
    <rect x="474" y="44" width="112" height="16" rx="3" style="fill:${c.exon};stroke:${c.ink2};stroke-width:1"></rect>
    <text x="120" y="56" text-anchor="middle" style="font-family:${M};font-size:9.5px;fill:${c.ink2}">exon 1</text>
    <text x="530" y="56" text-anchor="middle" style="font-family:${M};font-size:9.5px;fill:${c.ink2}">exon 2</text>
    <text x="0" y="104" style="font-family:${M};font-size:10.5px;fill:${c.ink3}">your read</text>
    <rect x="54" y="86" width="132" height="26" rx="5" style="fill:${c.lineSoft};stroke:${c.line};stroke-width:1.5"></rect>
    <rect x="472" y="86" width="116" height="26" rx="5" style="fill:${c.lineSoft};stroke:${c.line};stroke-width:1.5"></rect>
    <path d="M186 99 H200 V78 H458 V99 H472" style="fill:none;stroke:${c.line};stroke-width:1.5;stroke-dasharray:4 4;stroke-linejoin:round"></path>
    ${letters('ACGTTAGC', 56, 104, c.ink)}
    ${letters('CTAGGAT', 474, 104, c.ink)}
    <line x1="56" y1="130" x2="586" y2="130" style="stroke:${c.border};stroke-width:1"></line>
    <text x="0" y="156" style="font-family:${M};font-size:10.5px;fill:${c.ink3}">CIGAR</text>
    <text x="120" y="156" text-anchor="middle" style="font-family:${M};font-size:15px;font-weight:500;fill:${c.ink}">8M</text>
    <text x="330" y="156" text-anchor="middle" style="font-family:${M};font-size:15px;font-weight:500;fill:${c.line}">240N</text>
    <text x="530" y="156" text-anchor="middle" style="font-family:${M};font-size:15px;font-weight:500;fill:${c.ink}">7M</text>
  </svg>`;

  const xs = [18, 70, 122, 174, 226, 278, 330];
  const st = ['settled', 'stale', 'settled', 'thr', 'next', 'open', 'inter'];
  const stop = (x, s) => ({
    settled: `<circle cx="${x}" cy="36" r="6" style="fill:${c.settled}"></circle>`,
    stale: `<circle cx="${x}" cy="36" r="6.5" style="fill:${c.measSoft};stroke:${c.measBar};stroke-width:2.5"></circle>`,
    thr: `<circle cx="${x}" cy="36" r="10" style="fill:${c.settled};stroke:${c.ink};stroke-width:3"></circle><circle cx="${x}" cy="36" r="3" style="fill:${c.surface}"></circle>`,
    next: `<circle cx="${x}" cy="36" r="9" style="fill:${c.selSoft};stroke:${c.sel};stroke-width:2.5"></circle><circle cx="${x}" cy="36" r="3" style="fill:${c.sel}"></circle>`,
    inter: `<circle cx="${x}" cy="36" r="9" style="fill:${c.surface};stroke:${c.ink};stroke-width:2.5"></circle>`,
    open: `<circle cx="${x}" cy="36" r="6" style="fill:${c.surface};stroke:${c.ink3};stroke-width:2"></circle>`,
  })[s];
  const lbl = (x, y, s, bold) => `<text x="${x}" y="${y}" text-anchor="middle" style="font-family:${UI};font-size:11px;font-weight:${bold ? 700 : 500};fill:${c.ink2}">${s}</text>`;
  const map = `<svg viewBox="0 0 350 104" width="100%" style="display:block">
    <path d="M174 36 L214 76 H300" style="fill:none;stroke:${c.rail};stroke-width:4;stroke-linecap:round;stroke-linejoin:round"></path>
    <circle cx="244" cy="76" r="5" style="fill:${c.surface};stroke:${c.ink3};stroke-width:2"></circle>
    <circle cx="296" cy="76" r="5" style="fill:${c.surface};stroke:${c.ink3};stroke-width:2"></circle>
    <line x1="18" y1="36" x2="330" y2="36" style="stroke:${c.line};stroke-width:6;stroke-linecap:round"></line>
    ${xs.map((x, i) => stop(x, st[i])).join('')}
    ${lbl(70, 16, 'Sequencer')}${lbl(174, 16, 'Coordinates', true)}${lbl(226, 60, 'STAR')}${lbl(330, 16, 'Counts')}${lbl(270, 98, 'Aligner internals')}
  </svg>`;
  const dot = (col, soft) => `<span style="width:10px;height:10px;border-radius:50%;background:${soft};border:2px solid ${col};flex:none"></span>`;
  const row = (d, title, meta, metaCol) => `<div style="display:flex;align-items:center;gap:12px;padding:9px 0;border-top:1px solid ${c.border}">${d}<div style="display:flex;flex-direction:column;gap:1px;flex:1;min-width:0"><span style="font-size:14px;font-weight:500">${title}</span><span style="font-size:12px;color:${metaCol}">${meta}</span></div></div>`;
  const choice = (s, state) => {
    const base = `display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:10px;font-family:${M};font-size:13.5px;`;
    if (state === 'right') return `<div style="${base}border:2px solid ${c.ink};background:${c.surface};color:${c.ink}"><svg width="14" height="14" viewBox="0 0 16 16"><path d="M3 8.5l3 3 7-7" style="fill:none;stroke:${c.ink};stroke-width:2;stroke-linecap:round;stroke-linejoin:round"></path></svg>${s}</div>`;
    if (state === 'wrong') return `<div style="${base}border:1px solid ${c.border2};color:${c.ink3};text-decoration:line-through">${s}</div>`;
    return `<div style="${base}border:1px solid ${c.border2};color:${c.ink2}">${s}</div>`;
  };

  return `${head(c)}
<div style="width:1280px;height:860px;display:flex;flex-direction:column;background:${c.bg};color:${c.ink};font-family:${UI};overflow:hidden">
  <header style="height:60px;flex:none;display:flex;align-items:center;justify-content:space-between;gap:24px;padding:0 28px;border-bottom:1px solid ${c.border}">
    <div style="display:flex;align-items:center;gap:28px">
      ${logo(c, 'Comeni Code')}
      <nav style="display:flex;align-items:center;gap:4px;font-size:14px">${navItem(c, 'Home', true)}${navItem(c, 'Review')}${navItem(c, 'Weekly')}${navItem(c, 'Knowledge')}</nav>
    </div>
    <div style="display:flex;align-items:center;gap:12px">
      <div style="display:flex;align-items:center;gap:8px;width:230px;height:34px;padding:0 12px;border-radius:9px;border:1px solid ${c.border2};background:${c.surface};color:${c.ink3};font-size:13px">
        <svg width="14" height="14" viewBox="0 0 16 16"><circle cx="7" cy="7" r="5" style="fill:none;stroke:currentColor;stroke-width:1.6"></circle><path d="M11 11l3.5 3.5" style="stroke:currentColor;stroke-width:1.6;stroke-linecap:round"></path></svg>
        Search stops, e.g. CIGAR</div>
      ${seg(c, ['Learn', 'Studio'], 0)}
    </div>
  </header>

  <main style="flex:1;display:grid;grid-template-columns:minmax(0, 1fr) 390px;gap:20px;padding:22px 28px 24px;min-height:0">
    <section style="${panel(c)};padding:24px 30px;display:flex;flex-direction:column;gap:15px;min-width:0">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:16px">
        <span style="${label(c)}">Stop 9 of 11 · Splice-aware alignment</span>
        <div style="display:flex;gap:4px;align-items:center">
          ${[1, 1, 1, 1, 1, 2, 0, 0, 0].map(v => `<span style="width:22px;height:5px;border-radius:2px;background:${v === 1 ? c.line : v === 2 ? c.ink : c.border2}"></span>`).join('')}
          <span style="font-family:${M};font-size:11.5px;color:${c.ink3};margin-left:8px">6 / 9</span>
        </div>
      </div>
      <h1 style="margin:0;font-size:31px;font-weight:600;letter-spacing:-.02em;line-height:1.15;text-wrap:balance">Why an RNA read can jump a gap</h1>
      <p style="margin:0;font-size:15.5px;line-height:1.6;color:${c.ink2};max-width:62ch">A mature mRNA has had its introns spliced out. Align one of its reads back to the genome and it lands in two pieces, with the whole intron between them.</p>
      <figure style="margin:0;${gridBg(c)};border:1px solid ${c.border};border-radius:10px;padding:12px 18px 8px;display:flex;flex-direction:column;gap:4px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="${label(c)}">Figure · read alignment</span>
          <span style="font-family:${M};font-size:11px;color:${c.ink3}">CIGAR computed from the drawing</span>
        </div>
        ${figure}
      </figure>
      <div style="display:flex;flex-direction:column;gap:10px">
        <span style="font-size:15px;font-weight:600">Which CIGAR describes this read?</span>
        <div style="display:grid;grid-template-columns:repeat(3, minmax(0, 1fr));gap:10px">${choice('15M')}${choice('8M 240N 7M', 'right')}${choice('8M 240D 7M', 'wrong')}</div>
        <div style="display:flex;gap:12px;align-items:baseline;padding:10px 14px;border-radius:10px;background:${c.openSoft};font-size:13.5px;line-height:1.5">
          <span style="font-size:12px;font-weight:600;color:${c.open};flex:none">Common mix-up</span>
          <span>D is a deletion from the read. N is reference that was skipped — here, an intron. The read lost nothing.</span>
        </div>
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-top:auto">
        <a style="font-size:13.5px;color:${c.ink2}">Open as reference page</a>
        ${primary(c, 'Continue', '')}
      </div>
    </section>

    <aside style="display:flex;flex-direction:column;gap:14px;min-width:0">
      <div style="${panel(c)};padding:16px 20px;display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;justify-content:space-between;align-items:baseline">
          <span style="font-size:18px;font-weight:600">Today</span>
          <span style="font-size:12px;color:${c.ink3}">3 things · about 40 min</span>
        </div>
        ${map}
        <div style="display:flex;flex-direction:column">
          ${row(dot(c.sel, c.selSoft), 'Splice-aware alignment', '25 min · ready', c.sel)}
          ${row(dot(c.sel, c.selSoft), 'Alternative splicing', '10 min · side-door', c.sel)}
          ${row(dot(c.measBar, c.measSoft), 'How a sequencer reads DNA', 'Review due', c.meas)}
        </div>
      </div>
      <div style="${panel(c)};padding:14px 20px;display:flex;align-items:center;justify-content:space-between;gap:12px">
        <div style="display:flex;flex-direction:column;gap:2px">
          <span style="font-size:15px;font-weight:600">Review</span>
          <span style="font-size:13px;color:${c.ink2}">8 checks, mixed · about 6 min</span>
        </div>
        ${secondary(c, 'Start')}
      </div>
      <div style="${panel(c)};padding:16px 20px;display:flex;flex-direction:column;gap:9px">
        <span style="${label(c)}">Weekly problem · 16 Sep</span>
        <span style="font-size:18px;font-weight:600;line-height:1.25">Count the reads on one gene</span>
        <div style="display:flex;gap:16px;font-size:12.5px;color:${c.ink2}"><span>Rung 2 · one command</span><span>Solved by 38%</span></div>
        <div style="display:flex;flex-wrap:wrap;gap:6px">
          <span style="padding:3px 10px;border-radius:999px;border:1px solid ${c.border2};font-family:${M};font-size:11.5px;color:${c.ink2}">BAM and CIGAR</span>
          <span style="padding:3px 10px;border-radius:999px;border:1px solid ${c.border2};font-family:${M};font-size:11.5px;color:${c.ink2}">Coordinates</span>
          <span style="padding:3px 10px;border-radius:999px;border:1px solid ${c.sel};background:${c.selSoft};font-size:12px;color:${c.sel}">Counts matrix · ready</span>
        </div>
      </div>
    </aside>
  </main>
</div>
${foot}`;
}

export { T, head, foot, logo, navItem, chip, primary, secondary, panel, label, seg, gridBg, labs, code, MONO, UI };
