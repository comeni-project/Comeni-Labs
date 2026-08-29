#!/usr/bin/env python3
"""Every /runs board, from one shell and one run.

Continuity is structural: the shell, the palette, the motion vocabulary and — crucially — the
RUN ITSELF are declared once here. The timeline, the envelope and every tile are COMPUTED from
that one task list by the same arithmetic the real page would use, so a number cannot disagree
with the bar beside it the way it did across the first builder set.
"""
from pathlib import Path

OUT = Path(__file__).parent

# ── the validated five, plus the ground ───────────────────────────────────────────────
FAIL, ATTN, OK, INK_I, RUN = '#E3674E', '#C1B508', '#10AA91', '#6CB7FF', '#BD6DCD'
BG, INK, MUT, DIM = '#080B0D', '#DFE6E6', '#67757A', '#455257'
LINE, LINE2, PANEL, PANEL2 = '#172025', '#121A1D', '#0C1216', '#0A1014'
SLATE = '#7E959D'
"""Magnitude with no category. **Not the interaction blue** — #6CB7FF means *you can click this*
and a bar wearing it is a promise the page does not keep."""

HEAD = '''
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&family=Chivo:wght@400;500;600;800&family=Chivo+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body { margin:0; background:#080B0D; color:#DFE6E6; font-variant-numeric:tabular-nums; }
    a { color:#6CB7FF; text-decoration:none; } a:hover { color:#fff; }
    .m  { font-family:var(--fm); }
    .lb { font-family:var(--fm); font-size:9.5px; letter-spacing:.15em;
          text-transform:uppercase; color:#67757A; }
    .layer { position:absolute; inset:0; pointer-events:none; }
    .breathe { animation:breathe 46s ease-in-out infinite alternate; }
    @keyframes breathe { to { opacity:1.85; } }
    .slowA { transform-box:view-box; transform-origin:140px 900px; animation:spin 680s linear infinite; }
    .slowB { transform-box:view-box; transform-origin:1300px 70px;  animation:spin 980s linear infinite reverse; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .rule { background-image:
              linear-gradient(rgba(108,183,255,.026) 1px, transparent 1px),
              linear-gradient(90deg, rgba(108,183,255,.026) 1px, transparent 1px);
            background-size:36px 36px;
            mask-image:radial-gradient(105% 62% at 16% 0%, #000 0%, transparent 66%); }
    .scan { background-image:repeating-linear-gradient(180deg, rgba(255,255,255,.010) 0 1px, transparent 1px 3px); }
    .vig  { background:radial-gradient(130% 92% at 50% 3%, transparent 44%, rgba(8,11,13,.9) 100%); }

    /* five movements, one curve. nothing else moves. */
    .settle { animation:settle 200ms cubic-bezier(.32,.72,0,1) backwards; }
    @keyframes settle { from { opacity:0; transform:translateY(4px); } }
    .grow { animation:grow 520ms cubic-bezier(.32,.72,0,1) backwards; transform-origin:left; }
    @keyframes grow { from { transform:scaleX(0); } }
    .flow { background-image:linear-gradient(90deg, transparent 0 7px, rgba(8,11,13,.5) 7px 11px);
            background-size:18px 100%; animation:flow 1.1s linear infinite; }
    @keyframes flow { to { background-position:18px 0; } }
    .cur { animation:blink 1.1s steps(1) infinite; }
    @keyframes blink { 50% { opacity:0; } }
    .lift { transition:background-color 140ms ease, border-color 140ms ease,
                       transform 140ms cubic-bezier(.32,.72,0,1); }
    .lift:hover { background-color:#0E1418; transform:translateY(-1px); }
    @media (prefers-reduced-motion: reduce) {
      .breathe,.slowA,.slowB,.settle,.grow,.flow,.cur { animation:none !important; }
      .lift { transition:none; }
    }
    .seg { border:0; cursor:pointer; font-family:var(--fm); font-size:10px;
           letter-spacing:.08em; text-transform:uppercase; padding:6px 13px;
           transition:background-color 140ms ease, color 140ms ease; }
    .seg:focus-visible { outline:2px solid #6CB7FF; outline-offset:2px; }
    /* a panel is a bounded region of the page, not a floating card: one hairline, no shadow,
       no radius. Grafana's frame, in this palette. */
    .pl { border:1px solid #172025; background:rgba(12,18,22,.62); }
    .pl > .hd { display:flex; align-items:center; justify-content:space-between;
                padding:10px 14px; border-bottom:1px solid #121A1D; }
    /* the board's run table, and the run screen's process table */
    .rr { display:grid; grid-template-columns:150px 96px 1fr 116px 92px 88px;
          gap:16px; align-items:center; padding:11px 6px; border-bottom:1px solid #121A1D; }
    .pr { display:grid; grid-template-columns:186px 74px 1fr 92px 168px 96px 56px;
          gap:14px; align-items:center; padding:10px 6px; border-bottom:1px solid #121A1D; }
    .tk { display:grid; grid-template-columns:56px 176px 92px 1fr 82px 74px 58px;
          gap:14px; align-items:center; padding:9px 6px; border-bottom:1px solid #121A1D; }
    .hatch { background-image:repeating-linear-gradient(45deg,
               rgba(103,117,122,.20) 0 1px, transparent 1px 5px); }

    /* ── responsiveness ──────────────────────────────────────────────────────────────
       Three rules, and they are the whole of it.

       1. EVERY BAND IS auto-fit, NEVER A FIXED COLUMN COUNT. Four tiles become two, then
          one, and nothing is ever dropped to fit — dropping a tile drops a question.
       2. A TABLE SCROLLS INSIDE ITSELF. `.tbl` is the only place horizontal scrolling is
          allowed; the page body must never scroll sideways. The row keeps its `min-width`
          so columns stay aligned with their headings instead of crushing.
       3. THE CHARTS ARE ALREADY FLUID — every SVG is `width:100%` on a viewBox, so the
          timeline and the envelope reflow for free. What is NOT fluid is the lane-label
          gutter, which is a fixed pixel padding and shrinks in one place: `.tlpad`. */
    .band { display:grid; gap:14px; grid-template-columns:repeat(auto-fit, minmax(232px, 1fr)); }
    .pair { display:grid; gap:14px; align-items:start;
            grid-template-columns:repeat(auto-fit, minmax(330px, 1fr)); }
    .tbl  { overflow-x:auto; }
    .tbl > * { min-width:880px; }
    .tlpad { padding-left:132px; }
    .withRail { display:grid; gap:16px; align-items:start; grid-template-columns:1fr 400px; }
    @media (max-width: 1180px) {
      .tlpad { padding-left:96px; }
      .withRail { grid-template-columns:1fr; }
    }
    @media (max-width: 760px) {
      .tlpad { padding-left:0; }   /* lane labels move above their band below this */
    }
  </style>
'''

def field(h, w=1400):
    """The Observatory ground: two slow arc families, a masked graticule, scan, vignette."""
    return f'''
  <svg class="layer" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <g class="breathe" fill="none">
      <g class="slowA" stroke="#6CB7FF" stroke-width="1">
        <circle cx="140" cy="900" r="600"  opacity=".085"/>
        <circle cx="140" cy="900" r="880"  opacity=".055"/>
        <circle cx="140" cy="900" r="1220" opacity=".034"/>
        <path d="M140 900 L1520 200" stroke-width=".75" opacity=".055"/>
      </g>
      <g class="slowB" stroke="#10AA91">
        <circle cx="1300" cy="70" r="470" opacity=".055" stroke-width="1"/>
        <circle cx="1300" cy="70" r="790" opacity=".034" stroke-width="1"/>
      </g>
      <path d="M-60 780 Q 640 1000 1470 630" stroke="#10AA91" stroke-width="1" opacity=".026"/>
    </g>
  </svg>
  <div class="layer rule"></div>
  <div class="layer scan"></div>
  <div class="layer vig"></div>'''


def shell(crumb=None):
    """Nav — Builder, Runs, Registry, and nothing else. Runs is lit."""
    trail = ''
    if crumb:
        trail = (f'<span style="color:#2A3438;">/</span>'
                 f'<span class="m" style="font-size:12px; color:#8D9A9E;">{crumb}</span>')
    return f'''
    <div style="display:flex; align-items:center; justify-content:space-between;
                padding-bottom:20px; border-bottom:1px solid {LINE};">
      <div style="display:flex; align-items:baseline; gap:28px;">
        <span style="font-size:14px; font-weight:700; letter-spacing:-.02em;">Comeni</span>
        <span style="font-size:12.5px; color:{MUT};">Builder</span>
        <span style="font-size:12.5px; color:{INK}; border-bottom:1px solid {INK_I};
                     padding-bottom:3px;">Runs</span>
        <span style="font-size:12.5px; color:{MUT};">Registry</span>
        {trail}
      </div>
      <div style="display:flex; align-items:center; gap:20px;">
        <span class="m" style="font-size:11px; color:{DIM};">
          <span style="color:{INK_I};">&rsaquo;</span> ask for a pipeline, or jump to one
          <span style="color:#2A3438;">&#8984;K</span></span>
        <span class="m" style="font-size:11px; color:{MUT};">Ferreira lab</span>
      </div>
    </div>'''


def page(name, h, body, script_state='', props_extra='', w=1400, vals=''):
    """One artboard. The type tweak is the same three pairs every board carries."""
    doc = f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>{HEAD}</helmet>

<div style="--fs: {{{{ t.sans }}}}; --fm: {{{{ t.mono }}}}; font-family:var(--fs);
            position:relative; min-height:{h}px; overflow:hidden; background:{BG};">
{field(h, w)}
  <div style="position:relative; padding:28px 44px 40px;">
{body}
  </div>
</div>

<script data-dc-script data-props='{{"type":{{"editor":"enum","options":["Geist","Chivo","Plex"],"default":"Geist","section":"Type"}}{props_extra},"$preview":{{"width":{w},"height":{h}}}}}'>
class Component extends DCLogic {{
  constructor(p) {{ super(p); this.state = {{ {script_state} }}; }}
  renderVals() {{
    const PAIRS = {{
      Geist: {{ sans: '"Geist", system-ui, sans-serif',         mono: '"Geist Mono", ui-monospace, monospace' }},
      Chivo: {{ sans: '"Chivo", system-ui, sans-serif',         mono: '"Chivo Mono", ui-monospace, monospace' }},
      Plex:  {{ sans: '"IBM Plex Sans", system-ui, sans-serif', mono: '"IBM Plex Mono", ui-monospace, monospace' }}
    }};
    return {{ t: PAIRS[this.props.type] ?? PAIRS.Geist{vals} }};
  }}
}}
</script>
</body>
</html>
'''
    (OUT / f'{name}.dc.html').write_text(doc)
    return name


# ══ THE RUN ═══════════════════════════════════════════════════════════════════════════
# One task list. Every chart on every board is derived from it, by the arithmetic the real
# page would use — so the timeline, the envelope and the tiles cannot disagree.

NOW = 1300          # 21m 40s in
PROCS = ['FASTQC', 'TRIMGALORE', 'STAR_ALIGN', 'SAMTOOLS_SORT', 'SUBREAD_FEATURECOUNTS']


def _tasks():
    """(process, id, start, end|None, cpus, pct_cpu|None, mem_gb, peak_gb|None, status)

    `end`, `pct_cpu` and `peak_gb` are None while a task is live — which is the whole reason
    the *used* curve trails the *asked* one and must be cut rather than drawn falling.

    Six samples, a local executor, 21 minutes in. `pct_cpu` is a percentage of ONE core, as
    Nextflow reports it: 742 is 7.42 cores of the 8 this task reserved.
    """
    t, tid = [], 1
    for i in range(6):                                       # FASTQC — 6 done
        t.append(('FASTQC', tid, 6, 6 + 88 + (i % 3) * 8, 2, 172 + (i % 3) * 9,
                  6, 1.02 + (i % 3) * .11, 'done'))
        tid += 1
    for i in range(4):                                       # TRIMGALORE — first wave
        t.append(('TRIMGALORE', tid, 115, 115 + 205 + (i % 4) * 11, 4, 304 + (i % 3) * 9,
                  12, 2.71 + (i % 3) * .14, 'done'))
        tid += 1
    for i in range(2):                                       # TRIMGALORE — second wave
        t.append(('TRIMGALORE', tid, 325, 325 + 210 + i * 12, 4, 298 + i * 14,
                  12, 2.80 + i * .09, 'done'))
        tid += 1
    t.append(('STAR_ALIGN', 13, 525, 1145, 8, 742, 36, 33.1, 'done')) # attempt 2 — see RETRY
    t.append(('STAR_ALIGN', 14, 360, 1008, 8, 738, 36, 32.6, 'done'))
    t.append(('STAR_ALIGN', 15, 1010, None, 8, None, 36, None, 'running'))
    t.append(('STAR_ALIGN', 16, 1150, None, 8, None, 36, None, 'running'))
    t.append(('STAR_ALIGN', 17, None, None, 8, None, 36, None, 'queued'))
    t.append(('STAR_ALIGN', 18, None, None, 8, None, 36, None, 'queued'))
    return t


TASKS = _tasks()
RETRY = ('STAR_ALIGN', 13, 360, 520, 137)
"""Attempt 1 of task 13: OOM-killed at 36 GB, retried at 72 GB and succeeded at 1145.

**A retry is history, not a correction** — it draws in the same lane as a separate bar, because
the whole point of `Attempt` being per-attempt is that the try which asked for more memory is
the interesting one."""


def series(tasks, now=NOW):
    """The two curves, from BOUNDARIES rather than bins — A +delta at start, a -delta at end,
    sorted, prefix-summed. Exact at every breakpoint, no bucketing artefacts.

    `asked` is a RESERVATION and therefore exact. `used` is a TOTAL divided over the window:
    area-true, shape-false, and it exists only where a task has completed."""
    def sweep(events):
        events.sort()
        out, acc = [(0, 0.0)], 0.0
        for x, d in events:
            acc += d
            out.append((x, acc))
        return out

    asked, used = [], []
    for _p, _i, s, e, cpus, pct, _m, _pk, _st in tasks:
        if s is None:
            continue
        # **A running task does not release its reservation at `now`.** Closing the
        # interval at the clock made the asked curve fall to zero at the right edge — the
        # exact artefact the used curve is hatched to avoid, arriving on the exact half.
        asked.append((s, float(cpus)))
        if e is not None:
            asked.append((e, -float(cpus)))
        if e is not None and pct is not None:
            asked_share = pct / 100.0
            used += [(s, asked_share), (e, -asked_share)]
    last_done = max((e for *_x, e, _c, _p, _m, _k, _s in
                     [(0, 0, t[2], t[3], t[4], t[5], t[6], t[7], t[8]) for t in tasks]
                     if e is not None), default=0)
    return sweep(asked), sweep(used), last_done


ASKED, USED, LAST_DONE = series(TASKS)


def step_path(pts, x0, y0, w, h, xmax, ymax, close=False, xend=None):
    """A step polyline in SVG user units. Steps, never a smooth line: smoothness is the visual
    grammar of 'I sampled this', and only one of these two curves was sampled."""
    def X(v): return x0 + (v / xmax) * w
    def Y(v): return y0 + h - (v / ymax) * h
    d, py = [], None
    for x, y in pts:
        if py is None:
            d.append(f'M{X(x):.1f} {Y(y):.1f}')
        else:
            d.append(f'H{X(x):.1f} V{Y(y):.1f}')
        py = y
    d.append(f'H{X(xmax if xend is None else xend):.1f}')
    if close:
        d.append(f'V{y0 + h:.1f} H{X(0):.1f} Z')
    return ' '.join(d)


# ══ charts ════════════════════════════════════════════════════════════════════════════
TL_W = 1230          # the shared x-axis every band-2 chart uses
COL = {'FASTQC': OK, 'TRIMGALORE': OK, 'STAR_ALIGN': RUN,
       'SAMTOOLS_SORT': DIM, 'SUBREAD_FEATURECOUNTS': DIM}


def _pack(bars):
    """Greedy sub-row packing inside one process lane. Concurrent tasks stack; a finished row
    is reused. **This is what keeps a lane the process rather than the task** — at 5,000 tasks
    the same arithmetic caps the stack and the remainder becomes a density band."""
    rows: list[int] = []
    out = []
    for s, e, *rest in sorted(bars, key=lambda b: b[0]):
        for r, free in enumerate(rows):
            if free <= s:
                rows[r] = e
                out.append((s, e, r, *rest))
                break
        else:
            rows.append(e)
            out.append((s, e, len(rows) - 1, *rest))
    return out, max(1, len(rows))


def timeline(now=NOW, tasks=None, retry=RETRY, h_row=7, gap=9):
    """The Gantt. One band per DECLARED process, in artifact order, so a process that has not
    been reached still has a lane — the table's length is known before the first event and the
    timeline's is too."""
    tasks = tasks if tasks is not None else TASKS
    def X(v): return (v / now) * TL_W

    bands, y = [], 0
    for proc in PROCS:
        bars = [(t[2], t[3] if t[3] is not None else now, t[8], t[1])
                for t in tasks if t[0] == proc and t[2] is not None]
        if retry and retry[0] == proc:
            bars.append((retry[2], retry[3], 'failed', retry[1]))
        packed, nrows = _pack(bars) if bars else ([], 1)
        bands.append((proc, packed, nrows, y, bool(bars)))
        y += nrows * h_row + (gap + 5 if not bars else gap)
    total = y + 22

    out = [f'<svg viewBox="0 0 {TL_W} {total}" width="100%" height="{total}" '
           f'style="display:block; overflow:visible;">']
    # ── the graticule, at an interval the run's own length picks. A fixed five minutes
    #    gave a 41-second run exactly one rule, labelled 0m. ──
    step = 10 if now <= 120 else 60 if now <= 600 else 300 if now <= 3600 else 900
    for sec in range(0, int(now) + 1, step):
        x = X(sec)
        label = f'{sec}s' if step < 60 else f'{sec // 60}m'
        out.append(f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{y - gap + 2}" '
                   f'stroke="#131C21" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{total - 6}" fill="{DIM}" font-size="9" '
                   f'font-family="var(--fm)" text-anchor="middle">{label}</text>')
    for proc, packed, nrows, by, reached in bands:
        label_y = by + (nrows * h_row) / 2 + 3
        if not reached:
            out.append(f'<line x1="0" y1="{by + 3:.0f}" x2="{TL_W}" y2="{by + 3:.0f}" '
                       f'stroke="#131C21" stroke-width="1" stroke-dasharray="2 6"/>')
        for s, e, r, status, _tid in packed:
            x, w = X(s), max(2.0, X(e) - X(s))
            fill = {'done': OK, 'running': RUN, 'failed': FAIL}[status]
            op = '.30' if status == 'failed' else ('.34' if status == 'running' else '.62')
            out.append(f'<rect x="{x:.1f}" y="{by + r * h_row:.0f}" width="{w:.1f}" '
                       f'height="{h_row - 2}" fill="{fill}" fill-opacity="{op}" '
                       f'stroke="{fill}" stroke-opacity=".75" stroke-width="1"/>')
            if status == 'running':      # the only thing on the board that animates
                out.append(f'<rect x="{x:.1f}" y="{by + r * h_row:.0f}" width="{w:.1f}" '
                           f'height="{h_row - 2}" fill="url(#liveGrad)"/>')
        out.append(f'<text x="-10" y="{label_y:.0f}" fill="{MUT if reached else "#2E393D"}" '
                   f'font-size="9.5" font-family="var(--fm)" text-anchor="end">{proc}</text>')
    out.append(f'<defs><linearGradient id="liveGrad" x1="0" x2="1">'
               f'<stop offset="0" stop-color="{RUN}" stop-opacity="0"/>'
               f'<stop offset="1" stop-color="{RUN}" stop-opacity=".34"/></linearGradient></defs>')
    out.append('</svg>')
    return '\n'.join(out), total


def ticks_of(h, ymax):
    def Y(v): return h - (v / ymax) * h
    return ''.join(
        f'<line x1="0" y1="{Y(v):.1f}" x2="{TL_W}" y2="{Y(v):.1f}" stroke="#131C21"/>'
        f'<text x="-10" y="{Y(v) + 3:.1f}" fill="{DIM}" font-size="9" font-family="var(--fm)" '
        f'text-anchor="end">{v}</text>' for v in (0, 8, 16, 24))


def envelope(now=NOW, h=104, reserved_only=False, asked=None, used=None, last=None):
    """Asked against used, on the timeline's x-axis.

    Two curves and they are not the same KIND of fact — the line is a reservation and therefore
    exact; the area is a per-task total divided over its window, so its integral is right and
    its shape is invented. The legend says which is which, and the region after the last
    completion is hatched rather than drawn falling to zero."""
    ymax = 28
    asked = ASKED if asked is None else asked
    used = USED if used is None else used
    last = LAST_DONE if last is None else last
    a = step_path(asked, 0, 0, TL_W, h, now, ymax)
    if reserved_only:
        # **The panel changes identity rather than showing an empty box.** Until a task
        # completes there is no *used* series at all — but the reservation is exact and live,
        # so the honest panel is one full curve called what it is, not two with one missing.
        return f'''<svg viewBox="0 0 {TL_W} {h}" width="100%" height="{h}"
     style="display:block; overflow:visible;">
  {ticks_of(h, ymax)}
  <path d="{a}" fill="none" stroke="{SLATE}" stroke-width="1.5"/>
  <path d="{a} V{h} H0 Z" fill="{SLATE}" fill-opacity=".07"/>
</svg>'''
    u = step_path([p for p in used if p[0] <= last], 0, 0, TL_W, h, now, ymax,
                  close=True, xend=last)
    xcut = (last / now) * TL_W
    def Y(v): return h - (v / ymax) * h
    ticks = ticks_of(h, ymax)
    return f'''<svg viewBox="0 0 {TL_W} {h}" width="100%" height="{h}"
     style="display:block; overflow:visible;">
  <defs><pattern id="nohatch" width="7" height="7" patternUnits="userSpaceOnUse"
        patternTransform="rotate(45)">
    <line x1="0" y1="0" x2="0" y2="7" stroke="{MUT}" stroke-width="1" stroke-opacity=".26"/>
  </pattern></defs>
  {ticks}
  <path d="{u}" fill="{OK}" fill-opacity=".18"/>
  <path d="{u}" fill="none" stroke="{OK}" stroke-width="1.25" stroke-opacity=".55"/>
  <path d="{a}" fill="none" stroke="{SLATE}" stroke-width="1.5"/>
  <rect x="{xcut:.1f}" y="0" width="{TL_W - xcut:.1f}" height="{h}" fill="url(#nohatch)"/>
  <line x1="{xcut:.1f}" y1="0" x2="{xcut:.1f}" y2="{h}" stroke="{MUT}" stroke-width="1"
        stroke-dasharray="3 3"/>
</svg>'''


def completions(now=NOW, bucket=120, w=118, h=26):
    """Every completion in the run, bucketed — the tile's evidence that it is still moving.
    Not a rate: a rate over ten minutes of ten-minute tasks swings between 0 and 6 and says
    nothing. The last bar's distance from the right edge is the answer."""
    n = int(now / bucket) + 1
    hist = [0] * n
    for t in TASKS:
        if t[3] is not None:
            hist[min(n - 1, int(t[3] / bucket))] += 1
    top = max(1, max(hist))
    bw = w / n
    bars = ''.join(
        f'<rect x="{i * bw:.1f}" y="{h - max(1.5, (c / top) * h):.1f}" width="{bw - 1.6:.1f}" '
        f'height="{max(1.5, (c / top) * h):.1f}" fill="{OK if c else "#1B262B"}" '
        f'fill-opacity="{".62" if c else "1"}"/>' for i, c in enumerate(hist))
    return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="display:block;">{bars}</svg>'


# ══ pieces ════════════════════════════════════════════════════════════════════════════
def tile(label, figure, note, colour=INK, extra='', delay=0):
    return f'''
      <div class="pl settle" style="padding:13px 15px 14px; animation-delay:{delay}ms;">
        <div class="lb">{label}</div>
        <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:10px;
                    margin-top:9px;">
          <span class="m" style="font-size:29px; line-height:1; letter-spacing:-.03em;
                                 color:{colour};">{figure}</span>
          {extra}
        </div>
        <div style="font-size:11px; color:{MUT}; margin-top:8px; line-height:1.45;">{note}</div>
      </div>'''


def panel(label, body, right='', pad='14px 24px 18px'):
    return f'''
      <div class="pl settle">
        <div class="hd"><span class="lb">{label}</span>{right}</div>
        <div style="padding:{pad};">{body}</div>
      </div>'''


def bar(pct, colour, track='#141D21', h=6, w='100%', cls='grow'):
    return (f'<span style="display:block; width:{w}; height:{h}px; background:{track};">'
            f'<span class="{cls}" style="display:block; height:100%; width:{min(100, pct):.0f}%;'
            f' background:{colour};"></span></span>')


def chip(text, colour, solid=False):
    bgc = colour + '1F' if not solid else colour
    return (f'<span class="m" style="font-size:9.5px; letter-spacing:.1em; text-transform:uppercase;'
            f' padding:3px 8px; color:{"#080B0D" if solid else colour};'
            f' background:{bgc}; border:1px solid {colour}{"" if solid else "44"};">{text}</span>')


PROC_ROWS = [
    # name, done, seen, running, queued, failed, slowest, asked_gb, peak_gb, cpus, used_cpu, retries
    ('FASTQC',                6, 6, 0, 0, 0, '1m 44s',  6,  1.24, 2, 1.90, 0),
    ('TRIMGALORE',            6, 6, 0, 0, 0, '3m 58s', 12,  2.89, 4, 3.22, 0),
    ('STAR_ALIGN',            2, 6, 2, 2, 0, '10m 20s',36, 33.10, 8, 7.42, 1),
    ('SAMTOOLS_SORT',         0, 0, 0, 0, 0, None,      8,  None, 4, None,  0),
    ('SUBREAD_FEATURECOUNTS', 0, 0, 0, 0, 0, None,      8,  None, 2, None,  0),
]

PROC_ROWS_FAILED = [
    ('FASTQC',                6, 6, 0, 0, 0, '1m 44s',  6,  1.24, 2, 1.90, 0),
    ('TRIMGALORE',            6, 6, 0, 0, 0, '3m 58s', 12,  2.89, 4, 3.22, 0),
    ('STAR_ALIGN',            1, 6, 0, 4, 1, '10m 48s',72, 71.40, 8, 7.38, 2),
    ('SAMTOOLS_SORT',         0, 0, 0, 0, 0, None,      8,  None, 4, None,  0),
    ('SUBREAD_FEATURECOUNTS', 0, 0, 0, 0, 0, None,      8,  None, 2, None,  0),
]

PROC_ROWS_EARLY = [
    ('FASTQC',                0, 6, 4, 2, 0, None,      6,  None, 2, None,  0),
    ('TRIMGALORE',            0, 0, 0, 0, 0, None,     12,  None, 4, None,  0),
    ('STAR_ALIGN',            0, 0, 0, 0, 0, None,     36,  None, 8, None,  0),
    ('SAMTOOLS_SORT',         0, 0, 0, 0, 0, None,      8,  None, 4, None,  0),
    ('SUBREAD_FEATURECOUNTS', 0, 0, 0, 0, 0, None,      8,  None, 2, None,  0),
]


def process_table(rows=None):
    """**Absent is not zero.** A process that has been reached but has produced no completed
    task has no peak — a peak is only known when a task ends — so the cell says so rather than
    drawing an empty bar that reads as *used nothing*."""
    rows = rows if rows is not None else PROC_ROWS
    head = f'''<div class="pr" style="border-bottom:1px solid {LINE};">
        <span class="lb">process</span><span class="lb">tasks</span><span class="lb">state</span>
        <span class="lb" style="text-align:right;">slowest</span>
        <span class="lb">memory &middot; peak</span>
        <span class="lb">cpu &middot; used</span>
        <span class="lb" style="text-align:right;">retries</span></div>'''
    out = []
    for i, (name, done, seen, running, queued, failed, slow, ask, peak,
            cpus, used, retries) in enumerate(rows):
        if seen == 0:
            out.append(f'''<div class="pr lift" style="animation-delay:{i*30}ms;">
              <span class="m" style="font-size:11.5px; color:#3B474B;">{name}</span>
              <span class="m" style="font-size:11px; color:#2E393D;">&mdash;</span>
              <span style="font-size:11px; color:#2E393D;">not started</span>
              <span class="m" style="font-size:11px; color:#2E393D; text-align:right;">&mdash;</span>
              <span class="m" style="font-size:11px; color:#2E393D;">asks {ask} GB</span>
              <span class="m" style="font-size:11px; color:#2E393D;">asks {cpus}</span>
              <span class="m" style="font-size:11px; color:#2E393D; text-align:right;">&mdash;</span>
            </div>''')
            continue
        segs = ('<span style="display:flex; height:7px; gap:2px;">'
                + (f'<span class="grow" style="flex:{done}; background:{OK};"></span>' if done else '')
                + (f'<span class="grow" style="flex:{failed}; background:{FAIL};"></span>' if failed else '')
                + (f'<span class="grow flow" style="flex:{running}; background:{RUN};"></span>' if running else '')
                + (f'<span style="flex:{queued}; background:#1B262B;"></span>' if queued else '')
                + '</span>')
        if peak is None:
            mem = (f'<span class="m" style="font-size:10.5px; color:#3B474B;">'
                   f'asks {ask} GB &middot; no peak until a task ends</span>')
        else:
            over = ask / peak
            hot = peak > ask * .95
            colour = FAIL if hot else (ATTN if over > 2 else OK)
            mem = (f'<span style="display:flex; align-items:center; gap:8px;">'
                   f'<span style="position:relative; flex:1; height:7px; background:#141D21;">'
                   f'<span class="grow" style="position:absolute; inset:0 auto 0 0;'
                   f' width:{min(100, 100/over):.0f}%; background:{colour}; opacity:.8;"></span>'
                   f'</span><span class="m" style="font-size:10.5px; color:{colour if colour!=OK else MUT};'
                   f' white-space:nowrap;">{peak:.1f}/{ask}</span></span>')
        cpu = (f'<span class="m" style="font-size:11px; color:#3B474B;">asks {cpus}</span>'
               if used is None else
               f'<span class="m" style="font-size:11px; color:{MUT};">{used:.1f} of {cpus}</span>')
        out.append(f'''<div class="pr lift settle" style="animation-delay:{i*30}ms;">
          <span class="m" style="font-size:11.5px; color:{INK};">{name}</span>
          <span class="m" style="font-size:11px; color:{MUT};">{done} of {seen}</span>
          {segs}
          <span class="m" style="font-size:11px; color:{MUT}; text-align:right;">{slow or "&mdash;"}</span>
          {mem}
          {cpu}
          <span class="m" style="font-size:11px; text-align:right;
                color:{ATTN if retries else "#2E393D"};">{retries or "&mdash;"}</span>
        </div>''')
    return f'<div class="tbl"><div>{head}{"".join(out)}</div></div>'


def run_graph(rows=None):
    rows = rows if rows is not None else PROC_ROWS
    """3C's layout, coloured by the fold — the same object the table is, drawn as the shape the
    pipeline has. Node fill is the proportion of its tasks done; nothing here is a second
    implementation of anything, the positions come from `dag-core`."""
    NW, NH, GAP, Y = 196, 74, 62, 26
    out = [f'<svg viewBox="0 0 {5*NW + 4*GAP} {NH + 60}" width="100%" '
           f'height="{NH + 60}" style="display:block; overflow:visible;">']
    for i, (name, done, seen, running, _queued, *_rest) in enumerate(rows):
        x = i * (NW + GAP)
        reached = seen > 0
        stroke = COL[name] if reached else '#243036'
        frac = (done / seen) if seen else 0
        out.append(f'<rect x="{x}" y="{Y}" width="{NW}" height="{NH}" fill="#0C1216" '
                   f'stroke="{stroke}" stroke-opacity="{".8" if reached else "1"}"/>')
        out.append(f'<rect x="{x}" y="{Y}" width="3" height="{NH}" fill="{stroke}"/>')
        if frac:
            out.append(f'<rect x="{x+3}" y="{Y+NH-4}" width="{(NW-3)*frac:.0f}" height="4" '
                       f'fill="{OK}" fill-opacity=".7"/>')
        out.append(f'<text x="{x+14}" y="{Y+26}" fill="{INK if reached else "#3B474B"}" '
                   f'font-size="11.5" font-family="var(--fm)">{name}</text>')
        sub = (f'{done} of {seen} tasks' if reached else 'not started')
        out.append(f'<text x="{x+14}" y="{Y+46}" fill="{MUT if reached else "#2E393D"}" '
                   f'font-size="10" font-family="var(--fm)">{sub}</text>')
        if running:
            out.append(f'<text x="{x+NW-14}" y="{Y+46}" fill="{RUN}" font-size="10" '
                       f'font-family="var(--fm)" text-anchor="end">{running} running</text>')
        if i < 4:
            x2 = x + NW
            out.append(f'<path d="M{x2} {Y+NH/2} H{x2+GAP}" stroke="{"#2A3B42" if reached else "#1B252A"}" '
                       f'stroke-width="1" fill="none"/>')
            out.append(f'<circle cx="{x2+GAP/2}" cy="{Y+NH/2}" r="2" fill="#2A3B42"/>')
    out.append('</svg>')
    return '\n'.join(out)


# ══ /runs/{id} ════════════════════════════════════════════════════════════════════════
def run_header(phase='running', elapsed='21m 40s', sentence=None, colour=RUN, action='Cancel'):
    sentence = sentence or (
        f'<span style="color:{INK};">STAR_ALIGN</span> &middot; 2 of 6 tasks done, '
        f'2 running, 2 waiting for a slot')
    return f'''
    <div class="settle" style="padding:26px 0 22px; display:flex; align-items:flex-start;
                justify-content:space-between; gap:40px; border-bottom:1px solid {LINE};">
      <div>
        <div style="display:flex; align-items:baseline; gap:16px;">
          <span style="font-size:31px; font-weight:600; letter-spacing:-.035em;
                       line-height:1;">rnaseq-counts</span>
          {chip(phase, colour)}
          <span class="m" style="font-size:11.5px; color:{DIM};">a3f9c2e1</span>
        </div>
        <div style="font-size:12.5px; color:{MUT}; margin-top:11px;">{sentence}</div>
      </div>
      <div style="display:flex; align-items:center; gap:22px;">
        <div style="text-align:right;">
          <div class="m" style="font-size:23px; color:{colour}; letter-spacing:-.02em;">
            {elapsed}{'<span class="cur">&#9646;</span>' if phase == 'running' else ''}</div>
          <div class="m" style="font-size:10.5px; color:{DIM}; margin-top:4px;">
            local &middot; started 21:04</div>
        </div>
        <span class="m lift" style="font-size:10.5px; letter-spacing:.08em;
              text-transform:uppercase; padding:8px 15px; color:{MUT};
              border:1px solid {LINE}; cursor:pointer;">{action}</span>
      </div>
    </div>'''


def band1(tiles):
    return f'<div class="band" style="padding:20px 0 0;">{tiles}</div>'


STEP_STRIP = (
    '<span style="display:flex; gap:3px; width:120px; height:9px;">'
    + f'<span class="grow" style="flex:1; background:{OK};"></span>' * 2
    + f'<span class="grow flow" style="flex:1; background:{RUN};"></span>'
    + '<span style="flex:1; background:#1B262B;"></span>' * 2 + '</span>')


def tiles_live():
    return (
        tile('progress', '2 <span style="font-size:16px; color:' + MUT + ';">of 5</span>',
             'Steps, not tasks &mdash; the artifact declares five. '
             '<span style="color:' + DIM + ';">Nextflow discovers tasks as channels emit, '
             'so a task percentage has no denominator.</span>',
             extra=STEP_STRIP, delay=0)
        + tile('failures', '0', '1 task retried &mdash; STAR_ALIGN task 13, '
               'OOM-killed at 36 GB, succeeded at 72.', colour=INK,
               extra=chip('1 retry', ATTN), delay=30)
        + tile('moving', '2m 35s',
               'Since the last completion. Two STAR tasks are 4 and 2 minutes in.',
               extra=completions(), delay=60)
        + tile('resource fit', '4.3&times;',
               'TRIMGALORE asks 12 GB and peaked at 2.9. '
               '<span style="color:' + DIM + ';">Worst over-ask of three processes that '
               'reported.</span>', colour=ATTN, delay=90))


LEGEND = f'''<span style="display:flex; align-items:center; gap:18px;">
  <span class="m" style="font-size:9.5px; color:{MUT}; display:flex; align-items:center; gap:6px;">
    <i style="width:14px; height:2px; background:{SLATE}; display:block;"></i>
    asked &mdash; a reservation, exact</span>
  <span class="m" style="font-size:9.5px; color:{MUT}; display:flex; align-items:center; gap:6px;">
    <i style="width:14px; height:8px; background:{OK}; opacity:.35; display:block;"></i>
    used &mdash; a total spread over each task, derived</span>
  <span class="m hatch" style="font-size:9.5px; color:{MUT}; padding:2px 7px;">
    no completion yet</span></span>'''


def band2():
    tl, _h = timeline()
    return panel('timeline', f'''
      <div class="tlpad">{tl}</div>
      <div style="display:flex; align-items:baseline; justify-content:space-between;
                  flex-wrap:wrap; gap:10px; padding:16px 0 8px;
                  border-top:1px solid {LINE2}; margin-top:6px;">
        <span class="lb">cpu &mdash; asked against used</span>{LEGEND}</div>
      <div class="tlpad">{envelope()}</div>''',
      right=f'<span class="m" style="font-size:10.5px; color:{DIM};">'
            f'18 tasks &middot; 12 done &middot; 2 running &middot; 2 waiting</span>')


def toggle(active='table'):
    on, off = f'background:#122029; color:{INK_I};', f'background:transparent; color:{MUT};'
    return (f'<span style="display:flex; border:1px solid {LINE};">'
            f'<button class="seg" style="{on if active=="table" else off}">table</button>'
            f'<button class="seg" style="{on if active=="graph" else off}">graph</button></span>')


TASK_ROWS = [
    (13, 'STAR_ALIGN', 'done',     'SRR6357070', '10m 20s', '33.1 GB', '0',  2),
    (14, 'STAR_ALIGN', 'done',     'SRR6357071', '10m 48s', '32.6 GB', '0',  1),
    (15, 'STAR_ALIGN', 'running',  'SRR6357072', '4m 50s',  '&mdash;', '&mdash;', 1),
    (16, 'STAR_ALIGN', 'running',  'SRR6357073', '2m 30s',  '&mdash;', '&mdash;', 1),
    (17, 'STAR_ALIGN', 'queued',   'SRR6357074', '&mdash;', '&mdash;', '&mdash;', 1),
]


def tasks_table():
    head = f'''<div class="tk" style="border-bottom:1px solid {LINE};">
      <span class="lb">task</span><span class="lb">process</span><span class="lb">state</span>
      <span class="lb">tag</span><span class="lb" style="text-align:right;">realtime</span>
      <span class="lb" style="text-align:right;">peak rss</span>
      <span class="lb" style="text-align:right;">exit</span></div>'''
    rows = ''
    for i, (tid, proc, st, tag, rt, rss, ex, att) in enumerate(TASK_ROWS):
        c = {'done': OK, 'running': RUN, 'queued': MUT}[st]
        rows += f'''<div class="tk lift settle" style="animation-delay:{i*30}ms;">
          <span class="m" style="font-size:11px; color:{MUT};">{tid}</span>
          <span class="m" style="font-size:11px; color:{INK};">{proc}</span>
          <span class="m" style="font-size:10.5px; color:{c};">{st}{
            f' &times;{att}' if att > 1 else ''}</span>
          <span class="m" style="font-size:11px; color:{MUT};">{tag}</span>
          <span class="m" style="font-size:11px; color:{MUT}; text-align:right;">{rt}</span>
          <span class="m" style="font-size:11px; color:{MUT}; text-align:right;">{rss}</span>
          <span class="m" style="font-size:11px; color:{MUT}; text-align:right;">{ex}</span>
        </div>'''
    return f'<div class="tbl"><div>{head}{rows}</div></div>'


def tabs(active='tasks'):
    def t(name, n=None):
        on = name == active
        return (f'<span class="m lift" style="font-size:11px; padding:7px 14px; cursor:pointer;'
                f' color:{INK if on else MUT}; background:{"#122029" if on else "transparent"};'
                f' border:1px solid {INK_I+"55" if on else "transparent"};">{name}'
                + (f' <span style="color:{DIM};">{n}</span>' if n else '') + '</span>')
    return (f'<span style="display:flex; gap:4px;">{t("tasks", "18")}{t("console")}</span>')


# ══ /runs — the board ═════════════════════════════════════════════════════════════════
DAYS = [(3,0),(5,1),(2,0),(0,0),(6,0),(4,2),(7,0),(3,0),(5,1),(8,0),(2,0),(6,1),(4,0),(6,0)]
PIPES = [('rnaseq-counts', 38, 24), ('wgs-variants', 134, 9),
         ('atac-peaks', 51, 18), ('qc-only', 6, 10)]
RUNS = [
    ('a3f9c2e1', 'rnaseq-counts', 'running',   12, 18, '21m 40s', 'local', RUN),
    ('7d1e4b90', 'atac-peaks',    'running',    4, 22, '6m 12s',  'local', RUN),
    ('c02ab7f3', 'rnaseq-counts', 'succeeded', 18, 18, '39m 04s', 'local', OK),
    ('19fe6c44', 'wgs-variants',  'failed',    61, 140,'1h 04m',  'local', FAIL),
    ('be7710da', 'qc-only',       'succeeded',  6,  6, '5m 47s',  'local', OK),
    ('4a0c93e5', 'rnaseq-counts', 'succeeded', 18, 18, '36m 51s', 'local', OK),
]


def runs_per_day():
    top = max(s + f for s, f in DAYS)
    cols = ''
    for i, (s, f) in enumerate(DAYS):
        total = s + f
        H = 74
        cols += ('<div style="flex:1; display:flex; flex-direction:column; '
                 'justify-content:flex-end; align-items:center; gap:2px; min-width:0;">'
                 '<span style="display:flex; flex-direction:column; justify-content:flex-end; '
                 'gap:2px; width:100%; max-width:22px;">')
        if total == 0:
            cols += '<i style="display:block; height:2px; background:#1B262B;"></i>'
        else:
            if f:
                cols += (f'<i class="grow" style="display:block; height:{f/top*H:.0f}px; '
                         f'background:{FAIL}; opacity:.85;"></i>'
                         f'<i style="display:block; height:2px; background:{BG};"></i>')
            cols += (f'<i class="grow" style="display:block; height:{s/top*H:.0f}px; '
                     f'background:{OK}; opacity:.8;"></i>')
        cols += ('</span>' + f'<span class="m" style="font-size:9px; color:{DIM}; '
                 f'text-align:center; height:12px;">'
                 f'{"14 Aug" if i==3 else ("21 Aug" if i==10 else "")}</span></div>')
    legend = (f'<span style="display:flex; gap:14px;">'
              f'<span class="m" style="font-size:9.5px; color:{MUT}; display:flex; gap:6px; '
              f'align-items:center;"><i style="width:8px;height:8px;background:{OK};'
              f'display:block;"></i>succeeded</span>'
              f'<span class="m" style="font-size:9.5px; color:{MUT}; display:flex; gap:6px; '
              f'align-items:center;"><i style="width:8px;height:8px;background:{FAIL};'
              f'display:block;"></i>failed</span></span>')
    return panel('runs per day',
                 f'<div style="position:relative;">'
                 f'<span class="m" style="position:absolute; left:0; top:-2px; font-size:9px; '
                 f'color:{DIM};">{top}</span>'
                 f'<span style="position:absolute; left:0; right:0; top:4px; height:1px; '
                 f'background:#141D21;"></span>'
                 f'<div style="display:flex; align-items:flex-end; gap:4px; height:100px; '
                 f'padding-left:16px;">{cols}</div></div>',
                 right=legend)


def duration_by_pipeline():
    top = max(m for _n, m, _c in PIPES)
    rows = ''
    for i, (name, mins, _count) in enumerate(PIPES):
        label = f'{mins//60}h {mins%60:02d}m' if mins >= 60 else f'{mins}m'
        rows += f'''<div class="settle" style="display:grid; grid-template-columns:112px 1fr 72px;
                    gap:12px; align-items:center; padding:7px 0; animation-delay:{i*30}ms;">
          <span class="m" style="font-size:11px; color:{INK};">{name}</span>
          <span style="display:block; height:9px; background:#141D21;">
            <span class="grow" style="display:block; height:100%; width:{mins/top*100:.0f}%;
                  background:{SLATE}; opacity:.5;"></span></span>
          <span class="m" style="font-size:11px; color:{MUT}; text-align:right;">{label}</span>
        </div>'''
    return panel('median duration, by pipeline', rows,
                 right=f'<span class="m" style="font-size:10px; color:{DIM};">'
                       f'over 61 runs &middot; 14 days</span>')
NOW_FAILED = 1331


def failed_tasks():
    """The same run, taken to its actual end. The three attempts are three bars in the
    STAR_ALIGN lane, because an attempt is history and a retry that asked for more memory is
    the interesting one."""
    t = [x for x in TASKS if x[0] in ('FASTQC', 'TRIMGALORE')]
    t.append(('STAR_ALIGN', 14, 360, 1008, 8, 738, 36, 32.6, 'done'))
    t.append(('STAR_ALIGN', 13, 360, 602, 8, None, 36, 35.9, 'failed'))
    t.append(('STAR_ALIGN', 13, 607, 918, 8, None, 48, 47.6, 'failed'))
    t.append(('STAR_ALIGN', 13, 923, 1331, 8, None, 72, 71.4, 'failed'))
    return t
FAILED_STRIP = (
    '<span style="display:flex; gap:3px; width:120px; height:9px;">'
    + f'<span class="grow" style="flex:1; background:{OK};"></span>' * 2
    + f'<span class="grow" style="flex:1; background:{FAIL};"></span>'
    + '<span style="flex:1; background:#1B262B;"></span>' * 2 + '</span>')


EARLY_STRIP = (
    '<span style="display:flex; gap:3px; width:120px; height:9px;">'
    + f'<span class="grow flow" style="flex:1; background:{RUN};"></span>'
    + '<span style="flex:1; background:#1B262B;"></span>' * 4 + '</span>')
# ══ the run screen, with a REAL toggle — one board, not two ═══════════════════════════
def build_run_view():
    """`table` and `graph` were two artboards of one screen, which is two chances to drift.
    The toggle is state, so the board carries both and nothing can disagree."""
    band3 = f'''
      <div class="pl settle">
        <div class="hd"><span class="lb">processes</span>
          <span style="display:flex; border:1px solid {LINE};">
            <button class="seg" onClick="{{{{ asTable }}}}"
                    style="background:{{{{ v.tBg }}}}; color:{{{{ v.tFg }}}};">table</button>
            <button class="seg" onClick="{{{{ asGraph }}}}"
                    style="background:{{{{ v.gBg }}}}; color:{{{{ v.gFg }}}};">graph</button>
          </span></div>
        <sc-if value="{{{{ v.isTable }}}}" hint-placeholder-val="{{{{ true }}}}">
          <div style="padding:4px 24px 10px;">{process_table()}</div>
        </sc-if>
        <sc-if value="{{{{ v.isGraph }}}}" hint-placeholder-val="{{{{ false }}}}">
          <div style="padding:18px 24px 22px;">{run_graph()}</div>
        </sc-if>
      </div>'''
    body = (shell('rnaseq-counts') + run_header() + band1(tiles_live()) + f'''
    <div style="padding-top:14px;">{band2()}</div>
    <div style="padding-top:14px;">{band3}</div>
    <div style="padding-top:14px;">
      {panel('tasks', tasks_table()
             + f'<div class="m" style="font-size:11px; color:{DIM}; padding:12px 6px 0;">'
               f'13 more &mdash; filtered to STAR_ALIGN by clicking its lane above.</div>',
             right=tabs(), pad='4px 24px 14px')}
    </div>''')
    return page('RunView', 1330, body, script_state="view: 'table'", vals='''
      , isTable: this.state.view === 'table', isGraph: this.state.view === 'graph',
      asTable: () => this.setState({ view: 'table' }),
      asGraph: () => this.setState({ view: 'graph' }),
      v: {
        isTable: this.state.view === 'table', isGraph: this.state.view === 'graph',
        tBg: this.state.view === 'table' ? '#122029' : 'transparent',
        tFg: this.state.view === 'table' ? '#6CB7FF' : '#67757A',
        gBg: this.state.view === 'graph' ? '#122029' : 'transparent',
        gFg: this.state.view === 'graph' ? '#6CB7FF' : '#67757A'
      }''')


# ══ the failure, as the record actually holds it ══════════════════════════════════════
REPORT = """Error executing process &gt; 'NFCORE_RNASEQ:RNASEQ:ALIGN_STAR:STAR_ALIGN (SRR6357072)'

Caused by:
  Process `STAR_ALIGN (SRR6357072)` terminated with an error exit status (137)

Command exit status:
  137

Command error:
  .command.sh: line 9:    47 Killed  STAR --genomeDir star --readFilesIn ...

Work dir:
  /data/runs/a3f9c2e1/work/6b/1f0c9d4a2e"""


def failure_card():
    """**Shows the failure. Does not explain it.**

    Every field here is one the record holds and `Failure.tsx` already renders: the worst failed
    task from `/tasks?status=FAILED&sort=-peak_rss_bytes&limit=1`, `memory_asked_bytes` from the
    overview row, and `manifest.report` — Nextflow's own `errorReport`, which is RUN-level and
    arrives once, not once per attempt.

    What is deliberately absent: any sentence naming a cause. `137` is glossed as SIGKILL
    because 128+9 is POSIX arithmetic; *the OOM killer did it* is an inference, and §18.1 says
    nothing explains a failure until W3. The per-attempt escalation table is absent for a
    different reason — the numbers exist in `run_task.attempts` and are not projected."""
    return f'''
      <div class="pl settle" style="border-color:{FAIL}55; background:rgba(227,103,78,.045);">
        <div class="hd" style="border-bottom-color:{FAIL}33;">
          <span style="display:flex; align-items:baseline; gap:12px;">
            <span class="m" style="font-size:13.5px; color:{FAIL};">STAR_ALIGN</span>
            <span class="m" style="font-size:12px; color:{MUT};">(SRR6357072)</span>
            <span class="m" style="font-size:12px; color:{INK};">exited 137</span>
            {chip('sigkill', FAIL)}
            <span class="m" style="font-size:12px; color:{MUT};">on attempt 3</span>
          </span>
          <span class="lb">from the record &middot; nothing interpreted</span>
        </div>
        <div style="padding:16px 24px 20px;">
          <div style="display:flex; align-items:center; gap:14px;">
            <span style="display:block; width:210px; height:8px; background:#141D21;">
              <span class="grow" style="display:block; height:100%; width:99%;
                    background:{FAIL}; opacity:.85;"></span></span>
            <span class="m" style="font-size:12px; color:{INK};">
              peaked at 71.4 GB of 72 GB asked</span>
            <span class="m" style="font-size:10.5px; color:{DIM};">
              &mdash; shown only because both halves are known</span>
          </div>
          <pre class="m" style="margin:16px 0 0; padding:14px 16px; font-size:11px;
               line-height:1.75; color:#A9B7BB; background:{PANEL2}; border:1px solid {LINE};
               max-height:186px; overflow:auto; white-space:pre-wrap;">{REPORT}</pre>
          <div style="display:flex; align-items:center; justify-content:space-between;
                      margin-top:12px;">
            <span class="lb">nextflow&rsquo;s own errorReport &middot; shown, not explained</span>
            <span class="m lift" style="font-size:11px; padding:8px 15px; cursor:pointer;
                  color:{MUT}; border:1px solid {LINE};">open the console at this task</span>
          </div>
        </div>
      </div>'''


def build_run_failed():
    tl, _h = timeline(now=NOW_FAILED, tasks=failed_tasks(), retry=None)
    tiles = (tile('progress', '2 <span style="font-size:16px; color:' + MUT + ';">of 5</span>',
                  'STAR_ALIGN never finished, so nothing downstream of it ran.',
                  extra=FAILED_STRIP)
             + tile('failures', '1', 'One task, three attempts, the last exited 137.',
                    colour=FAIL, extra=chip('terminate', FAIL), delay=30)
             + tile('moving', 'stopped', 'Nextflow terminated the run 22m in, after the '
                    'third attempt.', colour=MUT, delay=60)
             + tile('resource fit', '99%', 'Peak RSS against what the failing attempt asked.',
                    colour=FAIL, delay=90))
    body = (shell('rnaseq-counts')
            + run_header(phase='failed', elapsed='22m 11s', colour=FAIL, action='Relaunch',
                         sentence=f'<span style="color:{INK};">STAR_ALIGN</span> &middot; '
                                  f'1 of 6 tasks done &middot; terminated after task 13 '
                                  f'failed three times, four tasks never started')
            + band1(tiles)
            + f'<div style="padding-top:14px;">{failure_card()}</div>' + f'''
    <div style="padding-top:14px;">
      {panel('timeline', f'<div class="tlpad">{tl}</div>',
             right=f'<span class="m" style="font-size:10.5px; color:{DIM};">'
                   f'the red bars are the three attempts, in the STAR_ALIGN lane</span>')}
    </div>
    <div style="padding-top:14px;">
      {panel('processes', process_table(PROC_ROWS_FAILED), right=toggle(), pad='4px 24px 10px')}
    </div>''')
    return page('RunFailed', 1330, body)


def build_run_early():
    """41 seconds in — the state that breaks every dashboard.

    **The envelope does not wait for a completion to show something.** Until a task ends there
    is no *used* series at all, so the panel is not a two-curve chart with one curve missing:
    it is `cpu reserved`, one exact curve, live and complete. It gains its second curve and its
    second name when the first task finishes. A hatched empty box was the first answer and it
    was the wrong one — an absent series is a reason to draw a different panel, not an empty
    one."""
    early = [(p, i, s, None, c, None, m, None, 'running')
             for p, i, s, _e, c, _pc, m, _pk, _st in TASKS if p == 'FASTQC'][:4]
    tl, _h = timeline(now=41, tasks=early, retry=None)
    a_early, u_early, _ld = series(early, now=41)
    tiles = (tile('progress', '0 <span style="font-size:16px; color:' + MUT + ';">of 5</span>',
                  'FASTQC is the first step and no task of it has finished.',
                  extra=EARLY_STRIP, colour=MUT)
             + tile('failures', '0', 'Nothing has failed.', colour=MUT, delay=30)
             + tile('moving', '&mdash;', 'No task has completed yet, so there is nothing to '
                    'measure against.', colour=MUT, delay=60)
             + tile('resource fit', 'no basis', 'A peak is only known once a task ends. '
                    '<span style="color:' + DIM + ';">Four are 40 seconds in.</span>',
                    colour=MUT, delay=90))
    band = panel('timeline',
        f'<div class="tlpad">{tl}</div>'
        f'<div style="display:flex; align-items:baseline; justify-content:space-between;'
        f' padding:16px 0 8px; border-top:1px solid {LINE2}; margin-top:6px;">'
        f'<span class="lb">cpu reserved</span>'
        f'<span class="m" style="font-size:9.5px; color:{MUT}; display:flex; align-items:center;'
        f' gap:6px;"><i style="width:14px; height:2px; background:{SLATE}; display:block;"></i>'
        f'a reservation, exact &mdash; the used curve joins it at the first completion</span>'
        f'</div>'
        f'<div class="tlpad">'
        f'{envelope(now=41, reserved_only=True, asked=a_early, used=u_early, last=0)}</div>',
        right=f'<span class="m" style="font-size:10.5px; color:{DIM};">'
              f'6 tasks &middot; 0 done &middot; 4 running &middot; 2 waiting</span>')
    body = (shell('rnaseq-counts')
            + run_header(elapsed='41s',
                         sentence=f'<span style="color:{INK};">FASTQC</span> &middot; '
                                  f'4 tasks running, 2 waiting &middot; nothing has finished')
            + band1(tiles) + f'''
    <div style="padding-top:14px;">{band}</div>
    <div style="padding-top:14px;">
      {panel('processes', process_table(PROC_ROWS_EARLY), right=toggle(), pad='4px 24px 10px')}
    </div>''')
    return page('RunEarly', 1000, body)


# ══ the console ═══════════════════════════════════════════════════════════════════════
def console_lines():
    """One line per TASK event, in order — the run's own lifecycle is what the header says and
    repeating it here is three lines among four hundred (§4.3 finding 1).

    The tag is what distinguishes a task from its siblings and **only** that: Nextflow's `name`
    is `PROCESS (tag)`, so printing the process beside it once read
    `STAR_ALIGN (STAR_ALIGN (SRR6357072))` on every line."""
    GLYPH = {'COMPLETED': '&check;', 'RUNNING': '&#9679;', 'SUBMITTED': '&middot;',
             'FAILED': '&times;', 'CACHED': '&check;'}
    C = {'COMPLETED': OK, 'RUNNING': RUN, 'SUBMITTED': MUT, 'FAILED': FAIL, 'CACHED': DIM}
    ev = []
    base = 21 * 3600 + 4 * 60
    # A task emits SUBMITTED when the executor takes it and COMPLETED/FAILED when it ends, so
    # a real console has roughly two lines per task and they are interleaved across processes.
    src = [('FASTQC', 1, 6, 100, 'COMPLETED', 'SRR6357070'),
           ('FASTQC', 2, 6, 94, 'COMPLETED', 'SRR6357071'),
           ('FASTQC', 3, 6, 108, 'COMPLETED', 'SRR6357072'),
           ('FASTQC', 4, 6, 96, 'COMPLETED', 'SRR6357073'),
           ('FASTQC', 5, 6, 102, 'COMPLETED', 'SRR6357074'),
           ('FASTQC', 6, 6, 110, 'COMPLETED', 'SRR6357075'),
           ('TRIMGALORE', 7, 115, 320, 'COMPLETED', 'SRR6357070'),
           ('TRIMGALORE', 8, 115, 331, 'COMPLETED', 'SRR6357071'),
           ('TRIMGALORE', 9, 115, 342, 'COMPLETED', 'SRR6357072'),
           ('TRIMGALORE', 10, 115, 353, 'COMPLETED', 'SRR6357073'),
           ('TRIMGALORE', 11, 325, 535, 'COMPLETED', 'SRR6357074'),
           ('TRIMGALORE', 12, 325, 547, 'COMPLETED', 'SRR6357075'),
           ('STAR_ALIGN', 13, 360, 520, 'FAILED', 'SRR6357072'),
           ('STAR_ALIGN', 14, 360, 1008, 'COMPLETED', 'SRR6357071'),
           ('STAR_ALIGN', 13, 525, 1145, 'COMPLETED', 'SRR6357072'),
           ('STAR_ALIGN', 15, 1010, None, 'RUNNING', 'SRR6357073'),
           ('STAR_ALIGN', 16, 1150, None, 'RUNNING', 'SRR6357074')]
    for proc, tid, st, en, status, tag in src:
        ev.append((base + st, 'SUBMITTED', proc, tag, tid))
        ev.append((base + (en if en is not None else st + 1),
                   status if en is not None else 'RUNNING', proc, tag, tid))
    ev.sort()
    rows = ''
    for at, status, proc, tag, _tid in ev:
        hh, mm, ss = at // 3600, (at // 60) % 60, at % 60
        hot = status == 'FAILED'
        rows += (f'<div class="lift" style="display:grid; '
                 f'grid-template-columns:14px 74px 96px 186px 1fr; gap:12px; height:22px;'
                 f' align-items:center; padding:0 8px;'
                 f'{" background:rgba(227,103,78,.07);" if hot else ""}">'
                 f'<span class="m" style="font-size:11px; color:{C[status]};">{GLYPH[status]}</span>'
                 f'<span class="m" style="font-size:11px; color:{DIM};">{hh:02d}:{mm:02d}:{ss:02d}</span>'
                 f'<span class="m" style="font-size:11px; color:{C[status]};">{status.lower()}</span>'
                 f'<span class="m" style="font-size:11px; color:{INK};">{proc}</span>'
                 f'<span class="m" style="font-size:11px; color:{MUT};">({tag})'
                 + (f' <span style="color:{FAIL};">exit 137</span>' if hot else '')
                 + '</span></div>')
    return rows


def build_console():
    ctl = ('<span style="display:flex; gap:6px; align-items:center;">'
           + ''.join(f'<span class="m lift" style="font-size:10.5px; padding:5px 11px;'
                     f' border:1px solid {LINE}; color:{MUT}; cursor:pointer;">{t}</span>'
                     for t in ('all processes &or;', 'all states &or;'))
           + f'<span class="m lift" style="font-size:10.5px; padding:5px 11px;'
             f' border:1px solid {OK}55; color:{OK}; background:{OK}14; cursor:pointer;">'
             f'&#9679; following</span></span>')
    lines = console_lines()
    inner = (f'<div style="display:flex; align-items:center; justify-content:space-between;'
             f' padding-bottom:10px; border-bottom:1px solid {LINE2};">'
             f'<span class="m" style="font-size:11px; color:{MUT};">'
             f'34 lines &middot; task events only</span>{ctl}</div>'
             f'<div style="padding-top:6px;">{lines}</div>'
             f'<div style="display:flex; align-items:center; justify-content:space-between;'
             f' padding-top:12px; margin-top:8px; border-top:1px solid {LINE2};">'
             f'<span class="m" style="font-size:10.5px; color:{DIM};">virtualised &mdash; a '
             f'5,000-task run is 15,000 events, and putting them all in the DOM is how a '
             f'console that pages correctly still feels broken</span>'
             f'<span class="m" style="font-size:10.5px; color:{DIM};">right-click a line to '
             f'copy it, or filter to its process</span></div>')
    body = (shell('rnaseq-counts') + run_header()
            + f'<div style="padding-top:20px;">'
              f'{panel("console", inner + composer(), right=tabs("console"))}</div>')
    return page('RunConsole', 1500, body)


# ══ writing to the console — a palette over a closed vocabulary, never a shell ════════
VERBS = [
    ('cancel',        'terminate the head process',            'running',  True),
    ('relaunch',      'launch again, optionally -resume',      'terminal', False),
    ('retry task N',  'relaunch -resume, targeting one failure','terminal', False),
    ('pause',         'stop submitting new tasks',             'running',  True),
    ('apply',         'take a run-level proposal into site.config', 'any', False),
]


def composer():
    """§11. **The console displays text; the interactive part is a command palette over a
    vocabulary.** There is no code path from this box to a shell, and adding one means adding a
    verb — visibly, in a diff. That is what makes the audit finite: a reviewer checks a list of
    five, not a sanitiser.

    WHICH VERBS ARE OFFERED IS THE RUN'S PHASE. `cancel` and `pause` exist only while it runs;
    `relaunch` and `retry` only once it is terminal. A greyed verb says why rather than
    vanishing, so the vocabulary is learnable from one screen.

    THE PREVIEW IS THE POINT. Typing produces a typed `Intent` — kind, `because`, whether it
    needs a named human, and what the audit row will hold — and the person confirms THAT, not
    the string they typed."""
    rows = ''
    for verb, what, when, live in VERBS:
        on = live or verb == 'apply'
        rows += (f'<div class="lift" style="display:grid; grid-template-columns:132px 1fr 120px;'
                 f' gap:14px; align-items:baseline; padding:7px 10px; cursor:pointer;">'
                 f'<span class="m" style="font-size:11.5px; color:{INK if on else "#3B474B"};">'
                 f'{verb}</span>'
                 f'<span style="font-size:11px; color:{MUT if on else "#3B474B"};">{what}</span>'
                 f'<span class="m" style="font-size:10px; color:{DIM}; text-align:right;">'
                 + ('' if on else f'needs a {when} run') + '</span></div>')
    preview = (
        f'<div style="border:1px solid {INK_I}33; background:#0B1419; padding:13px 16px;'
        f' margin-top:10px;">'
        f'<div class="m" style="font-size:11.5px; color:{INK}; padding-bottom:9px;">'
        f'<span style="color:{INK_I};">&rsaquo;</span> cancel</div>'
        + ''.join(
            f'<div style="display:grid; grid-template-columns:86px 1fr; gap:12px;'
            f' padding:3px 0;"><span class="lb">{k}</span>'
            f'<span class="m" style="font-size:11px; color:{c};">{v}</span></div>'
            for k, v, c in (
                ('intent', 'CANCEL', INK),
                ('because', 'OPERATOR_REQUEST', MUT),
                ('requires', 'approval by a named human', ATTN),
                ('audit', 'who &middot; when &middot; why &middot; prior phase', MUT),
                ('not', 'pipeline.yml &mdash; no verb here touches the artifact', DIM)))
        + f'<div style="display:flex; gap:8px; margin-top:12px;">'
          f'<span class="m lift" style="font-size:10.5px; padding:7px 14px; cursor:pointer;'
          f' color:{INK_I}; border:1px solid {INK_I}55; background:#122029;">confirm</span>'
          f'<span class="m lift" style="font-size:10.5px; padding:7px 14px; cursor:pointer;'
          f' color:{MUT}; border:1px solid {LINE};">discard</span></div>'
          f'<div class="m" style="font-size:10px; color:{DIM}; margin-top:11px; '
          f'padding-top:10px; border-top:1px solid {LINE};">once this run is terminal the same '
          f'box offers <span style="color:{MUT};">relaunch --resume --mem 96.GB</span>, and the '
          f'preview names the override as <span style="color:{MUT};">'
          f'RELAUNCH(resume=true, overrides={{memory: 96.GB}})</span> before anything runs.'
          f'</div></div>')
    return (f'<div style="margin-top:14px; border-top:1px solid {LINE}; padding-top:14px;">'
            f'<div style="display:flex; align-items:center; justify-content:space-between;'
            f' padding-bottom:9px;"><span class="lb">run operations</span>'
            f'<span class="m" style="font-size:10px; color:{DIM};">'
            f'a closed vocabulary of five &mdash; there is no shell behind this box</span></div>'
            f'<div style="display:flex; align-items:center; gap:11px; border:1px solid {LINE};'
            f' background:{PANEL2}; padding:10px 13px;">'
            f'<span class="m" style="font-size:12px; color:{INK_I};">&rsaquo;</span>'
            f'<span class="m" style="font-size:12px; color:{INK};">cancel'
            f'<span class="cur">&#9646;</span></span>'
            f'<span class="m" style="font-size:10px; color:{DIM}; margin-left:auto;">'
            f'&#8984;K anywhere</span></div>'
            f'<div style="border:1px solid {LINE}; border-top:0; background:rgba(10,16,20,.9);'
            f' padding:5px 3px;">{rows}</div>{preview}</div>')


# ══ the monitor — DEFERRED. Drawn so the shape is settled, not so it ships ═════════════
def brief(badge, badge_colour, text, cites=None, delay=0):
    return f'''
      <div class="settle" style="padding:13px 0; border-bottom:1px solid {LINE2};
                                 animation-delay:{delay}ms;">
        <div style="display:flex; align-items:center; gap:9px; padding-bottom:8px;">
          {chip(badge, badge_colour)}
          <span class="m" style="font-size:10px; color:{DIM};">21:19</span>
        </div>
        <div style="font-size:12px; color:{INK}; line-height:1.6;">{text}</div>
        {f'<div class="m lift" style="font-size:10.5px; color:{INK_I}; margin-top:9px; '
         f'cursor:pointer;">{cites}</div>' if cites else ''}
      </div>'''


def build_monitor():
    rail = f'''
      <div class="pl" style="height:100%; display:flex; flex-direction:column;">
        <div class="hd" style="flex-direction:column; align-items:stretch; gap:7px;">
          <div style="display:flex; align-items:center; justify-content:space-between;">
            <span class="lb">monitor</span>
            <span class="m lift" style="font-size:14px; color:{MUT}; cursor:pointer;">&rsaquo;</span>
          </div>
          <div class="m" style="font-size:10px; color:{DIM};">
            guarded &middot; local model &middot; 3 calls this run</div>
        </div>
        <div style="flex:1; padding:2px 16px 0; overflow:hidden;">
          {brief('heartbeat', MUT,
                 'Nothing has failed. STAR_ALIGN is the only step running and its two live '
                 'tasks are inside the spread of the four that finished.',
                 'read 5 process rows', 0)}
          <div class="settle" style="padding:13px 0; animation-delay:30ms; display:flex;
                      justify-content:flex-end;">
            <span style="font-size:12px; color:{INK}; background:#122029; padding:9px 13px;
                  border:1px solid {INK_I}33; max-width:80%;">
              how much longer?</span></div>
          {brief('you asked', INK_I,
                 'Two steps of five are done. STAR_ALIGN has four tasks left and its six '
                 'completed ones averaged <span class="m">10m 04s</span>, so about '
                 '<span class="m">20 minutes</span> at two at a time. '
                 '<span style="color:' + MUT + ';">SAMTOOLS_SORT and FEATURECOUNTS have never '
                 'run in this pipeline, so I have no basis for those two.</span>',
                 'read the process table &middot; 18 task rows', 60)}
          {brief('new signature', ATTN,
                 'STAR_ALIGN task 13 exited 137 on attempt 1 and was retried at 72 GB. '
                 'Peak RSS was 99% of the request on the attempt that failed.',
                 'read task 13, 3 attempts', 90)}
          <div class="settle" style="border:1px solid {ATTN}44; background:{ATTN}0F;
                      padding:13px 14px; margin-top:12px; animation-delay:120ms;">
            <div style="display:flex; align-items:center; gap:9px; padding-bottom:9px;">
              {chip('run-level', ATTN)}
              <span class="m" style="font-size:10px; color:{MUT};">changes the launch</span>
            </div>
            <pre class="m" style="margin:0 0 11px; font-size:10.5px; color:#A9B7BB;
                 background:{PANEL2}; border:1px solid {LINE}; padding:9px 11px;
                 white-space:pre-wrap;">withName: STAR_ALIGN {{
-   memory = 36.GB
+   memory = 96.GB
}}</pre>
            <div style="display:flex; gap:8px; align-items:center;">
              <span class="m lift" style="font-size:10.5px; padding:7px 13px; cursor:pointer;
                    color:{INK_I}; border:1px solid {INK_I}55; background:#122029;">apply</span>
              <span class="m" style="font-size:10px; color:{DIM};">
                needs a named human &middot; never pipeline.yml</span>
            </div>
          </div>
        </div>
        <div style="padding:12px 16px 14px; border-top:1px solid {LINE};">
          <div style="display:flex; align-items:center; gap:10px; border:1px solid {LINE};
                      background:{PANEL2}; padding:9px 12px;">
            <span class="m" style="font-size:11px; color:{DIM};">
              ask about this run<span class="cur">&#9646;</span></span>
            <span class="m" style="font-size:10px; color:{DIM}; margin-left:auto;">
              guarded &mdash; you will see the payload first</span>
          </div>
        </div>
      </div>'''
    tl, _h = timeline()
    # two by two, because the rail took a third of the width — the four are the four
    # regardless of how they wrap, and dropping one to fit is dropping a question.
    left = (run_header()
            + f'<div class="band" style="padding:20px 0 0;">{tiles_live()}</div>'
            + f'<div style="padding-top:14px;">'
              f'{panel("timeline", f"<div style=\'padding-left:132px;\'>{tl}</div>")}</div>'
            + f'<div style="padding-top:14px;">'
              f'{panel("processes", process_table(), right=toggle(), pad="4px 24px 10px")}</div>')
    body = (shell('rnaseq-counts')
            + f'''
    <div style="display:flex; align-items:center; gap:12px; padding:14px 0 0;">
      {chip('not in the MVP', ATTN)}
      <span class="m" style="font-size:11px; color:{MUT};">deferred 2026-08-29 &mdash; the
        design is wiener.md &sect;10 and none of it is built. Drawn so the shape is settled.</span>
    </div>
    <div class="withRail" style="padding-top:6px;">
      <div>{left}</div>
      <div style="position:sticky; top:0; min-height:900px;">{rail}</div>
    </div>''')
    return page('RunMonitor', 1080, body)


# ══ /runs — rebuilt for a researcher rather than an administrator ═════════════════════
# The four 14-day tiles (runs, failed, median, p95) told you about the INSTANCE. A researcher
# is asking about their work: what is running, what came back, what needs me, and is this run
# normal. `median duration` earned its place only once it moved onto a row as *vs usual*.

RUNNING = [
    # id, pipeline, done, running, seen, elapsed, usual_s, elapsed_s
    ('a3f9c2e1', 'rnaseq-counts', 12, 2, 18, '21m 40s', 2280, 1300),
    ('7d1e4b90', 'atac-peaks',     4, 2, 22, '6m 12s',  3060,  372),
]

NEEDS = [
    ('19fe6c44', 'wgs-variants', 'SAMTOOLS_SORT exited 137 on attempt 3', 'yesterday', FAIL),
    ('4a0c93e5', 'rnaseq-counts', 'finished, but 3 tasks retried before they passed',
     '2 days ago', ATTN),
]

DONE_RECENTLY = [
    ('c02ab7f3', 'rnaseq-counts', '39m 04s', '2h ago', '18 tasks, no retries', 2280, 2344),
    ('be7710da', 'qc-only',       '5m 47s',  'yesterday', '6 tasks, no retries', 360, 347),
    ('4a0c93e5', 'rnaseq-counts', '36m 51s', '2 days ago', '18 tasks, 3 retried', 2280, 2211),
]


def versus(elapsed_s, usual_s, live=False):
    """How this run compares with what this pipeline usually takes. **The single most useful
    number on the board**, and it is why `median duration by pipeline` stopped being a panel:
    a median in the abstract is trivia, and the same median beside a run is a judgement."""
    ratio = elapsed_s / usual_s
    if live:
        pct = min(100, ratio * 100)
        col = ATTN if ratio > 1.25 else MUT
        return (f'<span style="display:flex; align-items:center; gap:9px;">'
                f'<span style="position:relative; width:104px; height:6px; background:#141D21;">'
                f'<span class="grow" style="position:absolute; inset:0 auto 0 0; '
                f'width:{pct:.0f}%; background:{col}; opacity:.75;"></span>'
                f'<span style="position:absolute; left:100%; top:-3px; width:1px; height:12px; '
                f'background:{MUT};"></span></span>'
                f'<span class="m" style="font-size:10.5px; color:{DIM}; white-space:nowrap;">'
                f'usually {usual_s // 60}m</span></span>')
    delta = (ratio - 1) * 100
    col = ATTN if abs(delta) > 25 else DIM
    return (f'<span class="m" style="font-size:10.5px; color:{col};">'
            f'{"+" if delta >= 0 else ""}{delta:.0f}% vs usual</span>')


def now_band():
    strips = ''
    for i, (rid, name, done, running, seen, el, usual, els) in enumerate(RUNNING):
        strips += f'''<a class="lift settle" style="display:block; padding:14px 16px;
              border:1px solid {LINE}; background:rgba(12,18,22,.6); text-decoration:none;
              animation-delay:{i*30}ms;">
          <div style="display:flex; align-items:baseline; justify-content:space-between;">
            <span style="display:flex; align-items:baseline; gap:12px;">
              <span style="font-size:15px; color:{INK}; font-weight:500;">{name}</span>
              <span class="m" style="font-size:10px; color:{DIM};">{rid}</span></span>
            <span class="m" style="font-size:14px; color:{RUN};">{el}</span>
          </div>
          <div style="display:flex; gap:3px; height:8px; margin:11px 0 10px;">
            <span class="grow" style="flex:{done}; background:{OK}; opacity:.8;"></span>
            <span class="grow flow" style="flex:{running}; background:{RUN};"></span>
            <span style="flex:{seen-done-running}; background:#1B262B;"></span></div>
          <div style="display:flex; align-items:center; justify-content:space-between;">
            <span class="m" style="font-size:10.5px; color:{MUT};">
              {done} done &middot; {running} running &middot; {seen-done-running} waiting</span>
            {versus(els, usual, live=True)}
          </div>
        </a>'''
    return f'''
    <div class="settle" style="padding:26px 0 0;">
      <div style="display:flex; align-items:baseline; gap:14px; padding-bottom:14px;">
        <span class="lb">running now</span>
        <span class="m" style="font-size:11px; color:{MUT};">
          2 runs &middot; 6 tasks in flight &middot; oldest started 21 min ago</span>
      </div>
      <div class="pair">{strips}</div>
    </div>'''


def needs_you():
    """**Only exists when it has something in it.** A card reading *nothing needs you* is a
    card that trains people to stop looking at the place things appear."""
    rows = ''
    for i, (_rid, name, why, when, col) in enumerate(NEEDS):
        rows += f'''<a class="lift settle" style="display:grid;
              grid-template-columns:14px 1fr 96px; gap:14px; align-items:center;
              padding:12px 6px; border-bottom:1px solid {LINE2}; text-decoration:none;
              animation-delay:{i*30}ms;">
          <span style="width:6px; height:26px; background:{col};"></span>
          <span>
            <span style="display:block; font-size:12.5px; color:{INK};">{name}</span>
            <span class="m" style="display:block; font-size:11px; color:{MUT}; margin-top:3px;">
              {why}</span></span>
          <span class="m" style="font-size:10.5px; color:{DIM}; text-align:right;">{when}</span>
        </a>'''
    return panel('needs you', rows,
                 right=f'<span class="m" style="font-size:10px; color:{DIM};">'
                       f'2 &mdash; nothing else since the 14th</span>')


def finished_recently():
    rows = ''
    for i, (_rid, name, dur, when, what, usual, els) in enumerate(DONE_RECENTLY):
        rows += f'''<a class="lift settle" style="display:grid;
              grid-template-columns:1fr 88px 108px; gap:14px; align-items:center;
              padding:12px 6px; border-bottom:1px solid {LINE2}; text-decoration:none;
              animation-delay:{i*30}ms;">
          <span>
            <span style="display:block; font-size:12.5px; color:{INK};">{name}</span>
            <span class="m" style="display:block; font-size:11px; color:{MUT}; margin-top:3px;">
              {what}</span></span>
          <span class="m" style="font-size:11px; color:{MUT}; text-align:right;">{dur}</span>
          <span style="text-align:right;">{versus(els, usual)}<br>
            <span class="m" style="font-size:10px; color:{DIM};">{when}</span></span>
        </a>'''
    return panel('finished recently', rows,
                 right=f'<span class="m" style="font-size:10px; color:{DIM};">'
                       f'outputs need publishDir &mdash; see the notes</span>')


def runs_table():
    head = f'''<div class="rr" style="border-bottom:1px solid {LINE};">
      <span class="lb">pipeline</span><span class="lb">state</span><span class="lb">tasks</span>
      <span class="lb" style="text-align:right;">duration</span>
      <span class="lb" style="text-align:right;">vs usual</span>
      <span class="lb" style="text-align:right;">run</span></div>'''
    body = [
        ('a3f9c2e1', 'rnaseq-counts', 'running',   12, 18, '21m 40s', 2280, 1300, RUN),
        ('7d1e4b90', 'atac-peaks',    'running',    4, 22, '6m 12s',  3060,  372, RUN),
        ('c02ab7f3', 'rnaseq-counts', 'succeeded', 18, 18, '39m 04s', 2280, 2344, OK),
        ('19fe6c44', 'wgs-variants',  'failed',    61, 140,'1h 04m',  8040, 3840, FAIL),
        ('be7710da', 'qc-only',       'succeeded',  6,  6, '5m 47s',   360,  347, OK),
        ('4a0c93e5', 'rnaseq-counts', 'succeeded', 18, 18, '36m 51s', 2280, 2211, OK),
    ]
    rows = ''
    for i, (rid, name, phase, done, seen, dur, usual, els, c) in enumerate(body):
        # **A delta needs a finished run.** `-43% vs usual` on a run still going reads
        # as *it was faster*, which is the opposite of what it means.
        vs = (f'<span class="m" style="font-size:10.5px; color:{DIM};">&mdash;</span>'
              if phase == 'failed' else
              f'<span class="m" style="font-size:10.5px; color:{DIM};">of ~{usual//60}m</span>'
              if phase == 'running' else versus(els, usual))
        rows += f'''<div class="rr lift settle" style="animation-delay:{i*30}ms;">
          <span style="font-size:12.5px; color:{INK};">{name}</span>
          <span class="m" style="font-size:10.5px; color:{c};">{phase}</span>
          <span style="display:flex; align-items:center; gap:10px;">
            <span style="flex:1; max-width:150px;">{bar(done/seen*100, c)}</span>
            <span class="m" style="font-size:10.5px; color:{MUT};">{done}/{seen}</span></span>
          <span class="m" style="font-size:11px; color:{MUT}; text-align:right;">{dur}</span>
          <span style="text-align:right;">{vs}</span>
          <span class="m" style="font-size:11px; color:{INK_I}; text-align:right;">{rid}</span>
        </div>'''
    filters = ('<span style="display:flex; gap:6px;">'
               + ''.join(f'<span class="m lift" style="font-size:10px; letter-spacing:.08em;'
                         f' text-transform:uppercase; padding:5px 11px; border:1px solid '
                         f'{LINE}; color:{INK if f=="all" else MUT}; cursor:pointer;'
                         f' background:{"#122029" if f=="all" else "transparent"};">{f}</span>'
                         for f in ('all', 'running', 'failed', 'rnaseq-counts')) + '</span>')
    return panel('61 runs', f'<div class="tbl"><div>{head}{rows}</div></div>',
                 right=filters)


def build_runs_board():
    body = (shell() + now_band() + f'''
    <div class="pair" style="padding-top:26px;">
      {needs_you()}{finished_recently()}
    </div>
    <div style="padding-top:14px;">{runs_table()}</div>''')
    return page('RunsBoard', 900, body)


if __name__ == '__main__':
    for m in [build_runs_board(), build_run_view(), build_run_failed(), build_run_early(),
              build_console(), build_monitor()]:
        print('wrote', m + '.dc.html')
