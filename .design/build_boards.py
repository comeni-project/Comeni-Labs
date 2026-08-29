# Every builder board is composed from the SAME shell and the SAME canvas.
# Continuity is not remembered here, it is structural: change a node once.
import pathlib

HEAD = pathlib.Path('_bhead.html').read_text()

def page(body, h=880):
    return f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
{HEAD}
</helmet>

<div style="position:relative; min-height:{h}px; overflow:hidden; background:#080B0D;">
  <svg class="layer" viewBox="0 0 1400 {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <g class="breathe" fill="none"><g class="slowA" stroke="#6CB7FF" stroke-width="1">
      <circle cx="120" cy="880" r="580" opacity=".07"/>
      <circle cx="120" cy="880" r="860" opacity=".045"/>
      <circle cx="120" cy="880" r="1200" opacity=".028"/>
    </g><path d="M-60 700 Q 640 920 1470 540" stroke="#10AA91" stroke-width="1" opacity=".022"/></g>
  </svg>
  <div class="layer vig"></div>
{body}
</div>
</x-dc>
</body>
</html>
'''

NAV = '''      <div class="shell">
        <div style="display:flex; align-items:baseline; gap:26px;">
          <span style="font-size:14px; font-weight:700; letter-spacing:-.02em;">Comeni</span>
          <span style="font-size:12.5px;">Builder</span>
          <span style="font-size:12.5px; color:#67757A;">Runs</span>
          <span style="font-size:12.5px; color:#67757A;">Registry</span>
        </div>
        <span class="m" style="font-size:11px; color:#67757A;">Ferreira lab</span>
      </div>
'''

def title_row(view='canvas', name='rnaseq-counts', status=None, run=True):
    on  = 'background:#122029; color:#6CB7FF;'
    off = 'color:#67757A; cursor:pointer;'
    st = status if status is not None else (
        'saved 4s ago &middot; <span style="color:#10AA91;">valid</span> &middot; '
        '<span style="color:#E3674E;">2 values need you</span>')
    runbtn = ('<span class="lift" style="font-size:13.5px; font-weight:600; color:#080B0D; '
              'background:#6CB7FF; padding:9px 26px; cursor:pointer;">Run</span>') if run else (
              '<span style="font-size:13.5px; font-weight:600; color:#2A3438; '
              'border:1px solid #16202400; background:#0D1316; padding:9px 26px;">Run</span>')
    return f'''      <div style="display:flex; align-items:center; justify-content:space-between; padding:20px 0 16px;">
        <div style="display:flex; align-items:baseline; gap:18px;">
          <span style="font-size:26px; font-weight:600; letter-spacing:-.03em;">{name}</span>
          <span class="m" style="font-size:10.5px; color:#455257;">{st}</span>
        </div>
        <div style="display:flex; align-items:center; gap:14px;">
          <div style="display:flex; border:1px solid #1E282C;">
            <span class="m{'' if view=='canvas' else ' lift'}" style="font-size:10px; letter-spacing:.09em;
                  text-transform:uppercase; padding:7px 15px; {on if view=='canvas' else off}">Canvas</span>
            <span class="m{'' if view=='artifact' else ' lift'}" style="font-size:10px; letter-spacing:.09em;
                  text-transform:uppercase; padding:7px 15px; {on if view=='artifact' else off}">Artifact</span>
          </div>
          {runbtn}
        </div>
      </div>
'''

def header(view='canvas', name='rnaseq-counts', status=None, run=True):
    return ('    <div style="padding:22px 30px 0;">\n' + NAV
            + title_row(view, name, status, run) + '    </div>\n')

# ── the canvas, identical on every board that shows one ────────────────────
# ── one symbol, one geometry, derived once ────────────────────────────────
NODE_W, NODE_H, SRC_W, SRC_H = 172, 112, 120, 80
GAP = 52
X = {'src': 22, 'trim': 194, 'star': 418, 'sort': 642, 'fc': 866}
Y_MAIN, Y_FASTQC = 150, 320
CONN   = NODE_H / 2            # every symbol connects on its spine
CONN2  = NODE_H / 2 + 22       # a secondary input sits below it
SRC_CONN = SRC_H / 2

def nx_in(x):        return x - 3.5
def nx_out(x):       return x + NODE_W + 3.5 - 7
def spine(y):        return y + CONN
def spine2(y):       return y + CONN2

Y_SRC   = Y_MAIN + CONN - SRC_CONN            # so a source lines up with the chain
Y_REF   = Y_FASTQC + 118

P = {
  'reads_out': (X['src'] + SRC_W, Y_SRC + SRC_CONN),
  'ref_out':   (X['src'] + SRC_W, Y_REF + SRC_CONN),
  'trim_in':   (X['trim'], spine(Y_MAIN)),        'trim_out': (X['trim'] + NODE_W, spine(Y_MAIN)),
  'star_in':   (X['star'], spine(Y_MAIN)),        'star_ref': (X['star'], spine2(Y_MAIN)),
  'star_out':  (X['star'] + NODE_W, spine(Y_MAIN)),
  'sort_in':   (X['sort'], spine(Y_MAIN)),        'sort_out': (X['sort'] + NODE_W, spine(Y_MAIN)),
  'fc_in':     (X['fc'],   spine(Y_MAIN)),        'fc_out':   (X['fc'] + NODE_W, spine(Y_MAIN)),
  'qc_in':     (X['trim'], spine(Y_FASTQC)),      'qc_out':   (X['trim'] + NODE_W, spine(Y_FASTQC)),
}

def wire(a, b, bend=None):
    """Orthogonal routing. Right angles read engineered; beziers read playful."""
    (x1, y1), (x2, y2) = P[a], P[b]
    if y1 == y2:
        return f'<path d="M{x1} {y1} H{x2}"/>'
    mx = bend if bend is not None else (x1 + x2) / 2
    return f'<path d="M{x1} {y1} H{mx} V{y2} H{x2}"/>'

FIELD = pathlib.Path('_field.html').read_text()

def field_layers(kind='arcs', drag=False):
    """The canvas is a window onto the field, not a surface with wallpaper.
    A grid exists only while something is being moved — Galaxy's idea, scoped to the gesture."""
    grid = """        <div style="position:absolute; inset:0; display:__GRID__;
                    background-image:
                      linear-gradient(rgba(108,183,255,.115) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(108,183,255,.115) 1px, transparent 1px),
                      linear-gradient(rgba(108,183,255,.060) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(108,183,255,.060) 1px, transparent 1px),
                      linear-gradient(rgba(108,183,255,.028) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(108,183,255,.028) 1px, transparent 1px);
                    background-size:80px 80px, 80px 80px, 40px 40px, 40px 40px, 8px 8px, 8px 8px;
                    background-position:0 0;"></div>
"""
    corners = """        <div style="position:absolute; left:16px; top:16px; width:16px; height:16px;
                    border-left:1px solid #28353C; border-top:1px solid #28353C;"></div>
        <div style="position:absolute; right:16px; top:16px; width:16px; height:16px;
                    border-right:1px solid #28353C; border-top:1px solid #28353C;"></div>
        <div style="position:absolute; left:16px; bottom:16px; width:16px; height:16px;
                    border-left:1px solid #28353C; border-bottom:1px solid #28353C;"></div>
        <div style="position:absolute; right:16px; bottom:16px; width:16px; height:16px;
                    border-right:1px solid #28353C; border-bottom:1px solid #28353C;"></div>
"""
    if kind == 'live':                      # tweak-driven on the main board
        return FIELD + grid.replace('__GRID__', '{{ g.grid }}') + corners
    return FIELD + (grid.replace('__GRID__', 'block') if drag else '') + corners

def node(x, y, nm, role, rows, foot, tier='ok', sel=False, plus=False, extra=''):
    cls = 'node settle' + (' sel' if sel else '') + ('' if tier == 'ok' else f' {tier}')
    pr = ''.join(
        f'            <div class="pr"><span style="color:{"#4A5C64" if d=="in" else "#3E5058"};">'
        f'{"&#9666;" if d=="in" else "&#9656;"}</span>'
        f'<span style="color:{"#7E8F95" if d=="in" else "#6B7C82"};">{t}</span></div>\n'
        for d, t in rows)
    ports = (f'          <div class="port{" on" if sel else ""}" style="left:-4px; top:{CONN-3.5}px;"></div>\n'
             f'          <div class="port{" on" if sel else ""}" style="right:-4px; top:{CONN-3.5}px;"></div>\n')
    if any(d == 'in' for d, _ in rows[1:]) and nm.endswith('ALIGN'):
        ports += f'          <div class="port{" on" if sel else ""}" style="left:-4px; top:{CONN2-3.5}px;"></div>\n'
    return (f'        <div class="{cls}" style="left:{x}px; top:{y}px;">\n{ports}'
            f'          <div class="hd"><span class="m" style="font-size:11px; font-weight:500;">{nm}</span>{extra}</div>\n'
            f'          <div class="rows">\n{pr}          </div>\n'
            f'          <div class="ft">{foot}</div>\n'
            f'          {"<div class=\'plus\' style=\'right:-27px; top:" + str(CONN-9) + "px;\'>+</div>" if plus else ""}\n'
            f'        </div>\n')

ELLIPSIS = '\n            <span class="m" style="font-size:9px; color:#455257; margin-left:auto; cursor:pointer;">&#8943;</span>'

def canvas(sel='star', swap=False, empty=False, overlay='', dim=False, field='arcs', drag=False):
    if empty:
        inner = field_layers(field, drag) + """        <div style="position:absolute; inset:0; display:flex; align-items:center; justify-content:center;">
          <div style="text-align:center;">
            <div class="m" style="font-size:11px; color:#2A3438; letter-spacing:.14em;
                        text-transform:uppercase;">Nothing drawn yet</div>
            <div style="font-size:12.5px; color:#3A474C; padding-top:9px;">
              Answer on the right, or <span style="color:#455257;">+ Add step</span> to place one yourself</div>
          </div>
        </div>
"""
    else:
        guides = field_layers(field, drag)
        paths = ''.join('            ' + p + '\n' for p in [
            wire('reads_out', 'trim_in'),
            wire('reads_out', 'qc_in', bend=X['trim'] - 26),
            wire('trim_out', 'star_in'),
            wire('ref_out', 'star_ref', bend=X['star'] - 26),
            wire('star_out', 'sort_in'),
            wire('sort_out', 'fc_in'),
        ])
        wires = ('        <svg style="position:absolute; inset:0;" width="100%" height="100%" aria-hidden="true">\n'
                 '          <g fill="none" stroke="#2C3E45" stroke-width="1.5" stroke-linejoin="miter">\n'
                 + paths + '          </g>\n        </svg>\n')

        src = f"""        <div class="src settle" style="left:{X['src']}px; top:{Y_SRC}px;">
          <div class="port" style="right:-4px; top:{SRC_CONN-3.5}px;"></div>
          <div class="lb" style="color:#6CB7FF; font-size:8px;">Input</div>
          <div class="m" style="font-size:11px; padding-top:4px;">reads</div>
          <div class="m" style="font-size:8.5px; color:#5D6C71; padding-top:3px;">fastq.reads[paired]</div>
        </div>
        <div class="src settle" style="left:{X['src']}px; top:{Y_REF}px; animation-delay:30ms;">
          <div class="port" style="right:-4px; top:{SRC_CONN-3.5}px;"></div>
          <div class="lb" style="color:#6CB7FF; font-size:8px;">Input</div>
          <div class="m" style="font-size:11px; padding-top:4px;">reference</div>
          <div class="m" style="font-size:8.5px; color:#5D6C71; padding-top:3px;">genome.index.star</div>
        </div>
"""
        if swap:
            n1 = node(X['trim'], Y_MAIN, '<span style="text-decoration:line-through; text-decoration-color:#E3674E;">TRIMGALORE</span>',
                      '', [('in','fastq.reads'),('out','fastq.reads[trimmed]')], 'removed by the swap')
            n3 = node(X['star'], Y_MAIN, 'HISAT2_ALIGN', '',
                      [('in','fastq.reads'),('in','genome.index.hisat2'),('out','alignment.bam')],
                      '12 settled &middot; 2 re-resolved', tier='meas', sel=True,
                      extra='\n            <span class="m" style="font-size:8.5px; color:#C1B508; margin-left:auto;">NEW</span>')
        else:
            n1 = node(X['trim'], Y_MAIN, 'TRIMGALORE', '',
                      [('in','fastq.reads'),('out','fastq.reads[trimmed]')], '9 settled')
            n3 = node(X['star'], Y_MAIN, 'STAR_ALIGN', '',
                      [('in','fastq.reads[trimmed]'),('in','genome.index.star'),('out','alignment.bam')],
                      '14 settled', tier='meas', sel=(sel=='star'), extra=ELLIPSIS)
        nodes = (n1
            + node(X['trim'], Y_FASTQC, 'FASTQC', '',
                   [('in','fastq.reads'),('out','qc.report')], '4 settled', plus=True)
            + n3
            + node(X['sort'], Y_MAIN, 'SAMTOOLS_SORT', '',
                   [('in','alignment.bam'),('out','alignment.bam[sorted]')], '6 settled')
            + node(X['fc'], Y_MAIN, 'FEATURECOUNTS', '',
                   [('in','alignment.bam[sorted]'),('out','counts.matrix')],
                   '<span style="color:#E3674E;">2 need you</span> &middot; 11 settled',
                   tier='open', sel=(sel=='fc'), extra=ELLIPSIS, plus=True))
        snap = ''
        if field == 'live':
            gy, gx = spine(Y_MAIN), X['sort'] + NODE_W / 2
            snap = (f'        <div style="position:absolute; left:0; right:0; top:{gy}px; height:1px;'
                    f' border-top:1px dashed rgba(108,183,255,.45); display:{{{{ g.lift }}}};"></div>\n'
                    f'        <div style="position:absolute; top:0; bottom:0; left:{gx}px; width:1px;'
                    f' border-left:1px dashed rgba(108,183,255,.45); display:{{{{ g.lift }}}};"></div>\n'
                    f'        <div class="m" style="position:absolute; left:{gx+8}px; top:{gy-22}px;'
                    f' font-size:9px; color:#6CB7FF; display:{{{{ g.lift }}}};">aligned &middot; spine, column 3</div>\n')
        inner = guides + wires + src + nodes + snap

    mini = '' if empty else """        <div style="position:absolute; right:18px; bottom:18px; width:146px; height:58px;
                    border:1px solid #1B262B; background:rgba(8,13,16,.82);">
          <div style="position:absolute; left:8px; top:18px; width:11px; height:5px; border:1px solid #33454C;"></div>
          <div style="position:absolute; left:8px; top:38px; width:11px; height:5px; border:1px solid #33454C;"></div>
          <div style="position:absolute; left:31px; top:18px; width:15px; height:5px; border:1px solid #3E525A;"></div>
          <div style="position:absolute; left:31px; top:32px; width:15px; height:5px; border:1px solid #3E525A;"></div>
          <div style="position:absolute; left:58px; top:18px; width:15px; height:5px; border:1px solid #6CB7FF;"></div>
          <div style="position:absolute; left:85px; top:18px; width:15px; height:5px; border:1px solid #3E525A;"></div>
          <div style="position:absolute; left:112px; top:18px; width:15px; height:5px; border:1px solid #E3674E;"></div>
        </div>
"""
    ctrls = """        <div style="position:absolute; left:22px; bottom:18px; display:flex; gap:8px;">
          <span class="m lift" style="font-size:10px; color:#67757A; border:1px solid #1E282C;
                padding:6px 11px; cursor:pointer;">Fit</span>
          <span class="m lift" style="font-size:10px; color:#6CB7FF; border:1px solid #1E3A4E;
                padding:6px 11px; cursor:pointer;">+ Add step</span>
        </div>
"""
    d = ' opacity:.34;' if dim else ''
    return (f'      <div style="position:relative; overflow:hidden; border-top:1px solid #141C20;">\n'
            f'        <div style="position:absolute; inset:0;{d}">\n{inner}{mini}{ctrls}        </div>\n'
            f'{overlay}      </div>\n')

def rail(tab, body):
    a_on = tab == 'assistant'
    return f'''      <div style="border-left:1px solid #141C20; border-top:1px solid #141C20;
                  display:flex; flex-direction:column; min-height:0;">
        <div style="display:flex; gap:2px; padding:14px 16px 0;">
          <span class="m{'' if a_on else ' lift'}" style="font-size:10px; letter-spacing:.09em;
                text-transform:uppercase; padding:6px 11px;
                {'color:#DFE6E6; box-shadow:inset 0 -2px 0 #6CB7FF;' if a_on else 'color:#67757A; cursor:pointer;'}">Assistant</span>
          <span class="m{' lift' if a_on else ''}" style="font-size:10px; letter-spacing:.09em;
                text-transform:uppercase; padding:6px 11px;
                {'color:#67757A; cursor:pointer;' if a_on else 'color:#DFE6E6; box-shadow:inset 0 -2px 0 #6CB7FF;'}">Step</span>
        </div>
        <div style="flex:1; overflow:hidden; padding:20px 18px 0;">
{body}
        </div>
      </div>
'''

def cols(canvas_html, rail_html):
    return ('    <div style="flex:1; display:grid; grid-template-columns:1fr 302px; min-height:0;">\n'
            + canvas_html + rail_html + '    </div>\n')

def shellwrap(inner, h=880):
    return f'  <div style="position:relative; display:flex; flex-direction:column; height:{h}px;">\n{inner}  </div>\n'

print('helpers defined')

# ── rail bodies ────────────────────────────────────────────────────────────
RAIL_STEP = '''          <div class="settle">
            <div class="m" style="font-size:14px; font-weight:500;">STAR_ALIGN</div>
            <div class="m" style="font-size:10px; color:#455257; padding-top:4px;">nf-core/star/align@2.7.11a</div>
          </div>
          <div class="settle" style="animation-delay:40ms; padding-top:20px;">
            <div class="lb" style="padding-bottom:9px;">Why this tool</div>
            <div style="font-size:12.5px; color:#889699; line-height:1.55;">
              Read length 151 bp &mdash; measured, not asserted. Rule R04.</div>
            <div class="lift" style="margin-top:12px; border:1px solid #1E282C; padding:8px 12px;
                        font-size:12px; color:#6CB7FF; cursor:pointer; display:inline-block;">
              Swap for something else</div>
          </div>
          <div class="settle" style="animation-delay:80ms; padding-top:24px;">
            <div class="lb" style="padding-bottom:11px;">Values</div>
            <div style="display:flex; align-items:baseline; gap:9px;">
              <span style="color:#10AA91; font-size:8px;">&#9679;</span>
              <span style="font-size:12.5px; color:#889699;">14 settings, all settled</span></div>
            <div class="m lift" style="font-size:11px; color:#6CB7FF; padding-top:10px; cursor:pointer;">
              open on the node &#8943;</div>
          </div>'''

RAIL_SWAP = '''          <div class="settle">
            <div class="m" style="font-size:12.5px;">STAR_ALIGN <span style="color:#455257;">&rarr;</span>
              <span style="color:#C1B508;">HISAT2_ALIGN</span></div>
            <div style="font-size:12px; color:#889699; padding-top:6px; line-height:1.5;">
              Ranked 2nd of 4. Peaks near 8 GB where STAR wants 38.</div>
          </div>
          <div class="settle" style="animation-delay:40ms; padding-top:22px;">
            <div class="lb" style="color:#C1B508; padding-bottom:13px;">This also changes</div>
            <div style="display:flex; gap:10px; padding-bottom:14px;">
              <span style="color:#E3674E; font-size:8px; padding-top:5px;">&#9679;</span>
              <div><div class="m" style="font-size:11.5px;">TRIMGALORE <span style="color:#E3674E;">removed</span></div>
                <div style="font-size:11.5px; color:#889699; padding-top:4px; line-height:1.45;">
                  Only STAR declares <span class="m" style="font-size:10.5px;">[trimmed]</span>.
                  Nothing else asks for it.</div></div>
            </div>
            <div style="display:flex; gap:10px; padding-bottom:14px;">
              <span style="color:#E3674E; font-size:8px; padding-top:5px;">&#9679;</span>
              <div><div class="m" style="font-size:11.5px;">--sjdbOverhang <span style="color:#E3674E;">dropped</span></div>
                <div style="font-size:11.5px; color:#889699; padding-top:4px; line-height:1.45;">
                  HISAT2 has no route for it.</div></div>
            </div>
            <div style="display:flex; gap:10px; padding-bottom:14px;">
              <span style="color:#C1B508; font-size:8px; padding-top:5px;">&#9679;</span>
              <div><div class="m" style="font-size:11.5px;">2 settings re-resolve</div>
                <div style="font-size:11.5px; color:#889699; padding-top:4px; line-height:1.45;">
                  <span class="m" style="font-size:10.5px;">--rna-strandness</span> and
                  <span class="m" style="font-size:10.5px;">--max-intronlen</span>, both tier 2.</div></div>
            </div>
            <div style="display:flex; gap:10px;">
              <span style="color:#10AA91; font-size:8px; padding-top:5px;">&#9679;</span>
              <div><div class="m" style="font-size:11.5px;">SAMTOOLS_SORT unaffected</div>
                <div style="font-size:11.5px; color:#889699; padding-top:4px; line-height:1.45;">
                  Still fed <span class="m" style="font-size:10.5px;">alignment.bam</span>.</div></div>
            </div>
          </div>
          <div class="settle" style="animation-delay:120ms; display:flex; gap:9px; padding-top:24px;">
            <span class="lift" style="font-size:12.5px; font-weight:600; color:#080B0D; background:#6CB7FF;
                  padding:9px 18px; cursor:pointer;">Apply all four</span>
            <span class="lift" style="font-size:12.5px; color:#889699; border:1px solid #1E282C;
                  padding:9px 16px; cursor:pointer;">Cancel</span>
          </div>'''

RAIL_ASSISTANT = '''          <div style="display:flex; flex-direction:column; gap:16px;">
            <div class="settle" style="font-size:13.5px; color:#889699; line-height:1.6;">
              What do you want to make?</div>
            <div class="settle" style="animation-delay:60ms; align-self:flex-end; max-width:90%;
                        background:#122029; padding:11px 13px; font-size:13px; line-height:1.5;">
              gene counts from paired-end RNA-seq, mouse liver, 24 samples</div>
            <div class="settle" style="animation-delay:140ms;">
              <div style="font-size:13px; color:#889699; line-height:1.55; padding-bottom:12px;">
                Here is the goal I read. Correct anything before it builds.</div>
              <div style="border:1px solid #22333B; background:#0A1014;">
                <div style="padding:10px 13px; border-bottom:1px solid #162025; display:flex;
                            justify-content:space-between; align-items:baseline;">
                  <span class="lb">Goal</span>
                  <span class="m" style="font-size:9.5px; color:#455257;">editable</span></div>
                <div style="padding:12px 13px; display:flex; flex-direction:column; gap:10px;">
                  <div style="display:grid; grid-template-columns:60px 1fr; gap:9px; align-items:baseline;">
                    <span class="lb" style="letter-spacing:.1em;">Have</span>
                    <span class="m" style="font-size:11px; color:#6CB7FF;">fastq.reads[paired]</span></div>
                  <div style="display:grid; grid-template-columns:60px 1fr; gap:9px; align-items:baseline;">
                    <span class="lb" style="letter-spacing:.1em;">Want</span>
                    <span class="m" style="font-size:11px; color:#6CB7FF;">counts.matrix</span></div>
                  <div style="display:grid; grid-template-columns:60px 1fr; gap:9px; align-items:baseline;">
                    <span class="lb" style="letter-spacing:.1em;">Organism</span>
                    <span class="m" style="font-size:11px;">mus_musculus</span></div>
                  <div style="display:grid; grid-template-columns:60px 1fr; gap:9px; align-items:start;">
                    <span class="lb" style="letter-spacing:.1em; padding-top:2px;">Unsure</span>
                    <div><span class="m" style="font-size:11px; color:#C1B508;">strandedness</span>
                      <div style="font-size:11.5px; color:#889699; padding-top:4px; line-height:1.45;">
                        You did not say, and I will not invent it.</div></div></div>
                </div>
                <div style="padding:11px 13px; border-top:1px solid #162025; display:flex; gap:9px;">
                  <span class="lift" style="font-size:12.5px; font-weight:600; color:#080B0D;
                        background:#6CB7FF; padding:7px 16px; cursor:pointer;">Build this</span>
                  <span class="lift" style="font-size:12.5px; color:#889699; border:1px solid #1E282C;
                        padding:7px 14px; cursor:pointer;">Edit</span></div>
              </div>
            </div>
          </div>'''
print('rails defined')

# ── overlays ───────────────────────────────────────────────────────────────
PORT_POPOVER = '''        <div class="pop" style="position:absolute; left:600px; top:150px; width:372px;
                    background:#0A1014; border:1px solid #22333B; box-shadow:0 20px 50px -24px #000;">
          <div style="padding:13px 15px 11px; border-bottom:1px solid #162025;">
            <div style="display:flex; align-items:baseline; justify-content:space-between;">
              <span class="m" style="font-size:11px;">Accepts <span style="color:#6CB7FF;">alignment.bam</span></span>
              <span class="m" style="font-size:10px; color:#455257;">6 of 1,604</span></div>
            <div style="margin-top:10px; border:1px solid #1E282C; background:#080D10;
                        padding:7px 10px; display:flex; align-items:center; gap:8px;">
              <span class="m" style="font-size:11px; color:#6CB7FF;">&#8981;</span>
              <span class="m" style="font-size:11px;">sort</span>
              <span class="cur m" style="font-size:11px; color:#6CB7FF;">&#9646;</span></div>
          </div>
          <div class="settle lift" style="padding:11px 15px; border-bottom:1px solid #121A1D;
                      background:#0E1418; cursor:pointer;">
            <div style="display:flex; align-items:baseline; justify-content:space-between;">
              <span class="m" style="font-size:12px; font-weight:500;">SAMTOOLS_SORT</span>
              <span class="m" style="font-size:9px; color:#10AA91; letter-spacing:.1em;">RANKED FIRST</span></div>
            <div class="m" style="font-size:9.5px; color:#67757A; padding-top:4px;">
              alignment.bam &rarr; alignment.bam[coordinate_sorted]</div>
            <div style="font-size:11.5px; color:#889699; padding-top:6px; line-height:1.45;">
              The only producer of the state FEATURECOUNTS asks for.</div>
          </div>
          <div class="settle lift" style="padding:11px 15px; border-bottom:1px solid #121A1D;
                      animation-delay:30ms; cursor:pointer;">
            <div class="m" style="font-size:12px;">SAMTOOLS_INDEX</div>
            <div class="m" style="font-size:9.5px; color:#67757A; padding-top:4px;">
              alignment.bam &rarr; alignment.bam.bai</div></div>
          <div class="settle lift" style="padding:11px 15px; border-bottom:1px solid #121A1D;
                      animation-delay:60ms; cursor:pointer;">
            <div class="m" style="font-size:12px;">SAMTOOLS_STATS</div>
            <div class="m" style="font-size:9.5px; color:#67757A; padding-top:4px;">
              alignment.bam &rarr; qc.report</div></div>
          <div class="settle lift" style="padding:11px 15px; border-bottom:1px solid #121A1D;
                      animation-delay:90ms; cursor:pointer;">
            <div class="m" style="font-size:12px;">PICARD_MARKDUPLICATES</div>
            <div class="m" style="font-size:9.5px; color:#67757A; padding-top:4px;">
              alignment.bam &rarr; alignment.bam[deduplicated]</div></div>
          <div style="padding:10px 15px; display:flex; align-items:center; justify-content:space-between;">
            <span class="m" style="font-size:10px; color:#455257;">&#8595;&#8593; move &middot; &#8629; add</span>
            <span class="m" style="font-size:10px; color:#6CB7FF; cursor:pointer;">Browse everything &#8984;K</span></div>
        </div>
'''

SETTINGS_POPOVER = """        <div class="pop" style="position:absolute; left:700px; top:270px; width:352px;
                    background:#0A1014; border:1px solid #22333B; box-shadow:0 20px 50px -24px #000;">
          <div style="padding:12px 15px 11px; border-bottom:1px solid #162025;
                      display:flex; align-items:baseline; justify-content:space-between;">
            <span class="m" style="font-size:11.5px; font-weight:500;">FEATURECOUNTS</span>
            <span class="m" style="font-size:10px; color:#455257;">14 settings</span>
          </div>

          <div class="settle" style="padding:12px 15px 4px; background:rgba(227,103,78,.05);
                      border-bottom:1px solid #1A2226;">
            <div class="lb" style="color:#E3674E; padding-bottom:11px;">Needs you &middot; 2</div>
            <div style="padding-bottom:13px;">
              <div class="m" style="font-size:11px; padding-bottom:7px;">strandedness</div>
              <div style="display:flex; gap:5px; flex-wrap:wrap;">
                <span class="m lift" style="font-size:10px; padding:5px 9px; border:1px solid #1E3A4E;
                      background:#101E27; color:#6CB7FF; cursor:pointer;">measure it</span>
                <span class="m lift" style="font-size:10px; padding:5px 9px; border:1px solid #1E282C;
                      color:#889699; cursor:pointer;">unstranded</span>
                <span class="m lift" style="font-size:10px; padding:5px 9px; border:1px solid #1E282C;
                      color:#889699; cursor:pointer;">forward</span>
                <span class="m lift" style="font-size:10px; padding:5px 9px; border:1px solid #1E282C;
                      color:#889699; cursor:pointer;">reverse</span>
              </div>
              <div style="font-size:11px; color:#67757A; padding-top:7px;">no rule matched</div>
            </div>
            <div style="padding-bottom:13px;">
              <div class="m" style="font-size:11px; padding-bottom:7px;">feature_type</div>
              <div style="display:flex; gap:5px;">
                <span class="m lift" style="font-size:10px; padding:5px 9px; border:1px solid #1E282C;
                      color:#889699; cursor:pointer;">exon</span>
                <span class="m lift" style="font-size:10px; padding:5px 9px; border:1px solid #1E282C;
                      color:#889699; cursor:pointer;">gene</span>
                <span class="m lift" style="font-size:10px; padding:5px 9px; border:1px solid #1E282C;
                      color:#889699; cursor:pointer;">transcript</span>
              </div>
              <div style="font-size:11px; color:#67757A; padding-top:7px;">no rule matched</div>
            </div>
          </div>

          <div class="settle" style="animation-delay:40ms; padding:12px 15px;
                      border-bottom:1px solid #1A2226;">
            <div class="lb" style="color:#C1B508; padding-bottom:10px;">Measured &middot; 1</div>
            <div style="display:flex; align-items:baseline; justify-content:space-between;">
              <span class="m" style="font-size:11px; color:#889699;">-T threads</span>
              <span class="m" style="font-size:11px;">4</span></div>
            <div style="font-size:11px; color:#67757A; padding-top:5px; line-height:1.45;">
              from the process label, cpus = 4</div>
          </div>

          <div class="settle lift" style="animation-delay:80ms; padding:11px 15px; cursor:pointer;
                      display:flex; align-items:center; justify-content:space-between;">
            <span style="font-size:12px; color:#889699;">11 settled</span>
            <span class="m" style="font-size:10px; color:#6CB7FF;">show &#9662;</span>
          </div>
        </div>
"""

def scrim(inner):
    return ('  <div class="layer" style="background:rgba(6,9,11,.76); backdrop-filter:blur(2px);"></div>\n'
            + inner)

RUN_SRC = pathlib.Path('_run_sheet.html').read_text()
BROWSE_SRC = pathlib.Path('_browse.html').read_text()


def _slice_div(src, anchor):
    """Take exactly one balanced <div> subtree starting at `anchor`."""
    i = src.index(anchor)
    depth, j = 0, i
    while True:
        o, c = src.find('<div', j), src.find('</div>', j)
        if c == -1:
            break
        if o != -1 and o < c:
            depth += 1
            j = o + 4
        else:
            depth -= 1
            j = c + 6
            if depth == 0:
                return src[i:j]
    return src[i:]

RUN_SHEET = _slice_div(RUN_SRC, '<div class="pop"')
BROWSE = _slice_div(BROWSE_SRC, '<div class="pop"')


ARTIFACT_BODY = '''      <div style="flex:1; overflow:hidden; padding:16px 30px 0; border-top:1px solid #141C20;">
        <div style="display:flex; gap:7px; padding-bottom:16px;">
          <span class="m lift" style="font-size:10px; color:#67757A; border:1px solid #1E282C;
                padding:5px 11px; cursor:pointer;">goal</span>
          <span class="m" style="font-size:10px; color:#6CB7FF; border:1px solid #1E3A4E;
                background:#101E27; padding:5px 11px;">steps</span>
          <span class="m lift" style="font-size:10px; color:#67757A; border:1px solid #1E282C;
                padding:5px 11px; cursor:pointer;">layers</span>
          <span class="m lift" style="font-size:10px; color:#67757A; border:1px solid #1E282C;
                padding:5px 11px; cursor:pointer;">gate</span>
          <span class="m lift" style="font-size:10px; color:#E3674E; border:1px solid #3A211C;
                padding:5px 11px; cursor:pointer;">open &middot; 2</span>
        </div>
        <div class="m" style="font-size:12px; line-height:1.95;">
          <div style="color:#2A3438;">62 &nbsp;<span style="color:#6CB7FF;">- id</span><span style="color:#67757A;">: star_align_1</span></div>
          <div style="color:#2A3438;">63 &nbsp;&nbsp;&nbsp;<span style="color:#6CB7FF;">contract</span><span style="color:#67757A;">: nf-core/star/align@2.7.11a</span></div>
          <div style="color:#2A3438;">64 &nbsp;&nbsp;&nbsp;<span style="color:#6CB7FF;">digest</span><span style="color:#67757A;">: sha256:9f2a41c8e7b3&hellip;</span></div>
          <div style="color:#2A3438;">65 &nbsp;&nbsp;&nbsp;<span style="color:#6CB7FF;">settings</span><span style="color:#67757A;">:</span></div>
          <div style="color:#2A3438;">66 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:#6CB7FF;">- name</span><span style="color:#67757A;">: sjdbOverhang</span></div>
          <div style="color:#2A3438;">67 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:#6CB7FF;">value</span><span style="color:#DFE6E6;">: 150</span></div>
          <div style="color:#2A3438;">68 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:#6CB7FF;">tier</span><span style="color:#C1B508;">: 3</span><span style="color:#2A3438;">&nbsp;&nbsp;# data-profiled</span></div>
          <div style="background:rgba(193,181,8,.05);"><span style="color:#2A3438;">69 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span><span style="color:#6CB7FF;">why</span><span style="color:#67757A;">:</span></div>
          <div style="background:rgba(193,181,8,.05);"><span style="color:#2A3438;">70 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span><span style="color:#6CB7FF;">reason</span><span style="color:#A8B4B2;">: read length 151 bp, less one</span></div>
          <div style="background:rgba(193,181,8,.05);"><span style="color:#2A3438;">71 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span><span style="color:#6CB7FF;">rule</span><span style="color:#A8B4B2;">: R04 read-length</span></div>
          <div style="background:rgba(193,181,8,.05);"><span style="color:#2A3438;">72 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span><span style="color:#6CB7FF;">premise</span><span style="color:#A8B4B2;">: measured, not asserted</span></div>
          <div style="color:#2A3438;">73 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:#6CB7FF;">via</span><span style="color:#67757A;">: ext_args</span></div>
          <div style="color:#2A3438;">74</div>
          <div style="color:#2A3438;">75 &nbsp;<span style="color:#6CB7FF;">- id</span><span style="color:#67757A;">: featurecounts_1</span></div>
          <div style="color:#2A3438;">76 &nbsp;&nbsp;&nbsp;<span style="color:#6CB7FF;">settings</span><span style="color:#67757A;">:</span></div>
          <div style="color:#2A3438;">77 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:#6CB7FF;">- name</span><span style="color:#67757A;">: strandedness</span></div>
          <div style="background:rgba(227,103,78,.07);"><span style="color:#2A3438;">78 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span><span style="color:#6CB7FF;">value</span><span style="color:#E3674E;">: null</span><span style="color:#E3674E;">&nbsp;&nbsp;&#9679; needs you</span></div>
          <div style="background:rgba(227,103,78,.07);"><span style="color:#2A3438;">79 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span><span style="color:#6CB7FF;">tier</span><span style="color:#E3674E;">: 4</span><span style="color:#2A3438;">&nbsp;&nbsp;# no rule matched</span></div>
          <div style="color:#2A3438;">80 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:#6CB7FF;">why</span><span style="color:#67757A;">:</span></div>
          <div style="color:#2A3438;">81 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style="color:#6CB7FF;">reason</span><span style="color:#A8B4B2;">: nothing in the registry decides this</span></div>
        </div>
        <div style="padding-top:20px; display:flex; gap:24px; align-items:baseline;">
          <span style="font-size:12.5px; color:#889699;">Edits here and edits on the canvas are the same edit.</span>
          <span class="m lift" style="font-size:10.5px; color:#6CB7FF; border:1px solid #1E3A4E;
                padding:6px 12px; cursor:pointer;">Download pipeline.yml</span>
        </div>
      </div>
'''

W = pathlib.Path
CANVAS_TWEAK = '''
<script data-dc-script data-props='{"state":{"editor":"enum","options":["idle","moving a step"],"default":"idle","section":"Canvas"},"$preview":{"width":1400,"height":880}}'>
class Component extends DCLogic {
  renderVals() {
    const moving = this.props.state === 'moving a step';
    return { g: { grid: moving ? 'block' : 'none',
                  lift: moving ? 'block' : 'none' } };
  }
}
</script>
'''
_c = canvas(field='live')
W('BuilderCanvas.dc.html').write_text(
    page(shellwrap(header() + cols(_c, rail('step', RAIL_STEP)))).replace('</x-dc>', '</x-dc>' + CANVAS_TWEAK))
W('BuilderPort.dc.html').write_text(page(shellwrap(header() + cols(canvas(overlay=PORT_POPOVER), rail('step', RAIL_STEP)))))
W('BuilderSettings.dc.html').write_text(page(shellwrap(header()
    + cols(canvas(sel='fc', overlay=SETTINGS_POPOVER), rail('step', RAIL_STEP)))))
W('BuilderSwap.dc.html').write_text(page(shellwrap(header() + cols(canvas(swap=True), rail('step', RAIL_SWAP)))))
W('BuilderEmpty.dc.html').write_text(page(shellwrap(
    header(name='untitled pipeline', status='not saved yet', run=False)
    + cols(canvas(empty=True), rail('assistant', RAIL_ASSISTANT)))))
W('BuilderRun.dc.html').write_text(page(
    shellwrap(header() + cols(canvas(dim=True), rail('step', RAIL_STEP))) + scrim(RUN_SHEET), h=900))
W('BuilderBrowse.dc.html').write_text(page(
    shellwrap(header() + cols(canvas(dim=True), rail('step', RAIL_STEP))) + scrim(BROWSE), h=900))
W('BuilderArtifact.dc.html').write_text(page(shellwrap(
    '    <div style="padding:22px 30px 0;">\n' + NAV + title_row('artifact') + '    </div>\n' + ARTIFACT_BODY)))
print('7 boards regenerated from one shell')
