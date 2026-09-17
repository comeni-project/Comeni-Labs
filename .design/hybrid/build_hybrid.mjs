// Comeni Labs in the hybrid identity shared with Comeni Code — the key pages, from one generator.
//   node .design/hybrid/build_hybrid.mjs
// Tokens are a copy of Comeni-Code/.design/_identity.mjs (identity is shared, code is not).
// One fixture below feeds every board, so a count on Home and the row it counts cannot disagree.
import { writeFileSync } from 'node:fs';
import { T, head, foot, logo, primary, secondary, seg, MONO, UI } from './_identity.mjs';

const D = new URL('.', import.meta.url).pathname;
let c = T.light;
const themed = (theme, fn) => { const prev = c; c = T[theme]; try { return fn(); } finally { c = prev; } };

// ── fixture ─────────────────────────────────────────────────────
const LAB = 'Ferreira lab';
const PIPES = [
  { name: 'rnaseq-counts', makes: 'gene counts from paired RNA-seq reads', steps: 6, settled: 36, measured: 4, open: 1, runs: 31, last: 'running', owner: 'R. Correia' },
  { name: 'atac-peaks', makes: 'peaks from paired ATAC-seq reads', steps: 7, settled: 29, measured: 2, open: 2, runs: 8, last: 'needs you', owner: 'M. Silva' },
  { name: 'wgs-variants', makes: 'small variants from whole-genome reads', steps: 11, settled: 58, measured: 6, open: 0, runs: 14, last: 'succeeded', owner: 'J. Costa' },
  { name: '16s-profile', makes: 'community profile from 16S amplicons', steps: 5, settled: 17, measured: 0, open: 1, runs: 0, last: 'needs you', owner: 'A. Reis' },
  { name: 'chip-peaks', makes: 'binding sites from ChIP-seq reads', steps: 6, settled: 31, measured: 3, open: 0, runs: 5, last: 'succeeded', owner: 'M. Silva' },
];
const RUNS = [
  ['running', 'rnaseq-counts', 'b71e04d2', 'R. Correia', 'now', '3 of 6 steps', '21m 40s', 0.62, null, '—'],
  ['failed', 'rnaseq-counts', 'a3f9c2e1', 'R. Correia', 'yesterday', 'STAR_ALIGN exited 137', '22m 11s', 0.99, 0.91, '—'],
  ['succeeded', 'wgs-variants', '5c20e9aa', 'J. Costa', '6 d ago', '11 of 11', '4h 12m', 0.24, 0.24, '18 files'],
  ['failed', 'atac-peaks', '9d11f7c0', 'M. Silva', '2 d ago', 'MACS2, 3 of 24 tasks', '38m 04s', 0.41, 0.38, '—'],
  ['succeeded', 'rnaseq-counts', '11ab93e5', 'A. Reis', '3 d ago', '6 of 6', '22m 51s', 0.33, 0.33, '6 files'],
  ['succeeded', 'chip-peaks', 'e0c4d6b1', 'M. Silva', '4 d ago', '6 of 6', '51m 10s', 0.47, 0.47, '9 files'],
  ['cancelled', 'wgs-variants', '72ff0a13', 'J. Costa', '6 d ago', 'cancelled at 4 of 11', '1h 02m', 0.2, 0.2, '—'],
  ['succeeded', 'atac-peaks', '3b9e0c77', 'M. Silva', '8 d ago', '7 of 7', '41m 33s', 0.36, 0.36, '12 files'],
  ['succeeded', 'rnaseq-counts', 'c8d1a4f0', 'R. Correia', '9 d ago', '6 of 6', '23m 02s', 0.3, 0.3, '6 files'],
  ['failed', 'chip-peaks', '0f7aa2d9', 'A. Reis', '11 d ago', 'BOWTIE2_ALIGN, 1 of 8', '6m 40s', 0.15, 0.12, '—'],
  ['succeeded', 'wgs-variants', '48e2b1c3', 'J. Costa', '12 d ago', '11 of 11', '4h 31m', 0.22, 0.22, '18 files'],
];
const QUEUE = {
  ai: [['pegi3s / prodigal', 'mapping inputs and outputs', '01:42', 'running'], ['nf-core / bcftools/mpileup', 'next · about 4 min', '', 'queued'], ['pegi3s / seda', 'second · about 9 min', '', 'queued']],
  review: [['nf-core / samtools/sort', '8 of 8', 2, '12 min'], ['nf-core / hisat2/align', '8 of 8', 1, '1 h'], ['pegi3s / clustalw', '6 of 8', 3, '4 h'], ['nf-core / trimgalore', '8 of 8', 1, '2 d'], ['nf-core / multiqc', '7 of 8', 2, '3 d']],
  changes: [['pegi3s / prodigal', 'the output’s state is a guess', 'R. Correia'], ['nf-core / bwa/mem', 'second input has no evidence', 'M. Silva']],
  failed: [['pegi3s / orphanimage', 'the source could not be read', 'MI0105']],
};

// ── pieces ──────────────────────────────────────────────────────
const page = (w, h, inner) => `${head(c)}
<div style="width:${w}px;height:${h}px;display:flex;flex-direction:column;background:${c.bg};color:${c.ink};font-family:${UI};overflow:hidden">
${inner}
</div>
${foot}`;
const ic = {
  search: `<svg width="15" height="15" viewBox="0 0 16 16"><circle cx="7" cy="7" r="5" style="fill:none;stroke:currentColor;stroke-width:1.6"></circle><path d="M11 11l3.5 3.5" style="stroke:currentColor;stroke-width:1.6;stroke-linecap:round"></path></svg>`,
  check: (col) => `<svg width="15" height="15" viewBox="0 0 16 16"><path d="M3 8.5l3 3 7-7" style="fill:none;stroke:${col};stroke-width:2;stroke-linecap:round;stroke-linejoin:round"></path></svg>`,
  chevron: `<svg width="12" height="12" viewBox="0 0 12 12"><path d="M3 4.5l3 3 3-3" style="fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round"></path></svg>`,
  play: `<svg width="11" height="11" viewBox="0 0 12 12"><path d="M3 1.5 L10 6 L3 10.5 Z" style="fill:currentColor"></path></svg>`,
  arrow: `<svg width="14" height="14" viewBox="0 0 16 16"><path d="M3 8h10M9 4l4 4-4 4" style="fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round"></path></svg>`,
  close: `<svg width="16" height="16" viewBox="0 0 16 16"><path d="M4 4l8 8M12 4l-8 8" style="stroke:currentColor;stroke-width:1.8;stroke-linecap:round"></path></svg>`,
  file: `<svg width="15" height="15" viewBox="0 0 16 16"><path d="M4 1.5h5l3.5 3.5v9.5h-8.5z M9 1.5V5h3.5" style="fill:none;stroke:currentColor;stroke-width:1.4;stroke-linejoin:round"></path></svg>`,
  send: `<svg width="15" height="15" viewBox="0 0 16 16"><path d="M2 8l11-5-4 11-2-4.5z" style="fill:none;stroke:currentColor;stroke-width:1.5;stroke-linejoin:round"></path></svg>`,
};
const mono = (s, extra = '') => `<span style="font-family:${MONO};${extra}">${s}</span>`;
const h1 = (s, size = 28) => `<h1 style="margin:0;font-size:${size}px;font-weight:600;letter-spacing:-.02em;line-height:1.15;text-wrap:balance">${s}</h1>`;
const h2 = (s, extra = '') => `<span style="font-size:15px;font-weight:600;${extra}">${s}</span>`;
const small = (s, col) => `<span style="font-size:12.5px;color:${col || c.ink3}">${s}</span>`;
const tag = (kind, s) => {
  const m = {
    amber: `background:${c.measSoft};color:${c.meas};font-weight:600`,
    blue: `background:${c.selSoft};color:${c.sel};font-weight:600`,
    red: `background:${c.openSoft};color:${c.open};font-weight:600`,
    green: `background:${c.lineSoft};color:${c.btn};font-weight:600`,
    grey: `border:1px solid ${c.border2};color:${c.ink2};font-weight:500`,
    dark: `background:${c.ink};color:${c.bg};font-weight:600`,
  }[kind];
  return `<span style="display:inline-flex;align-items:center;gap:6px;padding:2px 9px;border-radius:999px;font-size:11.5px;white-space:nowrap;${m}">${s}</span>`;
};
const panel = (extra = '') => `background:${c.surface};border:1px solid ${c.border};border-radius:14px;${extra}`;
const card = (inner, extra = '') => `<div style="${panel()}padding:18px 20px;display:flex;flex-direction:column;gap:10px;${extra}">${inner}</div>`;
const kbd = (k) => `<span style="font-family:${MONO};font-size:11px;padding:1px 6px;border-radius:5px;border:1px solid ${c.border2};background:${c.bg};color:${c.ink2}">${k}</span>`;
const box = (on) => `<span style="width:15px;height:15px;border-radius:4px;flex:none;display:flex;align-items:center;justify-content:center;${on ? `background:${c.sel}` : `border:1.5px solid ${c.border2}`}">${on ? ic.check('#FFFFFF') : ''}</span>`;
const radio = (on) => `<span style="width:16px;height:16px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;border:1.5px solid ${on ? c.sel : c.border2}">${on ? `<span style="width:8px;height:8px;border-radius:50%;background:${c.sel}"></span>` : ''}</span>`;
const searchBox = (ph, w = 300) => `<div style="display:flex;align-items:center;gap:8px;width:${w}px;height:34px;padding:0 12px;border-radius:9px;border:1px solid ${c.border2};background:${c.surface};font-size:13px;color:${c.ink3}">${ic.search}${ph}</div>`;
const sortBtn = (s) => `<span style="display:inline-flex;align-items:center;gap:6px;padding:6px 11px;border-radius:9px;border:1px solid ${c.border2};background:${c.surface};font-size:12.5px"><span style="color:${c.ink3}">Sort</span>${s}${ic.chevron}</span>`;
const views = (items) => `<div style="display:flex;gap:2px;border-bottom:1px solid ${c.border}">${items.map(([n, k, on]) => `<span style="display:flex;align-items:center;gap:7px;padding:9px 14px;font-size:13.5px;${on ? `color:${c.ink};font-weight:600;box-shadow:inset 0 -2px 0 ${c.ink}` : `color:${c.ink2}`}">${n}<span style="font-size:11.5px;padding:0 7px;border-radius:999px;background:${on ? c.ink : c.surface};color:${on ? c.bg : c.ink3};font-variant-numeric:tabular-nums">${k}</span></span>`).join('')}<span style="display:flex;align-items:center;padding:9px 12px;font-size:13px;color:${c.sel}">+ Save view</span></div>`;
const facet = (title, opts) => `<div style="display:flex;flex-direction:column;gap:2px;padding:10px 0;border-top:1px solid ${c.border}">
  <span style="font-size:12px;font-weight:600;color:${c.ink2};padding-bottom:4px">${title}</span>
  ${opts.map(([s, n, on]) => `<div style="display:flex;align-items:center;gap:8px;padding:3px 0;font-size:13px">${box(on)}<span style="flex:1;${on ? 'font-weight:600' : ''}">${s}</span><span style="color:${c.ink3};font-size:12px;font-variant-numeric:tabular-nums">${n}</span></div>`).join('')}</div>`;
const filterChip = (s) => `<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 5px 3px 10px;border-radius:999px;background:${c.selSoft};color:${c.sel};font-size:12px;font-weight:500">${s}<span style="display:flex">${ic.close}</span></span>`;
const disabled = (s) => `<span style="display:inline-flex;align-items:center;gap:8px;padding:10px 26px;border-radius:10px;background:${c.exon};color:${c.ink3};font-size:14.5px;font-weight:600">${ic.play}${s}</span>`;

// Certainty as a bar: settled spends no colour, measured is amber, open is red.
const certainty = (s, m, o, w = 150) => {
  const t = s + m + o;
  const seg1 = (n, col) => n ? `<span style="width:${(n / t) * 100}%;background:${col};border-radius:2px"></span>` : '';
  return `<div style="display:flex;flex-direction:column;gap:4px;width:${w}px">
    <div style="display:flex;gap:2px;height:6px">${seg1(s, c.border2)}${seg1(m, c.measBar)}${seg1(o, c.open)}</div>
    <span style="font-size:11.5px;color:${c.ink3};font-variant-numeric:tabular-nums">${s} settled · <span style="color:${m ? c.meas : c.ink3}">${m} measured</span> · <span style="color:${o ? c.open : c.ink3};${o ? 'font-weight:600' : ''}">${o} open</span></span></div>`;
};
const status = (st) => {
  const m = {
    running: [`<span style="width:10px;height:10px;border-radius:50%;background:${c.sel};box-shadow:0 0 0 4px ${c.selSoft}"></span>`, c.sel, 'running'],
    failed: [`<span style="width:10px;height:10px;border-radius:2px;background:${c.open};transform:rotate(45deg)"></span>`, c.open, 'failed'],
    succeeded: [`<span style="display:flex;color:${c.ink2}">${ic.check(c.ink2)}</span>`, c.ink2, 'succeeded'],
    cancelled: [`<span style="width:10px;height:10px;border-radius:50%;border:2px solid ${c.ink3}"></span>`, c.ink3, 'cancelled'],
    'needs you': [`<span style="width:10px;height:10px;border-radius:50%;background:${c.surface};border:2.5px solid ${c.open}"></span>`, c.open, 'needs you'],
  }[st];
  return `<span style="display:inline-flex;align-items:center;gap:8px;color:${m[1]};font-weight:${st === 'succeeded' || st === 'cancelled' ? 500 : 600};white-space:nowrap"><span style="width:16px;display:flex;justify-content:center">${m[0]}</span>${m[2]}</span>`;
};
const learnLink = (topic, mins, why) => `<div style="display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:10px;background:${c.bg};border:1px solid ${c.border}">
  <svg width="44" height="14" viewBox="0 0 44 14" style="flex:none"><line x1="3" y1="7" x2="41" y2="7" style="stroke:${c.line};stroke-width:4;stroke-linecap:round"></line><circle cx="7" cy="7" r="4" style="fill:${c.settled}"></circle><circle cx="22" cy="7" r="5" style="fill:${c.selSoft};stroke:${c.sel};stroke-width:2"></circle><circle cx="37" cy="7" r="4" style="fill:${c.surface};stroke:${c.ink3};stroke-width:1.5"></circle></svg>
  <div style="display:flex;flex-direction:column;min-width:0"><span style="font-size:12px;color:${c.ink3}">${why}</span><span style="font-size:13.5px;font-weight:600">${topic} · ${mins}</span></div>
  <span style="margin-left:auto;color:${c.sel};display:flex">${ic.arrow}</span></div>`;

// ── the top bar: logo (home) · three workspaces · search · learn · help · lab ─
const NAV = ['Build', 'Runs', 'Registry'];
const labsBar = (active) => `<header style="height:60px;flex:none;display:flex;align-items:center;gap:26px;padding:0 28px;border-bottom:1px solid ${c.border};background:${c.bg}">
  ${logo(c, 'Comeni Labs')}
  <nav style="display:flex;align-items:center;gap:4px;font-size:14px">${NAV.map(n => n === active
    ? `<span style="padding:6px 14px;border-radius:8px;background:${c.surface};border:1px solid ${c.border};color:${c.ink};font-weight:600">${n}</span>`
    : `<span style="padding:6px 12px;border:1px solid transparent;color:${c.ink2}">${n}</span>`).join('')}</nav>
  <div style="display:flex;align-items:center;gap:10px;width:400px;height:38px;padding:0 14px;border-radius:10px;border:1px solid ${c.border2};background:${c.surface};color:${c.ink3};font-size:13.5px;margin-left:auto">
    ${ic.search}<span>Describe an analysis, or jump to one</span><span style="margin-left:auto">${kbd('⌘K')}</span></div>
  <div style="display:flex;align-items:center;gap:16px;font-size:13px;color:${c.ink2}">
    <span style="display:inline-flex;align-items:center;gap:7px"><svg width="22" height="10" viewBox="0 0 22 10"><line x1="2" y1="5" x2="20" y2="5" style="stroke:${c.line};stroke-width:3;stroke-linecap:round"></line><circle cx="4" cy="5" r="2.5" style="fill:${c.surface};stroke:${c.ink};stroke-width:1.5"></circle><circle cx="18" cy="5" r="2.5" style="fill:${c.surface};stroke:${c.ink};stroke-width:1.5"></circle></svg>Learn in Code</span>
    <span style="width:28px;height:28px;border-radius:50%;border:1px solid ${c.border2};display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600;color:${c.ink2}">?</span>
    <span style="display:inline-flex;align-items:center;gap:8px;padding:4px 10px 4px 4px;border-radius:999px;border:1px solid ${c.border};background:${c.surface};color:${c.ink}">
      <span style="width:24px;height:24px;border-radius:50%;background:${c.selSoft};color:${c.sel};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600">FL</span>${LAB}${ic.chevron}</span>
  </div>
</header>`;
const subnav = (items, on) => `<div style="display:flex;gap:2px;padding:0 28px;border-bottom:1px solid ${c.border};background:${c.bg}">${items.map(s => `<span style="padding:10px 14px;font-size:13.5px;${s === on ? `color:${c.ink};font-weight:600;box-shadow:inset 0 -2px 0 ${c.ink}` : `color:${c.ink2}`}">${s}</span>`).join('')}</div>`;

// ── the pipeline canvas ─────────────────────────────────────────
const NW = 160;
const STEPS = {
  trim: { x: 170, y: 110, name: 'TRIMGALORE', ins: ['fastq.reads'], outs: ['fastq.reads[trimmed]'], foot: '9 settled' },
  qc: { x: 170, y: 330, name: 'FASTQC', ins: ['fastq.reads'], outs: ['qc.report'], foot: '4 settled' },
  star: { x: 370, y: 110, name: 'STAR_ALIGN', ins: ['fastq.reads[trimmed]', 'genome.index.star'], outs: ['alignment.bam'], foot: '13 settled', meas: '1 measured' },
  sort: { x: 570, y: 110, name: 'SAMTOOLS_SORT', ins: ['alignment.bam'], outs: ['alignment.bam[sorted]'], foot: '6 settled' },
  fc: { x: 770, y: 110, name: 'SUBREAD_FEATURECOUNTS', ins: ['alignment.bam[sorted]'], outs: ['counts.matrix', 'counts.summary'], foot: '3 settled', meas: '3 measured', open: '1 needs you' },
  mqc: { x: 770, y: 330, name: 'MULTIQC', ins: ['qc.report', 'counts.summary'], outs: ['qc.html'], foot: '2 settled' },
};
const portY = (n, i) => n.y + 37 + i * 19 + 9.5;
const inY = (k, i) => portY(STEPS[k], i);
const outY = (k, i) => portY(STEPS[k], STEPS[k].ins.length + i);
function pipelineCanvas({ show = Object.keys(STEPS), proposed = null, sel = null, h = 700 } = {}) {
  const on = (k) => show.includes(k) || k === proposed;
  const port = (dir, p) => `<div style="display:flex;align-items:center;gap:6px;height:19px;font-family:${MONO};font-size:10.5px;color:${dir === 'in' ? c.ink2 : c.ink3};white-space:nowrap;overflow:hidden">
    <svg width="9" height="9" viewBox="0 0 10 10" style="flex:none"><path d="${dir === 'in' ? 'M7 2 L3 5 L7 8' : 'M3 2 L7 5 L3 8'}" style="fill:none;stroke:${c.ink3};stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round"></path></svg>${p}</div>`;
  const dotAt = (side, y, hot) => `<span style="position:absolute;${side}:-5px;top:${y - 4}px;width:8px;height:8px;border-radius:2px;background:${hot ? c.sel : c.surface};border:1.5px solid ${hot ? c.sel : c.border2}"></span>`;
  const node = (k) => {
    const n = STEPS[k], isSel = sel === k, isProp = proposed === k;
    const edge = isSel ? `border:1.5px solid ${c.sel};box-shadow:0 0 0 3px ${c.selSoft}` : isProp ? `border:1.5px dashed ${c.sel}` : `border:1px solid ${c.border2}`;
    const ports = [...n.ins.map(p => port('in', p)), ...n.outs.map(p => port('out', p))].join('');
    const dots = [...n.ins.map((_, i) => dotAt('left', 37 + i * 19 + 9.5, isSel)), ...n.outs.map((_, i) => dotAt('right', 37 + (n.ins.length + i) * 19 + 9.5, isSel))].join('');
    const footer = isProp ? `<span style="color:${c.sel};font-weight:600">Proposed · not added yet</span>`
      : [n.open ? `<span style="color:${c.open};font-weight:600">${n.open}</span>` : '', n.meas ? `<span style="color:${c.meas};font-weight:500">${n.meas}</span>` : '', n.foot].filter(Boolean).join(' · ');
    return `<div style="position:absolute;left:${n.x}px;top:${n.y}px;width:${NW}px;border-radius:10px;background:${isProp ? c.canvas : c.surface};${edge};display:flex;flex-direction:column;${isProp ? 'opacity:.92' : ''}">
      ${dots}
      <div style="display:flex;align-items:center;height:32px;padding:0 10px;border-bottom:1px solid ${c.border}"><span style="font-family:${MONO};font-size:11px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${n.name}</span>${n.open && !isProp ? `<span style="margin-left:auto;width:8px;height:8px;border-radius:50%;background:${c.open};flex:none"></span>` : ''}</div>
      <div style="padding:5px 10px">${ports}</div>
      <div style="padding:5px 10px 7px;border-top:1px solid ${c.border};font-size:11px;color:${c.ink3};white-space:nowrap">${footer}</div></div>`;
  };
  const input = (x, y, name, type, note) => `<div style="position:absolute;left:${x}px;top:${y}px;width:130px;height:84px;border-radius:10px;background:${c.selSoft};border:1.5px dashed ${c.sel};display:flex;flex-direction:column;justify-content:center;gap:2px;padding:0 11px;box-sizing:border-box">
    <span style="position:absolute;right:-5px;top:38px;width:8px;height:8px;border-radius:2px;background:${c.surface};border:1.5px solid ${c.border2}"></span>
    <span style="font-size:11px;font-weight:600;color:${c.sel}">Input</span>
    <span style="font-family:${MONO};font-size:12px">${name}</span>
    <span style="font-family:${MONO};font-size:10px;color:${c.ink2}">${type}</span>${note ? `<span style="font-size:10.5px;color:${c.ink2}">${note}</span>` : ''}</div>`;
  const wire = (x1, y1, x2, y2, mx, { dash = false, hot = false } = {}) => {
    const st = `fill:none;stroke:${hot ? c.sel : c.rail};stroke-width:2;stroke-linejoin:round;${dash ? 'stroke-dasharray:5 4;' : ''}`;
    if (Math.abs(y1 - y2) < 0.5) return `<path d="M${x1} ${y1} H${x2}" style="${st}"></path>`;
    const r = 6, s = y2 > y1 ? 1 : -1;
    return `<path d="M${x1} ${y1} H${mx - r} Q${mx} ${y1} ${mx} ${y1 + s * r} V${y2 - s * r} Q${mx} ${y2} ${mx + r} ${y2} H${x2}" style="${st}"></path>`;
  };
  const W = [];
  const R = 146; // input right edge
  if (on('trim')) W.push(wire(R, 172, 170, inY('trim', 0), 158));
  if (on('qc')) W.push(wire(R, 172, 170, inY('qc', 0), 158));
  if (on('star')) { W.push(wire(330, outY('trim', 0), 370, inY('star', 0), 350)); W.push(wire(R, 492, 370, inY('star', 1), 358)); }
  if (on('sort')) W.push(wire(530, outY('star', 0), 570, inY('sort', 0), 550, { dash: proposed === 'sort', hot: proposed === 'sort' }));
  if (on('fc')) W.push(wire(730, outY('sort', 0), 770, inY('fc', 0), 750, { hot: sel === 'fc' }));
  if (on('mqc')) {
    W.push(wire(330, outY('qc', 0), 770, inY('mqc', 0), 750));
    const y1 = outY('fc', 1), y2 = inY('mqc', 1);
    W.push(`<path d="M930 ${y1} H938 Q944 ${y1} 944 ${y1 + 6} V294 Q944 300 938 300 H764 Q758 300 758 306 V${y2 - 6} Q758 ${y2} 764 ${y2} H770" style="fill:none;stroke:${c.rail};stroke-width:2;stroke-linejoin:round"></path>`);
  }
  const count = show.length;
  return `<section style="position:relative;height:${h}px;border-radius:14px;background-color:${c.canvas};background-image:radial-gradient(${c.grid} 1.2px, transparent 1.2px);background-size:20px 20px;border:1px solid ${c.border};overflow:hidden">
    <div style="position:absolute;left:16px;top:14px;right:16px;display:flex;justify-content:space-between;align-items:center">
      ${small(`${count} steps · 2 inputs`)}
      <span style="display:flex;gap:10px;align-items:center">${small('12 samples, one task each')}</span>
    </div>
    <svg style="position:absolute;left:0;top:0" width="980" height="${h}">${W.join('')}</svg>
    ${input(16, 130, 'reads', 'fastq.reads[paired]', '× 12 samples')}
    ${input(16, 450, 'reference', 'genome.index.star', 'read once per task')}
    ${Object.keys(STEPS).filter(on).map(node).join('')}
    <div style="position:absolute;left:16px;bottom:16px;display:flex;gap:8px">${secondary(c, 'Fit')}${secondary(c, '+ Add step', c.sel)}</div>
    <div style="position:absolute;right:16px;bottom:16px;padding:6px 10px;border-radius:9px;background:${c.surface};border:1px solid ${c.border};font-size:12px;color:${c.ink2};display:flex;gap:12px;align-items:center">
      <span style="display:flex;align-items:center;gap:5px"><span style="width:10px;height:6px;border-radius:2px;background:${c.border2}"></span>settled</span>
      <span style="display:flex;align-items:center;gap:5px"><span style="width:10px;height:6px;border-radius:2px;background:${c.measBar}"></span>measured</span>
      <span style="display:flex;align-items:center;gap:5px"><span style="width:10px;height:6px;border-radius:2px;background:${c.open}"></span>needs you</span></div>
  </section>`;
}
const pipelineHeader = (chips, view = 0, runBtn = true) => `<div style="height:74px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 28px">
  <div style="display:flex;align-items:center;gap:14px">
    <span style="font-size:26px;font-weight:600;letter-spacing:-.02em">rnaseq-counts</span>${chips}
  </div>
  <div style="display:flex;align-items:center;gap:14px">${seg(c, ['Canvas', 'Pipeline file'], view)}${runBtn ? primary(c, 'Run', ic.play) : disabled('Run')}</div>
</div>`;

// A vertical metro line of build steps: the same drawing Code uses for a route.
function stepLine(items) {
  const stop = (st) => ({
    done: `<span style="width:12px;height:12px;border-radius:50%;background:${c.settled}"></span>`,
    meas: `<span style="width:12px;height:12px;border-radius:50%;background:${c.measSoft};border:2.5px solid ${c.measBar};box-sizing:border-box"></span>`,
    now: `<span style="width:18px;height:18px;border-radius:50%;background:${c.selSoft};border:2.5px solid ${c.sel};box-sizing:border-box;display:flex;align-items:center;justify-content:center"><span style="width:6px;height:6px;border-radius:50%;background:${c.sel}"></span></span>`,
    open: `<span style="width:14px;height:14px;border-radius:50%;background:${c.surface};border:2.5px solid ${c.open};box-sizing:border-box"></span>`,
    todo: `<span style="width:12px;height:12px;border-radius:50%;background:${c.surface};border:2px solid ${c.ink3};box-sizing:border-box"></span>`,
  })[st];
  return `<div style="position:relative;display:flex;flex-direction:column">
    ${items.map(([st, title, meta, right], i) => {
      const lineCol = st === 'todo' || (items[i + 1] && items[i + 1][0] === 'todo') ? c.rail : c.line;
      return `<div style="position:relative;display:flex;align-items:center;gap:12px;min-height:34px">
        ${i < items.length - 1 ? `<span style="position:absolute;left:8px;top:17px;width:4px;height:34px;background:${lineCol};border-radius:2px"></span>` : ''}
        <span style="position:relative;width:20px;display:flex;justify-content:center;flex:none">${stop(st)}</span>
        <span style="font-size:13px;${st === 'now' ? 'font-weight:600' : ''};${st === 'todo' ? `color:${c.ink3}` : ''};font-family:${/^[A-Z_]+$/.test(title) ? MONO : UI}">${title}</span>
        <span style="font-size:12px;color:${c.ink3}">${meta}</span>
        <span style="margin-left:auto;font-size:11.5px;color:${st === 'meas' ? c.meas : st === 'open' ? c.open : c.ink3};${st === 'open' ? 'font-weight:600' : ''}">${right}</span></div>`;
    }).join('')}</div>`;
}
const composer = (ph) => `<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:12px;border:1px solid ${c.border2};background:${c.surface};font-size:13.5px;color:${c.ink3}"><span style="flex:1">${ph}</span><span style="width:30px;height:30px;border-radius:8px;background:${c.bg};border:1px solid ${c.border};display:flex;align-items:center;justify-content:center;color:${c.ink2}">${ic.send}</span></div>`;

// ── Home ────────────────────────────────────────────────────────
function home() {
  const cols = 'minmax(0, 1.6fr) 160px 70px 110px 110px';
  const pipeRow = (p) => `<div style="display:grid;grid-template-columns:${cols};align-items:center;gap:14px;padding:12px 16px;border-top:1px solid ${c.border};font-size:13px">
    <div style="display:flex;flex-direction:column;gap:2px;min-width:0"><span style="font-family:${MONO};font-size:13.5px;font-weight:500">${p.name}</span><span style="color:${c.ink2};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${p.makes} · ${p.steps} steps</span></div>
    ${certainty(p.settled, p.measured, p.open)}
    <span style="text-align:right;font-variant-numeric:tabular-nums">${p.runs}</span>
    ${status(p.last)}
    <span style="color:${c.ink2}">${p.owner}</span></div>`;
  const open = PIPES.reduce((a, p) => a + p.open, 0);
  return page(1440, 1100, `${labsBar('')}
  <main style="flex:1;display:flex;flex-direction:column;gap:22px;padding:28px 28px 32px">
    <div style="display:flex;justify-content:space-between;align-items:flex-end">
      <div style="display:flex;flex-direction:column;gap:4px">${h1(LAB)}<span style="font-size:14px;color:${c.ink2}">${PIPES.length} pipelines · 1 run going · ${open} values need a person</span></div>
      <div style="display:flex;gap:10px">${secondary(c, 'Import pipeline.yml')}${primary(c, 'New analysis')}</div>
    </div>

    <div style="display:grid;grid-template-columns:repeat(3, minmax(0, 1fr));gap:16px">
      ${card(`<div style="display:flex;justify-content:space-between;align-items:center">${h2('Running now')}${status('running')}</div>
        <span style="font-family:${MONO};font-size:15px;font-weight:500">rnaseq-counts <span style="color:${c.ink3};font-size:12px">b71e04d2</span></span>
        <div style="display:flex;gap:3px">${[1, 1, 1, 0.5, 0, 0].map(f => `<span style="flex:1;height:7px;border-radius:3px;background:${f === 1 ? c.line : f ? c.sel : c.border}"></span>`).join('')}</div>
        <span style="font-size:13px;color:${c.ink2}">3 of 6 steps · on SAMTOOLS_SORT, 9 of 12 tasks · 21m 40s</span>
        ${small('Started by R. Correia · relaunch of a3f9c2e1 with more memory')}`)}
      ${card(`<div style="display:flex;justify-content:space-between;align-items:center">${h2('Waiting on a person')}${tag('red', `${open} values`)}</div>
        ${[['atac-peaks', 'strandedness and fragment size', 2], ['rnaseq-counts', 'strandedness', 1], ['16s-profile', 'primer set', 1]].map(([n, what, k]) => `<div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-top:1px solid ${c.border};font-size:13px">
          <span style="width:9px;height:9px;border-radius:50%;border:2.5px solid ${c.open};flex:none"></span>
          <span style="font-family:${MONO};font-weight:500">${n}</span><span style="color:${c.ink2};flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${what}</span><a style="font-weight:500">Answer</a></div>`).join('')}
        ${small('No rule could settle these, so nothing runs until someone answers.')}`)}
      ${card(`<div style="display:flex;justify-content:space-between;align-items:center">${h2('Went wrong')}${status('failed')}</div>
        <span style="font-family:${MONO};font-size:15px;font-weight:500">rnaseq-counts <span style="color:${c.ink3};font-size:12px">a3f9c2e1</span></span>
        <span style="font-size:13px;color:${c.ink2}">STAR_ALIGN on SRR6357072 exited <b style="color:${c.ink}">137</b> on its third attempt, at 71.4 of 72 GB.</span>
        <div style="display:flex;gap:8px;align-items:center">${secondary(c, 'Open the run')}${small('relaunched · see Running now')}</div>`)}
    </div>

    <div style="flex:1;display:grid;grid-template-columns:minmax(0, 1fr) 380px;gap:18px;min-height:0">
      <section style="display:flex;flex-direction:column;gap:12px;min-width:0">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div style="display:flex;align-items:center;gap:14px">${h2('The lab’s work', 'font-size:17px')}${seg(c, ['By pipeline', 'By run'], 0)}</div>
          ${searchBox('Filter pipelines', 240)}
        </div>
        <div style="${panel()}overflow:hidden">
          <div style="display:grid;grid-template-columns:${cols};gap:14px;padding:9px 16px;font-size:11.5px;color:${c.ink3}"><span>Pipeline</span><span>How it was decided</span><span style="text-align:right">Runs</span><span>Last outcome</span><span>Owner</span></div>
          ${PIPES.map(pipeRow).join('')}
        </div>
        ${small('“How it was decided” counts every value in the pipeline: settled by a rule or a convention, measured from your files, or still open.')}
        <div style="${panel()}padding:16px 18px;display:flex;flex-direction:column;gap:10px">
          <div style="display:flex;justify-content:space-between;align-items:baseline">${h2('Compute this month')}${small('reserved against what tasks actually used')}</div>
          <div style="display:flex;flex-direction:column;gap:6px">
            ${[['wgs-variants', 1, 0.2], ['rnaseq-counts', 0.34, 0.2], ['atac-peaks', 0.14, 0.12], ['chip-peaks', 0.09, 0.08]].map(([n, r, u]) => `<div style="display:grid;grid-template-columns:130px 1fr 150px;align-items:center;gap:12px;font-size:12.5px">
              <span style="font-family:${MONO}">${n}</span>
              <div style="position:relative;height:10px"><span style="position:absolute;left:0;top:0;height:10px;width:${r * 100}%;border-radius:3px;background:${c.exon};border:1px solid ${c.border2};box-sizing:border-box"></span><span style="position:absolute;left:0;top:0;height:10px;width:${u * 100}%;border-radius:3px;background:${c.measBar}"></span></div>
              <span style="text-align:right;color:${c.ink2};font-variant-numeric:tabular-nums">${Math.round(r * 820)} / ${Math.round(u * 820)} GB·h</span></div>`).join('')}
          </div>
          ${small('Nearly all of the gap is wgs-variants: its callers ask for 64 GB and peak under 14.')}
        </div>
      </section>
      <aside style="display:flex;flex-direction:column;gap:16px;min-width:0">
        ${card(`<div style="display:flex;justify-content:space-between;align-items:center">${h2('Results ready')}<a style="font-size:13px;font-weight:500">All results</a></div>
          ${[['wgs-variants', '6 d ago', '18 files · 4.2 GB'], ['rnaseq-counts', '3 d ago', '6 files · 88 MB'], ['chip-peaks', '4 d ago', '9 files · 610 MB']].map(([n, w, f]) => `<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-top:1px solid ${c.border};font-size:13px"><span style="color:${c.ink2};display:flex">${ic.file}</span><span style="font-family:${MONO};font-weight:500">${n}</span><span style="color:${c.ink3}">${w}</span><span style="margin-left:auto;color:${c.ink2}">${f}</span></div>`).join('')}`)}
        ${card(`<div style="display:flex;justify-content:space-between;align-items:center">${h2('Changed in the registry')}<a style="font-size:13px;font-weight:500">Registry</a></div>
          <div style="display:flex;flex-direction:column;gap:4px;padding:8px 0;border-top:1px solid ${c.border}">
            <span style="font-size:13px">${mono('nf-core/star')} ${mono('2.7.11a → 2.7.11b', `color:${c.ink2}`)}</span>
            <span style="font-size:12.5px;color:${c.ink2}">Upgrading would change <b style="color:${c.ink}">1 setting</b> in rnaseq-counts.</span>
            <div style="display:flex;gap:8px;margin-top:4px">${secondary(c, 'Show the change')}</div></div>
          <div style="display:flex;flex-direction:column;gap:4px;padding:8px 0;border-top:1px solid ${c.border}">
            <span style="font-size:13px">Rule ${mono('R04')} read length, revised</span>
            <span style="font-size:12.5px;color:${c.ink2}">wgs-variants would come out the same. Nothing to do.</span></div>`)}
        ${learnLink('Library strandedness', '12 min', 'Two pipelines are waiting on this. Learn it in Code')}
      </aside>
    </div>
  </main>`);
}

// ── Describe ────────────────────────────────────────────────────
function describe() {
  const row = (label, value, why, t) => `<div style="display:grid;grid-template-columns:110px minmax(0, 1fr) auto;gap:14px;align-items:start;padding:12px 0;border-top:1px solid ${c.border}">
    <span style="font-size:12.5px;color:${c.ink3};padding-top:2px">${label}</span>
    <div style="display:flex;flex-direction:column;gap:3px;min-width:0"><span style="font-size:14px">${value}</span><span style="font-size:12.5px;color:${c.ink2};line-height:1.5">${why}</span></div>
    ${t}</div>`;
  const choice = (on, title, body, extra) => `<div style="flex:1;display:flex;gap:12px;padding:16px;border-radius:12px;background:${c.surface};${on ? `border:2px solid ${c.sel}` : `border:1px solid ${c.border2}`}">
    ${radio(on)}<div style="display:flex;flex-direction:column;gap:4px"><span style="font-size:14.5px;font-weight:600">${title}</span><span style="font-size:13px;color:${c.ink2};line-height:1.5">${body}</span>${extra || ''}</div></div>`;
  return page(1440, 1180, `${labsBar('Build')}
  <main style="flex:1;display:flex;justify-content:center;padding:44px 28px">
    <div style="width:860px;display:flex;flex-direction:column;gap:22px">
      <div style="display:flex;flex-direction:column;gap:6px">${h1('What do you want to analyse?', 32)}<span style="font-size:15px;color:${c.ink2}">Say it the way you would to a colleague. You’ll see what was understood before anything is built.</span></div>
      <div style="${panel()}padding:16px 18px;display:flex;flex-direction:column;gap:12px;border-color:${c.sel};box-shadow:0 0 0 3px ${c.selSoft}">
        <span style="font-size:16px;line-height:1.6">I have 12 paired-end RNA-seq samples from mouse liver, treated and control, and I want gene counts so I can run a differential expression analysis.</span>
        <div style="display:flex;justify-content:space-between;align-items:center">${small('The model reads this sentence. It never sees your files.')}${secondary(c, 'Read it again')}</div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">${small('Or start from')}${['Call variants from whole-genome reads', 'Find ATAC-seq peaks', 'Profile a 16S community', 'Open a pipeline.yml'].map(s => `<span style="padding:5px 12px;border-radius:999px;border:1px solid ${c.border2};background:${c.surface};font-size:12.5px;color:${c.ink2}">${s}</span>`).join('')}</div>

      <div style="${panel()}padding:18px 20px 8px">
        <div style="display:flex;justify-content:space-between;align-items:center;padding-bottom:10px">${h2('What was understood', 'font-size:17px')}<span style="display:flex;gap:8px;align-items:center">${small('Wrong? Click a line to correct it')}</span></div>
        ${row('You have', `${mono('fastq.reads[paired]')} × 12 samples`, 'From “12 paired-end RNA-seq samples”. You’ll point at the files when you run it.', tag('grey', 'you said'))}
        ${row('You want', `${mono('counts.matrix')} — reads per gene`, 'From “gene counts … differential expression”. The pipeline stops at counts; the statistics are yours.', tag('grey', 'you said'))}
        ${row('Organism', 'Mouse · reference GRCm39 with GENCODE M35 genes', 'From “mouse”. The newest assembly is the convention unless you name another.', tag('grey', 'convention'))}
        ${row('Read length', 'Measured when you add files', 'Alignment settings depend on it, so it is read from your reads rather than assumed.', tag('amber', 'will be measured'))}
        ${row('Strandedness', 'Not known yet', 'Your sentence doesn’t say, and counting with the wrong strand can drop half your reads. It won’t be guessed: you’ll be asked, or a step can measure it.', tag('red', 'needs you'))}
      </div>

      <div style="display:flex;flex-direction:column;gap:10px">
        ${h2('How do you want to build it?')}
        <div style="display:flex;gap:14px">
          ${choice(true, 'Step by step, with me', 'Each step is proposed with its reason and the alternatives. You add it, ask why, or pick another.', `<span style="margin-top:4px">${tag('green', 'good for a first pipeline')}</span>`)}
          ${choice(false, 'All at once', 'Everything a rule can settle is built in one go. Then only the open questions are left for you.')}
        </div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;padding-top:4px">
        ${small('The same description always gives the same pipeline.')}
        ${primary(c, 'Start building', ic.arrow)}
      </div>
    </div>
  </main>`);
}

// ── Build (step by step) ────────────────────────────────────────
function build() {
  const opt = (on, name, body, t) => `<div style="display:flex;gap:10px;padding:12px;border-radius:10px;background:${on ? c.selSoft : c.surface};border:1px solid ${on ? c.sel : c.border2}">
    ${radio(on)}<div style="display:flex;flex-direction:column;gap:3px;flex:1"><div style="display:flex;justify-content:space-between;gap:8px">${mono(name, 'font-size:12.5px;font-weight:500')}${t || ''}</div><span style="font-size:12.5px;color:${c.ink2};line-height:1.5">${body}</span></div></div>`;
  return page(1440, 900, `${labsBar('Build')}
  ${pipelineHeader(`${tag('blue', 'Building · step 4 of 6')}${small('Saved 3 s ago')}`, 0, false)}
  <main style="flex:1;display:grid;grid-template-columns:minmax(0, 1fr) 400px;gap:18px;padding:0 28px 24px;min-height:0">
    ${pipelineCanvas({ show: ['qc', 'trim', 'star'], proposed: 'sort', h: 718 })}
    <aside style="${panel()}display:flex;flex-direction:column;gap:14px;padding:16px 18px;min-height:0">
      ${stepLine([
        ['done', 'Goal', '12 paired samples → counts', 'you confirmed'],
        ['done', 'FASTQC', 'step 1', 'settled'],
        ['done', 'TRIMGALORE', 'step 2', 'settled'],
        ['meas', 'STAR_ALIGN', 'step 3', '1 measured'],
        ['now', 'Sort the alignments', 'step 4', ''],
        ['todo', 'Count reads per gene', 'step 5', ''],
        ['todo', 'Summarise quality', 'step 6', ''],
      ])}
      <div style="display:flex;flex-direction:column;gap:10px;padding:14px;border-radius:12px;border:1px solid ${c.border};background:${c.bg}">
        <div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:14.5px;font-weight:600">Step 4 · sort the alignments</span>${tag('grey', 'required')}</div>
        <span style="font-size:13px;line-height:1.55;color:${c.ink2}">Counting reads per gene needs a sorted BAM, so every version of this pipeline has a sort here. The only choice is which tool.</span>
        ${mono(`alignment.bam  →  alignment.bam[sorted]`, `font-size:11.5px;color:${c.ink3}`)}
        ${opt(true, 'SAMTOOLS_SORT', 'Makes exactly the sorted BAM the counting step asks for.', tag('blue', 'suggested'))}
        ${opt(false, 'SAMTOOLS_SORMADUP', 'Sorts and marks duplicates in one pass. Adds work you didn’t ask for.')}
        <div style="display:flex;gap:8px">${primary(c, 'Add it')}${secondary(c, 'Why this one?')}${secondary(c, 'Skip')}</div>
      </div>
      <div style="margin-top:auto">${composer('Ask about a step, or say what to change')}</div>
    </aside>
  </main>`);
}

// ── Answer an open value ────────────────────────────────────────
function question() {
  const ans = (on, v, body, extra) => `<div style="display:flex;gap:10px;padding:10px 12px;border-radius:10px;background:${on ? c.selSoft : c.surface};border:1px solid ${on ? c.sel : c.border2}">${radio(on)}<div style="display:flex;flex-direction:column;gap:2px;flex:1"><div style="display:flex;justify-content:space-between;gap:8px">${mono(v, 'font-size:12.5px;font-weight:500')}${extra || ''}</div><span style="font-size:12.5px;color:${c.ink2}">${body}</span></div></div>`;
  return page(1440, 980, `${labsBar('Build')}
  ${pipelineHeader(`${tag('green', 'Valid')}${tag('red', '1 value needs you')}${small('Saved just now')}`, 0, false)}
  <main style="flex:1;display:grid;grid-template-columns:minmax(0, 1fr) 420px;gap:18px;padding:0 28px 24px;min-height:0">
    ${pipelineCanvas({ sel: 'fc', h: 798 })}
    <aside style="${panel()}display:flex;flex-direction:column;gap:14px;padding:16px 18px;min-height:0">
      <div style="display:flex;justify-content:space-between;align-items:center">${seg(c, ['Step', 'Assistant'], 0)}<span style="color:${c.ink3};display:flex">${ic.close}</span></div>
      <div style="display:flex;flex-direction:column;gap:3px">${mono('SUBREAD_FEATURECOUNTS', 'font-size:15px;font-weight:500')}${mono('nf-core/subread/featurecounts@2.0.6', `font-size:11px;color:${c.ink3}`)}</div>
      <div style="display:flex;flex-direction:column;gap:10px;padding:14px;border-radius:12px;border:1.5px solid ${c.open};background:${c.surface}">
        <div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:14.5px;font-weight:600">Which strand were the reads made from?</span>${tag('red', 'needs you')}</div>
        <span style="font-size:12.5px;color:${c.ink3}">${mono('settings.strandedness')} · setting ${mono('-s')}</span>
        <span style="font-size:13px;line-height:1.55;color:${c.ink2};padding-left:12px;border-left:2px solid ${c.open}">No rule could settle it: your description doesn’t say, and nothing measured it. Counting against the wrong strand can drop half the reads without an error.</span>
        <span style="font-size:12.5px;font-weight:600">Answer from what you know <span style="font-weight:400;color:${c.ink3}">· these three are all the answers there are</span></span>
        ${ans(false, 'unstranded', 'Most older kits and many single-cell protocols.')}
        ${ans(false, 'forward', 'Ligation kits, e.g. ScriptSeq.')}
        ${ans(true, 'reverse', 'dUTP kits, e.g. Illumina TruSeq Stranded.', tag('grey', 'your answer'))}
        <div style="height:48px;border-radius:8px;border:1px solid ${c.border2};padding:8px 10px;font-size:12.5px;color:${c.ink};box-sizing:border-box">Kit is TruSeq Stranded mRNA, per the facility’s report.</div>
        ${small('Your reason is saved beside the value in the pipeline file, marked as answered by a person.')}
        <div style="display:flex;gap:8px">${primary(c, 'Save answer')}${secondary(c, 'Cancel')}</div>
      </div>
      <div style="display:flex;gap:10px;padding:12px 14px;border-radius:12px;border:1px dashed ${c.border2}">
        <div style="display:flex;flex-direction:column;gap:3px;flex:1"><span style="font-size:13.5px;font-weight:600">Not sure? Measure it instead</span><span style="font-size:12.5px;color:${c.ink2};line-height:1.5">Adds a step that checks 200,000 reads against the genes and settles this as <span style="color:${c.meas};font-weight:600">measured</span>.</span></div>
        <span style="align-self:center">${secondary(c, '+ Add step', c.sel)}</span>
      </div>
      <div style="margin-top:auto">${learnLink('Library strandedness', '12 min', 'What does this mean? Learn it in Code')}</div>
    </aside>
  </main>`);
}

// ── The pipeline file ───────────────────────────────────────────
function pipelineFile() {
  const cols = '200px 150px 118px minmax(0, 1fr)';
  const tierTag = (t) => ({ structural: tag('grey', 'required'), convention: tag('grey', 'convention'), measured: tag('amber', 'measured'), open: tag('red', 'needs you'), person: tag('dark', 'a person answered') })[t];
  const set = (k, v, t, why) => `<div style="display:grid;grid-template-columns:${cols};gap:14px;align-items:center;padding:9px 16px;border-top:1px solid ${c.border};font-size:13px">
    ${mono(k, 'font-size:12.5px')}${mono(v, `font-size:12.5px;${v === 'null' ? `color:${c.open}` : ''}`)}<span>${tierTag(t)}</span><span style="color:${c.ink2};line-height:1.45">${why}</span></div>`;
  const step = (name, pin, rows, note) => `<div style="${panel()}overflow:hidden">
    <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:${c.bg};border-bottom:1px solid ${c.border}">
      <div style="display:flex;align-items:center;gap:12px">${mono(name, 'font-size:14px;font-weight:500')}${mono(pin, `font-size:11.5px;color:${c.ink3}`)}</div>${small(note)}</div>
    <div style="display:grid;grid-template-columns:${cols};gap:14px;padding:8px 16px;font-size:11.5px;color:${c.ink3}"><span>Setting</span><span>Value</span><span>How it was decided</span><span>Why</span></div>
    ${rows.join('')}</div>`;
  const yaml = [
    ['k', 'steps:'], ['k', '  - id: star_align'], ['v', '    contract: nf-core/star/align@2.7.11a'], ['c', '    # sha256:4be1…c07e — pinned, so the same file builds the same pipeline'],
    ['k', '    settings:'], ['k', '      sjdbOverhang:'], ['v', '        value: 150'], ['v', '        why:'], ['m', '          tier: measured'], ['v', '          rule: R04'], ['v', '          premise: read_length = 151'],
    ['k', '      outSAMtype:'], ['v', '        value: BAM Unsorted'], ['v', '        why: { tier: structural, reason: "sorted next by samtools sort" }'],
    ['k', '  - id: featurecounts'], ['k', '    settings:'], ['k', '      strandedness:'], ['o', '        value: null'], ['o', '        why: { tier: ambiguous, open: true }'],
  ];
  const ycol = { k: c.ink, v: c.ink2, c: c.ink3, m: c.meas, o: c.open };
  return page(1440, 1060, `${labsBar('Build')}
  ${pipelineHeader(`${tag('green', 'Valid')}${tag('red', '1 value needs you')}`, 1, false)}
  <main style="flex:1;display:grid;grid-template-columns:minmax(0, 1fr) 440px;gap:18px;padding:0 28px 24px;min-height:0">
    <section style="display:flex;flex-direction:column;gap:14px;min-width:0">
      <div style="${panel()}padding:14px 18px;display:flex;align-items:center;gap:24px">
        <div style="display:flex;flex-direction:column;gap:6px;flex:1">
          <span style="font-size:14px;font-weight:600">41 values, and how each was decided</span>
          <div style="display:flex;gap:2px;height:10px"><span style="width:${36 / 41 * 100}%;background:${c.border2};border-radius:2px"></span><span style="width:${4 / 41 * 100}%;background:${c.measBar};border-radius:2px"></span><span style="width:${1 / 41 * 100}%;background:${c.open};border-radius:2px"></span></div>
          <span style="font-size:12px;color:${c.ink2}">36 settled by a rule or convention · <span style="color:${c.meas}">4 measured from your files</span> · <span style="color:${c.open};font-weight:600">1 needs you</span> · 0 chosen by a model</span>
        </div>
        <div style="display:flex;gap:8px">${secondary(c, 'Show only open')}${secondary(c, 'Download pipeline.yml')}</div>
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">${['Goal', 'Steps · 6', 'Settings · 41', 'Tools · 6 pinned', 'Registry layers · 2', 'Checks'].map((s, i) => `<span style="padding:5px 12px;border-radius:999px;font-size:12.5px;${i === 2 ? `background:${c.ink};color:${c.bg};font-weight:600` : `border:1px solid ${c.border2};background:${c.surface};color:${c.ink2}`}">${s}</span>`).join('')}</div>
      ${step('STAR_ALIGN', 'nf-core/star/align@2.7.11a', [
        set('sjdbOverhang', '150', 'measured', `Read length is ${mono('151 bp')}, measured from your files, minus one. Rule ${mono('R04')}.`),
        set('outSAMtype', 'BAM Unsorted', 'structural', 'The next step sorts, so sorting here would be done twice.'),
        set('outFilterMultimapNmax', '20', 'convention', 'ENCODE long-RNA settings, cited by the tool’s authors.'),
        set('twopassMode', 'None', 'convention', 'nf-core’s default for this module.'),
      ], '13 settled · 1 measured')}
      ${step('SUBREAD_FEATURECOUNTS', 'nf-core/subread/featurecounts@2.0.6', [
        set('strandedness', 'null', 'open', 'Not in your description, and not measured. Nothing runs until this is answered.'),
        set('isPairedEnd', 'true', 'measured', 'Both mates were found for all 12 samples.'),
        set('featureType', 'exon', 'convention', 'Counting over exons, grouped by gene, is the tool’s default for RNA-seq.'),
      ], '3 settled · 3 measured · 1 open')}
      ${small('4 more steps below · every value has a reason, or it is marked open')}
    </section>
    <aside style="${panel()}display:flex;flex-direction:column;min-height:0;overflow:hidden">
      <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid ${c.border}">${seg(c, ['pipeline.yml', 'main.nf'], 0)}${small('same file you download')}</div>
      <div style="flex:1;padding:12px 14px;background:${c.canvas};font-family:${MONO};font-size:12px;line-height:1.75;overflow:hidden">
        ${yaml.map(([k, s], i) => `<div style="display:flex;gap:14px;white-space:pre${k === 'o' ? `;background:${c.openSoft};margin:0 -14px;padding:0 14px` : ''}"><span style="color:${c.ink3};width:18px;text-align:right;flex:none">${i + 41}</span><span style="color:${ycol[k]}">${s}</span></div>`).join('')}
      </div>
      <div style="padding:12px 14px;border-top:1px solid ${c.border};font-size:12.5px;color:${c.ink2};line-height:1.5">This file <b style="color:${c.ink}">is</b> the pipeline. Open it anywhere and the same Nextflow comes out, with no network and no model.</div>
    </aside>
  </main>`);
}

// ── Run sheet ───────────────────────────────────────────────────
function runSheet() {
  const samples = ['SRR6357070', 'SRR6357071', 'SRR6357072', 'SRR6357073', 'SRR6357074', 'SRR6357075', 'SRR6357076'];
  const where = (on, title, body, t) => `<div style="display:flex;gap:10px;padding:12px;border-radius:10px;background:${c.surface};border:${on ? `2px solid ${c.sel}` : `1px solid ${c.border2}`}">${radio(on)}<div style="display:flex;flex-direction:column;gap:2px;flex:1"><div style="display:flex;justify-content:space-between">${`<span style="font-size:13.5px;font-weight:600">${title}</span>`}${t || ''}</div><span style="font-size:12.5px;color:${c.ink2};line-height:1.45">${body}</span></div></div>`;
  const stepHead = (n, s, done) => `<div style="display:flex;align-items:center;gap:10px"><span style="width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;${done ? `background:${c.line};color:#fff` : `border:2px solid ${c.ink};color:${c.ink}`}">${done ? ic.check('#FFFFFF') : n}</span>${h2(s, 'font-size:16px')}</div>`;
  return page(1440, 1040, `${labsBar('Build')}
  ${pipelineHeader(`${tag('green', 'Valid')}${tag('green', 'all values settled')}`, 0, true)}
  <main style="flex:1;display:grid;grid-template-columns:minmax(0, 1fr) 360px;gap:18px;padding:0 28px 24px;min-height:0">
    <section style="${panel()}padding:22px 24px;display:flex;flex-direction:column;gap:20px;min-width:0">
      <div style="display:flex;justify-content:space-between;align-items:center">${h1('Run rnaseq-counts', 24)}<span style="color:${c.ink3};display:flex">${ic.close}</span></div>
      ${stepHead(1, 'Your files', true)}
      <div style="margin-left:34px;display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:13px;color:${c.ink2}">Sample sheet · 12 samples, both mates found for each</span><div style="display:flex;gap:8px">${secondary(c, 'Replace sheet')}${secondary(c, 'Download template')}</div></div>
        <div style="border:1px solid ${c.border};border-radius:10px;overflow:hidden;font-size:12.5px">
          <div style="display:grid;grid-template-columns:140px minmax(0, 1fr) minmax(0, 1fr) 110px 90px;gap:10px;padding:7px 12px;background:${c.bg};color:${c.ink3};font-size:11.5px"><span>sample</span><span>fastq_1</span><span>fastq_2</span><span>condition</span><span style="text-align:right">read length</span></div>
          ${samples.map((s, i) => `<div style="display:grid;grid-template-columns:140px minmax(0, 1fr) minmax(0, 1fr) 110px 90px;gap:10px;padding:6px 12px;border-top:1px solid ${c.border};font-family:${MONO};font-size:11.5px"><span>${s}</span><span style="color:${c.ink2};overflow:hidden;text-overflow:ellipsis;white-space:nowrap">/data/liver/${s}_1.fastq.gz</span><span style="color:${c.ink2};overflow:hidden;text-overflow:ellipsis;white-space:nowrap">/data/liver/${s}_2.fastq.gz</span><span style="font-family:${UI}">${i % 2 ? 'treated' : 'control'}</span><span style="text-align:right;color:${c.meas}">151 bp</span></div>`).join('')}
          <div style="padding:6px 12px;border-top:1px solid ${c.border};color:${c.ink3}">5 more</div>
        </div>
      </div>
      ${stepHead(2, 'The reference', true)}
      <div style="margin-left:34px;display:flex;gap:10px;align-items:center;font-size:13px">
        <span style="padding:7px 12px;border-radius:9px;border:1px solid ${c.border2};background:${c.surface};display:inline-flex;gap:8px;align-items:center">${mono('GRCm39 · GENCODE M35')}${ic.chevron}</span>
        ${small('Index already built on this machine · 27 GB · used by 3 earlier runs')}
      </div>
      ${stepHead(3, 'Where it runs', false)}
      <div style="margin-left:34px;display:grid;grid-template-columns:repeat(3, minmax(0, 1fr));gap:10px">
        ${where(true, 'This machine', 'Docker on the lab server. Up to 32 CPUs and 128 GB for one task.', tag('green', 'ready'))}
        ${where(false, 'Kubernetes', 'The profile is written into the pipeline. You launch it on your cluster.', tag('grey', 'you launch'))}
        ${where(false, 'AWS Batch', 'The profile is written into the pipeline. You launch it with your account.', tag('grey', 'you launch'))}
      </div>
      <div style="margin-left:34px;display:flex;gap:18px;align-items:center;font-size:13px;color:${c.ink2}">
        <span>Largest task may use</span>
        <span style="padding:5px 10px;border-radius:8px;border:1px solid ${c.border2};font-family:${MONO};color:${c.ink}">16 CPUs</span>
        <span style="padding:5px 10px;border-radius:8px;border:1px solid ${c.border2};font-family:${MONO};color:${c.ink}">72 GB</span>
        ${small('STAR_ALIGN asks for 36 GB and may retry at up to 72 GB.')}
      </div>
    </section>
    <aside style="display:flex;flex-direction:column;gap:14px">
      ${card(`${h2('Ready to run')}
        ${[['Samples', '12'], ['Steps', '6'], ['Tasks, about', '62'], ['Where', 'this machine'], ['Took last time', '22m 51s'], ['Results go to', '/data/results/rnaseq-counts/…']].map(([k, v]) => `<div style="display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-top:1px solid ${c.border};font-size:13px"><span style="color:${c.ink2}">${k}</span><span style="text-align:right;${k === 'Results go to' ? `font-family:${MONO};font-size:11.5px` : ''}">${v}</span></div>`).join('')}
        <div style="display:flex;flex-direction:column;gap:6px;padding-top:6px">${primary(c, 'Start run', ic.play)}${small('Checked a moment ago: the pipeline passed a dry run.')}</div>`)}
      ${card(`${h2('What this run will record')}<span style="font-size:13px;line-height:1.55;color:${c.ink2}">Every task’s time, CPU and memory, and each retry with what it asked for. You can leave this page; the run keeps going.</span>`)}
    </aside>
  </main>`);
}

// ── Runs ────────────────────────────────────────────────────────
function runs() {
  const cols = '120px minmax(0, 1fr) 96px 110px 90px minmax(0, 1.2fr) 80px 120px 80px';
  const row = ([st, pipe, id, by, when, outcome, took, res, used, files], i) => `<div style="display:grid;grid-template-columns:${cols};align-items:center;gap:12px;padding:0 16px;height:46px;border-top:1px solid ${c.border};font-size:13px;${i === 1 ? `background:${c.selSoft};box-shadow:inset 3px 0 0 ${c.sel}` : ''}">
    ${status(st)}${mono(pipe, 'font-weight:500')}${mono(id, `color:${c.ink3};font-size:12px`)}
    <span style="color:${c.ink2}">${by}</span><span style="color:${c.ink2}">${when}</span>
    <span style="color:${st === 'failed' ? c.open : c.ink2};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${outcome}</span>
    <span style="text-align:right;font-variant-numeric:tabular-nums">${took}</span>
    <div style="position:relative;height:8px">${used === null ? `<span style="position:absolute;inset:0;border-radius:3px;background:repeating-linear-gradient(135deg, ${c.border2} 0 3px, transparent 3px 6px)"></span>` : `<span style="position:absolute;left:0;top:0;height:8px;width:${res * 100}%;border-radius:3px;background:${c.exon};border:1px solid ${c.border2};box-sizing:border-box"></span><span style="position:absolute;left:0;top:0;height:8px;width:${used * 100 * (res < 0.5 ? 0.45 : 0.9)}%;border-radius:3px;background:${c.measBar}"></span>`}</div>
    <span style="text-align:right;color:${c.ink2}">${files}</span></div>`;
  return page(1440, 1000, `${labsBar('Runs')}
  <main style="flex:1;display:flex;flex-direction:column;gap:16px;padding:24px 28px 28px;min-height:0">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div style="display:flex;align-items:baseline;gap:14px">${h1('Runs', 26)}${small('128 runs of 5 pipelines, newest first')}</div>
      ${searchBox('Search by pipeline, run id, sample or person')}
    </div>
    ${views([['All', 128, 1], ['Going now', 1], ['Went wrong', 9], ['Mine', 34], ['With results', 104]])}
    <div style="flex:1;display:grid;grid-template-columns:200px minmax(0, 1fr);gap:18px;min-height:0">
      <aside style="display:flex;flex-direction:column">
        <div style="display:flex;justify-content:space-between;padding-bottom:6px"><span style="font-size:13.5px;font-weight:600">Filters</span><a style="font-size:12px;font-weight:500">Clear</a></div>
        ${facet('Outcome', [['Going now', 1], ['Succeeded', 112], ['Went wrong', 9], ['Cancelled', 6]])}
        ${facet('Pipeline', [['rnaseq-counts', 52], ['wgs-variants', 31], ['atac-peaks', 22], ['chip-peaks', 18], ['16s-profile', 5]])}
        ${facet('Started by', [['R. Correia', 34], ['J. Costa', 31], ['M. Silva', 40], ['A. Reis', 23]])}
        ${facet('Where', [['This machine', 121], ['Kubernetes', 7]])}
        ${facet('When', [['This week', 11], ['This month', 38], ['Earlier', 79]])}
      </aside>
      <section style="display:flex;flex-direction:column;gap:10px;min-width:0">
        <div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:13.5px;font-weight:600">128 runs <span style="font-weight:400;color:${c.ink3}">· no filters</span></span><div style="display:flex;gap:8px;align-items:center">${sortBtn('Newest')}${seg(c, ['List', 'By pipeline'], 0)}</div></div>
        <div style="${panel()}overflow:hidden">
          <div style="display:grid;grid-template-columns:${cols};gap:12px;padding:9px 16px;font-size:11.5px;color:${c.ink3}"><span>Outcome</span><span>Pipeline</span><span>Run</span><span>Started by</span><span>When</span><span>Detail</span><span style="text-align:right">Took</span><span>Reserved · used</span><span style="text-align:right">Results</span></div>
          ${RUNS.map(row).join('')}
          <div style="padding:10px 16px;border-top:1px solid ${c.border};font-size:12.5px;color:${c.ink3}">117 more · keep scrolling</div>
        </div>
        <div style="display:flex;gap:18px;font-size:12px;color:${c.ink2};align-items:center">
          <span style="display:flex;gap:6px;align-items:center"><span style="width:18px;height:8px;border-radius:3px;background:${c.exon};border:1px solid ${c.border2}"></span>memory reserved</span>
          <span style="display:flex;gap:6px;align-items:center"><span style="width:18px;height:8px;border-radius:3px;background:${c.measBar}"></span>memory used at peak, measured</span>
          <span style="display:flex;gap:6px;align-items:center"><span style="width:18px;height:8px;border-radius:3px;background:repeating-linear-gradient(135deg, ${c.border2} 0 3px, transparent 3px 6px)"></span>not finished, so not known yet</span>
          ${kbd('J')} ${kbd('K')} <span>move</span> ${kbd('↵')} <span>open</span>
        </div>
      </section>
    </div>
  </main>`);
}

// ── A run ───────────────────────────────────────────────────────
const PROCS = ['FASTQC', 'TRIMGALORE', 'STAR_ALIGN', 'SAMTOOLS_SORT', 'SUBREAD_FEATURECOUNTS', 'MULTIQC'];
function timeline(failed) {
  const X0 = 170, W = 1100, MIN = 24, px = (m) => X0 + (m / MIN) * W;
  const lanes = failed ? {
    FASTQC: [[0, 1.6, 'd'], [0.2, 1.7, 'd'], [0.4, 1.5, 'd'], [1.7, 3.2, 'd'], [1.8, 3.4, 'd'], [2, 3.6, 'd']],
    TRIMGALORE: [[0, 3.8, 'd'], [0.3, 4, 'd'], [3.9, 7.6, 'd'], [4.1, 7.9, 'd'], [7.7, 11.4, 'd'], [8, 11.9, 'd']],
    STAR_ALIGN: [[4, 14.5, 'd'], [8, 12.6, 'x'], [12.7, 17.2, 'x'], [17.3, 22.1, 'x'], [14.6, 22.1, 'c']],
  } : {
    FASTQC: [[0, 1.6, 'd'], [0.2, 1.7, 'd'], [0.4, 1.5, 'd'], [1.7, 3.2, 'd'], [1.8, 3.4, 'd'], [2, 3.6, 'd']],
    TRIMGALORE: [[0, 3.8, 'd'], [0.3, 4, 'd'], [3.9, 7.6, 'd'], [4.1, 7.9, 'd'], [7.7, 11.4, 'd'], [8, 11.9, 'd']],
    STAR_ALIGN: [[4, 14.3, 'd'], [8, 11.8, 'x'], [11.9, 20.7, 'd'], [14.4, 21.7, 'r'], [12, 21.7, 'r']],
    SAMTOOLS_SORT: [[14.4, 16, 'd'], [20.8, 21.7, 'r']],
  };
  const LH = 40;
  const barCol = { d: [c.ink2, c.ink2], r: [c.sel, c.selSoft], x: [c.open, c.openSoft], c: [c.ink3, 'transparent'] };
  const rowsSvg = PROCS.map((p, li) => {
    const y = 18 + li * LH;
    const tasks = lanes[p] || [];
    const bars = tasks.map(([a, b, k], ti) => {
      const [stroke, fill] = barCol[k];
      const yy = y + 6 + (ti % 3) * 9;
      return k === 'd' ? `<rect x="${px(a)}" y="${yy}" width="${px(b) - px(a)}" height="6" rx="2" style="fill:${c.border2}"></rect>`
        : k === 'c' ? `<rect x="${px(a)}" y="${yy}" width="${px(b) - px(a)}" height="6" rx="2" style="fill:none;stroke:${c.ink3};stroke-width:1;stroke-dasharray:3 2"></rect>`
          : `<rect x="${px(a)}" y="${yy}" width="${px(b) - px(a)}" height="6" rx="2" style="fill:${fill};stroke:${stroke};stroke-width:1.5"></rect>`;
    }).join('');
    const hl = failed && p === 'STAR_ALIGN';
    return `${hl ? `<rect x="0" y="${y - 2}" width="1290" height="${LH}" style="fill:${c.openSoft};opacity:.55"></rect>` : ''}
      <text x="0" y="${y + 19}" style="font-family:${MONO};font-size:11px;fill:${hl ? c.open : c.ink2}">${p}</text>
      <line x1="${X0}" y1="${y + LH - 2}" x2="${X0 + W}" y2="${y + LH - 2}" style="stroke:${c.border};stroke-width:1"></line>${bars}
      ${tasks.length ? '' : `<text x="${X0 + 6}" y="${y + 19}" style="font-family:${UI};font-size:11px;fill:${c.ink3}">not started</text>`}`;
  }).join('');
  const top = 18 + PROCS.length * LH + 18;
  // CPU: asked (a reservation, exact) as a step line; used (a total spread over each task, derived) as a hatched step area.
  const asked = failed ? [[0, 8], [1.7, 14], [3.9, 12], [4, 20], [8, 16], [12.7, 16], [22.1, 0]] : [[0, 8], [1.7, 14], [3.9, 12], [4, 20], [8, 16], [11.9, 24], [14.4, 20], [20.8, 22], [21.7, 22]];
  const used = failed ? [[0, 5], [1.7, 9], [3.9, 8], [4, 13], [8, 12], [12.7, 8], [22.1, 0]] : [[0, 5], [1.7, 9], [3.9, 8], [4, 13], [8, 12], [11.9, 17], [14.4, 15]];
  const CH = 80, cy = (v) => top + CH - (v / 24) * CH;
  const stepPath = (pts, close) => {
    let d = `M${px(pts[0][0])} ${cy(pts[0][1])}`;
    for (let i = 1; i < pts.length; i++) d += ` H${px(pts[i][0])} V${cy(pts[i][1])}`;
    return close ? `${d} H${px(pts[pts.length - 1][0])} V${cy(0)} H${px(pts[0][0])} Z` : d;
  };
  const endUsed = used[used.length - 1][0];
  const ticks = [0, 4, 8, 12, 16, 20, 24].map(m => `<text x="${px(m)}" y="${top + CH + 18}" text-anchor="middle" style="font-family:${MONO};font-size:10.5px;fill:${c.ink3}">${m}m</text>`).join('');
  return `<svg viewBox="0 0 1290 ${top + CH + 26}" width="100%" style="display:block">
    <defs><pattern id="hatch${failed ? 'f' : 'r'}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="2.2" height="6" style="fill:${c.measBar}"></rect></pattern></defs>
    ${rowsSvg}
    ${!failed ? `<line x1="${px(21.7)}" y1="8" x2="${px(21.7)}" y2="${top + CH}" style="stroke:${c.sel};stroke-width:1.5;stroke-dasharray:3 3"></line><text x="${px(21.7) + 6}" y="12" style="font-family:${UI};font-size:11px;font-weight:600;fill:${c.sel}">now</text>` : ''}
    <text x="0" y="${top + 14}" style="font-family:${UI};font-size:11.5px;font-weight:600;fill:${c.ink}">CPUs</text>
    <text x="0" y="${top + 30}" style="font-family:${UI};font-size:11px;fill:${c.ink3}">asked · exact</text>
    <text x="0" y="${top + 44}" style="font-family:${UI};font-size:11px;fill:${c.meas}">used · spread, derived</text>
    <line x1="${X0}" y1="${cy(0)}" x2="${X0 + W}" y2="${cy(0)}" style="stroke:${c.border2};stroke-width:1"></line>
    <line x1="${X0}" y1="${cy(24)}" x2="${X0 + W}" y2="${cy(24)}" style="stroke:${c.border};stroke-width:1;stroke-dasharray:2 3"></line>
    <text x="${X0 - 8}" y="${cy(24) + 4}" text-anchor="end" style="font-family:${MONO};font-size:10.5px;fill:${c.ink3}">24</text>
    <text x="${X0 - 8}" y="${cy(0) + 4}" text-anchor="end" style="font-family:${MONO};font-size:10.5px;fill:${c.ink3}">0</text>
    <path d="${stepPath(used, true)}" style="fill:url(#hatch${failed ? 'f' : 'r'});opacity:.7"></path>
    <path d="${stepPath(asked)}" style="fill:none;stroke:${c.ink};stroke-width:2"></path>
    ${!failed ? `<text x="${px(endUsed) + 8}" y="${cy(8)}" style="font-family:${UI};font-size:11px;fill:${c.ink3}">no task finished since · used unknown</text>` : ''}
    ${ticks}
  </svg>`;
}
function runPage(failed) {
  const stats = failed ? [
    ['Progress', '2 of 6', 'steps finished', 'STAR_ALIGN never finished, so nothing after it ran.', null],
    ['Failures', '1', 'task, three attempts', 'The last attempt exited 137 and Nextflow stopped the run.', 'open'],
    ['Moving', 'stopped', '22 min in', 'After the third attempt of task 13.', null],
    ['Memory fit', '99%', 'peak of what was asked', 'SRR6357072 peaked at 71.4 GB of 72 GB.', 'open'],
  ] : [
    ['Progress', '3 of 6', 'steps finished', 'Steps, not tasks: tasks appear as data arrives, so a task percentage would have no total.', null],
    ['Failures', '0', '1 retry', 'STAR_ALIGN task 13 was stopped at 36 GB and succeeded at 72 GB.', 'meas'],
    ['Moving', '2m 35s', 'since the last task finished', 'Two STAR tasks are 7 and 10 minutes in.', null],
    ['Memory fit', '4.3×', 'over-asked, worst step', 'TRIMGALORE asks for 12 GB and peaked at 2.9.', 'meas'],
  ];
  const stat = ([k, big, sub, body, tone]) => `<div style="${panel()}padding:14px 16px;display:flex;flex-direction:column;gap:4px">
    <span style="font-size:12px;font-weight:500;color:${c.ink3}">${k}</span>
    <div style="display:flex;align-items:baseline;gap:8px"><span style="font-size:26px;font-weight:600;letter-spacing:-.02em;font-variant-numeric:tabular-nums;color:${tone === 'open' ? c.open : c.ink}">${big}</span><span style="font-size:12.5px;color:${tone === 'meas' ? c.meas : c.ink2}">${sub}</span></div>
    <span style="font-size:12.5px;line-height:1.5;color:${c.ink2}">${body}</span>
    ${k === 'Progress' ? `<div style="display:flex;gap:3px;margin-top:4px">${PROCS.map((_, i) => `<span style="flex:1;height:6px;border-radius:3px;background:${failed ? (i < 2 ? c.line : i === 2 ? c.open : c.border) : (i < 3 ? c.line : i === 3 ? c.sel : c.border)}"></span>`).join('')}</div>` : ''}</div>`;
  const pcols = 'minmax(0, 1.3fr) 90px 110px 90px 150px 110px 70px';
  const prow = ([p, tasks, st, slow, mem, cpu, retry], hl) => `<div style="display:grid;grid-template-columns:${pcols};gap:12px;align-items:center;padding:9px 16px;border-top:1px solid ${c.border};font-size:13px;${hl ? `background:${c.openSoft}` : ''}">
    ${mono(p, 'font-size:12.5px')}<span style="font-variant-numeric:tabular-nums">${tasks}</span><span style="color:${st === 'running' ? c.sel : st === 'failed' ? c.open : st === 'not started' ? c.ink3 : c.ink2};font-weight:${st === 'running' || st === 'failed' ? 600 : 400}">${st}</span>
    <span style="text-align:right;font-variant-numeric:tabular-nums">${slow}</span><span style="font-variant-numeric:tabular-nums">${mem}</span><span style="font-variant-numeric:tabular-nums;color:${c.ink2}">${cpu}</span><span style="text-align:right">${retry}</span></div>`;
  const memCell = (peak, ask) => ask ? `<span style="display:flex;align-items:center;gap:8px"><span style="position:relative;width:56px;height:6px;border-radius:3px;background:${c.exon}"><span style="position:absolute;left:0;top:0;height:6px;border-radius:3px;width:${Math.min(1, peak / ask) * 100}%;background:${c.measBar}"></span></span>${peak} / ${ask} GB</span>` : `<span style="color:${c.ink3}">asks ${peak} GB</span>`;
  const procRows = failed ? [
    ['FASTQC', '6 of 6', 'done', '1m 44s', memCell(1.2, 6), '1.9 of 2', '—'],
    ['TRIMGALORE', '6 of 6', 'done', '3m 58s', memCell(2.9, 12), '3.2 of 4', '—'],
    ['STAR_ALIGN', '1 of 6', 'failed', '10m 48s', memCell(71.4, 72), '7.4 of 8', '2'],
    ['SAMTOOLS_SORT', '—', 'not started', '—', memCell(8), 'asks 4', '—'],
    ['SUBREAD_FEATURECOUNTS', '—', 'not started', '—', memCell(8), 'asks 2', '—'],
    ['MULTIQC', '—', 'not started', '—', memCell(4), 'asks 1', '—'],
  ] : [
    ['FASTQC', '6 of 6', 'done', '1m 44s', memCell(1.2, 6), '1.9 of 2', '—'],
    ['TRIMGALORE', '6 of 6', 'done', '3m 58s', memCell(2.9, 12), '3.2 of 4', '—'],
    ['STAR_ALIGN', '4 of 6', 'running', '10m 20s', memCell(33.1, 36), '7.4 of 8', '1'],
    ['SAMTOOLS_SORT', '2 of 6', 'running', '1m 36s', memCell(3.1, 8), '3.6 of 4', '—'],
    ['SUBREAD_FEATURECOUNTS', '—', 'not started', '—', memCell(8), 'asks 2', '—'],
    ['MULTIQC', '—', 'not started', '—', memCell(4), 'asks 1', '—'],
  ];
  const header = `<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:20px">
    <div style="display:flex;flex-direction:column;gap:6px">
      ${small(`Runs / rnaseq-counts`)}
      <div style="display:flex;align-items:center;gap:14px"><span style="font-size:26px;font-weight:600;letter-spacing:-.02em">rnaseq-counts</span>${mono(failed ? 'a3f9c2e1' : 'b71e04d2', `color:${c.ink3};font-size:13px`)}${failed ? tag('red', 'went wrong') : tag('blue', 'running')}</div>
      <span style="font-size:13.5px;color:${c.ink2}">${failed ? 'Stopped in STAR_ALIGN after task 13 failed three times; 4 tasks never started · 22m 11s · this machine · started 21:04 by R. Correia' : 'On STAR_ALIGN and SAMTOOLS_SORT · 2 tasks running, 2 waiting for room · 21m 40s · this machine · started 09:12 by R. Correia'}</span>
    </div>
    <div style="display:flex;gap:8px;align-items:center">${secondary(c, 'Open the pipeline')}${secondary(c, 'Console')}${failed ? primary(c, 'Relaunch…') : secondary(c, 'Cancel run', c.open)}</div>
  </div>`;
  const failure = failed ? `<div style="${panel(`border-color:${c.open};`)}padding:18px 20px;display:grid;grid-template-columns:minmax(0, 1fr) minmax(0, 1.1fr);gap:24px">
    <div style="display:flex;flex-direction:column;gap:10px">
      <div style="display:flex;align-items:center;gap:10px">${mono('STAR_ALIGN', 'font-size:15px;font-weight:500')}${mono('SRR6357072', `color:${c.ink2};font-size:13px`)}${tag('red', 'exited 137')}</div>
      <span style="font-size:14px;line-height:1.55">Code 137 means the task was killed (SIGKILL) on its third attempt. The record doesn’t say who killed it, so nothing here guesses.</span>
      <div style="display:flex;flex-direction:column;gap:6px">
        <span style="font-size:12.5px;font-weight:600">The three attempts</span>
        ${[['1', 36, 35.8], ['2', 48, 47.6], ['3', 72, 71.4]].map(([n, ask, peak]) => `<div style="display:grid;grid-template-columns:70px 1fr 140px;gap:10px;align-items:center;font-size:12.5px"><span style="color:${c.ink2}">attempt ${n}</span><div style="position:relative;height:10px"><span style="position:absolute;left:0;top:0;height:10px;width:${(ask / 72) * 100}%;border-radius:3px;background:${c.exon};border:1px solid ${c.border2};box-sizing:border-box"></span><span style="position:absolute;left:0;top:0;height:10px;width:${(peak / 72) * 100}%;border-radius:3px;background:${c.measBar}"></span></div><span style="font-variant-numeric:tabular-nums;text-align:right">peak ${peak} of ${ask} GB</span></div>`).join('')}
        ${small('Each attempt used almost all of what it asked for.')}
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">${secondary(c, 'Relaunch with 96 GB for this step')}${secondary(c, 'Open the console at this task')}</div>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px;min-width:0">
      <div style="display:flex;justify-content:space-between">${h2('What Nextflow reported')}${small('shown as written')}</div>
      <pre style="margin:0;padding:12px 14px;border-radius:10px;background:${c.canvas};border:1px solid ${c.border};font-family:${MONO};font-size:11.5px;line-height:1.6;color:${c.ink2};white-space:pre-wrap">Error executing process > 'NFCORE_RNASEQ:ALIGN_STAR:STAR_ALIGN (SRR6357072)'

Caused by:
  Process \`STAR_ALIGN (SRR6357072)\` terminated with an error exit status (137)

Command error:
  .command.sh: line 9:    47 Killed    STAR --genomeDir star --readFilesIn ...

Work dir:
  /data/runs/a3f9c2e1/work/6b/1f0c9d4a2e</pre>
      ${learnLink('Why a task gets killed', '9 min', 'Exit codes and memory limits, in Code')}
    </div>
  </div>` : '';
  const H = failed ? 1500 : 1400;
  return page(1440, H, `${labsBar('Runs')}
  <main style="flex:1;display:flex;flex-direction:column;gap:18px;padding:22px 28px 28px">
    ${header}
    ${failure}
    <div style="display:grid;grid-template-columns:repeat(4, minmax(0, 1fr));gap:14px">${stats.map(stat).join('')}</div>
    <div style="${panel()}padding:16px 18px;display:flex;flex-direction:column;gap:10px">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div style="display:flex;align-items:baseline;gap:12px">${h2('Timeline')}${small(failed ? 'the red bars are the three attempts of task 13' : '26 tasks · 18 done · 2 running · 2 waiting')}</div>
        <div style="display:flex;gap:14px;font-size:12px;color:${c.ink2};align-items:center">
          <span style="display:flex;gap:6px;align-items:center"><span style="width:16px;height:6px;border-radius:2px;background:${c.border2}"></span>done</span>
          ${failed ? `<span style="display:flex;gap:6px;align-items:center"><span style="width:16px;height:6px;border-radius:2px;background:${c.openSoft};border:1.5px solid ${c.open}"></span>failed attempt</span><span style="display:flex;gap:6px;align-items:center"><span style="width:16px;height:6px;border-radius:2px;border:1px dashed ${c.ink3}"></span>stopped when the run ended</span>`
            : `<span style="display:flex;gap:6px;align-items:center"><span style="width:16px;height:6px;border-radius:2px;background:${c.selSoft};border:1.5px solid ${c.sel}"></span>running</span><span style="display:flex;gap:6px;align-items:center"><span style="width:16px;height:6px;border-radius:2px;background:${c.openSoft};border:1.5px solid ${c.open}"></span>failed attempt, retried</span>`}
        </div>
      </div>
      ${timeline(failed)}
    </div>
    <div style="${panel()}overflow:hidden">
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px">${h2('Steps')}${seg(c, ['Table', 'Graph'], 0)}</div>
      <div style="display:grid;grid-template-columns:${pcols};gap:12px;padding:6px 16px;font-size:11.5px;color:${c.ink3}"><span>Step</span><span>Tasks</span><span>State</span><span style="text-align:right">Slowest</span><span>Memory · peak of asked</span><span>CPUs · used of asked</span><span style="text-align:right">Retries</span></div>
      ${procRows.map((r) => prow(r, failed && r[0] === 'STAR_ALIGN')).join('')}
    </div>
    ${failed ? '' : `<div style="${panel()}overflow:hidden">
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px"><div style="display:flex;gap:10px;align-items:center">${h2('Tasks')}${filterChip('STAR_ALIGN')}</div>${searchBox('Sample or task id', 220)}</div>
      ${[['13', 'done ×2', 'SRR6357070', '10m 20s', '33.1 GB', '0'], ['14', 'done', 'SRR6357071', '10m 48s', '32.6 GB', '0'], ['15', 'running', 'SRR6357072', '9m 50s', '—', '—'], ['16', 'running', 'SRR6357073', '7m 30s', '—', '—'], ['17', 'waiting', 'SRR6357074', '—', '—', '—']].map(([n, st, s, t, m, e]) => `<div style="display:grid;grid-template-columns:60px 110px 150px 100px 100px 60px;gap:12px;padding:8px 16px;border-top:1px solid ${c.border};font-size:12.5px"><span style="font-family:${MONO};color:${c.ink3}">${n}</span><span style="color:${st === 'running' ? c.sel : c.ink2};font-weight:${st === 'running' ? 600 : 400}">${st}</span>${mono(s)}<span style="font-variant-numeric:tabular-nums">${t}</span><span style="font-variant-numeric:tabular-nums">${m}</span><span style="font-family:${MONO}">${e}</span></div>`).join('')}
    </div>`}
  </main>`);
}

// ── Registry ────────────────────────────────────────────────────
const REG_SUB = ['Overview', 'Catalogue', 'Work queue'];
function registry() {
  const flow = [['Found', '2,257', 'tools two sources offer'], ['Drafted', '2', 'everything provable, filled in'], ['With the model', '1', '6 waiting · one at a time'], ['Ready for review', '5', 'oldest waited 3 days'], ['In the registry', '245', 'approved by a person']];
  const xs = flow.map((_, i) => 60 + i * 300);
  const flowSvg = `<svg viewBox="0 0 1340 118" width="100%" style="display:block">
    <line x1="60" y1="40" x2="${xs[4]}" y2="40" style="stroke:${c.line};stroke-width:6;stroke-linecap:round"></line>
    ${xs.map((x, i) => i === 3 ? `<circle cx="${x}" cy="40" r="11" style="fill:${c.openSoft};stroke:${c.open};stroke-width:3"></circle>`
      : i === 2 ? `<circle cx="${x}" cy="40" r="10" style="fill:${c.selSoft};stroke:${c.sel};stroke-width:3"></circle><circle cx="${x}" cy="40" r="3.5" style="fill:${c.sel}"></circle>`
        : `<circle cx="${x}" cy="40" r="8" style="fill:${c.surface};stroke:${c.ink};stroke-width:3"></circle>`).join('')}
    ${flow.map(([k, n, s], i) => `<text x="${xs[i]}" y="16" text-anchor="middle" style="font-family:${UI};font-size:12px;font-weight:600;fill:${i === 3 ? c.open : c.ink2}">${k}</text>
      <text x="${xs[i]}" y="84" text-anchor="middle" style="font-family:${UI};font-size:22px;font-weight:600;fill:${c.ink}">${n}</text>
      <text x="${xs[i]}" y="106" text-anchor="middle" style="font-family:${UI};font-size:11.5px;fill:${c.ink3}">${s}</text>`).join('')}
  </svg>`;
  const source = (name, when, stale, rows, bar) => card(`<div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:16px;font-weight:600">${name}</span>${stale ? tag('amber', 'out of date · last read 2 d ago') : tag('green', `read ${when}`)}</div>
    <div style="display:flex;gap:2px;height:10px">${bar.map(([f, col]) => `<span style="width:${f * 100}%;background:${col};border-radius:2px"></span>`).join('')}</div>
    <div style="display:grid;grid-template-columns:repeat(4, minmax(0, 1fr));gap:10px">${rows.map(([n, k, col]) => `<div style="display:flex;flex-direction:column"><span style="font-size:18px;font-weight:600;font-variant-numeric:tabular-nums;color:${col || c.ink}">${n}</span><span style="font-size:12px;color:${c.ink2}">${k}</span></div>`).join('')}</div>
    ${stale ? `<div style="display:flex;justify-content:space-between;align-items:center;padding-top:6px;border-top:1px solid ${c.border}"><span style="font-size:12.5px;color:${c.ink2}">${mono('MI0104')} the catalogue page could not be read.</span>${secondary(c, 'Try again')}</div>` : `<span style="font-size:12.5px;color:${c.ink3}">Checked every hour and on startup. 2 requests, 10 s.</span>`}`);
  return page(1440, 1040, `${labsBar('Registry')}${subnav(REG_SUB, 'Overview')}
  <main style="flex:1;display:flex;flex-direction:column;gap:20px;padding:24px 28px 28px">
    <div style="display:flex;justify-content:space-between;align-items:flex-end">
      <div style="display:flex;flex-direction:column;gap:4px">${h1('Registry', 26)}<span style="font-size:14px;color:${c.ink2}">The tools your pipelines can use. Each one is described once, checked, and approved by a person.</span></div>
      <div style="display:flex;gap:10px;align-items:center">${small('last checked 03:00')}${secondary(c, 'Check sources now')}${primary(c, 'Add a tool')}</div>
    </div>
    <div style="${panel()}padding:18px 22px">${flowSvg}</div>
    <div style="display:grid;grid-template-columns:repeat(3, minmax(0, 1fr));gap:16px">
      ${card(`<div style="display:flex;justify-content:space-between;align-items:center">${h2('Ready for your review')}<span style="font-size:24px;font-weight:600;color:${c.open}">5</span></div><span style="font-size:13px;color:${c.ink2}">The oldest has waited 3 days. 4 passed every check.</span>${secondary(c, 'Start reviewing')}`)}
      ${card(`<div style="display:flex;justify-content:space-between;align-items:center">${h2('Stopped')}<span style="font-size:24px;font-weight:600">2</span></div><span style="font-size:13px;color:${c.ink2}">Both can be retried from where they stopped.</span>${secondary(c, 'See both')}`)}
      ${card(`<div style="display:flex;justify-content:space-between;align-items:center">${h2('Out of date')}<span style="font-size:24px;font-weight:600;color:${c.meas}">20</span></div><span style="font-size:13px;color:${c.ink2}">The tool changed upstream after it was added. 3 are used by your pipelines.</span>${secondary(c, 'Update the 3 in use')}`)}
    </div>
    <div style="display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:16px">
      ${source('nf-core', '14 min ago', false, [['2,062', 'found'], ['1,184', 'can be added'], ['214', 'in the registry'], ['16', 'out of date', c.meas]], [[198 / 1184, c.border2], [16 / 1184, c.measBar], [8 / 1184, c.sel], [962 / 1184, c.exon]])}
      ${source('pegi3s', '', true, [['195', 'found'], ['191', 'can be added'], ['31', 'in the registry'], ['4', 'out of date', c.meas]], [[27 / 191, c.border2], [4 / 191, c.measBar], [2 / 191, c.sel], [158 / 191, c.exon]])}
    </div>
    <div style="display:flex;gap:18px;font-size:12px;color:${c.ink2}">
      <span style="display:flex;gap:6px;align-items:center"><span style="width:16px;height:8px;border-radius:2px;background:${c.border2}"></span>current</span>
      <span style="display:flex;gap:6px;align-items:center"><span style="width:16px;height:8px;border-radius:2px;background:${c.measBar}"></span>out of date</span>
      <span style="display:flex;gap:6px;align-items:center"><span style="width:16px;height:8px;border-radius:2px;background:${c.sel}"></span>being added</span>
      <span style="display:flex;gap:6px;align-items:center"><span style="width:16px;height:8px;border-radius:2px;background:${c.exon}"></span>not added</span>
    </div>
  </main>`);
}

function workQueue() {
  const cols = '26px minmax(0, 1.4fr) minmax(0, 1.2fr) 90px 70px 90px';
  const group = (title, n, tone, rows) => `<div style="display:flex;align-items:center;gap:10px;padding:10px 16px;background:${c.bg};border-top:1px solid ${c.border};font-size:12.5px;font-weight:600">${ic.chevron}<span style="color:${tone || c.ink}">${title}</span><span style="color:${c.ink3};font-weight:400">${n}</span></div>${rows.join('')}`;
  const row = (sel, name, what, a, b, cc, o = {}) => `<div style="display:grid;grid-template-columns:${cols};gap:12px;align-items:center;padding:0 16px;height:44px;border-top:1px solid ${c.border};font-size:13px;${o.focus ? `background:${c.selSoft};box-shadow:inset 3px 0 0 ${c.sel}` : ''}">
    ${box(sel)}${mono(name, 'font-size:12.5px;font-weight:500')}<span style="color:${o.tone || c.ink2};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${what}</span><span style="font-variant-numeric:tabular-nums">${a}</span><span style="color:${c.ink2}">${b}</span><span style="text-align:right;color:${c.ink3}">${cc}</span></div>`;
  return page(1440, 1000, `${labsBar('Registry')}${subnav(REG_SUB, 'Work queue')}
  <main style="flex:1;display:flex;flex-direction:column;gap:14px;padding:22px 28px 28px;min-height:0">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div style="display:flex;align-items:baseline;gap:14px">${h1('Work queue', 26)}${small('Tools on their way into the registry. Only a person can approve one.')}</div>
      ${searchBox('Search tools')}
    </div>
    ${views([['Everything', 11, 1], ['Ready for review', 5], ['With the model', 3], ['Changes asked', 2], ['Stopped', 1]])}
    <div style="flex:1;display:grid;grid-template-columns:190px minmax(0, 1fr) 360px;gap:18px;min-height:0">
      <aside style="display:flex;flex-direction:column">
        <div style="padding-bottom:6px"><span style="font-size:13.5px;font-weight:600">Filters</span></div>
        ${facet('Source', [['nf-core', 7], ['pegi3s', 4]])}
        ${facet('Checks', [['All passed', 3], ['Some failed', 2]])}
        ${facet('Waiting', [['Under a day', 2], ['Over a day', 3]])}
        ${facet('Used by a pipeline', [['Yes', 2], ['No', 9]])}
      </aside>
      <section style="${panel()}overflow:hidden;min-width:0">
        <div style="display:grid;grid-template-columns:${cols};gap:12px;padding:9px 16px;font-size:11.5px;color:${c.ink3}"><span></span><span>Tool</span><span>State</span><span>Checks</span><span>Version</span><span style="text-align:right">Waiting</span></div>
        ${group('With the model', '3 · one at a time', c.sel, QUEUE.ai.map(([n, w, t, s]) => row(false, n, s === 'running' ? `<span style="color:${c.sel};font-weight:600">● ${w}</span>` : w, s === 'running' ? t : '—', '1', s === 'running' ? 'now' : 'queued')))}
        ${group('Ready for review', '5', c.open, QUEUE.review.map(([n, ch, rev, w], i) => row(i < 2, n, ch === '8 of 8' ? 'every check passed' : `<span style="color:${c.meas}">${8 - parseInt(ch)} check${8 - parseInt(ch) > 1 ? 's' : ''} to look at</span>`, ch, `rev ${rev}`, w, { focus: i === 0 })))}
        ${group('Changes asked', '2', null, QUEUE.changes.map(([n, why, who]) => row(false, n, `“${why}” · ${who}`, '—', 'rev 1', '1 d')))}
        ${group('Stopped', '1', null, QUEUE.failed.map(([n, why, code]) => row(false, n, `${mono(code)} ${why}`, '—', '—', '5 h')))}
        <div style="display:flex;align-items:center;gap:10px;padding:10px 16px;border-top:1px solid ${c.border};font-size:12.5px;color:${c.ink3}">${ic.chevron} Added recently · 10</div>
        <div style="position:relative;height:0"><div style="position:absolute;left:50%;top:20px;transform:translateX(-50%);display:flex;align-items:center;gap:14px;padding:10px 12px 10px 18px;border-radius:12px;background:${c.ink};color:${c.bg};box-shadow:${c.float};white-space:nowrap;font-size:13px"><b>2 selected</b><span style="opacity:.7">Open side by side</span><span style="opacity:.7">Ask for changes…</span></div></div>
      </section>
      <aside style="${panel()}padding:16px;display:flex;flex-direction:column;gap:12px">
        <div style="display:flex;justify-content:space-between;align-items:center">${tag('red', 'ready for review')}${small('waiting 12 min')}</div>
        ${mono('nf-core / samtools/sort', 'font-size:17px;font-weight:500')}
        <span style="font-size:13px;color:${c.ink2}">Revision 2 · asked for after “the output’s state wasn’t proved”.</span>
        ${stepLine([['done', 'Drafted', '8 values proved', ''], ['done', 'Model answered', '6 questions', ''], ['done', 'Built and checked', '8 of 8', ''], ['now', 'Your review', '', '']])}
        <div style="display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:8px">
          <div style="padding:8px 10px;border-radius:8px;background:${c.bg}"><span style="font-size:18px;font-weight:600">8</span><span style="display:block;font-size:11.5px;color:${c.ink2}">proved from the source</span></div>
          <div style="padding:8px 10px;border-radius:8px;background:${c.measSoft}"><span style="font-size:18px;font-weight:600;color:${c.meas}">6</span><span style="display:block;font-size:11.5px;color:${c.meas}">answered by the model</span></div>
        </div>
        <div style="margin-top:auto;display:flex;flex-direction:column;gap:8px">
          <div style="display:flex;gap:8px">${primary(c, 'Open review')}${secondary(c, 'Ask for changes…')}</div>
          <div style="display:flex;gap:10px;flex-wrap:wrap;font-size:11.5px;color:${c.ink3}"><span>${kbd('↵')} open</span><span>${kbd('J')} ${kbd('K')} next / previous</span><span>${kbd('X')} select</span></div>
        </div>
      </aside>
    </div>
  </main>`);
}

function adaptation() {
  const q = (id, question, answer, who, evidence, alts) => `<div style="${panel()}padding:14px 16px;display:flex;flex-direction:column;gap:8px">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
      <div style="display:flex;flex-direction:column;gap:2px"><span style="font-size:14px;font-weight:600">${question}</span>${mono(id, `font-size:11.5px;color:${c.ink3}`)}</div>
      ${who === 'model' ? tag('amber', 'the model answered') : tag('grey', 'proved from the source')}
    </div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">${mono(answer, `font-size:13px;font-weight:500;padding:4px 10px;border-radius:7px;background:${who === 'model' ? c.measSoft : c.bg};border:1px solid ${who === 'model' ? c.measBar : c.border}`)}
      ${alts ? `<span style="font-size:12px;color:${c.ink3}">out of ${alts}</span>` : ''}</div>
    ${evidence ? `<div style="display:flex;flex-direction:column;gap:4px;padding:8px 12px;border-radius:8px;background:${c.canvas};border-left:2px solid ${who === 'model' ? c.measBar : c.border2}">
      <span style="font-size:11.5px;color:${c.ink3}">${evidence[0]}</span>
      <span style="font-family:${MONO};font-size:12px;color:${c.ink2};white-space:pre-wrap">${evidence[1]}</span></div>` : ''}
    ${who === 'model' ? `<div style="display:flex;gap:8px">${secondary(c, 'Keep')}${secondary(c, 'Change…')}</div>` : ''}
  </div>`;
  return page(1440, 1180, `${labsBar('Registry')}${subnav(REG_SUB, 'Work queue')}
  <main style="flex:1;display:flex;flex-direction:column;gap:18px;padding:22px 28px 28px">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div style="display:flex;flex-direction:column;gap:6px">
        ${small('Work queue / nf-core')}
        <div style="display:flex;align-items:center;gap:14px">${mono('samtools/sort', 'font-size:26px;font-weight:500;letter-spacing:-.01em')}${mono('1.21', `color:${c.ink3};font-size:14px`)}${tag('red', 'ready for your review')}${tag('grey', 'revision 2')}</div>
        <span style="font-size:13.5px;color:${c.ink2}">Sorts alignments by position or by name. Read from nf-core/modules at ${mono('9339809')} · container pinned.</span>
      </div>
      <div style="display:flex;gap:8px">${secondary(c, 'Archive')}${secondary(c, 'Ask for changes…')}${primary(c, 'Approve and add')}</div>
    </div>
    <div style="${panel()}padding:14px 22px">
      <svg viewBox="0 0 1340 50" width="100%" style="display:block">
        <line x1="40" y1="30" x2="1300" y2="30" style="stroke:${c.line};stroke-width:6;stroke-linecap:round"></line>
        ${['Drafted', 'Analysed', 'Written', 'Checked', 'Your review'].map((s, i) => { const x = 40 + i * 315; return `${i === 4 ? `<circle cx="${x}" cy="30" r="10" style="fill:${c.selSoft};stroke:${c.sel};stroke-width:3"></circle><circle cx="${x}" cy="30" r="3.5" style="fill:${c.sel}"></circle>` : `<circle cx="${x}" cy="30" r="7" style="fill:${c.settled}"></circle>`}<text x="${x}" y="10" text-anchor="${i === 0 ? 'start' : i === 4 ? 'end' : 'middle'}" style="font-family:${UI};font-size:12px;font-weight:${i === 4 ? 700 : 500};fill:${i === 4 ? c.ink : c.ink2}">${s}</text>`; }).join('')}
      </svg>
    </div>
    <div style="display:flex;gap:2px;border-bottom:1px solid ${c.border}">${[['Answers', '14'], ['Settings', '9'], ['Checks', '8 of 8'], ['Code', ''], ['Since revision 1', '3 changes']].map(([s, k], i) => `<span style="display:flex;gap:7px;align-items:center;padding:9px 14px;font-size:13.5px;${i === 0 ? `color:${c.ink};font-weight:600;box-shadow:inset 0 -2px 0 ${c.ink}` : `color:${c.ink2}`}">${s}${k ? `<span style="font-size:11.5px;color:${c.ink3}">${k}</span>` : ''}</span>`).join('')}</div>
    <div style="flex:1;display:grid;grid-template-columns:minmax(0, 1fr) 380px;gap:18px">
      <section style="display:flex;flex-direction:column;gap:12px;min-width:0">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:13.5px;color:${c.ink2}"><b style="color:${c.ink}">8</b> answers were proved from the tool’s own files. <b style="color:${c.meas}">6</b> were answered by the model, each from the list it was given.</span>
          ${seg(c, ['Model’s first', 'In order'], 0)}
        </div>
        ${q('produces[0].type_id', 'What does the output carry?', 'alignment.bam', 'model', ['Evidence E004 · meta.yml, line 31', 'bam:\n  type: file\n  description: Sorted BAM/CRAM/SAM file'], '22 types')}
        ${q('produces[0].states', 'Is the output sorted, and how?', '[sorted, coordinate_sorted]', 'model', ['Evidence E011 · main.nf, line 24 — changed since revision 1', 'def sort_mode = args.contains("-n") ? "name" : "coordinate"'], '4 states')}
        ${q('consumes[0].type_id', 'What does the input carry?', 'alignment.bam', 'proved', ['From meta.yml · input[0]', 'pattern: "*.{bam,cram,sam}"'])}
        ${small('11 more · 3 answered by the model')}
      </section>
      <aside style="display:flex;flex-direction:column;gap:14px">
        ${card(`<div style="display:flex;justify-content:space-between;align-items:center">${h2('Checks')}${tag('green', '8 of 8 passed')}</div>
          ${['Every question answered from its list', 'The description matches the module', 'Builds in a test pipeline', 'Runs on the stub data', 'Settings reach the tool', 'Container is pinned', 'Licence recorded (MIT)', 'No free text sent anywhere it shouldn’t be'].map(s => `<div style="display:flex;gap:8px;align-items:center;font-size:12.5px;color:${c.ink2}">${ic.check(c.btn)}${s}</div>`).join('')}`)}
        ${card(`${h2('Your decision')}
          <div style="height:70px;border-radius:8px;border:1px solid ${c.border2};padding:8px 10px;font-size:12.5px;color:${c.ink3};box-sizing:border-box">A note for the record (shown if you ask for changes)</div>
          <div style="display:flex;gap:8px">${primary(c, 'Approve and add')}${secondary(c, 'Ask for changes')}</div>
          ${small('Approving writes the files to the lab’s registry with your name on them. Nothing is added without a person.')}`)}
        ${card(`<div style="display:flex;justify-content:space-between;align-items:center">${h2('Ask about this tool')}${tag('amber', 'goes to the model')}</div>
          <div style="display:flex;flex-direction:column;gap:6px;font-size:12.5px;line-height:1.5">
            <div style="align-self:flex-end;max-width:85%;padding:7px 10px;border-radius:10px;background:${c.selSoft}">Why coordinate_sorted and not just sorted?</div>
            <div style="max-width:92%;padding:7px 10px;border-radius:10px;background:${c.bg};color:${c.ink2}">Line 24 picks coordinate order unless ${mono('-n')} is passed, and nothing in the module passes it. E011.</div>
          </div>
          ${composer('Ask a question')}`)}
      </aside>
    </div>
  </main>`);
}

// ── How Labs uses colour ────────────────────────────────────────
function colours() {
  const row = (sw, name, meaning, where) => `<div style="display:grid;grid-template-columns:60px 170px minmax(0, 1fr) minmax(0, 1fr);gap:16px;align-items:center;padding:12px 0;border-top:1px solid ${c.border};font-size:13.5px">${sw}<span style="font-weight:600">${name}</span><span style="color:${c.ink2};line-height:1.5">${meaning}</span><span style="color:${c.ink2};line-height:1.5">${where}</span></div>`;
  const sw = (bg, bd, dash) => `<span style="width:40px;height:24px;border-radius:6px;background:${bg};border:2px ${dash ? 'dashed' : 'solid'} ${bd}"></span>`;
  return page(1100, 780, `<main style="flex:1;display:flex;flex-direction:column;gap:14px;padding:36px 40px">
    <div style="display:flex;justify-content:space-between;align-items:center">${logo(c, 'Comeni Labs')}${small('the same meanings as Comeni Code')}</div>
    ${h1('One meaning per colour', 30)}
    <span style="font-size:15px;color:${c.ink2};max-width:70ch;line-height:1.6">A settled value is the normal case, so it spends no colour at all. Colour is kept for the things a person should look at.</span>
    <div style="display:grid;grid-template-columns:60px 170px minmax(0, 1fr) minmax(0, 1fr);gap:16px;padding-top:10px;font-size:11.5px;color:${c.ink3}"><span></span><span>Name</span><span>Means</span><span>In Labs</span></div>
    ${row(sw(c.exon, c.border2), 'Settled', 'A rule, a convention or the structure decided it. Nothing to check.', 'Most values; finished tasks; steps already added')}
    ${row(sw(c.measSoft, c.measBar), 'Measured', 'Read from your data. Right as long as the measurement is.', 'Read length, pairing, memory actually used, model answers awaiting review')}
    ${row(sw(c.openSoft, c.open), 'Needs you', 'Could not be decided, or went wrong. Nothing moves until someone acts.', 'Open values, failed runs, tools waiting for review')}
    ${row(sw(c.selSoft, c.sel), 'Selected · now', 'What you are looking at, or what is happening right now.', 'Selected step, running tasks, the proposed next step, inputs')}
    ${row(sw(c.lineSoft, c.line), 'Valid · done', 'The path is sound. The line you have travelled.', 'Valid pipeline, completed stages, the step line, the main button')}
    <div style="display:flex;gap:14px;padding-top:12px;flex-wrap:wrap">${tag('grey', 'convention')}${tag('amber', 'measured')}${tag('red', 'needs you')}${tag('blue', 'running')}${tag('green', 'valid')}${tag('dark', 'a person answered')}</div>
  </main>`);
}

// ── write everything ────────────────────────────────────────────
const BOARDS = [
  ['Main', 'Home — the lab’s work', home(), 1440, 1100, 'Reached from: the logo, signing in.\nAnswers “what needs me, what is running, what went wrong” before listing anything. The table’s bar is every value in a pipeline by how it was decided — settled spends no colour.'],
  ['Describe', 'Describe — what do you want to analyse?', describe(), 1440, 1180, 'Reached from: New analysis, the search box, the first visit.\nThe model turns the sentence into a goal; the person sees and corrects what was understood before anything is built. Strandedness is not guessed. Two ways on: step by step, or all at once.'],
  ['Build', 'Build — step by step', build(), 1440, 900, 'The step line on the right is the same metro drawing as a route in Code: settled stops are plain, measured ones amber, the current one blue. The proposed step is drawn dashed on the canvas and is not added until the person says so.'],
  ['Question', 'Build — a value that needs you', question(), 1440, 980, 'An open value is a question with every legal answer listed. The person answers with a reason, which is saved beside the value, or adds a step that measures it instead. Learn it in Code sits under the question it explains.'],
  ['PipelineFile', 'Pipeline file — every value and its reason', pipelineFile(), 1440, 1060, 'The second view of the canvas is the file itself. Settings are grouped by step; each shows how it was decided and why. The file on the right is what you download.'],
  ['RunSheet', 'Run — files, reference, where', runSheet(), 1440, 1040, 'Reached from: Run. Three things to confirm, the measured read length shown per sample, and the three places a pipeline can go — only this machine is launched for you.'],
  ['Runs', 'Runs — every run, filterable', runs(), 1440, 1000, 'Built for hundreds of runs: saved views, filters with counts, a dense table. Reserved vs used memory per run shows where compute is wasted; a run that has not finished shows a hatch, not a zero.'],
  ['Run', 'A run — going', runPage(false), 1440, 1400, 'Four panels, then the timeline (tasks per step, CPUs asked vs used — used is derived, so hatched), then steps and tasks. Progress is counted in steps, because tasks have no known total.'],
  ['RunFailed', 'A run — went wrong (dark)', themed('dark', () => runPage(true)), 1440, 1500, 'Dark mode. The failure panel shows the record and nothing interpreted: exit 137 is SIGKILL, and the attempts show each asked and peak memory. Nextflow’s own report is quoted, not explained.'],
  ['Registry', 'Registry — overview', registry(), 1440, 1040, 'The flow is drawn as a line: found → drafted → with the model → ready for review → in the registry. Only the review stop is red, because only it needs a person.'],
  ['WorkQueue', 'Registry — work queue', workQueue(), 1440, 1000, 'Grouped by state, with saved views, filters, bulk actions and a detail pane — the same triage pattern as Code’s Requests.'],
  ['Adaptation', 'Registry — reviewing a tool', adaptation(), 1440, 1180, 'Model answers first and amber, each with the evidence it came from and how many answers it chose among. Checks and the decision on the right; the chat is marked as going to the model.'],
  ['Colours', 'One meaning per colour', colours(), 1100, 780, null],
];

const artboards = [], annotations = [];
let x = 0, y = 0, rowH = 0;
BOARDS.forEach(([stem, title, html, w, h, note], i) => {
  writeFileSync(`${D}${stem}.dc.html`, html);
  if (i > 0 && i % 3 === 0) { x = 0; y += rowH + 320; rowH = 0; }
  artboards.push({ file: `${stem}.dc.html`, title, x, y, w, h });
  if (note) annotations.push({ id: `note-${stem.toLowerCase()}`, x, y: y - 210, w: 620, text: note });
  x += w + 120; rowH = Math.max(rowH, h);
});
annotations.push({ id: 'note-brief', x: -760, y: -210, w: 620, text: 'Comeni Labs — redesigned in the hybrid identity shared with Comeni Code (Lexend, Geist Mono, one meaning per colour, metro lines).\n\nTop bar: logo (home) · Build · Runs · Registry · search that also takes a description · Learn in Code · help · lab.\n\nThe loop is describe → build → run → watch. Every board is light except the failed run, which shows dark.' });
writeFileSync(`${D}canvas.json`, JSON.stringify({ artboards, annotations, launch: { view: 'canvas' } }, null, 2));
console.log(artboards.map(a => a.file).join(' '));
