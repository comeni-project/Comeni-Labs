"""Builds every W2 artboard from ONE colour source: ../wiener-mockups/tokens.shared.css.

No hex literal appears below this docstring — the same guarantee `wiener-mockups/build.py`
makes, and it is checkable by grep rather than promised. These are the screens for the
decisions in `notes/specs/2026-08-24-w2-design-decisions.md`; the 2026-08-23 canvas next
door is the record of how the *direction* was picked and is left alone.
"""
import pathlib

TOKENS = pathlib.Path("../wiener-mockups/tokens.shared.css").read_text()

HEAD = '''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <style>
''' + TOKENS + '''
/* ---- proposed additions: interaction. Derived, like the elevation ramp above. ----

   --hover is NOT a new hue: it is --ink at 5%, so it tints whatever surface it lands on
   and it inverts for free in dark mode, where --ink is light. That is the same argument
   the Depth tokens make from --shadow.

   IT ALSO CLOSES A DEFECT. `hover:bg-[var(--hover)]` appears five times in
   frontend/src/build/ — Compare, Findings and two Builder lists — and --hover is defined
   NOWHERE. Those five hover states are dead CSS, which is why the builder feels inert.

   --t is the house timing, and it is not new either: it is what Tailwind's
   `transition-colors` already resolves to in the seven places the product uses it. Naming
   it is what lets everything else agree with those seven. */
:root {
  --hover: color-mix(in oklab, var(--ink) 5%, transparent);
  --hover-strong: color-mix(in oklab, var(--ink) 9%, transparent);
  --t: 140ms cubic-bezier(.4, 0, .2, 1);
  --t-lift: 180ms cubic-bezier(.2, .7, .3, 1);
  --ring: 0 0 0 2px var(--paper), 0 0 0 4px var(--pea);
}

    body { margin:0; font-family:var(--font-ui); font-size:13px; line-height:1.5;
           color:var(--ink); background:var(--paper); -webkit-font-smoothing:antialiased; }
    a { color:var(--pea); text-decoration:none; transition:color var(--t); }
    a:hover { color:var(--ink); }

    /* Every interactive thing agrees on one timing, and NOTHING that encodes a quantity
       moves. A bar never animates on hover: motion that implies a number nothing measured
       is the fault §9.2 refuses when it forbids a rate on a live edge. */
    .row { cursor:pointer; transition:background-color var(--t); }
    .row:hover { background:var(--hover); }
    .row:hover .caret { color:var(--ink); transform:translateX(2px); }
    .caret { transition:color var(--t), transform var(--t); }
        .trow { transition:background-color var(--t); }
    .trow:hover { background:var(--hover); }
    .btn, .btn-q, .btn-off, .tab, .chip {
      transition:background-color var(--t), color var(--t), box-shadow var(--t-lift),
                 border-color var(--t), transform var(--t-lift); }
    .btn:hover, .btn-q:hover, .chip:hover { box-shadow:var(--e2); transform:translateY(-1px); }
    .btn:active, .btn-q:active, .chip:active { box-shadow:var(--e1); transform:translateY(0); }
    .btn-q:hover, .chip:hover { background:var(--hover); border-color:var(--line-2); }
    .btn-off { cursor:not-allowed; }
    .tab:hover { background:var(--hover); color:var(--ink); }
    .tab.on:hover { background:var(--surface); }
    .mi { transition:background-color var(--t), color var(--t); }
    .mi:hover { background:var(--hover); color:var(--ink); }
    .mi[style*="not-allowed"]:hover { background:transparent; color:var(--ink-3); }
    .step { transition:background-color var(--t); border-radius:var(--r); }
    .step:hover { background:var(--hover); }
    /* Keyboard parity. The product has focus-visible in three places and no shared ring;
       one token means a keyboard reaches everything a mouse does. */
    .row:focus-visible, .btn:focus-visible, .btn-q:focus-visible, .tab:focus-visible,
    .chip:focus-visible { outline:none; box-shadow:var(--ring); }
    /* Reduced motion removes the TRANSITION, never the feedback: the colour still changes,
       it just arrives at once. */
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { transition-duration:.01ms !important;
                               animation-duration:.01ms !important;
                               animation-iteration-count:1 !important; }
      .btn:hover, .btn-q:hover, .chip:hover { transform:none; }
    }
    @keyframes flow { to { stroke-dashoffset:-24; } }
    @keyframes breathe { 0%,100% { opacity:.55; } 50% { opacity:1; } }
    .live { stroke-dasharray:6 6; animation:flow 1.1s linear infinite; }
    .breathe { animation:breathe 2.4s ease-in-out infinite; }
    .mono { font-family:var(--font-data); }
    .lbl { font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--ink-3); }
    .card { background:var(--surface); border:1px solid var(--line); border-radius:var(--r);
            box-shadow:var(--e2); }
    .panel { background:var(--surface); border:1px solid var(--line); border-radius:var(--r);
             box-shadow:var(--e3); display:flex; flex-direction:column; overflow:hidden; }
    .strip { padding:9px 16px; background:var(--surface-2); border-bottom:1px solid var(--line);
             display:flex; align-items:center; gap:12px; }
    .well { height:6px; border-radius:3px; background:var(--surface-2); overflow:hidden;
            box-shadow:var(--well); display:flex; }
    .btn { padding:6px 12px; border-radius:var(--r); background:var(--pea);
           color:var(--on-pea); font-size:12.5px; font-weight:600; box-shadow:var(--e1);
           border:0; display:inline-block; }
    .btn-q { padding:6px 12px; border-radius:var(--r); border:1px solid var(--line-2);
             color:var(--ink-2); font-size:12.5px; background:var(--surface);
             display:inline-block; }
    .btn-off { padding:6px 12px; border-radius:var(--r); border:1px solid var(--line);
               color:var(--ink-3); font-size:12.5px; background:var(--surface-2);
               display:inline-block; }
    .tabs { display:flex; gap:2px; }
    .tab { padding:5px 13px; font-size:12.5px; color:var(--ink-3); border-radius:var(--r);
           background:transparent; }
    .tab.on { color:var(--ink); font-weight:600; background:var(--surface);
              box-shadow:var(--e1); }
    .th { font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--ink-3);
          font-weight:600; }
    .absent { color:var(--line-2); font-family:var(--font-data); font-size:12.5px; }
  </style>
</helmet>
'''

TAIL = '''</x-dc>
</body>
</html>
'''


def page(body, h=900):
    return HEAD + ('<div style="display:flex; flex-direction:column; height:%dpx; '
                   'background:var(--paper); overflow:hidden;">\n' % h) + body + '</div>\n' + TAIL


# ---------------------------------------------------------------- chrome

def nav(section, sub=None):
    subnav = ''
    if sub:
        subnav = ('<span style="width:1px; height:20px; background:var(--line);"></span>'
                  '<div style="display:flex; gap:2px;">' + ''.join(
                      '<span style="padding:6px 12px; font-size:13px; %s">%s</span>' % (
                          'font-weight:600; color:var(--ink); '
                          'box-shadow:inset 0 -2px 0 var(--pea);' if on
                          else 'color:var(--ink-2);', name)
                      for name, on in sub) + '</div>')
    return '''  <nav style="display:flex; align-items:center; gap:28px; padding:0 20px; height:54px;
              background:var(--surface); border-bottom:1px solid var(--line);
              box-shadow:var(--e1); position:relative; z-index:3; flex:0 0 auto;">
    <span style="display:flex; align-items:baseline; gap:8px; font-family:var(--font-display);
                 font-size:21px; letter-spacing:-.015em; color:var(--ink);">
      <i style="width:9px; height:9px; align-self:center; border-radius:50%% 50%% 50%% 0;
                background:var(--pea); transform:rotate(-45deg);"></i>Comeni Labs</span>
    <div style="display:flex; gap:2px; margin-left:8px;">%s</div>
    %s
    <span style="margin-left:auto; padding:4px 8px; border:1px solid var(--line);
                 border-radius:var(--r); font-size:11.5px; color:var(--ink-3);
                 background:var(--surface); box-shadow:var(--e1);">
      What the words mean <span class="mono">?</span></span>
  </nav>
''' % (''.join('<span style="padding:6px 12px; font-size:13px; %s">%s</span>' % (
        'font-weight:600; color:var(--ink); box-shadow:inset 0 -2px 0 var(--pea);'
        if name == section else 'color:var(--ink-2);', name)
        for name in ("Builder", "Forge", "Runs")), subnav)


DOT = ('<i style="display:inline-block; width:8px; height:8px; border-radius:50%%; '
       'background:%s;"></i>')


def runhead(phase, colour, elapsed, finished, declared, pipeline=True):
    """The header and the ONE honest progress bar: steps finished of steps DECLARED.

    D6. A task-level denominator is discovered as channels emit, so a percentage over it is
    a number nobody can source. The artifact declares its steps before the run starts.
    """
    pct = round(100 * finished / declared)
    back = ('<span style="margin-left:auto; font-size:11.5px; color:var(--pea);">'
            '&#8617; pipeline</span>') if pipeline else ''
    return '''  <div style="flex:0 0 auto; padding:16px 24px 14px; background:var(--surface-2);
       border-bottom:1px solid var(--line); box-shadow:var(--e1); position:relative; z-index:2;">
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:3px;">
      <span style="font-size:11.5px; color:var(--ink-3);">&#8592; Board</span>%s
    </div>
    <div style="display:flex; align-items:baseline; gap:14px;">
      <span class="mono" style="font-size:26px; letter-spacing:-.01em;">run 85bbe6a0</span>
      <span style="display:flex; align-items:center; gap:7px; font-size:13px; color:var(--ink-2);">
        %s %s</span>
      <span class="mono" style="margin-left:auto; font-size:13px; color:var(--ink-3);">%s</span>
    </div>
    <div style="display:flex; align-items:center; gap:14px; margin-top:11px;">
      <span style="font-size:12.5px; color:var(--ink-2); white-space:nowrap;">
        <b class="mono">%d</b> of <b class="mono">%d</b> steps finished</span>
      <span class="well" style="flex:1 1 auto; height:8px; max-width:520px;">
        <i style="width:%d%%; background:var(--pea);"></i></span>
      <span class="lbl" style="white-space:nowrap;">declared by the artifact</span>
    </div>
  </div>
''' % (back, DOT % colour, phase, elapsed, finished, declared, pct)


def tabs(active, note='following &middot; read-only until W4'):
    names = ("Overview", "Console", "Graph", "Tasks")
    return ('    <div class="strip">\n      <div class="tabs">' + ''.join(
        '<span class="tab%s">%s</span>' % (' on' if n == active else '', n) for n in names)
        + '</div>\n      <span style="margin-left:auto; font-size:11.5px; color:var(--ink-3);">'
        + note + '</span>\n    </div>\n')


# ---------------------------------------------------------------- the overview

COLS = ('minmax(230px,1.3fr) 116px 132px minmax(150px,1fr) minmax(120px,.8fr) '
        'minmax(130px,.9fr) minmax(150px,1fr)')


def bar(pct, colour, width=None):
    """Length encodes quantity, on an identical scale down every column. That is what makes
    a column of these a small multiple rather than seven unrelated bars."""
    if pct is None:
        return '<span class="absent">&mdash;</span>'
    inner = '<i style="width:%d%%; background:%s;"></i>' % (pct, colour)
    return ('<span class="well" style="height:7px; width:%s;">%s</span>'
            % (width or '100%', inner))


def cell(pct, colour, text, sub=None):
    if pct is None and text is None:
        return '<span class="absent">&mdash;</span>'
    return ('<div style="display:flex; flex-direction:column; gap:4px;">%s'
            '<span class="mono" style="font-size:11.5px; color:var(--ink-2);">%s</span>%s</div>'
            % (bar(pct, colour), text,
               '<span class="lbl">%s</span>' % sub if sub else ''))


def orow(name, tasks, seen, prog, prog_col, mem, mem_t, cpu, cpu_t, tim, tim_t, io, io_t,
         retried=None, failed=None, note=None, dim=False, open_=False,
         demo=False):
    left = ('<div style="display:flex; flex-direction:column; gap:2px; min-width:0;">'
            '<span class="mono" style="font-size:13px; color:%s;">%s%s</span>%s</div>'
            % ('var(--ink-3)' if dim else 'var(--ink)', name,
               (' <span style="color:var(--measured); font-size:11.5px;">&#8635;%d</span>'
                % retried) if retried else '',
               '<span class="lbl">%s</span>' % note if note else ''))
    if tasks is None:
        count = '<span class="absent">&mdash;</span>'
    else:
        count = ('<div style="display:flex; flex-direction:column; gap:2px;">'
                 '<span class="mono" style="font-size:13px;">%s</span>%s%s</div>'
                 % ('%d done' % tasks,
                    '<span class="lbl" style="color:var(--undecided);">%d failed</span>' % failed
                    if failed else '',
                    '<span class="lbl">%d more seen</span>' % seen if seen else ''))
    caret = ('<svg class="caret" width="11" height="11" viewBox="0 0 24 24" fill="none" '
             'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" '
             'style="color:%s; flex:0 0 auto; transform:rotate(%ddeg);">'
             '<polyline points="9 6 15 12 9 18"></polyline></svg>'
             % ('var(--ink)' if open_ else 'var(--ink-3)', 90 if open_ else 0))
    # **No chips appear on hover.** They offered `console` and `tasks`, which are two of the
    # four tabs sitting directly above the table — an affordance that covers a column to reach
    # something already one click away, and it covered *read / written*. Operator, 2026-08-24.
    # What a row hover does is tint and move the caret; the shortcut lives on right-click (D10).
    reveal = ''
    return ('  <div class="row" tabindex="0" style="display:grid; grid-template-columns:%s; '
            'gap:18px; align-items:center; padding:13px 18px 13px 24px; '
            'border-bottom:1px solid var(--line); position:relative;%s">\n'
            '    <span style="position:absolute; left:7px;">%s</span>%s\n'
            '    %s\n    %s\n    %s\n    %s\n    %s\n    %s\n    %s\n  </div>\n'
            % (COLS, ' background:var(--surface-2);' if open_ else
               (' background:var(--hover);' if demo else ''), caret, reveal, left,
               count, bar(prog, prog_col), cell(mem, 'var(--measured)', mem_t),
               cell(cpu, 'var(--pea)', cpu_t), cell(tim, 'var(--ink-2)', tim_t),
               cell(io, 'var(--ink-2)', io_t)))


def ohead():
    return ('  <div style="display:grid; grid-template-columns:%s; gap:18px; '
            'padding:9px 18px 9px 24px; border-bottom:1px solid var(--line-2); '
            'background:var(--surface);">%s</div>\n'
            % (COLS, ''.join('<span class="th">%s</span>' % h for h in
                             ("Process", "Tasks", "Progress", "Memory peak / asked",
                              "CPU used / asked", "Worst realtime", "Read / written"))))


TASK_COLS = '120px 60px 70px 110px 90px 100px 1fr'
TASK_NAMES = ("Tag", "Attempt", "Exit", "Memory", "CPU", "Realtime", "")


def trow(tag, att, exit_, mem, cpu, rt, mark='', bad=False, indent=True):
    """ONE task row shape. The Tasks tab and the expanded process row are two callers of it —
    the same reason `dag-core` serves two canvases."""
    tone = 'var(--undecided)' if bad else 'var(--ink-2)'
    return ('    <div class="trow" style="display:grid; grid-template-columns:%s; gap:16px; '
            'padding:6px 18px 6px %dpx; font-family:var(--font-data); font-size:11.5px; '
            'color:%s;%s">'
            '<span style="color:%s;">%s</span><span>%s</span><span>%s</span>'
            '<span>%s</span><span>%s</span><span>%s</span><span style="color:%s;">%s</span>'
            '</div>\n'
            % (TASK_COLS, 46 if indent else 18, tone,
               ' background:var(--undecided-soft); box-shadow:inset 2px 0 0 var(--undecided);'
               if bad else '',
               'var(--ink)' if not bad else 'var(--undecided)', tag,
               ('<span style="color:var(--measured);">%s</span>' % att) if att != '1' else att,
               exit_, mem, cpu, rt, 'var(--undecided)' if bad else 'var(--ink-3)', mark))


def taskcols():
    return ('    <div style="display:grid; grid-template-columns:%s; gap:16px; '
            'padding:7px 18px 7px 46px; border-bottom:1px solid var(--line); '
            'border-top:1px solid var(--line);">%s</div>\n'
            % (TASK_COLS, ''.join('<span class="th">%s</span>' % h for h in TASK_NAMES)))


def panel(inner, tab="Overview", note='following &middot; read-only until W4'):
    return ('  <div style="flex:1 1 auto; padding:16px 24px 22px; min-height:0; display:flex;">\n'
            '    <section class="panel" style="flex:1 1 auto; min-width:0;">\n'
            + tabs(tab, note) + inner + '    </section>\n  </div>\n')


FOOT = ('  <div style="margin-top:auto; padding:10px 24px; border-top:1px solid var(--line); '
        'background:var(--surface-2); display:flex; gap:22px; align-items:center;">'
        '<span class="lbl">%s</span>'
        '<span class="lbl" style="margin-left:auto;">every bar shares its column&rsquo;s scale '
        '&middot; &mdash; means nothing was reported, never zero</span></div>\n')

ROWS_OK = (
    orow("STAR_GENOMEGENERATE", 1, 0, 100, "var(--pea)",
         48, "31.0 / 64 GB", 78, "78%", 60, "4m01s", 39, "1.2G / 31G")
    + orow("STAR_ALIGN", 12, 0, 100, "var(--pea)",
           96, "61.2 / 64 GB", 81, "81%", 100, "6m41s", 91, "31G / 44G", retried=1)
    + orow("SAMTOOLS_SORT", 12, 0, 100, "var(--pea)",
           14, "8.9 / 64 GB", 40, "40%", 5, "22s", 100, "44G / 38G", demo=True)
    + orow("SUBREAD_FEATURECOUNTS", 3, 9, 25, "var(--measured)",
           8, "5.1 / 64 GB", 22, "22%", 15, "1m02s", None, None)
    + orow("MULTIQC", None, 0, 0, "var(--pea)", None, None, None, None, None, None, None, None,
           note="not started", dim=True))

TASKS_ALIGN = (
    taskcols()
    + trow("sample_01", "1", "0", "58.1 GB", "79%", "6m02s")
    + trow("sample_02", "1", "0", "61.2 GB", "81%", "6m41s", mark="worst")
    + trow("sample_03", "2", "0", "44.9 GB", "77%", "5m10s", mark="&#8635; retried once")
    + trow("sample_04", "1", "0", "57.7 GB", "80%", "6m18s")
    + trow("sample_05", "1", "0", "52.4 GB", "76%", "5m44s")
    + '    <div style="padding:7px 18px 9px 46px; font-size:11.5px; color:var(--ink-3);">'
      '7 more &middot; sorted by memory</div>\n')

pathlib.Path("Main.dc.html").write_text(page(
    nav("Runs", [("Board", False), ("This run", True)])
    + runhead("running", "var(--measured)", "7m12s", 3, 5)
    + panel(ohead() + ROWS_OK + FOOT % "5 processes declared &middot; 28 tasks seen")))

pathlib.Path("Expanded.dc.html").write_text(page(
    nav("Runs", [("Board", False), ("This run", True)])
    + runhead("running", "var(--measured)", "7m12s", 3, 5)
    + panel(ohead()
            + orow("STAR_GENOMEGENERATE", 1, 0, 100, "var(--pea)",
                   48, "31.0 / 64 GB", 78, "78%", 60, "4m01s", 39, "1.2G / 31G")
            + orow("STAR_ALIGN", 12, 0, 100, "var(--pea)",
                   96, "61.2 / 64 GB", 81, "81%", 100, "6m41s", 91, "31G / 44G",
                   retried=1, open_=True)
            + TASKS_ALIGN
            + orow("SAMTOOLS_SORT", 12, 0, 100, "var(--pea)",
                   14, "8.9 / 64 GB", 40, "40%", 5, "22s", 100, "44G / 38G")
            + orow("SUBREAD_FEATURECOUNTS", 3, 9, 25, "var(--measured)",
                   8, "5.1 / 64 GB", 22, "22%", 15, "1m02s", None, None)
            + orow("MULTIQC", None, 0, 0, "var(--pea)", None, None, None, None, None, None,
                   None, None, note="not started", dim=True)
            + FOOT % "one TaskRow, two callers &middot; the Tasks tab renders the same shape")))

BANNER = '''  <div style="flex:0 0 auto; margin:16px 24px 0; padding:15px 18px;
       background:var(--undecided-soft); border:1px solid var(--undecided);
       border-radius:var(--r); box-shadow:var(--e2); display:flex; flex-direction:column;
       gap:10px;">
    <div style="display:flex; align-items:baseline; gap:10px;">
      <span class="mono" style="font-size:15px; color:var(--fault);">STAR_ALIGN
        (sample_07) exited 137 on attempt 2</span>
      <span style="margin-left:auto;" class="lbl">from the record &middot; nothing interpreted</span>
    </div>
    <div style="display:flex; align-items:center; gap:10px;">
      <span class="well" style="height:7px; width:170px;">
        <i style="width:99%; background:var(--undecided);"></i></span>
      <span class="mono" style="font-size:12.5px; color:var(--ink-2);">
        peaked at 63.8 of 64 GB asked</span>
    </div>
    <pre class="mono" style="margin:0; padding:10px 12px; background:var(--surface);
         border:1px solid var(--line); border-radius:var(--r); box-shadow:var(--well);
         font-size:11.5px; line-height:1.7; color:var(--ink-2); overflow:hidden;
         white-space:pre-wrap;">Command error:
  .command.sh: line 9:   214 Killed    STAR --genomeDir star --readFilesIn ...
  slurmstepd: error: Detected 1 oom-kill event(s) in StepId=41822.batch.</pre>
    <span class="lbl">Nextflow&rsquo;s own errorReport &middot; shown, not explained &mdash; W3 explains</span>
  </div>
'''

pathlib.Path("Failure.dc.html").write_text(page(
    nav("Runs", [("Board", False), ("This run", True)])
    + runhead("failed", "var(--undecided)", "9m02s", 2, 5)
    + BANNER
    + panel(ohead()
            + orow("STAR_GENOMEGENERATE", 1, 0, 100, "var(--pea)",
                   48, "31.0 / 64 GB", 78, "78%", 60, "4m01s", 39, "1.2G / 31G")
            + orow("STAR_ALIGN", 11, 0, 92, "var(--undecided)",
                   100, "63.8 / 64 GB", 81, "81%", 100, "6m41s", 91, "29G / 41G",
                   retried=2, failed=1, open_=True)
            + taskcols()
            + trow("sample_06", "1", "0", "58.1 GB", "79%", "6m02s")
            + trow("sample_07", "2", "137", "63.8 GB", "74%", "4m11s",
                   mark="killed &mdash; out of memory", bad=True)
            + trow("sample_08", "1", "0", "57.7 GB", "80%", "6m18s")
            + '    <div style="padding:7px 18px 9px 46px; font-size:11.5px; '
              'color:var(--ink-3);">9 more &middot; the failing task and its siblings first</div>\n'
            + orow("SAMTOOLS_SORT", 11, 0, 92, "var(--pea)",
                   14, "8.9 / 64 GB", 40, "40%", 5, "22s", 96, "41G / 36G")
            + orow("SUBREAD_FEATURECOUNTS", None, 0, 0, "var(--pea)", None, None, None, None,
                   None, None, None, None, note="not started", dim=True)
            + orow("MULTIQC", None, 0, 0, "var(--pea)", None, None, None, None, None, None,
                   None, None, note="not started", dim=True)
            + FOOT % "the failed process opens itself &middot; its siblings are the comparison",
            note='not following &middot; the run is over'), h=1010))


# ---------------------------------------------------------------- 4. the Tasks tab
def chip(label, value, open_=False):
    return ('<span class="chip btn-q" tabindex="0" style="display:inline-flex; '
            'align-items:center; gap:7px; box-shadow:var(--e1);">'
            '%s <b style="color:var(--ink); font-weight:600;">%s</b>'
            '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round"><polyline points="6 9 12 15 18 9">'
            '</polyline></svg></span>' % (label, value))


FILTERS = ('    <div style="display:flex; align-items:center; gap:10px; padding:11px 18px; '
           'border-bottom:1px solid var(--line); background:var(--surface);">%s%s%s'
           '<span class="btn-q" style="box-shadow:var(--e1);">&#8635; retried only</span>'
           '<span style="margin-left:auto; font-size:11.5px; color:var(--ink-3);">'
           '<b class="mono">412</b> tasks &middot; sorted by memory</span></div>\n'
           % (chip("process", "all"), chip("status", "all"), chip("attempt", "any")))

pathlib.Path("Tasks.dc.html").write_text(page(
    nav("Runs", [("Board", False), ("This run", True)])
    + runhead("running", "var(--measured)", "7m12s", 3, 5)
    + panel(FILTERS
            + ('    <div style="display:grid; grid-template-columns:190px %s; gap:16px; '
               'padding:8px 18px; border-bottom:1px solid var(--line-2);">'
               '<span class="th">Process</span>%s</div>\n'
               % (TASK_COLS, ''.join('<span class="th">%s</span>' % h for h in TASK_NAMES)))
            + ''.join(
                '    <div class="trow" style="display:grid; grid-template-columns:190px %s; '
                'gap:16px; padding:6px 18px; font-family:var(--font-data); font-size:11.5px; '
                'color:var(--ink-2); border-bottom:1px solid var(--line);">'
                '<span style="color:var(--ink);">%s</span><span style="color:var(--ink);">%s</span>'
                '<span style="color:%s;">%s</span><span>%s</span><span>%s</span><span>%s</span>'
                '<span>%s</span><span style="color:var(--ink-3);">%s</span></div>\n'
                % (TASK_COLS, proc, tag,
                   'var(--measured)' if att != '1' else 'var(--ink-2)', att,
                   ex, mem, cpu, rt, mark)
                for proc, tag, att, ex, mem, cpu, rt, mark in [
                    ("STAR_ALIGN", "sample_02", "1", "0", "61.2 GB", "81%", "6m41s", ""),
                    ("STAR_ALIGN", "sample_04", "1", "0", "57.7 GB", "80%", "6m18s", ""),
                    ("STAR_ALIGN", "sample_01", "1", "0", "58.1 GB", "79%", "6m02s", ""),
                    ("STAR_ALIGN", "sample_03", "2", "0", "44.9 GB", "77%", "5m10s",
                     "&#8635; retried once"),
                    ("STAR_GENOMEGENERATE", "&mdash;", "1", "0", "31.0 GB", "78%", "4m01s", ""),
                    ("SAMTOOLS_SORT", "sample_09", "1", "0", "8.9 GB", "40%", "24s", ""),
                    ("SAMTOOLS_SORT", "sample_02", "1", "0", "8.7 GB", "41%", "22s", ""),
                    ("SUBREAD_FEATURECOUNTS", "sample_01", "1", "&mdash;", "5.1 GB", "22%",
                     "running", ""),
                ])
            + '    <div style="padding:9px 18px; font-size:11.5px; color:var(--ink-3);">'
              '404 more &middot; only what fits the window is drawn</div>\n'
            + FOOT % "the same TaskRow as an expanded process &middot; virtualised at 5,000",
            tab="Tasks")))

# ---------------------------------------------------------------- 5. the console
def cline(t, glyph, colour, proc, sample, right, rcol="var(--ink-3)", bad=False):
    return ('        <div style="%s"><span style="color:var(--ink-3);">%s</span>  '
            '<span style="color:%s;"%s>%s</span>  %s <span style="color:var(--ink-3);">(%s)</span>'
            '<span style="float:right; color:%s;">%s</span></div>\n'
            % ('background:var(--undecided-soft); border-radius:var(--r); margin:2px -8px; '
               'padding:2px 8px; box-shadow:inset 2px 0 0 var(--undecided);' if bad else '',
               t, colour, ' class="breathe"' if glyph == "&#9679;" else '', glyph, proc,
               sample, rcol, right))


pathlib.Path("Console.dc.html").write_text(page(
    nav("Runs", [("Board", False), ("This run", True)])
    + runhead("running", "var(--measured)", "7m12s", 3, 5)
    + panel(('    <div style="display:flex; align-items:center; gap:10px; padding:11px 18px; '
             'border-bottom:1px solid var(--line); background:var(--surface);">%s%s'
             '<span style="font-size:11.5px; color:var(--ink-2);">filtered from the overview '
             '&mdash; <span style="color:var(--pea);">show everything</span></span>'
             '<span style="margin-left:auto; font-size:11.5px; color:var(--measured);">'
             'tailing</span></div>\n'
             % (chip("process", "STAR_ALIGN"), chip("status", "all")))
            + '      <div class="mono" style="flex:1 1 auto; padding:14px 18px; '
              'font-size:11.5px; line-height:1.95; color:var(--ink-2); overflow:hidden;">\n'
            + cline("20:31:04", "&#10003;", "var(--pea)", "STAR_ALIGN", "sample_01", "6m 02s")
            + cline("20:31:22", "&#10003;", "var(--pea)", "STAR_ALIGN", "sample_02", "6m 41s")
            + cline("20:32:18", "&#10007;", "var(--undecided)", "STAR_ALIGN", "sample_03",
                    "exit 137", "var(--undecided)", bad=True)
            + '        <div style="color:var(--ink-3); padding-left:22px;">'
              'retrying &middot; attempt 2 of 3, memory doubled by errorStrategy</div>\n'
            + cline("20:32:20", "&#9679;", "var(--measured)", "STAR_ALIGN", "sample_03",
                    "running")
            + cline("20:33:05", "&#10003;", "var(--pea)", "STAR_ALIGN", "sample_04", "6m 18s")
            + cline("20:33:41", "&#9679;", "var(--measured)", "STAR_ALIGN", "sample_05",
                    "running")
            + '        <div style="margin-top:14px; color:var(--ink-3);">'
              '&mdash; 38 of 412 events &middot; STAR_ALIGN only &mdash;</div>\n'
            + '      </div>\n'
            + FOOT % "kept, and no longer the front door &middot; zoom and filter, not tail -f",
            tab="Console")))


# ---------------------------------------------------------------- 6. the graph
def node(x, y, label, sub, colour, ring=None, fill="var(--surface)"):
    r = ('<rect x="%d" y="%d" width="188" height="60" rx="3" fill="none" stroke="%s" '
         'stroke-width="1" stroke-dasharray="3 3" opacity=".9"></rect>'
         % (x - 5, y - 5, ring)) if ring else ''
    return ('%s<rect x="%d" y="%d" width="178" height="50" rx="3" fill="%s" stroke="%s" '
            'stroke-width="1.5"></rect>'
            '<text x="%d" y="%d" font-family="var(--font-data)" font-size="12" fill="var(--ink)">'
            '%s</text>'
            '<text x="%d" y="%d" font-family="var(--font-data)" font-size="10.5" '
            'fill="var(--ink-3)">%s</text>'
            % (r, x, y, fill, colour, x + 12, y + 21, label, x + 12, y + 38, sub))


GRAPH = '''      <div style="flex:1 1 auto; position:relative; overflow:hidden;
           background:var(--paper); box-shadow:var(--well);">
        <svg width="100%%" height="100%%" viewBox="0 0 1360 520">
          <defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"
            markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z"
            fill="var(--line-2)"></path></marker></defs>
          <path d="M198 95 L 300 95" stroke="var(--line-2)" stroke-width="1.5" fill="none"
                marker-end="url(#a)"></path>
          <path d="M198 245 L 250 245 L 250 120 L 300 120" stroke="var(--line-2)"
                stroke-width="1.5" fill="none" marker-end="url(#a)"></path>
          <path d="M488 108 L 590 108" stroke="var(--line-2)" stroke-width="1.5" fill="none"
                marker-end="url(#a)"></path>
          <path d="M778 108 L 880 108" stroke="var(--measured)" stroke-width="2" fill="none"
                class="live" marker-end="url(#a)"></path>
          <path d="M1068 108 L 1170 108" stroke="var(--line)" stroke-width="1.5" fill="none"
                stroke-dasharray="4 4"></path>
          %s
          <text x="880" y="185" font-family="var(--font-ui)" font-size="11"
                fill="var(--ink-3)">this edge is active &mdash; and carries no rate</text>
        </svg>
      </div>
''' % (node(20, 70, "STAR_GENOMEGENERATE", "1 done", "var(--pea)")
       + node(20, 220, "entry &middot; reads", "12 samples", "var(--line-2)",
              fill="var(--surface-2)")
       + node(310, 83, "STAR_ALIGN", "12 done &middot; 1 retried", "var(--pea)",
              ring="var(--measured)")
       + node(600, 83, "SAMTOOLS_SORT", "12 done", "var(--pea)")
       + node(890, 83, "SUBREAD_FEATURECOUNTS", "3 done &middot; 9 more seen",
              "var(--measured)")
       + node(1180, 83, "MULTIQC", "not started", "var(--line)", fill="var(--surface-2)"))

pathlib.Path("Graph.dc.html").write_text(page(
    nav("Runs", [("Board", False), ("This run", True)])
    + runhead("running", "var(--measured)", "7m12s", 3, 5)
    + panel(GRAPH + FOOT % "dag-core&rsquo;s layout &middot; the same arithmetic the builder draws",
            tab="Graph")))

# ---------------------------------------------------------------- 7. the walk
def step(n, title, status, control, state, reason=None, last=False):
    marks = {"done": ("var(--pea)", "&#10003;"), "now": ("var(--measured)", "&#9679;"),
             "wait": ("var(--line-2)", "")}
    colour, glyph = marks[state]
    fill = colour if state != "wait" else "var(--surface)"
    ink = "var(--on-pea)" if state == "done" else (
        "var(--paper)" if state == "now" else "var(--ink-3)")
    rail = ('' if last else
            '<span style="position:absolute; left:18px; top:34px; bottom:-6px; width:1.5px; '
            'background:var(--line);"></span>')
    return ('      <div class="step" style="position:relative; padding:8px 8px 18px 34px; '
            'margin:0 -8px;">%s'
            '<span style="position:absolute; left:10px; top:10px; width:19px; height:19px; '
            'border-radius:50%%; background:%s; border:1.5px solid %s; color:%s; font-size:10px; '
            'display:flex; align-items:center; justify-content:center; box-shadow:var(--e1);">'
            '%s</span>'
            '<div style="display:flex; align-items:center; gap:10px; min-height:23px;">'
            '<span style="font-size:13px; font-weight:%s; color:%s;">%s</span>'
            '<span style="margin-left:auto; display:flex; gap:6px;">%s</span></div>'
            '<div style="font-size:11.5px; color:var(--ink-3); margin-top:2px;">%s</div>%s</div>\n'
            % (rail, fill, colour, ink, glyph or str(n),
               '600' if state == 'now' else '500',
               'var(--ink)' if state != 'wait' else 'var(--ink-3)', title,
               control, status,
               ('<div style="margin-top:6px; padding:6px 9px; background:var(--measured-soft); '
                'border-radius:var(--r); font-size:11.5px; color:var(--ink-2); '
                'box-shadow:var(--e1);">%s</div>' % reason) if reason else ''))


RAIL = ('    <aside class="panel" style="width:340px; flex:0 0 auto;">\n'
        '      <div class="strip"><span class="lbl">pipeline</span>'
        '<span style="margin-left:auto; font-size:11.5px; color:var(--ink-3);">'
        'rnaseq spine</span></div>\n'
        '      <div style="padding:16px 16px 6px;">\n'
        + step(1, "Draw", "4 steps &middot; no problems", "", "done")
        + step(2, "Keep", "kept 3 minutes ago",
               '<span class="btn-q">Keep</span>', "now",
               reason="You have changed it since you kept it. Keep again to gate the "
                      "new version.")
        + step(3, "Gate", "lint passed &middot; preview not run",
               '<span class="btn-q">Lint</span><span class="btn-q">Preview</span>', "now")
        + step(4, "Run", "nothing sent yet",
               '<span class="btn-off">Send to Wiener</span>', "wait",
               reason="A gate has to pass on the version you kept.", last=True)
        + '      </div>\n'
        '      <div style="margin-top:auto; padding:11px 16px; border-top:1px solid var(--line); '
        'background:var(--surface-2);"><span class="lbl">why a control is off is written '
        'under it, never in a tooltip</span></div>\n'
        '      <div style="padding:9px 16px; border-top:1px solid var(--line); display:flex; '
        'gap:2px;">'
        '<span class="tab on">Review</span><span class="tab">Problems</span>'
        '<span class="tab">Compare</span></div>\n'
        '    </aside>\n')

CANVAS = ('    <section class="panel" style="flex:1 1 auto; min-width:0;">\n'
          '      <div class="strip"><span class="lbl">canvas</span>'
          '<span style="margin-left:auto; font-size:11.5px; color:var(--ink-3);">'
          '4 steps &middot; 3 wires</span></div>\n'
          '      <div style="flex:1 1 auto; background:var(--paper); box-shadow:var(--well); '
          'position:relative; overflow:hidden;">\n'
          '        <svg width="100%" height="100%" viewBox="0 0 900 520">\n'
          '          <defs><marker id="b" viewBox="0 0 10 10" refX="9" refY="5" '
          'markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" '
          'fill="var(--line-2)"></path></marker></defs>\n'
          '          <path d="M198 120 L 300 120" stroke="var(--line-2)" stroke-width="1.5" '
          'fill="none" marker-end="url(#b)"></path>\n'
          '          <path d="M488 120 L 590 120" stroke="var(--line-2)" stroke-width="1.5" '
          'fill="none" marker-end="url(#b)"></path>\n'
          '          <path d="M198 270 L 250 270 L 250 145 L 300 145" stroke="var(--line-2)" '
          'stroke-width="1.5" fill="none" marker-end="url(#b)"></path>\n'
          + node(20, 95, "STAR_GENOMEGENERATE", "tier 1", "var(--line-2)")
          + node(20, 245, "entry &middot; reads", "fastq.reads", "var(--line-2)",
                 fill="var(--surface-2)")
          + node(310, 95, "STAR_ALIGN", "tier 2", "var(--line-2)")
          + node(600, 95, "SAMTOOLS_SORT", "tier 1", "var(--line-2)")
          + '        </svg>\n      </div>\n    </section>\n')

pathlib.Path("Walk.dc.html").write_text(page(
    nav("Builder")
    + '  <div style="flex:1 1 auto; display:flex; gap:14px; padding:16px 20px 20px; '
      'min-height:0;">\n' + CANVAS + RAIL + '  </div>\n'))

print("built:", ", ".join(sorted(p.name for p in pathlib.Path(".").glob("*.dc.html"))))


# ---------------------------------------------------------------- 8. right-click
def item(label, keys='', off=False, tag=''):
    return ('        <div class="mi" style="display:flex; align-items:center; gap:14px; '
            'padding:6px 12px; font-size:12.5px; color:%s;%s">'
            '<span>%s</span>%s<span class="mono" style="margin-left:auto; font-size:11px; '
            'color:var(--ink-3);">%s</span></div>\n'
            % ('var(--ink-3)' if off else 'var(--ink-2)',
               ' cursor:not-allowed;' if off else '', label,
               ('<span class="lbl" style="padding:1px 5px; border:1px solid var(--line-2); '
                'border-radius:var(--r); color:var(--ink-3);">%s</span>' % tag) if tag else '',
               keys))


def rule():
    return ('        <div style="height:1px; margin:5px 0; background:var(--line);"></div>\n')


def menu(title, rows, x, y, w=268):
    return ('      <div style="position:absolute; left:%dpx; top:%dpx; width:%dpx; '
            'background:var(--surface); border:1px solid var(--line-2); '
            'border-radius:var(--r); box-shadow:var(--e3); padding:5px 0; z-index:5;">\n'
            '        <div class="lbl" style="padding:4px 12px 6px;">%s</div>\n%s      </div>\n'
            % (x, y, w, title, rows))


PROCESS_MENU = menu("STAR_ALIGN", (
    item("Show its tasks", "&#9166;")
    + item("Open in console", "C")
    + item("Show in graph", "G")
    + rule()
    + item("Copy process name")
    + item("Copy this row as TSV", "&#8984;C")
    + rule()
    + item("Retry the failed tasks", off=True, tag="W4")
    + item("Cancel this process", off=True, tag="W4")), 300, 210)

TASK_MENU = menu("STAR_ALIGN &middot; sample_07", (
    item("Open in console here", "&#9166;")
    + rule()
    + item("Copy work directory")
    + item("Copy task hash")
    + item("Copy the command line")
    + rule()
    + item("Retry this task", off=True, tag="W4")), 760, 300)

pathlib.Path("Menus.dc.html").write_text(page(
    nav("Runs", [("Board", False), ("This run", True)])
    + runhead("running", "var(--measured)", "7m12s", 3, 5)
    + ('  <div style="flex:1 1 auto; padding:16px 24px 22px; min-height:0; display:flex; '
       'position:relative;">\n'
       '    <section class="panel" style="flex:1 1 auto; min-width:0;">\n'
       + tabs("Overview")
       + ohead()
       + orow("STAR_GENOMEGENERATE", 1, 0, 100, "var(--pea)",
              48, "31.0 / 64 GB", 78, "78%", 60, "4m01s", 39, "1.2G / 31G")
       + orow("STAR_ALIGN", 12, 0, 100, "var(--pea)",
              96, "61.2 / 64 GB", 81, "81%", 100, "6m41s", 91, "31G / 44G",
              retried=1, demo=True)
       + orow("SAMTOOLS_SORT", 12, 0, 100, "var(--pea)",
              14, "8.9 / 64 GB", 40, "40%", 5, "22s", 100, "44G / 38G")
       + orow("SUBREAD_FEATURECOUNTS", 3, 9, 25, "var(--measured)",
              8, "5.1 / 64 GB", 22, "22%", 15, "1m02s", None, None)
       + orow("MULTIQC", None, 0, 0, "var(--pea)", None, None, None, None, None, None, None,
              None, note="not started", dim=True)
       + FOOT % ("right-click a row &middot; Shift+F10 opens the same menu from the keyboard")
       + '    </section>\n' + PROCESS_MENU + TASK_MENU + '  </div>\n')))
print("menus built")
