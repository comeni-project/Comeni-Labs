"""Builds every artboard from ONE colour source: tokens.shared.css.

No hex literal appears below this docstring. If a colour needs changing it changes
in that file, once, and every artboard follows — which is the same guarantee
frontend/src/tokens.css gives the real product.
"""
import pathlib

TOKENS = pathlib.Path("tokens.shared.css").read_text()

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
    body { margin:0; font-family:var(--font-ui); font-size:13px; line-height:1.5;
           color:var(--ink); background:var(--paper); -webkit-font-smoothing:antialiased; }
    a { color:var(--pea); text-decoration:none; } a:hover { color:var(--ink); }
    @keyframes flow { to { stroke-dashoffset:-24; } }
    @keyframes breathe { 0%,100% { opacity:.5; } 50% { opacity:1; } }
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
           color:var(--on-pea); font-size:12.5px; font-weight:600; box-shadow:var(--e1); }
    .btn-q { padding:6px 12px; border-radius:var(--r); border:1px solid var(--line-2);
             color:var(--ink-2); font-size:12.5px; background:var(--surface); }
    .seg { display:flex; border:1px solid var(--line); border-radius:var(--r);
           overflow:hidden; box-shadow:var(--e1); }
    .seg > span { padding:3px 12px; font-size:11.5px; color:var(--ink-2);
                  background:var(--surface); }
    .seg > .on { background:var(--ink); color:var(--paper); font-weight:600; }
  </style>
</helmet>
'''
TAIL = "</x-dc>\n</body>\n</html>\n"

NAV = '''  <nav style="display:flex; align-items:center; gap:28px; padding:0 20px; height:54px;
              background:var(--surface); border-bottom:1px solid var(--line);
              box-shadow:var(--e1); position:relative; z-index:2; flex:0 0 auto;">
    <span style="display:flex; align-items:baseline; gap:8px; font-family:var(--font-display);
                 font-size:21px; letter-spacing:-.015em; color:var(--ink);">
      <i style="width:9px; height:9px; align-self:center; border-radius:50% 50% 50% 0;
                background:var(--pea); transform:rotate(-45deg);"></i>Comeni Labs</span>
    <div style="display:flex; gap:2px; margin-left:8px;">
      <span style="padding:6px 12px; font-size:13px; color:var(--ink-2);">Builder</span>
      <span style="padding:6px 12px; font-size:13px; color:var(--ink-2);">Forge</span>
      <span style="padding:6px 12px; font-size:13px; font-weight:600; color:var(--ink);
                   box-shadow:inset 0 -2px 0 var(--pea);">Runs</span>
    </div>
    <span style="width:1px; height:20px; background:var(--line);"></span>
    <div style="display:flex; gap:2px;">
      <span style="padding:6px 12px; font-size:13px; color:var(--ink-2);">Board</span>
      <span style="padding:6px 12px; font-size:13px; font-weight:600; color:var(--ink);
                   box-shadow:inset 0 -2px 0 var(--pea);">This run</span>
    </div>
    <span style="margin-left:auto; padding:4px 8px; border:1px solid var(--line);
                 border-radius:var(--r); font-size:11.5px; color:var(--ink-3);
                 background:var(--surface); box-shadow:var(--e1);">
      What the words mean <span class="mono">?</span></span>
  </nav>
'''

def page(body):
    return HEAD + '''<div style="display:flex; flex-direction:column; height:900px;
     background:var(--paper); overflow:hidden;">
''' + NAV + body + "</div>\n" + TAIL

def count(label, n, colour):
    return f'''      <div style="display:flex; flex-direction:column; gap:1px;">
        <span class="lbl">{label}</span>
        <span class="mono" style="font-size:15px; color:{colour};">{n}</span></div>
'''

def statcard(label, big, small, pct, colour):
    return f'''        <div class="card" style="padding:11px 14px;">
          <div class="lbl">{label}</div>
          <div class="mono" style="font-size:21px; color:{colour}; line-height:1.3;">{big}<span
               style="font-size:12px; color:var(--ink-3);">{small}</span></div>
          <div class="well" style="margin-top:6px;"><i style="width:{pct}%; background:{colour};"></i></div>
        </div>
'''

STATS = ('''    <div style="padding:0 20px 14px; display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px;">
'''
  + statcard("memory &middot; star_align", "31.8", "/32 GB", 99, "var(--undecided)")
  + statcard("cpu &middot; star_align", "1", "/8 cores", 13, "var(--measured)")
  + statcard("queued", "23", "/134 min", 17, "var(--pea)")
  + statcard("i/o &middot; star_align", "412", " GB read", 100, "var(--ink-3)")
  + "    </div>\n")

def identity(sub):
    return f'''      <div class="card" style="padding:9px 14px; min-width:230px;">
        <div class="mono" style="font-size:15px;">rnaseq-spine &middot; run 4c1e</div>
        <div style="font-size:11.5px; color:var(--ink-3);">{sub}</div></div>
'''

def header(sub, running, done, cached, failed, more="Less", stats=True, procs=""):
    return ('''  <div style="flex:0 0 auto; background:var(--surface-2); border-bottom:1px solid var(--line);
              box-shadow:var(--e1); position:relative; z-index:1;">
    <div style="display:flex; align-items:center; gap:22px; padding:14px 20px;">
''' + identity(sub)
  + count("running", running, "var(--measured)") + count("done", done, "var(--pea)")
  + count("cached", cached, "var(--ink-3)")
  + count("failed", failed, "var(--undecided)" if failed != "0" else "var(--ink-3)")
  + f'''      <div style="margin-left:auto;"><span class="btn-q" style="display:inline-flex;
           align-items:center; gap:6px; box-shadow:var(--e1);">{more}
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round"><polyline points="{"18 15 12 9 6 15" if more=="Less" else "6 9 12 15 18 9"}"></polyline></svg>
      </span></div>
    </div>
''' + (STATS if stats else "") + procs + "  </div>\n")

# ------------------------------------------------------------------ artboards
def console(lines, tab_graph=False, note="3 failures", note_col="var(--undecided)"):
    return f'''    <section class="panel" style="min-width:0;">
      <div class="strip">
        <span class="seg"><span class="{'' if tab_graph else 'on'}">Console</span><span
              class="{'on' if tab_graph else ''}">Graph</span></span>
        <span style="font-size:11.5px; color:{note_col};">{note}</span>
        <span style="margin-left:auto; font-size:11.5px; color:var(--ink-3);">read-only until W4</span>
      </div>
      <div class="mono" style="flex:1 1 auto; padding:14px 18px; font-size:11.5px;
           line-height:1.9; color:var(--ink-2); overflow:hidden;">
{lines}      </div>
    </section>
'''

def ok(t, p, s, d):   return f'''        <div><span style="color:var(--ink-3);">{t}</span>  <span style="color:var(--pea);">&#10003;</span>  {p} <span style="color:var(--ink-3);">({s})</span><span style="float:right; color:var(--ink-3);">{d}</span></div>\n'''
def run_(t, p, s):    return f'''        <div><span style="color:var(--ink-3);">{t}</span>  <span class="breathe" style="color:var(--measured);">&#9679;</span>  {p} <span style="color:var(--ink-3);">({s})</span><span style="float:right; color:var(--ink-3);">running</span></div>\n'''
def bad(t, p, s, e):  return f'''        <div style="background:var(--undecided-soft); border-radius:var(--r); margin:3px -8px; padding:3px 8px; box-shadow:inset 2px 0 0 var(--undecided);"><span style="color:var(--ink-3);">{t}</span>  <span style="color:var(--undecided);">&#10007;</span>  {p} <span style="color:var(--ink-3);">({s})</span><span style="float:right; color:var(--undecided);">{e}</span></div>\n'''
def sub(t):           return f'''        <div style="color:var(--ink-3); padding-left:22px;">{t}</div>\n'''

def wiener(body, calls):
    return f'''    <aside class="panel" style="min-width:0;">
      <div class="strip"><span class="lbl">wiener</span>
        <span style="margin-left:auto; font-size:11.5px; color:var(--ink-3);">
          <span class="mono">{calls}</span> calls this run</span></div>
      <div style="flex:1 1 auto; padding:16px; display:flex; flex-direction:column; gap:14px;">
{body}      </div>
      <div style="padding:12px 16px; border-top:1px solid var(--line); background:var(--surface-2);
                  display:flex; gap:8px; align-items:center;">
        <span style="flex:1 1 auto; padding:7px 10px; border:1px solid var(--line-2);
                     border-radius:var(--r); font-size:13px; color:var(--ink-3);
                     background:var(--paper); box-shadow:var(--well);">Ask about this run&hellip;</span>
        <span class="btn">Ask</span>
      </div>
    </aside>
'''

PROPOSAL = '''        <div style="border:1px solid var(--line); border-radius:var(--r);
             overflow:hidden; box-shadow:var(--e1);">
          <div style="padding:8px 12px; background:var(--measured-soft);
                      border-bottom:1px solid var(--line);">
            <span class="lbl" style="color:var(--measured);">proposed &middot; not applied</span></div>
          <div style="padding:12px; display:flex; flex-direction:column; gap:10px;">
            <div class="mono" style="font-size:11.5px; line-height:1.7; color:var(--ink-2);">
              <div style="color:var(--ink-3);">site.config &middot; withName: STAR_ALIGN</div>
              <div style="color:var(--undecided);">-&nbsp;&nbsp;memory = 32.GB</div>
              <div style="color:var(--pea);">+&nbsp;&nbsp;memory = 64.GB</div></div>
            <p style="margin:0; font-size:11.5px; color:var(--ink-3);">Changes how it runs, never
              the pipeline. <span class="mono">-resume</span> keeps the 203 tasks already done.</p>
            <div style="display:flex; gap:8px;"><span class="btn">Apply and relaunch</span>
              <span class="btn-q">Dismiss</span></div>
          </div>
        </div>
'''

GRID = '''  <div style="flex:1 1 auto; display:grid; grid-template-columns:1fr 360px; gap:14px;
              padding:14px 20px 18px; min-height:0;">
'''

PROCS = '''    <div style="padding:0 20px 16px; display:flex; flex-direction:column; gap:6px;">
''' + "".join(f'''      <div style="display:flex; align-items:center; gap:14px;">
        <span class="mono" style="width:210px; font-size:11.5px; color:{c};">{n}</span>
        <span class="well" style="flex:1 1 auto; height:8px;">{bars}</span>
        <span class="mono" style="width:90px; text-align:right; font-size:11.5px; color:{rc};">{r}</span></div>
''' for n, bars, r, c, rc in [
  ("FASTQC", '<i style="width:100%; background:var(--pea);"></i>', "24 / 24", "var(--ink-2)", "var(--ink-3)"),
  ("TRIMGALORE", '<i style="width:100%; background:var(--pea);"></i>', "12 / 12", "var(--ink-2)", "var(--ink-3)"),
  ("STAR_ALIGN", '<i style="width:58%; background:var(--pea);"></i><i style="width:17%; background:var(--measured);"></i><i style="width:25%; background:var(--undecided);"></i>', "3 failed", "var(--ink)", "var(--undecided)"),
  ("SAMTOOLS_SORT", '<i style="width:75%; background:var(--pea);"></i>', "9 / 12", "var(--ink-2)", "var(--ink-3)"),
  ("SUBREAD_FEATURECOUNTS", "", "waiting", "var(--ink-3)", "var(--ink-3)"),
]) + "    </div>\n"

# ---- Main: going well, strip collapsed
pathlib.Path("Main.dc.html").write_text(page(
  header("12 samples &middot; local &middot; started 41m ago", "6", "134", "22", "0",
         more="More", stats=False)
  + GRID
  + console(ok("20:31:04","FASTQC","sample_09","4.1s") + ok("20:31:04","TRIMGALORE","sample_09","1m 12s")
            + run_("20:31:22","STAR_ALIGN","sample_10") + run_("20:31:22","STAR_ALIGN","sample_11")
            + ok("20:32:18","STAR_ALIGN","sample_09","6m 02s")
            + run_("20:33:05","SUBREAD_FEATURECOUNTS","sample_09")
            + '        <div style="margin-top:12px; color:var(--ink-3);">&mdash; 162 events &middot; tailing &mdash;</div>\n',
            note="following", note_col="var(--measured)")
  + wiener('''        <div style="display:flex; flex-direction:column; gap:5px;">
          <span class="lbl">on start</span>
          <p style="margin:0; font-size:13px; color:var(--ink-2);">Twelve samples through the
            RNA-seq spine, local executor. Nothing has failed. I will speak when a failure is one
            I have not seen in this run.</p></div>
        <div style="border-top:1px solid var(--line); padding-top:14px; display:flex;
             flex-direction:column; gap:5px;"><span class="lbl">watching for</span>
          <div style="font-size:11.5px; color:var(--ink-3); line-height:1.9;">
            &middot; a failure signature not seen before<br>&middot; the run ending<br>
            &middot; a heartbeat, every 4 hours</div></div>
''', 1)
  + "  </div>\n"))

# ---- Failure: strip expanded, console
pathlib.Path("Failure.dc.html").write_text(page(
  header("12 samples &middot; local &middot; 2h 14m", "2", "203", "22", "3", procs=PROCS)
  + GRID
  + console(ok("22:14:31","STAR_ALIGN","sample_07","7m 41s")
            + bad("22:15:02","STAR_ALIGN","sample_10","exit 137")
            + sub("31.8 GB of 32 &middot; 8 cpus &middot; attempt 1 of 3 &middot; killed at 6m 12s")
            + bad("22:21:44","STAR_ALIGN","sample_10","exit 137")
            + run_("22:21:45","SAMTOOLS_SORT","sample_08")
            + '        <div style="margin-top:12px; color:var(--ink-3);">&mdash; 418 events &mdash;</div>\n')
  + wiener('''        <div style="display:flex; flex-direction:column; gap:6px;">
          <span class="lbl">new failure &middot; star_align &middot; 137</span>
          <p style="margin:0; font-size:13px; color:var(--ink);">It peaked at 31.8 of 32&nbsp;GB
            before the kernel took it &mdash; that is the ceiling, not the genome. The two other
            137s this run are the same signature.</p>
          <p style="margin:0; font-size:13px; color:var(--ink-2);">Nextflow will retry twice more
            at the same size, so all three will fail the same way.</p></div>
''' + PROPOSAL + '''        <p style="margin:0; font-size:11.5px; color:var(--ink-3);">Nothing is applied
          without you. Wiener proposes; a named person approves.</p>
''', 2)
  + "  </div>\n"))
print("Main, Failure rebuilt in Depth")

# ---- Graph: same dashboard, graph view, no per-process bars (the graph is those)
GRAPH = '''    <section class="panel" style="min-width:0;">
      <div class="strip">
        <span class="seg"><span>Console</span><span class="on">Graph</span></span>
        <span style="display:flex; align-items:center; gap:14px; font-size:11.5px; color:var(--ink-3);">
          <span style="display:flex; align-items:center; gap:5px;"><i style="width:8px; height:8px;
            border-radius:2px; background:var(--pea); box-shadow:var(--e1);"></i>done</span>
          <span style="display:flex; align-items:center; gap:5px;"><i style="width:8px; height:8px;
            border-radius:2px; background:var(--measured); box-shadow:var(--e1);"></i>running</span>
          <span style="display:flex; align-items:center; gap:5px;"><i style="width:8px; height:8px;
            border-radius:2px; background:var(--undecided); box-shadow:var(--e1);"></i>failed</span>
        </span>
        <span style="margin-left:auto; font-size:11.5px; color:var(--ink-3);">
          the builder&rsquo;s own layout, coloured</span>
      </div>
      <div style="flex:1 1 auto; padding:14px 18px; overflow:hidden;
                  background:var(--paper); box-shadow:var(--well);">
        <svg viewBox="0 0 1000 600" style="width:100%; height:100%;" fill="none">
          <defs><filter id="lift" x="-40%" y="-40%" width="180%" height="180%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="var(--ink)" flood-opacity=".16"/>
          </filter></defs>
          <g stroke-width="1.5" stroke="var(--line-2)">
            <path d="M155 58 L155 100"></path>
            <path d="M155 58 L155 80 L395 80 L395 100"></path>
            <path d="M700 58 L700 196 L490 196 L490 226"></path>
            <path d="M395 400 L395 470"></path></g>
          <g stroke-width="2.5" stroke="var(--measured)" class="live">
            <path d="M395 156 L395 226"></path><path d="M395 282 L395 342"></path></g>
          <g filter="url(#lift)">
            <rect x="80" y="26" width="150" height="32" rx="16" fill="var(--surface)" stroke="var(--line-2)"></rect>
            <rect x="625" y="26" width="150" height="32" rx="16" fill="var(--surface)" stroke="var(--line-2)"></rect>
            <rect x="60" y="100" width="190" height="56" rx="3" fill="var(--surface)" stroke="var(--pea)" stroke-width="2"></rect>
            <rect x="300" y="100" width="190" height="56" rx="3" fill="var(--surface)" stroke="var(--pea)" stroke-width="2"></rect>
            <rect x="294" y="220" width="202" height="68" rx="3" fill="none" stroke="var(--undecided)" stroke-width="1" opacity=".4"></rect>
            <rect x="300" y="226" width="190" height="56" rx="3" fill="var(--undecided-soft)" stroke="var(--undecided)" stroke-width="2"></rect>
            <rect x="300" y="342" width="190" height="58" rx="3" fill="var(--surface)" stroke="var(--measured)" stroke-width="2"></rect>
            <rect x="280" y="470" width="230" height="56" rx="3" fill="var(--surface)" stroke="var(--line-2)" stroke-dasharray="4 4"></rect>
          </g>
          <g font-family="var(--font-data)" font-size="11.5" text-anchor="middle">
            <text x="155" y="47" fill="var(--ink-3)">fastq.reads</text>
            <text x="700" y="47" fill="var(--ink-3)">genome.fasta</text>
            <text x="155" y="126" fill="var(--ink)">FASTQC</text>
            <text x="155" y="144" fill="var(--pea)" font-size="10">24 / 24</text>
            <text x="395" y="126" fill="var(--ink)">TRIMGALORE</text>
            <text x="395" y="144" fill="var(--pea)" font-size="10">12 / 12</text>
            <text x="395" y="250" fill="var(--ink)">STAR_ALIGN</text>
            <text x="395" y="268" fill="var(--undecided)" font-size="10">7 / 12 &middot; 3 failed &middot; attempt 2</text>
            <text x="395" y="370" fill="var(--ink)">SAMTOOLS_SORT</text>
            <text x="395" y="388" fill="var(--measured)" font-size="10">9 / 12 &middot; 2 running</text>
            <text x="395" y="496" fill="var(--ink-3)">SUBREAD_FEATURECOUNTS</text>
            <text x="395" y="514" fill="var(--ink-3)" font-size="10">waiting</text>
            <text x="545" y="316" fill="var(--ink-3)" font-size="10" text-anchor="start">active &mdash; not a rate</text>
          </g>
        </svg>
      </div>
    </section>
'''
pathlib.Path("Graph.dc.html").write_text(page(
  header("12 samples &middot; local &middot; 2h 14m", "2", "203", "22", "3")
  + GRID + GRAPH
  + wiener('''        <div style="display:flex; flex-direction:column; gap:6px;">
          <span class="lbl">star_align &middot; selected</span>
          <div class="mono" style="font-size:11.5px; color:var(--ink-2); line-height:1.95;">
            <div>memory&nbsp;&nbsp; 32 GB<span style="float:right; color:var(--undecided);">peak 31.8 GB</span></div>
            <div>cpus&nbsp;&nbsp;&nbsp;&nbsp; 8<span style="float:right; color:var(--measured);">104% &middot; 1 core</span></div>
            <div>realtime&nbsp;&mdash;<span style="float:right; color:var(--ink);">6m 41s worst</span></div>
            <div>read&nbsp;&nbsp;&nbsp;&nbsp; &mdash;<span style="float:right; color:var(--ink);">412 GB</span></div>
          </div>
          <p style="margin:0; font-size:11.5px; color:var(--ink-3);">Twelve tasks, aggregated. The
            worst is shown rather than the mean &mdash; the maximum is what kills a run and the
            mean is what hides it.</p></div>
''' + PROPOSAL, 2)
  + "  </div>\n"))

# ---- Board
def brow(name, samples, phase, colour, bars, elapsed, when):
    return f'''        <div style="display:grid; grid-template-columns:280px 110px 1fr 140px 120px;
             align-items:center; gap:20px; padding:12px 18px; border-bottom:1px solid var(--line);">
          <div><div class="mono" style="font-size:13px;">{name}</div>
            <div style="font-size:11.5px; color:var(--ink-3);">{samples}</div></div>
          <span style="justify-self:start; padding:2px 9px; border-radius:var(--r); font-size:11.5px;
                font-family:var(--font-data); color:{colour}; border:1px solid {colour};
                background:var(--surface); box-shadow:var(--e1);">{phase}</span>
          <span class="well" style="height:8px;">{bars}</span>
          <span class="mono" style="font-size:11.5px; color:var(--ink-3);">{elapsed}</span>
          <span style="font-size:11.5px; color:var(--ink-3); text-align:right;">{when}</span>
        </div>
'''
P = '<i style="width:100%; background:var(--pea);"></i>'
pathlib.Path("Board.dc.html").write_text(page('''  <div style="flex:1 1 auto; display:flex; flex-direction:column; min-height:0; padding:22px 30px 26px;">
    <div style="display:flex; align-items:baseline; gap:14px;">
      <h1 style="margin:0; font-family:var(--font-display); font-size:26px; font-weight:400;
                 letter-spacing:-.01em;">Runs</h1>
      <span style="font-size:13px; color:var(--ink-3);">one row per run &mdash; a gate is not a run,
        and none of these is one</span>
      <span class="btn" style="margin-left:auto; padding:7px 14px; font-size:13px;">Submit a run</span>
    </div>
    <div style="display:flex; gap:8px; margin:16px 0 14px;">
      <span style="padding:4px 11px; border-radius:var(--r); background:var(--ink); color:var(--paper);
            font-size:11.5px; box-shadow:var(--e1);">All 24</span>
      <span class="btn-q" style="padding:4px 11px; font-size:11.5px;">Running 2</span>
      <span class="btn-q" style="padding:4px 11px; font-size:11.5px; color:var(--undecided);">Failed 3</span>
      <span class="btn-q" style="padding:4px 11px; font-size:11.5px;">Succeeded 19</span>
    </div>
    <div class="panel" style="flex:1 1 auto;">
      <div style="display:grid; grid-template-columns:280px 110px 1fr 140px 120px; gap:20px;
           padding:9px 18px; background:var(--surface-2); border-bottom:1px solid var(--line);">
        <span class="lbl">pipeline &middot; run</span><span class="lbl">phase</span>
        <span class="lbl">tasks</span><span class="lbl">elapsed</span>
        <span class="lbl" style="text-align:right;">started</span></div>
'''
  + brow("rnaseq-spine · 4c1e", "12 samples &middot; local", "running", "var(--measured)",
         '<i style="width:66%; background:var(--pea);"></i><i style="width:9%; background:var(--measured);"></i><i style="width:25%; background:var(--undecided);"></i>', "2h 14m", "today 20:01")
  + brow("rnaseq-spine · 9a07", "4 samples &middot; local", "running", "var(--measured)",
         '<i style="width:41%; background:var(--pea);"></i><i style="width:12%; background:var(--measured);"></i>', "38m", "today 21:37")
  + brow("rnaseq-spine · 77b2", "12 samples &middot; local", "failed", "var(--undecided)",
         '<i style="width:82%; background:var(--pea);"></i><i style="width:18%; background:var(--undecided);"></i>', "6h 02m", "yesterday")
  + brow("rnaseq-spine · 1de4", "12 samples &middot; local", "succeeded", "var(--pea)", P, "5h 44m", "yesterday")
  + brow("rnaseq-spine · c380", "8 samples &middot; local", "succeeded", "var(--pea)", P, "3h 51m", "20 Aug")
  + brow("rnaseq-spine · 2f1a", "12 samples &middot; local", "cancelled", "var(--ink-3)",
         '<i style="width:34%; background:var(--pea);"></i>', "1h 09m", "19 Aug")
  + '''      <div style="flex:1 1 auto;"></div>
      <div style="padding:10px 18px; border-top:1px solid var(--line); background:var(--surface-2);
           font-size:11.5px; color:var(--ink-3);">24 runs &middot; the record is kept forever;
        the live tail is not</div>
    </div>
  </div>
'''))
print("Graph, Board rebuilt in Depth")
