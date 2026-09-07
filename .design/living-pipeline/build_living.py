# The living-pipeline canvas. Every board is composed from the SAME shell, the SAME canvas
# and the SAME fixture, so continuity is structural rather than remembered.
#
#     python3 build_living.py                       # rebuild every board
#     python3 ../_prev.py --dir living-pipeline --glob 'Living*'   # then LOOK at them
#
# **The fixture is the point.** Every count, name, tier and author on all ten boards comes
# from `S` below — the Forge canvas's lesson, and it is what stops the transcript claiming
# `4 of 7` beside a canvas holding five nodes.
import pathlib

HERE = pathlib.Path(__file__).parent
HEAD = (HERE / '_lhead.html').read_text()
FIELD = (HERE.parent / '_field.html').read_text()

W, RAIL = 1400, 420           # the board, and the conversation's column
CANVAS = W - RAIL             # 980

# ── the session every board is a moment of ─────────────────────────────────────────────────
S = {
    'name': 'rnaseq-counts',
    'prose': 'gene counts from paired-end RNA-seq of mouse liver, 24 files',
    'files': 24,
    'samples': 12,            # measurement.n_samples — the ONLY reason a board may say ×12
    'model': 'qwen2.5-coder:14b',
    'registry': 'comeni-registry@v0.2.0',
    'total': 7,
}

# process, contract id, in-rows, out-rows, settled count, tier, author, one-line why
STEPS = [
    ('FASTQC', 'nf-core/fastqc@0.12.1',
     ['fastq.reads'], ['qc.report'], 4, 'ok', 'res',
     'Every goal that names reads gets one. Tier 1 — nothing else can produce qc.report.'),
    ('TRIMGALORE', 'nf-core/trimgalore@0.6.10',
     ['fastq.reads'], ['fastq.reads[trimmed]'], 9, 'ok', 'res',
     'STAR_ALIGN declares state_required_conventional: [trimmed], so this is forced.'),
    ('STAR_ALIGN', 'nf-core/star/align@2.7.11a',
     ['fastq.reads[trimmed]', 'genome.index.star'], ['alignment.bam'], 14, 'meas', 'res',
     'Read length 151 bp — measured from your data, not asserted. Rule R04.'),
    ('SAMTOOLS_SORT', 'nf-core/samtools/sort@1.21',
     ['alignment.bam'], ['alignment.bam[sorted]'], 6, 'ok', 'res',
     'The only producer of the state FEATURECOUNTS asks for.'),
    ('SUBREAD_FEATURECOUNTS', 'nf-core/subread/featurecounts@2.0.6',
     ['alignment.bam[sorted]', 'genome.annotation.gtf'], ['counts.matrix'], 11, 'open', 'res',
     'You asked for a counts matrix and this is one of two tools that make one.'),
]

# ── page scaffolding ───────────────────────────────────────────────────────────────────────
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
  <svg class="layer" viewBox="0 0 {W} {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
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

def title(status, view='canvas', run=True, name=None, mode='Build'):
    """ONE strip of chrome, and the living builder has no tabs anywhere beneath it.

    The old builder stacked four bands — panel header, its own three tabs, `Rail`'s three
    under those, the gate panel. The rail here is the conversation and nothing else, so
    there is nothing for a tab strip to switch between."""
    on, off = 'background:#122029; color:#6CB7FF;', 'color:#67757A; cursor:pointer;'
    btn = ('<span class="lift" style="font-size:13.5px; font-weight:600; color:#080B0D;'
           ' background:#6CB7FF; padding:9px 26px; cursor:pointer;">Run</span>') if run else (
          '<span style="font-size:13.5px; font-weight:600; color:#2A3438;'
          ' background:#0D1316; padding:9px 26px;">Run</span>')
    return f'''      <div style="display:flex; align-items:center; justify-content:space-between; padding:20px 0 16px;">
        <div style="display:flex; align-items:baseline; gap:16px;">
          <span style="font-size:26px; font-weight:600; letter-spacing:-.03em;">{name or S['name']}</span>
          <span class="m" style="font-size:9.5px; letter-spacing:.12em; text-transform:uppercase;
                color:#67757A; border:1px solid #1E282C; padding:3px 7px;">{mode}</span>
          <span class="m" style="font-size:10.5px; color:#455257;">{status}</span>
        </div>
        <div style="display:flex; align-items:center; gap:14px;">
          <div style="display:flex; border:1px solid #1E282C;">
            <span class="m{'' if view=='canvas' else ' lift'}" style="font-size:10px; letter-spacing:.09em;
                  text-transform:uppercase; padding:7px 15px; {on if view=='canvas' else off}">Canvas</span>
            <span class="m{'' if view=='artifact' else ' lift'}" style="font-size:10px; letter-spacing:.09em;
                  text-transform:uppercase; padding:7px 15px; {on if view=='artifact' else off}">Artifact</span>
          </div>
          {btn}
        </div>
      </div>
'''

def header(status, **kw):
    return '    <div style="padding:22px 30px 0;">\n' + NAV + title(status, **kw) + '    </div>\n'

def cols(left, right, h=880):
    return (f'  <div style="position:relative; display:flex; flex-direction:column;'
            f' min-height:{h}px;">\n'
            f'{{HEADER}}'
            f'    <div class="split" style="flex:1; display:grid;'
            f' grid-template-columns:1fr {RAIL}px; min-height:0;">\n'
            f'{left}{right}    </div>\n  </div>\n')

# ── canvas geometry — derived ONCE, never written twice (`impl-geom`) ───────────────────────
NW, NH, SW, SH = 172, 112, 120, 80
PITCH = 224
SPINE = NH / 2
SPINE2 = NH / 2 + 22

def gx(i):        return 260 + i * PITCH        # column i's left edge
def out(i):       return gx(i) + NW
def inn(i):       return gx(i)

def corners():
    c = ''
    for h, v, sx, sy in (('left', 'top', 16, 16), ('right', 'top', 16, 16),
                         ('left', 'bottom', 16, 16), ('right', 'bottom', 16, 16)):
        c += (f'        <div style="position:absolute; {h}:{sx}px; {v}:{sy}px; width:16px; height:16px;'
              f' border-{h}:1px solid #28353C; border-{v}:1px solid #28353C;"></div>\n')
    return c

def node(x, y, nm, rows, foot, tier='ok', by='res', sel=False, ghost=False,
         leaving=False, extra='', ports=None, chan=None):
    """One uniform 172x112 symbol. `by` is the AUTHOR and it is drawn as stroke, never hue."""
    cls = ' '.join(['node', 'settle']
                   + ([tier] if tier != 'ok' else [])
                   + (['by-model'] if by == 'model' else [])
                   + (['sel'] if sel else [])
                   + (['ghost'] if ghost else [])
                   + (['leaving'] if leaving else []))
    pr = ''.join(
        f'            <div class="pr"><span style="color:{"#4A5C64" if d=="in" else "#3E5058"};">'
        f'{"&#9666;" if d=="in" else "&#9656;"}</span>'
        f'<span style="color:{"#7E8F95" if d=="in" else "#6B7C82"};">{t}</span></div>\n'
        for d, t in rows)
    pt = ports if ports is not None else [('in', SPINE, ''), ('out', SPINE, '')]
    ph = ''
    for side, cy, kind in pt:
        k = f' {kind}' if kind else ''
        tall = 29 if kind == 'gather' else (25 if kind == 'many' else 7)
        edge = 'left:-4px' if side == 'in' else 'right:-4px'
        if kind == 'gather':
            edge = 'left:-6px' if side == 'in' else 'right:-6px'
        bars = ('<i style="top:6px;"></i><i style="top:12px;"></i><i style="top:18px;"></i>'
                if kind == 'many' else '')
        ph += (f'          <div class="port{k}{" on" if sel else ""}"'
               f' style="{edge}; top:{cy - tall/2}px;">{bars}</div>\n')
    notch = '          <div class="notch"></div>\n' if by == 'hum' else ''
    ft = '' if ghost else f'          <div class="ft">{foot}</div>\n'
    ch = chan or ''
    return (f'        <div class="{cls}" style="left:{x}px; top:{y}px;">\n{ph}{notch}'
            f'          <div class="hd"><span class="m" style="font-size:11px; font-weight:500;">{nm}</span>{extra}</div>\n'
            f'          <div class="rows">\n{pr}          </div>\n{ft}{ch}        </div>\n')

def src(x, y, label, type_id, many=False, count=None, becomes=None, dim=False):
    """A SOURCE carries a TYPE and never a path — invariant 15, drawn."""
    tall = 25 if many else 7
    bars = '<i style="top:6px;"></i><i style="top:12px;"></i><i style="top:18px;"></i>' if many else ''
    tag = ''
    if many:
        n = f'&times;{count} samples' if count else '&times;N items'
        tag = (f'          <div class="m" style="font-size:8.5px; color:#6CB7FF; padding-top:3px;">'
               f'{n}</div>\n')
    was = ('text-decoration:line-through; text-decoration-color:#C1B508;' if becomes else '')
    new = (f'          <div class="m" style="font-size:8.5px; color:#C1B508; padding-top:2px;">'
           f'{becomes}</div>\n' if becomes else '')
    o = ' opacity:.55;' if dim else ''
    return (f'        <div class="src settle" style="left:{x}px; top:{y}px;{o}">\n'
            f'          <div class="port{" many" if many else ""}" style="right:-4px;'
            f' top:{SH/2 - tall/2}px;">{bars}</div>\n'
            f'          <div class="lb" style="color:#6CB7FF; font-size:8px;">Input</div>\n'
            f'          <div class="m" style="font-size:11px; padding-top:4px;">{label}</div>\n'
            f'          <div class="m" style="font-size:8.5px; color:#5D6C71; padding-top:3px;'
            f' {was}">{type_id}</div>\n'
            f'{new}{tag}        </div>\n')

# ── wires. `1 -> 1` is one stroke; `N -> N` is a ribbon; `N -> 1` converges. ────────────────
STRANDS = (-6, 0, 6)

def _leg(x1, y1, x2, y2, bend=None):
    if y1 == y2:
        return f'M{x1} {y1} H{x2}'
    mx = bend if bend is not None else (x1 + x2) / 2
    return f'M{x1} {y1} H{mx} V{y2} H{x2}'

def wire(a, b, kind='one', bend=None, cls=''):
    """`a` and `b` are (x, y). `kind` is one | many | gather."""
    (x1, y1), (x2, y2) = a, b
    c = f' class="{cls}"' if cls else ''
    if kind == 'one':
        return f'<path{c} d="{_leg(x1, y1, x2, y2, bend)}"/>'
    if kind == 'many':
        # three parallel strands. The bend moves with the strand so the verticals nest
        # rather than collapsing onto one line.
        return ''.join(
            f'<path{c} d="{_leg(x1, y1 + d, x2, y2 + d, None if bend is None else bend + d)}"/>'
            for d in STRANDS)
    # gather: the strands run to a convergence column, drop to the spine, and ONE stroke
    # continues into the port. That shape IS `.collect()`.
    conv = (bend if bend is not None else x2 - 72)
    out = ''.join(f'<path{c} d="M{x1} {y1 + d} H{conv + d} V{y2} H{conv + 5}"/>' for d in STRANDS)
    return out + f'<path{c} d="M{conv + 5} {y2} H{x2}"/>'

def chan_label(x, y, text, note=None):
    n = f'<b> &middot; {note}</b>' if note else ''
    return f'        <div class="chan" style="left:{x}px; top:{y}px;">{text}{n}</div>\n'

def canvas(inner, scale=1.0, dim=False, overlay='', foot=True, mini=True,
           pan=0, view=None):
    ctrls = '''        <div style="position:absolute; left:22px; bottom:18px; display:flex; gap:8px; z-index:3;">
          <span class="m lift" style="font-size:10px; color:#67757A; border:1px solid #1E282C;
                padding:6px 11px; cursor:pointer;">Fit</span>
          <span class="m lift" style="font-size:10px; color:#6CB7FF; border:1px solid #1E3A4E;
                padding:6px 11px; cursor:pointer;">+ Add step</span>
        </div>
''' if foot else ''
    mm = '''        <div style="position:absolute; right:18px; bottom:18px; width:146px; height:58px;
                    border:1px solid #1B262B; background:rgba(8,13,16,.82); z-index:3;">
          <div style="position:absolute; left:8px; top:18px; width:11px; height:5px; border:1px solid #33454C;"></div>
          <div style="position:absolute; left:8px; top:38px; width:11px; height:5px; border:1px solid #33454C;"></div>
          <div style="position:absolute; left:31px; top:18px; width:15px; height:5px; border:1px solid #3E525A;"></div>
          <div style="position:absolute; left:31px; top:32px; width:15px; height:5px; border:1px solid #3E525A;"></div>
          <div style="position:absolute; left:58px; top:18px; width:15px; height:5px; border:1px solid #6CB7FF;"></div>
          <div style="position:absolute; left:85px; top:18px; width:15px; height:5px; border:1px dashed #3E525A;"></div>
        </div>
''' if mini is True else (mini if mini else '')
    sc = ('' if scale == 1.0 else
          f' transform:scale({scale}); transform-origin:0 0; width:{100/scale:.4f}%;'
          f' height:{100/scale:.4f}%;')
    if pan:
        sc += f' left:{-pan}px;'
    d = ' opacity:.34;' if dim else ''
    return (f'      <div class="cv" style="position:relative; overflow:hidden;'
            f' border-top:1px solid #141C20;">\n'
            f'        <div style="position:absolute; inset:0;{d}">\n{FIELD}{corners()}'
            f'        <div style="position:absolute; inset:0;{sc}">\n{inner}        </div>\n'
            f'{mm}{ctrls}        </div>\n{overlay}      </div>\n')

def rail(body, composer=True, ph='Ask about a step, or say what to change'):
    cmp_ = f'''        <div style="padding:14px 18px 18px; border-top:1px solid #141C20;">
          <div class="cmp">
            <span class="m" style="font-size:13px; color:#6CB7FF;">&rsaquo;</span>
            <span style="font-size:12.5px; color:#455257;">{ph}</span>
            <span class="m cur" style="font-size:13px; color:#6CB7FF; margin-left:-4px;">&#9608;</span>
          </div>
        </div>
''' if composer else ''
    return (f'      <div class="tk" style="border-left:1px solid #141C20;'
            f' border-top:1px solid #141C20;\n'
            f'                  display:flex; flex-direction:column; min-height:0;">\n'
            f'        <div style="flex:1; overflow:hidden; padding:20px 18px 0;">\n'
            f'          <div class="log">\n{body}          </div>\n        </div>\n{cmp_}      </div>\n')

# ── transcript pieces ──────────────────────────────────────────────────────────────────────
def turn(tick, inner, delay=0):
    d = f' style="animation-delay:{delay}ms;"' if delay else ''
    return (f'            <div class="turn settle"{d}>\n'
            f'              <div class="tick {tick}"></div>\n{inner}            </div>\n')

def said(text, delay=0):
    return turn('you', f'              <div class="said">{text}</div>\n', delay)

def says(text, delay=0):
    return turn('', f'              <div class="says">{text}</div>\n', delay)

def receipt(text, tick='hum', delay=0):
    return turn(tick, f'              <div class="rcpt">{text}</div>\n', delay)

BY_WORD = {'res': 'settled', 'model': 'model chose', 'hum': 'you chose', 'meas': 'measured'}

def done(name, by='res', note=None, delay=0):
    """An accepted decision, collapsed. Fifteen of these is a readable list; fifteen expanded
    cards is not — and the collapsed row is what makes the log an inspector you can click."""
    n = f'<span style="font-size:11px; color:#455257;">{note}</span>' if note else ''
    return turn(by, f'              <div class="done"><span class="nm">{name}</span>{n}'
                    f'<span class="by">{BY_WORD[by]}</span></div>\n', delay)

def block(head, body, foot=None, right=None, delay=0, tick='', tone=None):
    r = f'<span class="m" style="font-size:9.5px; color:#455257;">{right}</span>' if right else ''
    hc = f' style="color:{tone};"' if tone else ''
    f = f'          <div class="ft">{foot}</div>\n' if foot else ''
    inner = (f'              <div class="blk">\n'
             f'          <div class="hd"><span class="lb"{hc}>{head}</span>{r}</div>\n'
             f'          <div class="bd">{body}</div>\n{f}'
             f'              </div>\n')
    return turn(tick, inner, delay)

def option(name, why, pick=False, foc=False, tag=None):
    c = 'opt' + (' pick' if pick else '') + (' foc' if foc else '')
    t = (f'<span class="m" style="font-size:9px; color:#6CB7FF; margin-left:auto;'
         f' white-space:nowrap;">{tag}</span>') if tag else ''
    return (f'<div class="{c} lift"><span class="dot"></span>'
            f'<span style="flex:1;"><span class="m" style="font-size:11px; color:#DFE6E6;">{name}</span>'
            f'<span style="display:block; font-size:11.5px; color:#889699; line-height:1.45;'
            f' padding-top:4px;">{why}</span></span>{t}</div>')

def row(label, value, colour=None, note=None):
    c = f' style="color:{colour};"' if colour else ''
    n = (f'<div style="font-size:11.5px; color:#889699; padding-top:4px; line-height:1.45;">{note}</div>'
         if note else '')
    return (f'<div style="display:grid; grid-template-columns:66px 1fr; gap:9px;'
            f' align-items:start; padding-bottom:9px;">'
            f'<span class="lb" style="letter-spacing:.1em; padding-top:2px;">{label}</span>'
            f'<div><span class="m" style="font-size:11px;"{c}>{value}</span>{n}</div></div>')

def bullet(colour, name, why):
    return (f'<div style="display:flex; gap:10px; padding-bottom:12px;">'
            f'<span style="color:{colour}; font-size:8px; padding-top:5px;">&#9679;</span>'
            f'<div><div class="m" style="font-size:11.5px;">{name}</div>'
            f'<div style="font-size:11.5px; color:#889699; padding-top:4px; line-height:1.45;">{why}</div>'
            f'</div></div>')

def write(name, body, h=880, header_html=''):
    html = page(body.replace('{HEADER}', header_html), h)
    (HERE / f'{name}.dc.html').write_text(html)
    print(f'  {name}.dc.html  {len(html.splitlines())} lines')

print('living-pipeline: helpers ready')

# ══════════════════════════════════════════════════════════════════════════════════════════
#  1. THE DOOR — where a session starts, and where Build/Spawn is chosen
# ══════════════════════════════════════════════════════════════════════════════════════════
def mode_card(name, sub, lines, picked):
    dot = ('<span style="width:9px; height:9px; border:1px solid #6CB7FF; background:#6CB7FF;'
           ' box-shadow:inset 0 0 0 2px #080B0D; flex:none; margin-top:3px;"></span>' if picked else
           '<span style="width:9px; height:9px; border:1px solid #4A5C64; flex:none;'
           ' margin-top:3px;"></span>')
    li = ''.join(f'<div style="font-size:12px; color:#889699; line-height:1.5;'
                 f' padding-top:6px;">{one}</div>' for one in lines)
    return (f'<div class="lift" style="flex:1; display:flex; gap:11px; padding:15px 17px;'
            f' border:1px solid {"#1E3A4E" if picked else "#1E282C"};'
            f' background:{"#0B141A" if picked else "transparent"}; cursor:pointer;">{dot}'
            f'<div><div style="font-size:14px; font-weight:600; letter-spacing:-.01em;">{name}</div>'
            f'<div style="font-size:12px; color:#67757A; padding-top:3px;">{sub}</div>{li}</div></div>')

def board_open():
    body = f'''  <div style="position:relative; height:880px; display:flex; flex-direction:column;">
    <div style="padding:22px 30px 0;">
{NAV}    </div>
    <div style="flex:1; display:flex; flex-direction:column; align-items:center;
                justify-content:center; gap:30px; padding:0 30px 60px;">
      <h1 class="settle" style="margin:0; text-align:center; font-size:34px; font-weight:600;
             letter-spacing:-.03em; line-height:1.25; max-width:22ch; text-wrap:balance;">
        What do you want to make?</h1>
      <div class="settle" style="animation-delay:120ms; width:min(660px,100%);
           display:flex; align-items:center; gap:12px; padding:15px 18px;
           background:#0B1013; border:1px solid #1E3A4E;">
        <span class="m" style="font-size:14px; color:#6CB7FF;">&rsaquo;</span>
        <span style="font-size:15px;">{S['prose']}</span>
        <span class="m cur" style="font-size:15px; color:#6CB7FF;">&#9608;</span>
      </div>
      <div class="settle" style="animation-delay:180ms; width:min(660px,100%);
           display:flex; gap:12px;">
        {mode_card('Build step by step', 'You choose at each real decision.',
                   ['Every step is shown with the reason it is there, and the '
                    'alternatives that would also fit.'], True)}
        {mode_card('Spawn the whole thing', 'It makes the safe choices and stops where it cannot.',
                   ['Same engine, same pipeline. It only stops where a person '
                    'genuinely has to answer.'], False)}
      </div>
      <div class="settle" style="animation-delay:240ms; display:flex; align-items:center;
           gap:16px; width:min(660px,100%);">
        <span class="go" style="padding:10px 22px; font-size:13.5px;">Start building</span>
        <span style="font-size:12.5px; color:#455257;">or
          <span style="color:#6CB7FF;">draw it yourself</span> &mdash; the canvas without a
          conversation</span>
      </div>
      <div class="settle" style="animation-delay:300ms; width:min(660px,100%);
           border-top:1px solid #141C20; padding-top:14px; display:flex; gap:9px;
           align-items:baseline;">
        <span class="lb" style="color:#455257;">Sends</span>
        <span style="font-size:11.5px; color:#455257; line-height:1.5;">
          Your sentence, and nothing else. No filenames, no sample names, no paths &mdash;
          those belong to the run, not the pipeline.</span>
      </div>
    </div>
  </div>
'''
    write('LivingOpen', body)


# ══════════════════════════════════════════════════════════════════════════════════════════
#  2. THE GOAL — what it read back, and the one thing it will not assume
# ══════════════════════════════════════════════════════════════════════════════════════════
EMPTY = '''        <div style="position:absolute; inset:0; display:flex; align-items:center;
                    justify-content:center;">
          <div style="text-align:center;">
            <div class="m" style="font-size:11px; color:#3E5058; letter-spacing:.14em;
                        text-transform:uppercase;">Nothing built yet</div>
            <div style="font-size:12.5px; color:#5D6C71; padding-top:9px;">
              Confirm the goal on the right and the steps arrive one at a time</div>
          </div>
        </div>
'''

def board_goal():
    """One block, not two. The grouping question lives INSIDE the goal because that is what it
    is — the goal is not complete without it, and stacking a summary card above a question card
    pushed the only thing anybody had to answer below the fold."""
    choose = (option('12 paired samples', 'R1 and R2 per sample. Runs 12 times.',
                     pick=True, tag='likely')
              + option('24 independent items', 'Every file on its own. Runs 24 times.')
              + option('Lanes to merge', 'Several per sample, joined before alignment.')
              + option('One combined dataset', 'All 24 are one thing. Runs once.'))

    goal = (row('Have', 'fastq.reads[paired]', '#6CB7FF')
            + row('Want', 'counts.matrix', '#6CB7FF')
            + row('Organism', 'mus_musculus')
            + row('Unsure', 'strandedness', '#C1B508',
                  'You did not say, and I will not invent it.')
            + '<div style="border-top:1px solid #162025; margin:4px -12px 0; padding:13px 12px 0;">'
            + '<div class="lb" style="color:#C1B508; padding-bottom:7px;">'
              'How are the 24 files grouped?</div>'
            + '<div style="font-size:12px; color:#889699; line-height:1.5; padding-bottom:11px;">'
              'This is not a detail. Four readings are possible and the pipeline is different '
              'for every one.</div>' + choose + '</div>')

    rail_html = rail(
        said(S['prose'])
        + says('Here is the goal I read. Nothing is decided yet.', 40)
        + block('Goal', goal,
                foot='<span class="go">Use this goal</span><span class="no">Edit</span>',
                right='editable', tick='wait', delay=90))

    body = cols(canvas(EMPTY, foot=False, mini=False), rail_html)
    write('LivingGoal', body,
          header_html=header('understanding &middot; <span style="color:#C1B508;">1 question</span>',
                             run=False))


# ══════════════════════════════════════════════════════════════════════════════════════════
#  3. BUILD — the primary state. Four settled, one proposed as a ghost.
# ══════════════════════════════════════════════════════════════════════════════════════════
YM, YQ = 140, 300            # the main chain, and the QC branch
YS = YM + SPINE - SH / 2     # the entry source lines up with the chain it feeds
# **A mid-pipeline input sits in the layer before the step that consumes it**, not in a
# left-hand gutter beside the entry channels. `genome.index.star` is not something you have at
# the start of an analysis — it enters AT the aligner, and drawing it at the far left both said
# otherwise and dragged a wire across the whole graph.
YREF = 470

def built_graph(ghost=('SAMTOOLS_SORT', ['alignment.bam'], ['alignment.bam[sorted]']),
                star_by='res', star_sel=False, star_leaving=False, sub=None):
    """The chain, its two sources, and the three collection shapes drawn on the wires.

    **The branch bend needs room.** It first ran in the 32px between the source's port and the
    first column, so three nested strands rendered as six vertical lines in a 32px gutter. The
    gutter is 124px now and the bend sits in the middle of it."""
    ps = [('in', SPINE, 'many'), ('out', SPINE, 'many')]
    reads, ref = (16 + SW, YS + SH/2), (gx(0) + SW, YREF + SH/2)
    branch = gx(0) - 62
    solid = ('        <svg style="position:absolute; inset:0;" width="100%" height="100%" aria-hidden="true">\n'
             '          <g fill="none" stroke="#2C3E45" stroke-width="1.5" stroke-linejoin="miter">\n')
    for one in (wire(reads, (inn(0), YQ + SPINE), 'many', bend=branch),
                wire(reads, (inn(0), YM + SPINE), 'many'),
                wire((out(0), YM + SPINE), (inn(1), YM + SPINE), 'many'),
                wire(ref, (inn(1), YM + SPINE2), 'one', bend=gx(1) - 44)):
        solid += '            ' + one + '\n'
    solid += '          </g>\n'
    if ghost:
        solid += ('          <g fill="none" stroke="#2C3E45" stroke-width="1.5" stroke-dasharray="5 5"'
                  ' stroke-linejoin="miter" opacity=".6">\n'
                  '            ' + wire((out(1), YM + SPINE), (inn(2), YM + SPINE), 'many') + '\n'
                  '          </g>\n')
    solid += '        </svg>\n'

    g = (src(16, YS, 'reads', 'fastq.reads[paired]', many=True, count=S['samples'])
         + src(gx(0), YREF, 'reference', 'genome.index.star')
         + node(gx(0), YQ, 'FASTQC', [('in', 'fastq.reads'), ('out', 'qc.report')],
                '4 settled', ports=ps)
         + node(gx(0), YM, 'TRIMGALORE',
                [('in', 'fastq.reads'), ('out', 'fastq.reads[trimmed]')], '9 settled', ports=ps)
         + node(gx(1), YM, 'STAR_ALIGN',
                [('in', 'fastq.reads[trimmed]'), ('in', 'genome.index.star'),
                 ('out', 'alignment.bam')], '14 settled', tier='meas', by=star_by,
                sel=star_sel, leaving=star_leaving, ports=ps + [('in', SPINE2, '')]))
    if sub:
        g += sub
    if ghost:
        nm, ins, outs = ghost
        g += node(gx(2), YM, nm, [('in', i) for i in ins] + [('out', o) for o in outs],
                  '', ghost=True, ports=ps,
                  extra='<span class="m" style="font-size:8.5px; color:#6CB7FF;'
                        ' margin-left:auto;">PROPOSED</span>')
    # **Above the wire, inside the gutter it describes.** These sat under the first node.
    labels = (chan_label(reads[0] + 12, reads[1] - 24, 'once per sample')
              + chan_label(ref[0] + 12, ref[1] - 24, 'read once per task'))
    return solid + g + labels

def board_build():
    alts = (option('SAMTOOLS_SORT', 'The only tool that produces the sorted state '
                   'FEATURECOUNTS asks for.', pick=True, tag='recommended')
            + option('SAMTOOLS_SORMADUP', 'Sorts and marks duplicates in one pass. '
                     'Adds a step you did not ask for.'))
    prop = ('<div style="font-size:12.5px; color:#889699; line-height:1.55; padding-bottom:6px;">'
            'Nothing downstream reads an unsorted BAM. This is structural &mdash; there is no '
            'version of your pipeline without a sort.</div>'
            '<div class="m" style="font-size:10px; color:#455257; padding-bottom:12px;">'
            'alignment.bam &nbsp;&rarr;&nbsp; alignment.bam[sorted]</div>' + alts)

    rail_html = rail(
        done('Goal confirmed', 'hum', '12 paired samples')
        + done('FASTQC', 'res', 'step 1')
        + done('TRIMGALORE', 'res', 'step 2')
        + done('STAR_ALIGN', 'res', 'step 3 &middot; measured')
        + says('Step 4 of 7, on the canvas already and drawn dashed. Nothing is committed '
               'until you add it.', 60)
        + block('Step 4 &mdash; sort the alignments', prop,
                foot='<span class="go">Add it</span><span class="no">Show me why</span>'
                     '<span class="no">Skip</span>',
                right='tier 1', delay=110))

    body = cols(canvas(built_graph()), rail_html)
    write('LivingBuild', body,
          header_html=header('building &middot; 4 of 7 steps &middot; saved 3s ago'))



# ══════════════════════════════════════════════════════════════════════════════════════════
#  4. CHOOSE — an alternative previewed on the canvas, and everything it would drag with it
# ══════════════════════════════════════════════════════════════════════════════════════════
def board_choose():
    """**One slot, one box.** The first version drew HISAT2 as a second node BELOW STAR with a
    connector between them, and it read as a pipeline that had gained a module rather than one
    whose aligner was being swapped. `n-bswap` on the 2026-08-29 canvas already settled this —
    *TRIMGALORE struck through, HISAT2 IN PLACE* — and departing from it was the mistake.

    The canvas shows what the graph WOULD BECOME, not a comparison widget. Comparing is the
    rail's job, and it already has the candidate list.

    Hover **and** focus preview: `impl-walkbugs` records a palette unreachable by keyboard, and
    an option list whose canvas preview fires only on hover repeats that exactly."""
    ps = [('in', SPINE, 'many'), ('out', SPINE, 'many')]
    reads = (16 + SW, YS + SH / 2)
    ref = (gx(0) + SW, YREF + SH / 2)

    sv = ('        <svg style="position:absolute; inset:0;" width="100%" height="100%" aria-hidden="true">\n'
          # what SURVIVES the swap, at full strength
          '          <g fill="none" stroke="#2C3E45" stroke-width="1.5" stroke-linejoin="miter">\n'
          '            ' + wire(reads, (inn(0), YQ + SPINE), 'many', bend=gx(0) - 62) + '\n'
          '            ' + wire((out(1), YM + SPINE), (inn(2), YM + SPINE), 'many') + '\n'
          '          </g>\n'
          # what GOES: dimmed, not deleted — the slot and its neighbours must stay put
          '          <g fill="none" stroke="#2C3E45" stroke-width="1.5" stroke-linejoin="miter"'
          ' opacity=".3">\n'
          '            ' + wire(reads, (inn(0), YM + SPINE), 'many') + '\n'
          '            ' + wire((out(0), YM + SPINE), (inn(1), YM + SPINE), 'many') + '\n'
          '          </g>\n'
          # what would ARRIVE: dashed, and the reads reach the aligner directly
          '          <g fill="none" stroke="#C1B508" stroke-width="1.5" stroke-dasharray="5 5"'
          ' stroke-linejoin="miter" opacity=".55">\n')
    sv += ('            ' + wire(reads, (inn(1), YM + SPINE), 'many') + '\n'
           '            ' + wire(ref, (inn(1), YM + SPINE2), 'one', bend=gx(1) - 44) + '\n'
           '          </g>\n        </svg>\n')

    g = (src(16, YS, 'reads', 'fastq.reads[paired]', many=True, count=S['samples'])
         + src(gx(0), YREF, 'reference', 'genome.index.star',
               becomes='genome.index.hisat2')
         + node(gx(0), YQ, 'FASTQC', [('in', 'fastq.reads'), ('out', 'qc.report')],
                '4 settled', ports=ps)
         + node(gx(0), YM, 'TRIMGALORE',
                [('in', 'fastq.reads'), ('out', 'fastq.reads[trimmed]')],
                '<span style="color:#E3674E;">removed by this swap</span>',
                leaving=True, ports=ps)
         # ONE box in the slot. The tool leaving is named in the footer, so the SLOT persists
         # and nothing on the canvas moves — object permanence without a second node.
         + node(gx(1), YM, 'HISAT2_ALIGN',
                [('in', 'fastq.reads'), ('in', 'genome.index.hisat2'), ('out', 'alignment.bam')],
                '<span style="color:#C1B508; text-decoration:line-through;'
                ' text-decoration-color:#C1B508;">STAR_ALIGN</span>',
                ghost=True, tier='meas', ports=ps + [('in', SPINE2, '')],
                extra='<span class="m" style="font-size:8.5px; color:#C1B508;'
                      ' margin-left:auto;">INSTEAD</span>')
         + node(gx(2), YM, 'SAMTOOLS_SORT',
                [('in', 'alignment.bam'), ('out', 'alignment.bam[sorted]')], '6 settled',
                ports=ps))

    labels = (chan_label(gx(0) + 6, YM - 22, 'the reads would pass straight through')
              + chan_label(ref[0] + 12, ref[1] - 24, 'a different index'))

    alts = (option('STAR_ALIGN', 'On the canvas now. Ranked 1st of 4 &mdash; splice-aware, and '
                   'your reads are 151 bp.', pick=True, tag='in use')
            + option('HISAT2_ALIGN', 'Ranked 2nd. Peaks near 8 GB where STAR wants 38.',
                     foc=True, tag='focused')
            + option('SALMON_QUANT', 'Removes three later steps and answers a different '
                     'question.', tag='changes the goal'))

    changes = ('<div style="font-size:12.5px; color:#889699; line-height:1.5;'
               ' padding-bottom:10px;">Four things move. Nothing until you say so.</div>'
               + bullet('#E3674E', 'TRIMGALORE removed',
                        'Only STAR asks for <span class="m" style="font-size:10.5px;">[trimmed]</span>.')
               + bullet('#C1B508', 'A different reference',
                        '<span class="m" style="font-size:10.5px;">genome.index.hisat2</span>, '
                        'a file you will need at run time.')
               + bullet('#C1B508', '3 settings change',
                        '<span class="m" style="font-size:10.5px;">--sjdbOverhang</span> is '
                        'dropped; two re-resolve.')
               + bullet('#10AA91', 'SAMTOOLS_SORT unaffected',
                        'Still fed <span class="m" style="font-size:10.5px;">alignment.bam</span>.'))

    rail_html = rail(
        said('why star and not hisat2?', 0)
        + says('Read length, 151 bp. Tab or hover the alternatives and the canvas puts each '
               'one in STAR&rsquo;s place.', 40)
        + block('Step 3 &mdash; align the reads', alts, right='4 candidates', delay=70)
        + block('HISAT2_ALIGN in STAR&rsquo;s place', changes,
                foot='<span class="go">Apply all four</span><span class="no">Keep STAR</span>',
                right='preview', tick='wait', tone='#C1B508', delay=120))

    body = cols(canvas(sv + g + labels), rail_html)
    write('LivingChoose', body,
          header_html=header('building &middot; 4 of 7 steps &middot; '
                             '<span style="color:#C1B508;">previewing a swap</span>'))


# ══════════════════════════════════════════════════════════════════════════════════════════
#  5. PARAMETERS — the one thing the engine could not settle, asked once
# ══════════════════════════════════════════════════════════════════════════════════════════
SETTINGS_CARD = '''        <div class="pop" style="position:absolute; left:548px; top:398px; width:382px;
                    background:#0A1014; border:1px solid #22333B; box-shadow:0 20px 50px -24px #000; z-index:4;">
          <div style="padding:12px 14px 10px; border-bottom:1px solid #162025; display:flex;
                      align-items:baseline; justify-content:space-between;">
            <span class="m" style="font-size:11px;">SUBREAD_FEATURECOUNTS</span>
            <span class="m" style="font-size:9.5px; color:#455257;">13 values</span></div>
          <div style="padding:12px 14px;">
            <div style="display:flex; align-items:baseline; gap:8px; padding-bottom:5px;">
              <span style="color:#E3674E; font-size:8px;">&#9679;</span>
              <span class="m" style="font-size:11px;">-t &nbsp;feature type</span>
              <span class="m" style="font-size:9.5px; color:#E3674E; margin-left:auto;">needs you</span></div>
            <div style="font-size:11.5px; color:#889699; line-height:1.45; padding:0 0 10px 16px;">
              No rule covers it. Asked on the right.</div>
            <div style="display:flex; align-items:baseline; gap:8px; padding-bottom:5px;">
              <span style="color:#C1B508; font-size:8px;">&#9679;</span>
              <span class="m" style="font-size:11px;">-s &nbsp;strandedness</span>
              <span class="m" style="font-size:9.5px; color:#C1B508; margin-left:auto;">measured</span></div>
            <div style="font-size:11.5px; color:#889699; line-height:1.45; padding:0 0 10px 16px;">
              The module reads it from <span class="m" style="font-size:10.5px;">meta</span>.
              Premise: reverse-stranded, from 400k sampled reads.</div>
            <div style="display:flex; align-items:baseline; gap:8px;">
              <span style="color:#10AA91; font-size:8px;">&#9679;</span>
              <span class="m" style="font-size:11px; color:#889699;">11 settled</span>
              <span class="m lift" style="font-size:9.5px; color:#6CB7FF; margin-left:auto;
                    cursor:pointer;">show</span></div>
          </div>
        </div>
'''

def board_param():
    ps = [('in', SPINE, 'many'), ('out', SPINE, 'many')]
    chain = (node(gx(0), YM, 'STAR_ALIGN',
                  [('in', 'fastq.reads[trimmed]'), ('out', 'alignment.bam')], '14 settled',
                  tier='meas', ports=ps)
             + node(gx(1), YM, 'SAMTOOLS_SORT',
                    [('in', 'alignment.bam'), ('out', 'alignment.bam[sorted]')], '6 settled',
                    ports=ps)
             + node(gx(2), YM, 'SUBREAD_FEATURECOUNTS',
                    [('in', 'alignment.bam[sorted]'), ('in', 'genome.annotation.gtf'),
                     ('out', 'counts.matrix')],
                    '<span style="color:#E3674E;">1 needs you</span> &middot; 12 settled',
                    tier='open', sel=True, ports=ps + [('in', SPINE2, '')],
                    extra='<span class="m" style="font-size:9px; color:#455257;'
                          ' margin-left:auto; cursor:pointer;">&#8943;</span>'))
    wires = ('        <svg style="position:absolute; inset:0;" width="100%" height="100%" aria-hidden="true">\n'
             '          <g fill="none" stroke="#2C3E45" stroke-width="1.5" stroke-linejoin="miter">\n'
             '            ' + wire((out(0), YM + SPINE), (inn(1), YM + SPINE), 'many') + '\n'
             '            ' + wire((out(1), YM + SPINE), (inn(2), YM + SPINE), 'many') + '\n'
             '          </g>\n        </svg>\n')

    choose = (option('exon', 'Count reads landing in exons, summarised per gene. What an RNA-seq '
                     'counts matrix normally means.', pick=True, tag='conventional')
              + option('gene', 'Count against the whole gene body, introns included.')
              + option('transcript', 'One row per transcript rather than per gene.'))

    ask = ('<div style="font-size:12.5px; color:#889699; line-height:1.55; padding-bottom:6px;">'
           'featureCounts needs to know which rows of the GTF to count against. No rule in the '
           'registry covers this and I will not pick for you.</div>'
           '<div class="m" style="font-size:10px; color:#455257; padding-bottom:12px;">'
           '-t &nbsp;&middot;&nbsp; reaches the tool through task.ext.args</div>' + choose)

    rail_html = rail(
        receipt('you opened the values card on SUBREAD_FEATURECOUNTS', 'hum')
        + says('Twelve of its thirteen values are settled. This is the one that is not.', 30)
        + block('Which features should it count?', ask,
                foot='<span class="go">Use exon</span>'
                     '<span class="no">Type a value</span>',
                right='tier 4', tick='open', tone='#E3674E', delay=90)
        + block('One finding', bullet('#C1B508', 'MD0512 &middot; genome.annotation.gtf is unbound',
                                     'The pipeline is valid. A reference is data, so this '
                                     'is a question on the run sheet.'),
                right='does not block', tick='wait', tone='#C1B508', delay=140))

    body = cols(canvas(wires + chain, overlay=SETTINGS_CARD), rail_html)
    write('LivingParam', body,
          header_html=header('building &middot; 5 of 7 steps &middot; '
                             '<span style="color:#E3674E;">1 value needs you</span>'))


# ══════════════════════════════════════════════════════════════════════════════════════════
#  6. COLLECTION — the grammar board. Three shapes, and none of them is N copies of a node.
# ══════════════════════════════════════════════════════════════════════════════════════════
def band(y, caption, rule, detail):
    return (f'        <div class="m" style="position:absolute; left:22px; top:{y}px;'
            f' font-size:10px; letter-spacing:.1em; color:#67757A;">{caption}</div>\n'
            f'        <div style="position:absolute; left:22px; top:{y+17}px; width:190px;'
            f' font-size:11.5px; color:#889699; line-height:1.45;">{rule}</div>\n'
            f'        <div class="m" style="position:absolute; left:22px; top:{y+58}px;'
            f' font-size:9px; color:#455257; width:200px; line-height:1.5;">{detail}</div>\n')

def board_collect():
    """§1.7 drawn. **The middle shape is why this board exists** — today a per-sample channel
    and a run-scoped one are the same single stroke, so the canvas cannot say the one thing a
    researcher most needs to know about their own data."""
    A, B, C = 130, 330, 560
    x0, x1 = 250, 560
    g = ''
    sv = ('        <svg style="position:absolute; inset:0;" width="100%" height="100%" aria-hidden="true">\n'
          '          <g fill="none" stroke="#2C3E45" stroke-width="1.5" stroke-linejoin="miter">\n')

    # 1 -> 1 ─────────────────────────────────────────────────────────────────────────────
    g += src(x0, A + 12, 'reference', 'genome.index.star')
    g += node(x1, A, 'STAR_ALIGN', [('in', 'genome.index.star'), ('out', 'alignment.bam')],
              '1 value', ports=[('in', SPINE, ''), ('out', SPINE, '')])
    sv += '            ' + wire((x0 + SW, A + 12 + SH/2), (x1, A + SPINE), 'one') + '\n'

    # N -> N ─────────────────────────────────────────────────────────────────────────────
    g += src(x0, B + 12, 'reads', 'fastq.reads[paired]', many=True, count=S['samples'])
    g += node(x1, B, 'TRIMGALORE', [('in', 'fastq.reads'), ('out', 'fastq.reads[trimmed]')],
              f'runs {S["samples"]}&times;',
              ports=[('in', SPINE, 'many'), ('out', SPINE, 'many')])
    sv += '            ' + wire((x0 + SW, B + 12 + SH/2), (x1, B + SPINE), 'many') + '\n'

    # N -> 1 ─────────────────────────────────────────────────────────────────────────────
    g += node(x0 - 10, C, 'FASTQC', [('in', 'fastq.reads'), ('out', 'qc.report')],
              f'runs {S["samples"]}&times;',
              ports=[('in', SPINE, 'many'), ('out', SPINE, 'many')])
    g += node(x1 + 40, C, 'MULTIQC', [('in', 'qc.report'), ('out', 'qc.summary')], 'runs once',
              ports=[('in', SPINE, 'gather'), ('out', SPINE, '')])
    sv += '            ' + wire((x0 - 10 + NW, C + SPINE), (x1 + 40, C + SPINE), 'gather') + '\n'
    sv += '          </g>\n        </svg>\n'

    caps = (chan_label(x0 + SW + 12, A + 12 + SH/2 - 22, 'one value', 'read once per task')
            + chan_label(x0 + SW + 12, B + 12 + SH/2 - 22, f'&times;{S["samples"]} samples',
                         'once per sample')
            + chan_label(x0 - 10 + NW + 14, C + SPINE - 22, f'&times;{S["samples"]}', 'collect all'))

    txt = (band(A + 8, '1 &rarr; 1', 'A run-scoped value.',
                'ONE STROKE. The reference is read once per task and never consumed.')
           + band(B + 8, 'N &rarr; N', 'A per-item channel.',
                 'A THREE-STRAND RIBBON. Three strands whether N is 12 or 12,000 &mdash; the '
                 'count is on the source, never on the wire.')
           + band(C + 8, 'N &rarr; 1', 'A gathering input.',
                  'THE RIBBON CONVERGES. That shape is <b>.collect()</b>, and the port it '
                  'arrives at is drawn wide because it accepts all of them at once.'))

    rail_html = rail(
        says('You have 24 files. I read them as 12 paired samples, so most of this pipeline '
             'runs 12 times &mdash; the canvas says which parts.', 0)
        + block('How your data moves',
                '<div style="font-size:12.5px; color:#889699; line-height:1.6;">'
                'Three shapes, and no step is drawn twelve times. A pipeline with one node per '
                'file would be 60 boxes describing five decisions.</div>'
                '<div style="border-top:1px solid #162025; margin:12px -12px 0; padding:12px 12px 0;">'
                + row('Reference', '1 value', '#6CB7FF', 'Read once per task.')
                + row('Reads', f'&times;{S["samples"]}', '#6CB7FF', 'Once per sample, all the way to counts.')
                + row('Reports', f'&times;{S["samples"]} &rarr; 1', '#6CB7FF',
                      'MULTIQC waits for all twelve and emits one summary.')
                + '</div>', right='this run', delay=60)
        + says('The twelve is measured, not assumed &mdash; you told me the files are paired. '
               'Where I have no count the canvas says <span class="m" style="font-size:11px;">'
               '&times;N items</span> and nothing more.', 120)
        + receipt('no filename or sample id is in this pipeline &mdash; the binding belongs to '
                  'the run', 'res'))

    body = cols(canvas(sv + g + caps + txt, mini=False, foot=False), rail_html)
    write('LivingCollect', body,
          header_html=header('12 paired samples &middot; 24 files'))


# ══════════════════════════════════════════════════════════════════════════════════════════
#  7. SPAWN — the same engine, traversed automatically, and honest about who chose what
# ══════════════════════════════════════════════════════════════════════════════════════════
def board_spawn():
    """`Spawn` is not permission to label the whole graph AI-authored (Task 12). One node here
    was chosen by a model and it is the only one drawn with a dashed bar."""
    ps = [('in', SPINE, 'many'), ('out', SPINE, 'many')]
    y2 = YM + 200
    g = (src(16, YS, 'reads', 'fastq.reads[paired]', many=True, count=S['samples'])
         + node(gx(0), YM, 'TRIMGALORE',
                [('in', 'fastq.reads'), ('out', 'fastq.reads[trimmed]')], '9 settled', ports=ps)
         + node(gx(1), YM, 'STAR_ALIGN',
                [('in', 'fastq.reads[trimmed]'), ('out', 'alignment.bam')], '14 settled',
                tier='meas', ports=ps)
         + node(gx(2), YM, 'SAMTOOLS_SORT',
                [('in', 'alignment.bam'), ('out', 'alignment.bam[sorted]')], '6 settled', ports=ps)
         + node(gx(0), y2, 'FASTQC', [('in', 'fastq.reads'), ('out', 'qc.report')],
                '4 settled', ports=ps)
         + node(gx(3), YM, 'SUBREAD_FEATURECOUNTS',
                [('in', 'alignment.bam[sorted]'), ('out', 'counts.matrix')],
                '13 settled', tier='meas', by='model', ports=ps)
         + node(gx(3), y2, 'MULTIQC', [('in', 'qc.report'), ('out', 'qc.summary')], '',
                ghost=True, ports=[('in', SPINE, 'gather'), ('out', SPINE, '')],
                extra='<span class="m" style="font-size:8.5px; color:#6CB7FF;'
                      ' margin-left:auto;">ARRIVING</span>'))
    sv = ('        <svg style="position:absolute; inset:0;" width="100%" height="100%" aria-hidden="true">\n'
          '          <g fill="none" stroke="#2C3E45" stroke-width="1.5" stroke-linejoin="miter">\n')
    for one in (wire((16 + SW, YS + SH/2), (inn(0), YM + SPINE), 'many'),
                wire((16 + SW, YS + SH/2), (inn(0), y2 + SPINE), 'many', bend=gx(0) - 62),
                wire((out(0), YM + SPINE), (inn(1), YM + SPINE), 'many'),
                wire((out(1), YM + SPINE), (inn(2), YM + SPINE), 'many')):
        sv += '            ' + one + '\n'
    # the edge being drawn RIGHT NOW — `grow`, first paint only
    sv += '            ' + wire((out(2), YM + SPINE), (inn(3), YM + SPINE), 'many') + '\n'
    # the edge being drawn RIGHT NOW — `grow-x`, first paint only, and only ever this one
    sv += ('          </g>\n          <g fill="none" stroke="#2C3E45" stroke-width="1.5"'
           ' stroke-linejoin="miter" class="grow">\n            '
           + wire((out(0), y2 + SPINE), (inn(3), y2 + SPINE), 'gather') + '\n'
           '          </g>\n        </svg>\n')

    swatch = ''.join(
        f'          <span style="display:flex; align-items:center; gap:8px;">'
        f'<span style="position:relative; width:9px; height:19px;">'
        f'<span style="position:absolute; left:3px; top:0; bottom:0; width:3px;'
        f' {css}"></span>{mark}</span>'
        f'<span class="m" style="font-size:10px; color:#889699;">{word}</span></span>\n'
        for css, mark, word in (
            ('background:#4A5C64;', '', 'the engine settled it'),
            ('border-left:3px dashed #4A5C64;', '', 'a model chose it'),
            ('background:#4A5C64;', '<span style="position:absolute; left:0; top:4px;'
             ' width:3px; height:11px; background:#4A5C64;"></span>', 'you chose it')))
    legend = ('        <div style="position:absolute; left:22px; top:22px; display:flex;'
              ' gap:22px; align-items:center; background:rgba(12,18,22,.62);'
              ' border:1px solid #172025; padding:9px 15px;">\n'
              '          <span class="lb" style="letter-spacing:.12em;">Who chose</span>\n'
              + swatch + '        </div>\n')

    rail_html = rail(
        said(S['prose'])
        + done('Goal read', 'model', '12 paired samples')
        + done('FASTQC', 'res', 'tier 1')
        + done('TRIMGALORE', 'res', 'tier 1')
        + done('STAR_ALIGN', 'res', 'tier 3 &middot; measured')
        + done('SAMTOOLS_SORT', 'res', 'tier 1')
        + done('SUBREAD_FEATURECOUNTS', 'model', 'tier 4')
        + says('Six of seven. MULTIQC is arriving.', 60)
        + block('One choice was not mine to make quietly',
                '<div style="font-size:12.5px; color:#889699; line-height:1.5;'
                ' padding-bottom:11px;">Two tools make a counts matrix and no rule separates '
                'them, so a model picked. It is the only step drawn with a dashed edge, and it '
                'stays dashed in <span class="m" style="font-size:11px;">pipeline.yml</span>.</div>'
                + row('Chose', 'SUBREAD_FEATURECOUNTS', '#DFE6E6')
                + row('Over', 'HTSEQ_COUNT', '#889699')
                + row('Model', S['model'], '#889699'),
                foot='<span class="no">Choose it yourself</span>'
                     '<span class="no">Why these two?</span>',
                right='tier 4', tick='model', delay=110))

    body = cols(canvas(sv + g + legend, scale=.84), rail_html)
    write('LivingSpawn', body,
          header_html=header('spawning &middot; 6 of 7 steps &middot; '
                             '<span style="color:#889699;">1 model choice</span>',
                             mode='Spawn', run=False))


# ══════════════════════════════════════════════════════════════════════════════════════════
#  8. WHEN IT DOES NOT WORK — the state catalogue. Every one of these is a real stop.
# ══════════════════════════════════════════════════════════════════════════════════════════
def notice(mark, colour, head, body, foot=None, delay=0, tick=''):
    """A NOTICE has no panel. `impl-settled`: absence is absence — and a state that is not a
    decision must not wear the same border as one that is, or a refusal reads as a question."""
    f = (f'              <div style="display:flex; gap:8px; padding-top:10px;">{foot}</div>\n'
         if foot else '')
    return turn(tick,
                f'              <div style="display:flex; gap:9px;">'
                f'<span style="color:{colour}; font-size:9px; padding-top:4px;">{mark}</span>'
                f'<div><div style="font-size:12.5px; color:#DFE6E6; padding-bottom:5px;">{head}</div>'
                f'<div style="font-size:12px; color:#889699; line-height:1.55;">{body}</div>'
                f'</div></div>\n{f}', delay)

def board_trouble():
    ps = [('in', SPINE, 'many'), ('out', SPINE, 'many')]
    g = (src(16, YS, 'reads', 'fastq.reads[paired]', many=True, count=S['samples'])
         + node(gx(0), YM, 'TRIMGALORE',
                [('in', 'fastq.reads'), ('out', 'fastq.reads[trimmed]')], '9 settled', ports=ps)
         + node(gx(1), YM, 'STAR_ALIGN',
                [('in', 'fastq.reads[trimmed]'), ('out', 'alignment.bam')], '14 settled',
                tier='meas', ports=ps))
    sv = ('        <svg style="position:absolute; inset:0;" width="100%" height="100%" aria-hidden="true">\n'
          '          <g fill="none" stroke="#2C3E45" stroke-width="1.5" stroke-linejoin="miter">\n'
          '            ' + wire((16 + SW, YS + SH/2), (inn(0), YM + SPINE), 'many') + '\n'
          '            ' + wire((out(0), YM + SPINE), (inn(1), YM + SPINE), 'many') + '\n'
          '          </g>\n        </svg>\n')
    note = ('        <div style="position:absolute; left:22px; top:22px; max-width:430px;'
            ' background:rgba(12,18,22,.62); border:1px solid #172025; padding:13px 16px;">\n'
            '          <div class="lb" style="letter-spacing:.12em; padding-bottom:8px;">'
            'A catalogue, not a session</div>\n'
            '          <div style="font-size:12px; color:#889699; line-height:1.6;">Four stops '
            'drawn together so they can be compared. Only one is ever on screen at a time, and '
            'none of them is a panel &mdash; a refusal that wears the same border as a question '
            'reads as something you can answer.</div>\n        </div>\n')

    rail_html = rail(
        notice('&#9675;', '#6CB7FF', 'Working on it',
               'Sent to <span class="m" style="font-size:11px;">' + S['model'] + '</span>. '
               'The canvas is still yours &mdash; move things, open a step, nothing is locked.'
               '<span class="m cur" style="color:#6CB7FF; padding-left:4px;">&#9608;</span>',
               foot='<span class="no">Stop waiting</span>', tick='wait')
        + notice('&#9679;', '#E3674E', 'It would not answer, and it was right not to',
                 'No role in the registry describes <span class="m" style="font-size:11px;">'
                 'convert FASTQ to FASTA</span>. Nothing was guessed. You can name the role '
                 'yourself, or propose it as a new one for a curator to approve.',
                 foot='<span class="go">Choose a role</span><span class="no">Propose a new role</span>',
                 tick='open', delay=50)
        + notice('&#9633;', '#C1B508', 'This answer is out of date',
                 'The registry moved while the question was open &mdash; '
                 '<span class="m" style="font-size:11px;">' + S['registry'] + '</span> is not '
                 'what these two candidates came from. Nothing was applied.',
                 foot='<span class="go">Ask again</span><span class="no">Show what changed</span>',
                 tick='wait', delay=100)
        + notice('&#9679;', '#E3674E', 'The model did not come back',
                 'The turn failed and nothing changed. Your pipeline is exactly as it was four '
                 'steps ago, and it is saved.',
                 foot='<span class="go">Try again</span><span class="no">Carry on by hand</span>',
                 tick='open', delay=150)
        + notice('&#9675;', '#67757A', 'No model is configured here',
                 'Build and Spawn need one. Everything else works: draw the pipeline yourself, '
                 'and the engine settles every step it can prove.',
                 foot='<span class="no">How to configure one</span>', delay=200),
        composer=False)

    body = cols(canvas(sv + g + note, dim=True, mini=False), rail_html)
    write('LivingTrouble', body,
          header_html=header('<span style="color:#C1B508;">waiting</span> &middot; '
                             'saved 2m ago', run=False))


# ══════════════════════════════════════════════════════════════════════════════════════════
#  9. HARD CONTENT — 15 steps, a contract id that does not fit, four ports, a long reason
# ══════════════════════════════════════════════════════════════════════════════════════════
# **Ten columns, because that is what a fifteen-step pipeline IS.** The first version wrapped
# the chain onto three rows to make it fit, which put a wire running RIGHT TO LEFT on a canvas
# whose first law is left-to-right — `dag-core` does layered layout and never produces one.
# The second shrank it to fit and every label went with it.
#
# **So the board shows the honest answer: you pan.** Four columns at 1:1, the minimap saying
# where you are, and the transcript carrying all fifteen. That is the finding this board is
# for — beyond about six steps the canvas is where you look at ONE PART of a pipeline and the
# conversation is where you read the whole of it.
DENSE = [
    ('CAT_FASTQ', 0, 0), ('FASTQC_RAW', 0, 1), ('UMITOOLS_EXTRACT', 1, 0),
    ('TRIMGALORE', 2, 0), ('FASTQC_TRIM', 2, 1), ('BBMAP_BBSPLIT', 3, 0),
    ('SORTMERNA', 4, 0), ('STAR_ALIGN', 5, 0), ('SAMTOOLS_SORT', 6, 0),
    ('SAMTOOLS_INDEX', 6, 1), ('UMITOOLS_DEDUP', 7, 0), ('SUBREAD_FEATURECOUNTS', 8, 0),
    ('STRINGTIE_STRINGTIE', 8, 1), ('QUALIMAP_RNASEQ', 9, 1), ('MULTIQC', 9, 0),
]
CHAIN = ['CAT_FASTQ', 'UMITOOLS_EXTRACT', 'TRIMGALORE', 'BBMAP_BBSPLIT', 'SORTMERNA',
         'STAR_ALIGN', 'SAMTOOLS_SORT', 'UMITOOLS_DEDUP', 'SUBREAD_FEATURECOUNTS', 'MULTIQC']
BRANCH = [('CAT_FASTQ', 'FASTQC_RAW'), ('TRIMGALORE', 'FASTQC_TRIM'),
          ('SAMTOOLS_SORT', 'SAMTOOLS_INDEX'), ('SUBREAD_FEATURECOUNTS', 'STRINGTIE_STRINGTIE'),
          ('UMITOOLS_DEDUP', 'QUALIMAP_RNASEQ')]

def dense_minimap(seen):
    """Fifteen marks and a viewport box. The minimap is the only thing on the page that
    answers *where am I*, which is `impl-settled`'s whole reason for deleting the steps list."""
    marks = ''
    for n, c, r in DENSE:
        x, y = 8 + c * 13, 14 + r * 14
        col = ('#E3674E' if n == 'SUBREAD_FEATURECOUNTS' else
               '#C1B508' if n in ('STAR_ALIGN', 'SORTMERNA') else
               '#3E525A' if n in seen else '#253239')
        style = 'border:1px dashed' if n == 'MULTIQC' else 'border:1px solid'
        marks += (f'          <div style="position:absolute; left:{x}px; top:{y}px; width:9px;'
                  f' height:5px; {style} {col};"></div>\n')
    return ('        <div style="position:absolute; right:18px; bottom:18px; width:146px;'
            ' height:58px; border:1px solid #1B262B; background:rgba(8,13,16,.82); z-index:3;">\n'
            + marks +
            '          <div style="position:absolute; left:47px; top:6px; width:57px;'
            ' height:46px; border:1px solid #6CB7FF; background:rgba(108,183,255,.06);"></div>\n'
            '        </div>\n')

def board_dense():
    """**A design that works only on five short boxes is not done.** Fifteen steps, the longest
    contract id in the registry, a five-port signature, and a reason that runs to four lines."""
    pos = {n: (60 + c * PITCH, 150 + r * 250) for n, c, r in DENSE}
    seen = {n for n, _, _ in DENSE[:11]}
    sv = ('        <svg style="position:absolute; inset:0;" width="3000" height="100%" aria-hidden="true">\n'
          '          <g fill="none" stroke="#2C3E45" stroke-width="1.5" stroke-linejoin="miter">\n')
    for a, b in zip(CHAIN, CHAIN[1:], strict=False):
        (ax, ay), (bx, by) = pos[a], pos[b]
        sv += ('            ' + wire((ax + NW, ay + SPINE), (bx, by + SPINE),
                                     'gather' if b == 'MULTIQC' else 'many') + '\n')
    for a, b in BRANCH:
        (ax, ay), (bx, by) = pos[a], pos[b]
        sv += '            ' + wire((ax + NW, ay + SPINE), (bx, by + SPINE), 'many',
                                    bend=bx - 34) + '\n'
    sv += '          </g>\n        </svg>\n'
    g = ''.join(node(x, y, n, [('in', '&hellip;'), ('out', '&hellip;')],
                     '' if n == 'MULTIQC' else 'settled',
                     tier=('open' if n == 'SUBREAD_FEATURECOUNTS' else
                           'meas' if n in ('STAR_ALIGN', 'SORTMERNA') else 'ok'),
                     by=('model' if n == 'SORTMERNA' else 'hum' if n == 'BBMAP_BBSPLIT' else 'res'),
                     ghost=(n == 'MULTIQC'),
                     ports=[('in', SPINE, 'many'),
                            ('out', SPINE, 'gather' if n == 'MULTIQC' else 'many')])
                for n, (x, y) in pos.items())

    sig = ''.join(f'<div style="display:flex; gap:7px; padding-bottom:3px;">'
                  f'<span class="m" style="font-size:9.5px; color:{c};">{d}</span>'
                  f'<span class="m" style="font-size:10.5px; color:#7E8F95;">{tp}</span></div>'
                  for d, tp, c in (('&#9666;', 'alignment.bam[sorted]', '#4A5C64'),
                                   ('&#9666;', 'genome.annotation.gtf', '#4A5C64'),
                                   ('&#9666;', 'alignment.bam.bai', '#4A5C64'),
                                   ('&#9656;', 'counts.matrix', '#3E5058'),
                                   ('&#9656;', 'counts.summary', '#3E5058')))

    rail_html = rail(
        receipt('six steps above &mdash; scroll up, or click a step on the canvas', 'res')
        + ''.join(done(n, 'model' if n == 'SORTMERNA' else 'hum' if n == 'BBMAP_BBSPLIT' else 'res',
                       f'step {i+1}')
                  for i, (n, _, _) in enumerate(DENSE[5:11], start=5))
        + block('Step 12 &mdash; count the reads per gene',
                '<div class="m" style="font-size:10px; color:#455257; line-height:1.5;'
                ' padding-bottom:10px; overflow-wrap:anywhere;">'
                'nf-core/subread/featurecounts@2.0.6+build3.rnaseq-longname</div>'
                '<div style="font-size:12.5px; color:#889699; line-height:1.5;'
                ' padding-bottom:10px;">Two tools produce a counts matrix and no tier-3 rule '
                'separates them on anything I have measured, so this is a real choice rather '
                'than a default dressed up as one.</div>' + sig,
                foot='<span class="go">Add it</span><span class="no">Show 2 alternatives</span>',
                right='tier 4', tick='open', delay=60))

    body = cols(canvas(sv + g, pan=940, mini=dense_minimap(seen)), rail_html)
    write('LivingDense', body,
          header_html=header('building &middot; 11 of 15 steps &middot; '
                             '<span style="color:#E3674E;">1 needs you</span>'))


# ══════════════════════════════════════════════════════════════════════════════════════════
# 10. NARROWER, AND STILL — the layout at three widths, and every movement switched off
# ══════════════════════════════════════════════════════════════════════════════════════════
def frame(x, y, w, h, label, note, parts):
    """A wireframe of the shell at one width. Boxes and labels — this board argues about
    ARRANGEMENT, and drawing it in full fidelity would hide that behind the content."""
    out = (f'      <div style="position:absolute; left:{x}px; top:{y}px; width:{w}px;">\n'
           f'        <div style="display:flex; align-items:baseline; gap:10px; padding-bottom:9px;">\n'
           f'          <span class="m" style="font-size:11px; color:#DFE6E6;">{label}</span>\n'
           f'          <span style="font-size:11.5px; color:#67757A;">{note}</span></div>\n'
           f'        <div style="position:relative; width:{w}px; height:{h}px;'
           f' border:1px solid #1E282C; background:rgba(12,18,22,.62);">\n')
    for px, py, pw, ph, name, kind in parts:
        style = {'chrome': 'background:#0E1418; border:1px solid #172025;',
                 'canvas': 'border:1px solid #253239;',
                 'talk':   'border:1px solid #1E3A4E; background:#0B141A;',
                 'cmp':    'border:1px solid #1E3A4E;'}[kind]
        out += (f'          <div style="position:absolute; left:{px}px; top:{py}px;'
                f' width:{pw}px; height:{ph}px; {style} display:flex; align-items:center;'
                f' justify-content:center;">'
                f'<span class="m" style="font-size:9px; letter-spacing:.08em;'
                f' color:{"#6CB7FF" if kind in ("talk","cmp") else "#5D6C71"};">{name}</span></div>\n')
    return out + '        </div>\n      </div>\n'

def board_quiet():
    w1180 = frame(30, 92, 470, 300, '1180', 'the rail narrows to 360; nothing stacks yet', [
        (0, 0, 470, 26, 'ONE STRIP', 'chrome'),
        (0, 34, 322, 232, 'CANVAS', 'canvas'),
        (330, 34, 140, 196, 'CONVERSATION', 'talk'),
        (330, 238, 140, 28, 'COMPOSER', 'cmp')])
    w900 = frame(548, 92, 358, 300, '900', 'the stack point &mdash; conversation FIRST', [
        (0, 0, 358, 26, 'ONE STRIP', 'chrome'),
        (0, 34, 358, 132, 'CONVERSATION', 'talk'),
        (0, 172, 358, 28, 'COMPOSER', 'cmp'),
        (0, 208, 358, 58, 'CANVAS &mdash; 260px, scrolls', 'canvas')])
    wnar = frame(934, 92, 255, 300, '640', 'the floor. Below this is a different product.', [
        (0, 0, 255, 26, 'ONE STRIP', 'chrome'),
        (0, 34, 255, 150, 'CONVERSATION', 'talk'),
        (0, 190, 255, 26, 'COMPOSER', 'cmp'),
        (0, 224, 255, 42, 'CANVAS', 'canvas')])

    why = '''      <div style="position:absolute; left:30px; top:436px; width:1160px;
                  border-top:1px solid #172025; padding-top:16px; display:grid;
                  grid-template-columns:1fr 1fr; gap:34px;">
        <div>
          <div class="lb" style="padding-bottom:10px;">Why the stack point is 1000, not 1180</div>
          <div style="font-size:12.5px; color:#889699; line-height:1.6;">
            The canvas rules put the breakpoints at 1180 and 760, and say not to add a third
            without a piece of content that needs one. This has one: a proposal card carries two
            actions side by side and the canvas beside it carries a 172px column. Under about
            1000px those cannot both exist, and at 1180 they still can &mdash; so the rail
            narrows there and stacks lower down.
            <span style="display:block; padding-top:9px;">
            <b style="font-weight:500; color:#DFE6E6;">The conversation goes on top.</b> It is
            where the next thing to do lives. Stacking canvas-first puts an empty graph above
            the only actionable thing on the page.</span>
            <span style="display:block; padding-top:9px;">
            A rail STACKS, it does not overlay &mdash; an overlay drawer hides the graph the
            conversation is talking about.</span></div>
        </div>
        <div>
          <div class="lb" style="padding-bottom:10px;">With every movement switched off</div>
          <div style="font-size:12.5px; color:#889699; line-height:1.6;">
            <b style="font-weight:500; color:#DFE6E6;">Nothing here is only an animation.</b>
            A proposal arriving is a dashed node and a card; accepted, it is a solid node and a
            collapsed row. Both are states, and both are true in a screenshot.
            <span style="display:block; padding-top:9px;">
            <b style="font-weight:500; color:#DFE6E6;">A settling node does not travel.</b> It
            appears at the coordinates the blueprint already knew, wearing a link-coloured edge
            for as long as it is the newest thing. Reduced motion drops the fade, keeps the edge.</span>
            <span style="display:block; padding-top:9px;">
            <b style="font-weight:500; color:#DFE6E6;">A wire does not draw itself.</b>
            <span class="m" style="font-size:11px;">grow-x</span> is first paint only; with
            motion off the wire is simply there.</span>
            <span style="display:block; padding-top:9px;">
            <b style="font-weight:500; color:#DFE6E6;">Spawn does not replay.</b> The staged
            reveal is capped and runs once, on first arrival. On reload the graph is complete
            immediately &mdash; and with reduced motion it is complete the first time too.</span></div>
        </div>
      </div>
'''

    five = '''      <div style="position:absolute; left:30px; top:706px; width:1160px;
                  border-top:1px solid #172025; padding-top:16px;">
        <div class="lb" style="padding-bottom:11px;">Six domain events, five existing movements,
          no new curve</div>
        <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px 30px;">
'''
    for ev, mv, why_ in (
            ('proposal_shown', 'settle 200ms', 'the card, and the ghost on the canvas'),
            ('proposal_accepted', 'settle 200ms', 'the node at its blueprint position'),
            ('edge_committed', 'grow-x 520ms', 'first paint only, keyed on the edge&rsquo;s identity'),
            ('parameter_committed', 'settle 200ms', 'the value row, and its line in the artifact'),
            ('proposal_rejected', '&mdash;', 'the ghost is removed. Nothing moves to say so'),
            ('validation_changed', '&mdash;', 'the status line changes. Numbers never tween')):
        five += (f'          <div style="display:flex; flex-direction:column; gap:3px;">'
                 f'<span class="m" style="font-size:10.5px; color:#DFE6E6;">{ev}</span>'
                 f'<span class="m" style="font-size:10px; color:#6CB7FF;">{mv}</span>'
                 f'<span style="font-size:11.5px; color:#889699; line-height:1.4;">{why_}</span>'
                 f'</div>\n')
    five += '        </div>\n      </div>\n'

    body = (f'  <div style="position:relative; height:880px;">\n'
            f'    <div style="padding:22px 30px 0;">\n{NAV}    </div>\n'
            f'{w1180}{w900}{wnar}{why}{five}  </div>\n')
    write('LivingQuiet', body)



# ══════════════════════════════════════════════════════════════════════════════════════════
# 11. DONE — the artifact is the second view of the canvas, and it grew as you answered
# ══════════════════════════════════════════════════════════════════════════════════════════
YML = [
    ('# pipeline.yml — rnaseq-counts', 'c'), ('schema_version: 6', ''), ('', ''),
    ('goal:', 'k'),
    ('  have:  [fastq.reads[paired]]', ''), ('  want:  [counts.matrix]', ''),
    ('  organism: mus_musculus', ''),
    ('  # you chose this on 2026-09-07', 'c'),
    ('  grouping: paired', 'n'), ('', ''),
    ('steps:', 'k'),
    ('  - process: SUBREAD_FEATURECOUNTS', ''),
    ('    contract: nf-core/subread/featurecounts@2.0.6', ''),
    ('    why:', 'k'),
    ('      tier: 4', 'o'),
    ('      by: human', 'n'),
    ('      reason: >-', ''),
    ('        Two tools produce counts.matrix and no rule', 'n'),
    ('        separates them. You chose this one.', 'n'),
    ('    settings:', 'k'),
    ('      - name: feature_type', 'n'),
    ('        value: exon', 'n'),
    ('        via: task.ext.args', 'n'),
    ('        why: { tier: 4, by: human }', 'n'),
    ('      - name: strandedness', ''),
    ('        value: reverse', ''),
    ('        via: meta', ''),
    ('        why: { tier: 3, rule: R11, premise: 400k reads }', ''),
]

def board_done():
    """**The second view of the canvas is the ARTIFACT, not a list** (`impl-settled`), so the
    living pipeline needs no new surface for its YAML — the existing toggle already leads
    there. What is new is that it GREW while you answered, and the lines your last answer wrote
    are the ones marked."""
    rows = ''
    for line, kind in YML:
        col = {'c': '#3E5058', 'k': '#6CB7FF', 'o': '#E3674E', 'n': '#DFE6E6', '': '#889699'}[kind]
        mark = ('        <div style="position:absolute; left:0; width:2px; height:19px;'
                ' background:#6CB7FF;"></div>\n' if kind == 'n' else '')
        bg = ' background:rgba(108,183,255,.05);' if kind == 'n' else ''
        rows += (f'        <div style="position:relative; height:19px; padding-left:18px;{bg}">'
                 f'{mark}<span class="m" style="font-size:11px; color:{col};'
                 f' white-space:pre;">{line}</span></div>\n')
    chips = ''.join(
        f'<span class="m lift" style="font-size:10px; letter-spacing:.06em; padding:5px 10px;'
        f' border:1px solid {"#1E3A4E" if on else "#1E282C"};'
        f' color:{"#6CB7FF" if on else "#67757A"}; cursor:pointer;">{w}</span>'
        for w, on in (('goal', True), ('steps', False), ('settings', False),
                      ('layers', False), ('gate', False)))
    art = (f'      <div class="cv" style="position:relative; overflow:hidden;'
           f' border-top:1px solid #141C20;">\n'
           f'        <div style="position:absolute; inset:0; padding:18px 26px;'
           f' display:flex; flex-direction:column; gap:14px;">\n'
           f'        <div style="display:flex; align-items:center; gap:7px;">{chips}'
           f'<span class="m" style="font-size:10px; color:#455257; margin-left:auto;">'
           f'6 lines changed &middot; not kept yet</span></div>\n'
           f'        <div style="flex:1; overflow:hidden;">\n{rows}        </div>\n'
           f'        </div>\n      </div>\n')

    rail_html = rail(
        done('SUBREAD_FEATURECOUNTS', 'res', 'step 5')
        + done('feature type &rarr; exon', 'hum')
        + done('MULTIQC', 'res', 'step 7')
        + block('Seven steps, nothing open',
                '<div style="font-size:12.5px; color:#889699; line-height:1.55;'
                ' padding-bottom:12px;">Every value is settled and every one carries the reason '
                'it holds. You can run it now, or keep going.</div>'
                + row('Settled', '61 values', '#DFE6E6', 'By the engine, from declared data.')
                + row('Measured', '4 values', '#C1B508', 'Tier 3 &mdash; check the premise.')
                + row('Yours', '2 values', '#DFE6E6', 'The grouping, and the feature type.')
                + row('A model', 'nothing', '#889699',
                      'No tier-4 choice needed one on this pipeline.'),
                foot='<span class="go">Run it</span><span class="no">Keep as a draft</span>',
                right='complete', tick='res', delay=60)
        + says('Running asks where your data is. That question belongs to the run &mdash; the '
               'pipeline holds a shape, and the same one takes different data without an edit.', 120))

    body = cols(art, rail_html)
    write('LivingDone', body,
          header_html=header('7 of 7 steps &middot; '
                             '<span style="color:#10AA91;">valid</span> &middot; '
                             'nothing needs you', view='artifact'))


board_open()
board_goal()
board_build()
board_choose()
board_param()
board_collect()
board_spawn()
board_trouble()
board_dense()
board_quiet()
board_done()
