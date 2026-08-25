"""The /runs board — a dashboard, not a stack of rows.

Reuses `build.py`'s chrome verbatim rather than restating it: HEAD carries the shared
tokens, `nav()` draws the same bar, and `.panel` / `.strip` / `.well` / `.lbl` / `.th`
are the same classes every W2 artboard uses. Only the board's own content is new.

`build.py` writes its artboards at import, so only its definitions are executed here —
everything above the first `write_text` call.
"""
import pathlib

# **Bound by name, not spilled into globals.** `exec(..., globals())` works and leaves every
# imported name invisible to a linter — six `F821`s for functions that plainly exist. Naming
# what is borrowed is also the honest list of how much of `build.py` this file leans on.
_shared: dict = {}
_src = pathlib.Path("../w2-mockups/build.py").read_text()
exec(_src[: _src.index('pathlib.Path("Main.dc.html")')], _shared)  # noqa: S102
page, nav, DOT = _shared["page"], _shared["nav"], _shared["DOT"]

PEA, MEASURED, UNDECIDED = "var(--pea)", "var(--measured)", "var(--undecided)"

# Fourteen days, oldest first: (succeeded, failed). Drawn from what this instance has
# actually run — 24 Aug is the heavy day, and the two quiet days are real.
DAYS = [(2, 0), (3, 0), (0, 0), (4, 1), (5, 0), (3, 2), (6, 0), (2, 1), (0, 0),
        (5, 0), (7, 1), (4, 0), (6, 2), (9, 5)]


def band():
    """The board's header. Same `--surface-2` shelf every run page opens with, so the
    two screens are the same product rather than two designs."""
    return '''  <div style="flex:0 0 auto; padding:16px 24px 14px; background:var(--surface-2);
       border-bottom:1px solid var(--line); box-shadow:var(--e1); position:relative; z-index:2;">
    <div style="display:flex; align-items:baseline; gap:14px;">
      <span class="mono" style="font-size:26px; letter-spacing:-.01em;">runs</span>
      <span style="font-size:12.5px; color:var(--ink-2);">
        every pipeline this instance has executed</span>
      <span class="chip" style="margin-left:auto; padding:5px 11px;
            border:1px solid var(--line-2); border-radius:var(--r); background:var(--surface);
            font-size:12.5px; color:var(--ink-2);">last 14 days
        <span style="color:var(--ink-3);">&#9662;</span></span>
    </div>
  </div>
'''


def tile(label, figure, colour, sub, bar_pct=None, bar_col=None):
    """One stat tile. The figure is the tile — everything else is subordinate to it."""
    well = ''
    if bar_pct is not None:
        well = ('<span class="well" style="height:7px; margin-top:9px;">'
                '<i style="width:%d%%; background:%s;"></i></span>' % (bar_pct, bar_col))
    return '''    <div class="card" style="padding:13px 15px 14px; display:flex; flex-direction:column;">
      <span class="lbl">%s</span>
      <span class="mono" style="font-size:30px; line-height:1.15; margin-top:7px;
            letter-spacing:-.02em; color:%s;">%s</span>
      <span style="font-size:11.5px; color:var(--ink-3); margin-top:3px;">%s</span>%s
    </div>
''' % (label, colour, figure, sub, well)


def activity():
    """Runs per day, fourteen days, succeeded over failed.

    **A stacked column, because the question is a magnitude over time** and the two parts
    sum to something real — how much this instance ran. Status colours, both named in the
    legend, so identity is never colour alone. Only the tallest column is labelled: a
    number over every bar is the noise the shape already carries.
    """
    top = max(s + f for s, f in DAYS)
    cols = []
    for i, (ok, bad) in enumerate(DAYS):
        total = ok + bad
        label = ('<span class="mono" style="font-size:10px; color:var(--ink-2);">%d</span>'
                 % total) if total == top else '<span style="height:13px;"></span>'
        # A 2px gap between the two fills, so the boundary is a gap and never a hairline
        # that reads as a third value.
        stack = ''
        if bad:
            stack += ('<i style="height:%dpx; background:%s; border-radius:3px 3px 0 0;">'
                      '</i><i style="height:2px; background:var(--surface);"></i>'
                      % (max(3, round(bad / top * 92)), UNDECIDED))
        if ok:
            stack += ('<i style="height:%dpx; background:%s; border-radius:%s;"></i>'
                      % (max(3, round(ok / top * 92)), PEA,
                         '0 0 3px 3px' if bad else '3px'))
        if not total:
            stack = '<i style="height:2px; background:var(--line);"></i>'
        # **The axis names four days, not fourteen.** A tick under every column is
        # fourteen numbers nobody reads; four is enough to place any bar in the month.
        tick = ('%d Aug' % (11 + i)) if i % 4 == 3 else '&nbsp;'
        cols.append(
            '<div style="flex:1 1 0; display:flex; flex-direction:column; align-items:center; '
            'gap:4px; justify-content:flex-end;">%s'
            '<div style="width:100%%; max-width:24px; display:flex; flex-direction:column; '
            'justify-content:flex-end;">%s</div>'
            '<span class="mono" style="font-size:9.5px; color:var(--ink-3); '
            'white-space:nowrap;">%s</span></div>'
            % (label, stack, tick))
    legend = (
        '<span style="display:flex; align-items:center; gap:13px; margin-left:auto;">'
        '<span style="display:flex; align-items:center; gap:5px;" class="lbl">'
        '<i style="width:8px; height:8px; border-radius:2px; background:%s;"></i>succeeded</span>'
        '<span style="display:flex; align-items:center; gap:5px;" class="lbl">'
        '<i style="width:8px; height:8px; border-radius:2px; background:%s;"></i>failed</span>'
        '</span>' % (PEA, UNDECIDED))
    return '''    <div class="card" style="padding:13px 15px 11px; display:flex; flex-direction:column;">
      <div style="display:flex; align-items:baseline; gap:12px;">
        <span class="lbl">runs per day</span>%s
      </div>
      <div style="flex:1 1 auto; display:flex; align-items:flex-end; gap:3px; margin-top:8px;
           min-height:0; border-bottom:1px solid var(--line); padding-bottom:0;">%s</div>
      <div style="height:3px;"></div>
    </div>
''' % (legend, ''.join(cols))


def strip_filters(count):
    def sel(name, value):
        return ('<span style="display:flex; align-items:center; gap:6px;" class="lbl">%s'
                '<span class="chip" style="padding:4px 9px; border:1px solid var(--line);'
                ' border-radius:var(--r); background:var(--surface); font-size:11.5px;'
                ' color:var(--ink-2); text-transform:none; letter-spacing:0;">%s'
                ' <span style="color:var(--ink-3);">&#9662;</span></span></span>'
                % (name, value))
    return ('<div class="strip">%s%s%s'
            '<span class="lbl" style="margin-left:auto;">%s</span></div>'
            % (sel('phase', 'all'), sel('who', 'all'), sel('executor', 'all'), count))


def rhead():
    cols = [("run", ''), ("pipeline", ''), ("phase", ''), ("steps", ''),
            ("elapsed", ''), ("submitted", '')]
    return ('<div style="display:grid; grid-template-columns:%s; gap:18px; '
            'padding:8px 18px 8px 24px; background:var(--surface-2); '
            'border-bottom:1px solid var(--line); box-shadow:var(--e1);">%s</div>'
            % (GRID, ''.join('<span class="th">%s</span>' % c for c, _ in cols)))


GRID = ("minmax(170px,1.1fr) minmax(190px,1.3fr) 128px minmax(150px,1fr) "
        "104px minmax(160px,1fr)")


def rrow(rid, pipeline, phase, colour, done, declared, elapsed, who, when,
         because=None, last=False):
    """One run. **`steps` is a bar and a fraction**, the same pair the overview uses, so a
    board row and a run row say a number the same way."""
    pct = round(done / declared * 100) if declared else 0
    sub = ('<div class="mono" style="font-size:11px; color:%s; margin-top:2px;">%s</div>'
           % (UNDECIDED, because)) if because else ''
    return '''      <div class="row" tabindex="0" style="display:grid; grid-template-columns:%s;
           gap:18px; padding:12px 18px 12px 24px; align-items:center;
           border-bottom:%s;">
        <div><span class="mono" style="font-size:13px;">%s</span>%s</div>
        <span style="font-size:12.5px; color:var(--ink-2);">%s</span>
        <span style="display:flex; align-items:center; gap:7px; font-size:12.5px;
              color:var(--ink-2);">%s %s</span>
        <div style="display:flex; flex-direction:column; gap:4px;">
          <span class="well" style="height:7px;"><i style="width:%d%%; background:%s;"></i></span>
          <span class="mono" style="font-size:11.5px; color:var(--ink-2);">%d of %d</span>
        </div>
        <span class="mono" style="font-size:12.5px; color:var(--ink-2);">%s</span>
        <div style="display:flex; flex-direction:column;">
          <span style="font-size:12.5px; color:var(--ink-2);">%s</span>
          <span style="font-size:11px; color:var(--ink-3);">%s</span>
        </div>
      </div>
''' % (GRID, 'none' if last else '1px solid var(--line)', rid, sub, pipeline,
       DOT % colour, phase, pct, colour, done, declared, elapsed, who, when)


def pager(shown=7, total=49, page=1, pages=7):
    """**A page control, because 49 rows is already more than fits.**

    `1-7 of 49` before the arrows, so the range reads without counting pages — a bare
    `1 / 7` makes you do arithmetic to know whether the run you want is behind you.
    `newest first` stays on the left: the sort is a property of the list, not of the page
    you happen to be standing on.
    """
    def arrow(glyph, enabled):
        return ('<span class="chip" style="padding:3px 9px; border:1px solid var(--%s);'
                ' border-radius:var(--r); background:var(--surface); font-size:12.5px;'
                ' color:var(--%s);">%s</span>'
                % ('line-2' if enabled else 'line',
                   'ink-2' if enabled else 'line-2', glyph))

    def num(n):
        on = n == page
        return ('<span class="chip" style="min-width:24px; text-align:center; padding:3px 7px;'
                ' border-radius:var(--r); font-family:var(--font-data); font-size:12px; %s">'
                '%d</span>'
                % ('background:var(--surface); box-shadow:var(--e1); color:var(--ink);'
                   ' font-weight:600;' if on else 'color:var(--ink-3);', n))

    lo = (page - 1) * shown + 1
    numbers = (''.join(num(n) for n in (1, 2, 3))
               + '<span class="lbl" style="padding:0 3px;">&hellip;</span>' + num(pages))
    return ('      <div style="margin-top:auto; padding:9px 24px;'
            ' border-top:1px solid var(--line); background:var(--surface-2);'
            ' display:flex; gap:16px; align-items:center;">\n'
            '        <span class="lbl">newest first</span>\n'
            '        <span style="margin-left:auto; display:flex; align-items:center;'
            ' gap:12px;">\n'
            '          <span class="lbl">%d&ndash;%d of %d</span>\n'
            '          <span style="display:flex; align-items:center; gap:3px;">'
            '%s%s%s</span>\n'
            '        </span>\n'
            '      </div>\n'
            % (lo, lo + shown - 1, total, arrow('&#8249;', page > 1), numbers,
               arrow('&#8250;', page < pages)))


TILES = ''.join([
    tile("needs you", "3", UNDECIDED, "failed, and nobody has looked"),
    tile("running now", "2", MEASURED, "STAR_ALIGN, TRIMGALORE"),
    tile("succeeded &middot; 14 days", "86%", "var(--ink)", "42 of 49 runs", 86, PEA),
    tile("typical run", "4m12s", "var(--ink)", "p95 &nbsp;11m30s"),
])

ROWS = ''.join([
    rrow("4499bf9e", "rna-seq spine", "succeeded", PEA, 4, 4, "38s",
         "operator", "today, 22:13"),
    rrow("0d3a4e3d", "rna-seq spine", "failed", UNDECIDED, 0, 5, "3s",
         "operator", "today, 18:24",
         because="STAR_GENOMEGENERATE &middot; exit 127"),
    rrow("85bbe6a0", "rna-seq spine", "running", MEASURED, 3, 5, "7m12s",
         "operator", "today, 20:20"),
    rrow("e724d624", "rna-seq spine", "succeeded", PEA, 4, 4, "41s",
         "operator", "today, 19:40"),
    rrow("162ca5aa", "rna-seq &middot; trimmed", "failed", UNDECIDED, 1, 5, "1m04s",
         "replay", "today, 17:43",
         because="TRIMGALORE &middot; exit 1"),
    rrow("71d360cd", "rna-seq spine", "succeeded", PEA, 4, 4, "39s",
         "operator", "today, 17:56"),
    rrow("aaf4cf6c", "rna-seq spine", "succeeded", PEA, 4, 4, "44s",
         "operator", "yesterday, 17:32", last=True),
])

BODY = '''  <div style="flex:1 1 auto; padding:16px 24px 22px; min-height:0; display:flex;
       flex-direction:column; gap:14px;">
    <div style="flex:0 0 auto; display:grid;
         grid-template-columns:repeat(4, minmax(0, 1fr)) minmax(0, 2.4fr); gap:14px;
         height:172px;">
%s%s    </div>

    <section class="panel" style="flex:1 1 auto; min-height:0;">
      %s
      %s
      <div style="flex:1 1 auto; overflow:hidden;">
%s      </div>
%s    </section>
  </div>
''' % (TILES, activity(), strip_filters("49 runs"), rhead(), ROWS, pager())

pathlib.Path("Main.dc.html").write_text(
    page(nav("Runs", sub=[("Board", True), ("This run", False)]) + band() + BODY))
print("built: Main.dc.html")
