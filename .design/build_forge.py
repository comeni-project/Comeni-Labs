# Every Forge board is composed from ONE fixture and ONE shell.
#
# §8.6: "Generate them from one shared fixture so counts, status, graph, and activity cannot
# contradict one another." That is the whole reason this file exists rather than six hand-written
# boards — the overview says 5 ready for review, the work queue lists five rows, and the
# adaptation board's revision is the one the review board approves. Change a number once.
#
# The palette is `frontend/src/tokens.css`, lifted by value rather than by name: an artboard
# cannot resolve a CSS custom property from the app, and a second set of hexes that drifted
# would be a second theme, which §8 forbids.
import json
import pathlib

OUT = pathlib.Path(__file__).parent

# **Measured, not guessed.** Every board first shipped 100-350px taller than its content,
# so each artboard carried a band of empty paper that reading the HTML could never show.
# These are Chrome reporting each board's deepest laid-out element; re-measure when a
# board grows rather than adding slack.
HEIGHT = {'overview': 848, 'catalogue': 772, 'work': 1020, 'adaptation': 646, 'review': 691, 'review_changes': 757, 'review_code': 854, 'review_params': 982, 'answer_hole': 968}

# ── the palette, from frontend/src/tokens.css ─────────────────────────────────────────
PAPER, SURF, NODE = "#080B0D", "#0E1418", "#0C1216"
INK, INK2, INK3, INK4 = "#DFE6E6", "#889699", "#67757A", "#455257"
LINE, LINE2, SOFT = "#172025", "#2A3438", "#121A1D"
# **Prose never uses INK4.** #455257 on #0C1216 is about 2.5:1 — under AA, and it was
# carrying hint lines, footnotes and "version unresolved" until a rendered board was
# actually looked at. INK4 is for rules and separators; NOTE is the dimmest readable ink.
NOTE = INK3
PEA, MEAS, FAULT, RUN, LINK = "#10AA91", "#C1B508", "#E3674E", "#BD6DCD", "#6CB7FF"
NODELINE, RAIL, PORTLINE = "#253239", "#2C3E45", "#4A5C64"

# ── the one fixture ───────────────────────────────────────────────────────────────────
F = {
    "sources": [
        {
            "name": "nf-core",
            "adapted": 214, "adaptable": 1184, "current": 198, "outdated": 16,
            "in_progress": 8, "discovered": 1184, "unsupported": 0,
            "synced": "14m ago", "stale": False, "error": "",
        },
        {
            "name": "pegi3s",
            "adapted": 31, "adaptable": 191, "current": 27, "outdated": 4,
            "in_progress": 2, "discovered": 195, "unsupported": 4,
            "synced": "2d ago", "stale": True,
            "error": "MI0104 — the pegi3s catalogue could not be read",
        },
    ],
    "flow": {"discovered": 1379, "scaffold": 2, "ai_active": 1, "ai_waiting": 6,
             "review": 5, "registry": 245},
    "attention": {"review": 5, "failed": 2, "outdated": 20},
    "catalogue": [
        ("review", "prodigal", "pegi3s", "Predicts protein-coding genes in bacterial and "
         "archaeal genomes", "digest", "container + prose", "Review"),
        ("open", "fastqc", "nf-core", "Quality control checks on raw sequence data",
         "0.12.1", "Nextflow + metadata", "Adapt"),
        ("open", "clustalw", "pegi3s", "Multiple sequence alignment for DNA or proteins",
         "version unresolved", "container + prose", "Adapt"),
        ("done", "samtools/sort", "nf-core", "Sorts a BAM file by coordinate or by read name",
         "1.21", "Nextflow + metadata", "Open"),
        ("done", "star/align", "nf-core", "Spliced transcript alignment to a reference",
         "2.7.11b", "Nextflow + metadata", "Open"),
        ("open", "subread/featurecounts", "nf-core",
         "Counts reads against genomic features — a very long display name that has to wrap "
         "or truncate without pushing the action column off the row", "2.0.6",
         "Nextflow + metadata", "Adapt"),
    ],
    "work": {
        "active": ("pegi3s / prodigal", "analysis · mapping semantic ports", "01:42"),
        "queued": [("nf-core / bcftools/mpileup", 1), ("pegi3s / seda", 2)],
        "review": [
            ("nf-core / samtools/sort", "8/8", "rev 2", "12m"),
            ("nf-core / hisat2/align", "8/8", "rev 1", "1h"),
            ("pegi3s / clustalw", "6/8", "rev 3", "4h"),
            ("nf-core / trimgalore", "8/8", "rev 1", "2d"),
            ("nf-core / multiqc", "7/8", "rev 2", "3d"),
        ],
        "changes": [("pegi3s / prodigal", "state on the output is a guess", "R. Correia"),
                    ("nf-core / bwa/mem", "second port has no evidence", "M. Silva")],
        "failed": [("pegi3s / orphanimage", "MI0105 — the source could not be read")],
    },
    "adaptation": {
        "tool": "pegi3s / prodigal", "state": "GENERATING", "revision": 1,
        "source_digest": "7be1", "registry_digest": "41a9",
        "facts": 7, "holes": 9, "evidence": 18,
        "activity": [("10:31", "queued", "position 1 of 3"),
                     ("10:32", "claimed", "worker:abc123"),
                     ("10:32", "generating", "forge.analysis.v1")],
    },
    "review": {
        "tool": "nf-core / samtools/sort", "revision": 2, "files": 4,
        "checks": (8, 8), "unresolved": 0,
        "derived": 12, "proposed": 7, "human": 0,
        "consumes": ("alignment.bam", "unsorted"),
        "produces": ("alignment.bam", "coordinate_sorted"),
        "process": "SAMTOOLS_SORT", "params": 3,
        "rungs": [("contract loads", True), ("conforms to module", True),
                  ("Nextflow parses", True), ("ports coherent", True)],
        "chat": [("curator", "Why coordinate_sorted rather than queryname?"),
                 ("model", "The command line runs `samtools sort` with no `-n`, which is "
                  "coordinate order — E014, and main.nf:27.")],
    },
    # ── the code a reviewer is actually approving ─────────────────────────────────────
    # Each line carries its ORIGIN, and that is the point of the pane: an nf-core `main.nf`
    # should read as almost entirely `S`, so a block of `A` is loud without anybody being told
    # what to look for. Colour is secondary to the letter — §8, status never by colour alone.
    "contract_yml": [
        ("d", "id: nf-core/samtools/sort@1.21"),
        ("d", "declares: contract"),
        ("d", "kind: binding"),
        ("d", "target: nf-core/samtools/sort"),
        ("", ""),
        ("d", "consumes:"),
        ("s", "  - name: bam"),
        ("a", "    type_id: alignment.bam"),
        ("a", "    states: [unsorted]"),
        ("", ""),
        ("d", "produces:"),
        ("s", "  - name: bam"),
        ("a", "    type_id: alignment.bam"),
        ("a", "    states: [coordinate_sorted]"),
        ("s", "  - name: versions"),
        ("d", "    type_id: profile.yml"),
        ("", ""),
        ("a", "roles: [sort_bam]"),
        ("d", "nf_process: SAMTOOLS_SORT"),
        ("d", "nf_include: modules/nf-core/samtools/sort/main"),
        ("", ""),
        ("d", "provenance:"),
        ("h", "  drafted_by: R. Correia"),
        ("a", "  cite: 10.1093/gigascience/giab008"),
    ],
    "main_nf": [
        ("s", "process SAMTOOLS_SORT {"),
        ("s", "    tag \"$meta.id\""),
        ("s", "    label 'process_medium'"),
        ("", ""),
        ("s", "    container \"community.wave.seqera.io/library/samtools:1.21--…\""),
        ("", ""),
        ("s", "    input:"),
        ("s", "    tuple val(meta), path(bam)"),
        ("s", "    tuple val(meta2), path(fasta)"),
        ("", ""),
        ("s", "    output:"),
        ("s", "    tuple val(meta), path(\"*.bam\"), emit: bam"),
        ("s", "    path \"versions.yml\",              emit: versions"),
        ("", ""),
        ("s", "    script:"),
        ("s", "    def args = task.ext.args ?: ''"),
        ("s", "    def prefix = task.ext.prefix ?: \"${meta.id}\""),
        ("s", "    \"\"\""),
        ("s", "    samtools cat ${bam} | samtools sort \\\\"),
        ("s", "        $args \\\\"),
        ("s", "        -T $prefix \\\\"),
        ("s", "        --threads $task.cpus \\\\"),
        ("s", "        -o ${prefix}.bam##idx##${prefix}.bam.bai \\\\"),
        ("s", "        --write-index -"),
        ("s", "    \"\"\""),
        ("s", "}"),
    ],
    "params": [
        ("compression", "ext.args", "-l 1", "nf-core's own default for a sort step",
         "E007", True),
        ("sort_by_name", "ext.args", "false",
         "the tool documents -n; a rule may vary it per analysis", "E014", True),
        ("threads", "directive", "task.cpus", "set by the executor, never by a user",
         "E002", True),
        ("temp_prefix", "—", "unset",
         "proposed with no route — it would resolve and reach nothing", "", False),
    ],
    "rules": [
        {
            "premise": "library_prep is rrna_depleted and rrna_fraction > 0.10",
            "effect": "require a second sort pass before counting",
            "row": "sort_bam",
            "cite": "10.1186/s13059-016-0940-1",
            "ok": True,
        },
        {
            "premise": "read_length < 50",
            "effect": "prefer hisat2 over star",
            "row": "align_reads",
            "cite": "",
            "ok": False,
        },
    ],
    "hole": {
        "id": "consumes.bam.state",
        "question": "what state is the alignment on this input?",
        "why_open": "a .bam suffix says the container format; whether it is sorted is a "
                    "separate fact and the meta.yml does not state it",
        "hint": "ports.state.v1",
        "answered_by": "ollama/qwen2.5-coder:14b",
        "answered": "unsorted",
        "candidates": [
            ("unsorted", "used by 4 contracts", True),
            ("coordinate_sorted", "used by 9 contracts", False),
            ("queryname_sorted", "used by 2 contracts", False),
            ("deduplicated", "used by 1 contract", False),
        ],
        "evidence": [
            ("E014", "modules/nf-core/samtools/sort/main.nf:27",
             "samtools cat ${bam} | samtools sort $args -T $prefix"),
            ("E007", "modules/nf-core/samtools/sort/meta.yml:12",
             "description: Sorts a BAM file by coordinate or by read name"),
        ],
    },
}


def head(extra: str = "") -> str:
    """One head for six boards. A second copy would be a second theme."""
    return f"""  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap">
  <style>
    *, *::before, *::after {{ box-sizing:border-box; }}
    body {{ margin:0; background:{PAPER}; color:{INK};
           font-family:"Geist", system-ui, sans-serif; font-variant-numeric:tabular-nums; }}
    a {{ color:{LINK}; text-decoration:none; }} a:hover {{ color:#fff; }}
    .m  {{ font-family:"Geist Mono", ui-monospace, monospace; }}
    .lb {{ font-family:"Geist Mono", ui-monospace, monospace; font-size:9.5px;
          letter-spacing:.15em; text-transform:uppercase; color:{INK3}; }}
    .layer {{ position:absolute; inset:0; pointer-events:none; }}
    .breathe {{ animation:breathe 46s ease-in-out infinite alternate; }}
    @keyframes breathe {{ to {{ opacity:1.85; }} }}
    .slowA {{ transform-box:view-box; transform-origin:140px 900px;
             animation:spin 680s linear infinite; }}
    @keyframes spin {{ to {{ transform:rotate(360deg); }} }}
    .rule {{ background-image:
              linear-gradient(rgba(108,183,255,.026) 1px, transparent 1px),
              linear-gradient(90deg, rgba(108,183,255,.026) 1px, transparent 1px);
            background-size:36px 36px;
            mask-image:radial-gradient(105% 62% at 16% 0%, #000 0%, transparent 66%); }}
    .scan {{ background-image:repeating-linear-gradient(180deg,
             rgba(255,255,255,.010) 0 1px, transparent 1px 3px); }}
    .vig  {{ background:radial-gradient(130% 92% at 50% 3%, transparent 44%,
             rgba(8,11,13,.9) 100%); }}
    /* first-paint bar growth only; the AI lane is the one thing that flows. */
    .settle {{ animation:settle 200ms cubic-bezier(.32,.72,0,1) backwards; }}
    @keyframes settle {{ from {{ opacity:0; transform:translateY(4px); }} }}
    .grow {{ animation:grow 520ms cubic-bezier(.32,.72,0,1) backwards; transform-origin:left; }}
    @keyframes grow {{ from {{ transform:scaleX(0); }} }}
    .flow {{ background-image:linear-gradient(90deg, transparent 0 7px,
             rgba(8,11,13,.5) 7px 11px); background-size:18px 100%;
             animation:flow 1.1s linear infinite; }}
    @keyframes flow {{ to {{ background-position:18px 0; }} }}
    .cur {{ animation:blink 1.1s steps(1) infinite; }}
    @keyframes blink {{ 50% {{ opacity:0; }} }}
    .lift {{ transition:background-color 140ms ease, border-color 140ms ease,
                       transform 140ms cubic-bezier(.32,.72,0,1); }}
    .lift:hover {{ background-color:{SURF}; transform:translateY(-1px); }}
    @media (prefers-reduced-motion: reduce) {{
      .breathe,.slowA,.settle,.grow,.flow,.cur {{ animation:none !important; }}
      .lift {{ transition:none; }}
    }}
    :focus-visible {{ outline:2px solid {LINK}; outline-offset:2px; }}
    .btn {{ font-family:"Geist", system-ui, sans-serif; font-size:12px; padding:7px 14px;
           border:1px solid {LINE2}; background:transparent; color:{INK};
           cursor:pointer; transition:background-color 140ms ease; }}
    .btn:hover {{ background:{SURF}; }}
    .btn.go {{ border-color:{PEA}; color:{PEA}; }}
    .btn.off {{ border-color:{LINE}; color:{NOTE}; cursor:not-allowed; }}
    .seg {{ border:0; cursor:pointer; font-family:"Geist Mono", ui-monospace, monospace;
           font-size:10px; letter-spacing:.08em; text-transform:uppercase; padding:6px 13px;
           background:transparent; color:{INK3}; }}
    .seg[aria-current="true"] {{ background:{SURF}; color:{INK}; }}
    /* status is a SHAPE plus a label, never colour alone — §8 */
    /* **`inline-block`, and it is a bug fix.** `.dot` was inline, so width/height did
       nothing wherever it was a direct child of a `<td>` — the work queue rendered every
       status cell empty while the same class was correct inside a flex parent. Found by
       looking at a screenshot, which is the only way it could have been found. */
    .dot {{ display:inline-block; vertical-align:middle;
           width:8px; height:8px; flex:0 0 8px; }}
    .dot.done {{ background:{PEA}; }}
    .dot.open {{ background:transparent; border:1px solid {PORTLINE}; }}
    .dot.review {{ background:{MEAS}; clip-path:polygon(50% 0,100% 100%,0 100%); }}
    .dot.fail {{ background:{FAULT}; clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%); }}
    .dot.run {{ background:{RUN}; border-radius:50%; }}
    table {{ border-collapse:collapse; width:100%; }}
    th {{ font-family:"Geist Mono", ui-monospace, monospace; font-size:9.5px;
         letter-spacing:.15em; text-transform:uppercase; color:{INK3};
         text-align:left; font-weight:400; padding:0 0 9px; border-bottom:1px solid {LINE}; }}
    td {{ padding:11px 0; border-bottom:1px solid {SOFT}; font-size:12.5px; vertical-align:top; }}
    .scroller {{ overflow-x:auto; }}
    /* **The 1180 breakpoint, and it was missing.** §8.5: the chat rail stacks below
       content under 1180; §8.1: source cards and lower columns stack. Every split was an
       inline grid with no query, so at 900px the rail ran off the edge instead of stacking. */
    .split {{ display:grid; gap:26px; align-items:start; grid-template-columns:minmax(0,1fr) 372px; }}
    .split.narrow {{ grid-template-columns:minmax(0,1fr) 340px; }}
    .split.slim {{ grid-template-columns:minmax(0,1fr) 320px; }}
    .two {{ display:grid; gap:20px; align-items:start;
           grid-template-columns:repeat(2, minmax(0, 1fr)); }}
    @media (max-width:1180px) {{
      .split, .split.narrow, .split.slim, .two {{ grid-template-columns:minmax(0, 1fr); }}
    }}
{extra}  </style>"""


def page(body: str, h: int, extra_css: str = "") -> str:
    """The shell every board sits in: arc field, rule, scan, vignette, global nav."""
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
{head(extra_css)}
</helmet>

<div style="position:relative; min-height:{h}px; overflow:hidden; background:{PAPER};">
  <svg class="layer" viewBox="0 0 1400 {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
    <g class="breathe" fill="none">
      <g class="slowA" stroke="{LINK}" stroke-width="1">
        <circle cx="140" cy="900" r="600"  opacity=".085"/>
        <circle cx="140" cy="900" r="880"  opacity=".055"/>
        <circle cx="140" cy="900" r="1220" opacity=".034"/>
      </g>
      <path d="M-60 780 Q 640 1000 1470 630" stroke="{PEA}" stroke-width="1" opacity=".026"/>
    </g>
  </svg>
  <div class="layer rule"></div>
  <div class="layer scan"></div>
  <div class="layer vig"></div>

  <div style="position:relative; padding:26px 44px 40px;">
    <div style="display:flex; align-items:center; justify-content:space-between;
                padding-bottom:18px; border-bottom:1px solid {LINE};">
      <div style="display:flex; align-items:baseline; gap:28px;">
        <span style="font-size:14px; font-weight:700; letter-spacing:-.02em;">Comeni</span>
        <span style="font-size:12.5px; color:{INK3};">Builder</span>
        <span style="font-size:12.5px; color:{INK3};">Runs</span>
        <span style="font-size:12.5px; color:{INK};">Registry</span>
      </div>
      <span class="m" style="font-size:11px; color:{INK3};">Ferreira lab</span>
    </div>
{body}
  </div>
</div>
</x-dc>
</body>
</html>
"""


def subnav(current: str) -> str:
    """`Overview · Catalogue · Work queue`, below the global shell — §8, never in it."""
    items = ["Overview", "Catalogue", "Work queue"]
    tabs = "".join(
        f'<button class="seg" aria-current="{str(name == current).lower()}">{name}</button>'
        for name in items
    )
    return f"""    <div style="display:flex; gap:2px; padding:14px 0 0; border-bottom:1px solid {SOFT};">
{tabs}
    </div>
"""


def bar(source: dict) -> str:
    """Four mutually exclusive segments over the ADAPTABLE denominator.

    Unsupported sits outside it and is stated beneath — §8.1, and it is the difference between
    *we have not done these yet* and *these cannot be done*.
    """
    total = source["adaptable"]
    unadapted = total - source["current"] - source["outdated"] - source["in_progress"]
    parts = [
        (source["current"], PEA, "current"),
        (source["outdated"], MEAS, "outdated"),
        (source["in_progress"], RUN, "in progress"),
        (unadapted, "#1C262B", "not adapted"),
    ]
    segs = "".join(
        f'<div class="grow" title="{label}: {n}" style="flex:0 0 {n / total * 100:.3f}%;'
        f' background:{colour}; animation-delay:{i * 60}ms;"></div>'
        for i, (n, colour, label) in enumerate(parts)
    )
    return f'<div style="display:flex; gap:2px; height:10px;">{segs}</div>'


# ── 1. Overview ───────────────────────────────────────────────────────────────────────
def overview() -> str:
    cards = ""
    for source in F["sources"]:
        stale = (
            f'<span class="m" style="font-size:10.5px; color:{MEAS};">'
            f'&#9650; stale &middot; retry available</span>'
            if source["stale"]
            else f'<span class="m" style="font-size:10.5px; color:{NOTE};">'
            f'synced {source["synced"]}</span>'
        )
        unsupported = (
            f' &middot; <span style="color:{NOTE};">{source["unsupported"]} unsupported</span>'
            if source["unsupported"]
            else ""
        )
        cards += f"""        <div class="settle lift" style="border:1px solid {LINE}; background:{NODE};
                    padding:18px 20px; cursor:pointer;">
          <div style="display:flex; align-items:baseline; justify-content:space-between;
                      padding-bottom:12px;">
            <span class="lb" style="color:{INK2}; font-size:10.5px;">{source["name"]}</span>
            {stale}
          </div>
          <div style="display:flex; align-items:baseline; gap:8px; padding-bottom:12px;">
            <span style="font-size:30px; font-weight:600; letter-spacing:-.03em;
                         line-height:1;">{source["adapted"]}</span>
            <span style="font-size:13px; color:{INK2};">of {source["adaptable"]:,} adaptable</span>
          </div>
          {bar(source)}
          <div style="display:flex; gap:14px; padding-top:10px; font-size:11.5px; color:{INK2};">
            <span><span class="dot done" style="display:inline-block; margin-right:5px;
                  vertical-align:middle;"></span>{source["current"]} current</span>
            <span><span class="dot review" style="display:inline-block; margin-right:5px;
                  vertical-align:middle;"></span>{source["outdated"]} outdated</span>
            <span><span class="dot run" style="display:inline-block; margin-right:5px;
                  vertical-align:middle;"></span>{source["in_progress"]} in progress</span>
          </div>
          <div class="m" style="font-size:10.5px; color:{NOTE}; padding-top:8px;">
            {source["discovered"]:,} discovered{unsupported}
          </div>
        </div>
"""

    flow = F["flow"]
    stages = [
        ("Discovered", f'{flow["discovered"]:,}', None),
        ("Scaffold", str(flow["scaffold"]), None),
        ("AI lane", f'{flow["ai_active"]} active', "ai"),
        ("Review", str(flow["review"]), None),
        ("Registry", str(flow["registry"]), None),
    ]
    nodes = ""
    for i, (label, value, kind) in enumerate(stages):
        tail = (
            f'<div class="m" style="font-size:10px; color:{INK3}; padding-top:5px;">'
            f'capacity 1 &middot; {flow["ai_waiting"]} waiting</div>'
            if kind == "ai"
            else ""
        )
        # **The edge has to be visible or the flow is five cards.** It was a 1px line in a
        # `flex:1` gap, which rendered as nothing at 1400px — the brief asks for a count graph
        # and what shipped was a row of boxes. Fixed width, brighter rail, arrowhead.
        edge = (
            f'<div style="flex:0 0 46px; align-self:center; display:flex; align-items:center;'
            f' gap:0;">'
            f'<div style="flex:1; height:1px; background:{PORTLINE};"'
            + (' class="flow"' if kind == "ai" else "")
            + ">"
            f'</div><div style="width:0; height:0; border-left:4px solid {PORTLINE};'
            f' border-top:3px solid transparent; border-bottom:3px solid transparent;"></div>'
            f"</div>"
            if i
            else ""
        )
        border = f"1px solid {RUN}" if kind == "ai" else f"1px solid {LINE}"
        nodes += f"""{edge}          <div class="lift" style="border:{border}; background:{NODE};
                      padding:11px 15px; min-width:118px; cursor:pointer;">
            <div class="lb" style="padding-bottom:6px;">{label}</div>
            <div style="font-size:18px; font-weight:600; letter-spacing:-.02em;">{value}</div>
            {tail}
          </div>
"""

    need = F["attention"]
    body = f"""{subnav("Overview")}
    <div class="settle" style="display:flex; align-items:flex-end;
                justify-content:space-between; padding:26px 0 22px;">
      <div>
        <div style="font-size:26px; font-weight:600; letter-spacing:-.03em;">Registry</div>
        <div style="font-size:13px; color:{INK2}; padding-top:5px;">
          Keep the tool catalogue supplied and current.</div>
      </div>
      <div style="display:flex; align-items:center; gap:14px;">
        <span class="m" style="font-size:10.5px; color:{NOTE};">last sync 03:00</span>
        <button class="btn">Sync sources</button>
      </div>
    </div>

    <div class="two">
{cards}    </div>

    <div style="padding:30px 0 0;">
      <div class="lb" style="padding-bottom:13px;">The flow</div>
      <div class="scroller">
        <div style="display:flex; align-items:stretch; gap:0; min-width:900px;">
{nodes}        </div>
      </div>
    </div>

    <div class="two" style="padding:30px 0 0;">
      <div>
        <div class="lb" style="padding-bottom:13px;">Needs you</div>
        <div class="settle lift" style="border-left:2px solid {MEAS}; padding:9px 0 9px 14px;
                    cursor:pointer;">
          <div style="font-size:14px; font-weight:500;">{need["review"]} ready for review</div>
          <div style="font-size:12.5px; color:{INK2}; padding-top:3px;">
            Oldest has waited 3 days.</div>
        </div>
        <div class="settle lift" style="border-left:2px solid {FAULT}; padding:9px 0 9px 14px;
                    margin-top:12px; cursor:pointer; animation-delay:40ms;">
          <div style="font-size:14px; font-weight:500;">{need["failed"]} failed</div>
          <div style="font-size:12.5px; color:{INK2}; padding-top:3px;">
            Both retryable at the stage they stopped.</div>
        </div>
        <div class="settle lift" style="border-left:2px solid {LINE2}; padding:9px 0 9px 14px;
                    margin-top:12px; cursor:pointer; animation-delay:80ms;">
          <div style="font-size:14px; font-weight:500;">{need["outdated"]} tools outdated</div>
          <div style="font-size:12.5px; color:{INK2}; padding-top:3px;">
            Upstream moved since these were adapted.</div>
        </div>
      </div>
      <div>
        <div class="lb" style="padding-bottom:13px;">Source health</div>
        <div style="border:1px solid {LINE}; background:{NODE}; padding:14px 16px;">
          <div style="display:flex; align-items:center; gap:9px; font-size:12.5px;">
            <span class="dot done"></span>nf-core &mdash; synced 14m ago
          </div>
          <div style="display:flex; align-items:flex-start; gap:9px; font-size:12.5px;
                      padding-top:11px;">
            <span class="dot fail" style="margin-top:4px;"></span>
            <span>pegi3s &mdash; stale
              <span class="m" style="display:block; font-size:10.5px; color:{INK3};
                    padding-top:4px;">{F["sources"][1]["error"]}</span>
            </span>
          </div>
          <button class="btn" style="margin-top:14px;">Retry pegi3s</button>
        </div>
      </div>
    </div>
"""
    return page(body, HEIGHT["overview"])


# ── 2. Catalogue ──────────────────────────────────────────────────────────────────────
def catalogue() -> str:
    rows = ""
    for state, name, source, what, version, evidence, action in F["catalogue"]:
        label = {"done": "adapted", "open": "not adapted", "review": "in review"}[state]
        selected = name == "prodigal"
        rows += f"""            <tr class="lift" style="cursor:pointer;{
            f' background:{SURF};' if selected else ''}">
              <td style="width:104px;">
                <span style="display:flex; align-items:center; gap:7px;">
                  <span class="dot {state}"></span>
                  <span class="m" style="font-size:10px; color:{INK3};">{label}</span>
                </span>
              </td>
              <td style="width:210px;">
                <div style="font-weight:500;">{name}</div>
                <div class="m" style="font-size:10.5px; color:{INK3}; padding-top:3px;">
                  {source}</div>
              </td>
              <td style="color:{INK2}; padding-right:24px;">{what}</td>
              <td class="m" style="width:132px; font-size:11px; color:{
            INK4 if 'unresolved' in version else INK2};">{version}</td>
              <td class="m" style="width:150px; font-size:10.5px; color:{INK3};">{evidence}</td>
              <td style="width:84px; text-align:right;">
                <button class="btn" style="padding:5px 11px; font-size:11px;">{action}</button>
              </td>
            </tr>
"""

    body = f"""{subnav("Catalogue")}
    <div class="settle" style="display:flex; align-items:center; gap:14px; padding:26px 0 16px;">
      <div style="flex:1; border:1px solid {LINE2}; background:{NODE}; padding:9px 13px;
                  font-size:12.5px; color:{INK3};">
        Search name, description or keyword</div>
      <span class="m" style="font-size:11px; color:{INK3};">1,379 tools</span>
    </div>
    <div style="display:flex; gap:9px; padding-bottom:20px;">
      <button class="btn" style="padding:6px 12px; font-size:11.5px;">Source &#9662;</button>
      <button class="btn" style="padding:6px 12px; font-size:11.5px;">Status &#9662;</button>
      <button class="btn" style="padding:6px 12px; font-size:11.5px;">Category &#9662;</button>
      <button class="btn" style="padding:6px 12px; font-size:11.5px;">Has Nextflow &#9662;</button>
    </div>

    <div class="split">
      <div class="scroller">
        <table style="min-width:720px;">
          <thead><tr>
            <th>status</th><th>tool / source</th><th>what it does</th>
            <th>latest</th><th>evidence</th><th></th>
          </tr></thead>
          <tbody>
{rows}          </tbody>
        </table>
        <div style="display:flex; justify-content:space-between; align-items:center;
                    padding-top:16px;">
          <span class="m" style="font-size:10.5px; color:{NOTE};">1&ndash;6 of 1,379</span>
          <button class="btn" style="padding:5px 12px; font-size:11px;">Next &rsaquo;</button>
        </div>
      </div>

      <div class="settle" style="border:1px solid {LINE}; background:{NODE}; padding:18px 20px;">
        <div style="display:flex; align-items:baseline; justify-content:space-between;">
          <span style="font-size:16px; font-weight:600;">prodigal</span>
          <span class="m" style="font-size:10.5px; color:{INK3};">pegi3s</span>
        </div>
        <div style="font-size:12.5px; color:{INK2}; padding:9px 0 16px;">
          Predicts protein-coding genes in bacterial and archaeal genomes.</div>

        <div class="lb" style="padding-bottom:8px;">Container</div>
        <div class="m" style="font-size:10.5px; color:{INK2}; word-break:break-all;
                    padding-bottom:16px;">
          pegi3s/prodigal@sha256:9f2c…e41b<br>
          <span style="color:{NOTE};">linux/amd64 &middot; pinned by digest</span></div>

        <div class="lb" style="padding-bottom:8px;">What scaffolding can settle</div>
        <div style="display:flex; flex-direction:column; gap:7px; padding-bottom:16px;">
          <span style="display:flex; gap:8px; font-size:12px;">
            <span class="dot done" style="margin-top:4px;"></span>
            container reference, process name, directives</span>
          <span style="display:flex; gap:8px; font-size:12px;">
            <span class="dot open" style="margin-top:4px;"></span>
            <span>9 holes &mdash; every port type and state, the script body
              <span style="color:{INK3};">(no Nextflow upstream)</span></span></span>
        </div>

        <div class="lb" style="padding-bottom:8px;">Licence &amp; maintainers</div>
        <div style="font-size:12px; color:{INK2}; padding-bottom:18px;">
          GPL-3.0 &middot; pegi3s consortium</div>

        <button class="btn go" style="width:100%;">Adapt this tool</button>
      </div>
    </div>
"""
    return page(body, HEIGHT["catalogue"])


# ── 3. Work queue ─────────────────────────────────────────────────────────────────────
def work() -> str:
    active_tool, active_stage, active_time = F["work"]["active"]
    queued = "".join(
        f"""        <div style="display:flex; align-items:center; gap:13px; padding:9px 0 9px 25px;
                    border-left:1px solid {LINE2}; margin-left:4px;">
          <span class="dot open"></span>
          <span style="font-size:12.5px; flex:1;">{tool}</span>
          <span class="m" style="font-size:10.5px; color:{INK3};">position {n} &middot; approximate</span>
        </div>
"""
        for tool, n in F["work"]["queued"]
    )

    review = "".join(
        f"""            <tr class="lift" style="cursor:pointer;">
              <td style="width:36px;"><span class="dot review"></span></td>
              <td style="width:230px; font-weight:500;">{tool}</td>
              <td class="m" style="width:96px; font-size:11px; color:{
            PEA if checks == "8/8" else MEAS};">{checks} checks</td>
              <td class="m" style="width:84px; font-size:11px; color:{INK3};">{rev}</td>
              <td class="m" style="font-size:11px; color:{INK3};">waiting {waited}</td>
              <td style="width:76px; text-align:right;">
                <button class="btn" style="padding:5px 11px; font-size:11px;">Open</button></td>
            </tr>
"""
        for tool, checks, rev, waited in F["work"]["review"]
    )

    changes = "".join(
        f"""            <tr class="lift" style="cursor:pointer;">
              <td style="width:36px;"><span class="dot open"></span></td>
              <td style="width:230px; font-weight:500;">{tool}</td>
              <td style="color:{INK2};">{why}</td>
              <td class="m" style="width:110px; font-size:11px; color:{INK3};">{who}</td>
              <td style="width:76px; text-align:right;">
                <button class="btn" style="padding:5px 11px; font-size:11px;">Open</button></td>
            </tr>
"""
        for tool, why, who in F["work"]["changes"]
    )

    failed = "".join(
        f"""            <tr class="lift" style="cursor:pointer;">
              <td style="width:36px;"><span class="dot fail"></span></td>
              <td style="width:230px; font-weight:500;">{tool}</td>
              <td class="m" style="font-size:11px; color:{INK2};">{why}</td>
              <td style="width:76px; text-align:right;">
                <button class="btn" style="padding:5px 11px; font-size:11px;">Retry</button></td>
            </tr>
"""
        for tool, why in F["work"]["failed"]
    )

    body = f"""{subnav("Work queue")}
    <div class="settle" style="display:flex; align-items:center; justify-content:space-between;
                padding:26px 0 20px;">
      <div style="font-size:22px; font-weight:600; letter-spacing:-.025em;">Work queue</div>
      <div style="display:flex; gap:2px;">
        <button class="seg" aria-current="true">All</button>
        <button class="seg">Needs review</button>
        <button class="seg">AI work</button>
        <button class="seg">Failed</button>
      </div>
    </div>

    <div style="padding-bottom:26px;">
      <div style="display:flex; align-items:baseline; gap:12px; padding-bottom:12px;">
        <span class="lb">AI lane</span>
        <span class="m" style="font-size:10.5px; color:{NOTE};">capacity 1</span>
      </div>
      <div style="border:1px solid {RUN}; background:{NODE}; padding:13px 16px;
                  display:flex; align-items:center; gap:13px;">
        <span class="dot run"></span>
        <span style="font-size:13.5px; font-weight:500;">{active_tool}</span>
        <span style="font-size:12.5px; color:{INK2}; flex:1;">{active_stage}</span>
        <span class="m" style="font-size:11.5px; color:{RUN};">{active_time}<span class="cur">&#9646;</span></span>
      </div>
      <div style="height:10px; margin-left:4px; border-left:1px solid {LINE2};"></div>
{queued}    </div>

    <div style="padding-bottom:26px;">
      <div class="lb" style="padding-bottom:11px;">Ready for review ({len(F["work"]["review"])})</div>
      <div class="scroller"><table style="min-width:640px; max-width:1000px;"><tbody>
{review}      </tbody></table></div>
    </div>

    <div style="padding-bottom:26px;">
      <div class="lb" style="padding-bottom:11px;">Changes requested ({len(F["work"]["changes"])})</div>
      <div class="scroller"><table style="min-width:640px; max-width:1000px;"><tbody>
{changes}      </tbody></table></div>
    </div>

    <div style="padding-bottom:26px;">
      <div class="lb" style="padding-bottom:11px;">Failed ({len(F["work"]["failed"])})</div>
      <div class="scroller"><table style="min-width:640px; max-width:1000px;"><tbody>
{failed}      </tbody></table></div>
    </div>

    <div style="display:flex; align-items:center; gap:10px; padding-top:4px;
                border-top:1px solid {SOFT};">
      <button class="seg" style="padding-left:0;">&#9656; Recently published (10)</button>
    </div>
"""
    return page(body, HEIGHT["work"])


# ── 4. Adaptation while running ───────────────────────────────────────────────────────
def adaptation() -> str:
    a = F["adaptation"]
    stages = ["Scaffold", "Queued", "Analyse", "Implement", "Validate", "Review"]
    done, running = 2, 2
    track = ""
    for i, name in enumerate(stages):
        if i < done:
            mark, colour, weight = '<span class="dot done"></span>', INK2, "400"
        elif i == running:
            mark, colour, weight = '<span class="dot run"></span>', INK, "500"
        else:
            mark, colour, weight = '<span class="dot open"></span>', INK4, "400"
        edge = (
            f'<div style="flex:1; height:1px; background:{LINE2}; min-width:16px;"'
            + (' class="flow"' if i == running else "")
            + "></div>"
            if i
            else ""
        )
        track += (
            f'{edge}<div style="display:flex; align-items:center; gap:7px;">{mark}'
            f'<span style="font-size:12px; color:{colour}; font-weight:{weight};">{name}</span></div>'
        )

    activity = "".join(
        f"""          <div style="display:flex; gap:11px; padding:8px 0; border-bottom:1px solid {SOFT};">
            <span class="m" style="font-size:10.5px; color:{NOTE}; flex:0 0 40px;">{when}</span>
            <span style="font-size:12px; flex:1;">{what}
              <span class="m" style="display:block; font-size:10.5px; color:{INK3};
                    padding-top:2px;">{detail}</span></span>
          </div>
"""
        for when, what, detail in a["activity"]
    )

    body = f"""    <div class="settle" style="padding:22px 0 18px; border-bottom:1px solid {LINE};">
      <div style="display:flex; align-items:baseline; justify-content:space-between;">
        <div style="display:flex; align-items:baseline; gap:14px;">
          <span style="font-size:22px; font-weight:600; letter-spacing:-.025em;">{a["tool"]}</span>
          <span style="display:inline-flex; align-items:center; gap:7px;">
            <span class="dot run"></span>
            <span class="m" style="font-size:11px; color:{RUN}; letter-spacing:.1em;">{a["state"]}</span>
          </span>
          <span class="m" style="font-size:11px; color:{INK3};">revision {a["revision"]}</span>
        </div>
        <button class="btn">Archive</button>
      </div>
      <div class="m" style="font-size:10.5px; color:{NOTE}; padding-top:8px;">
        source digest {a["source_digest"]}&hellip; &middot;
        registry base {a["registry_digest"]}&hellip;</div>
    </div>

    <div class="scroller" style="padding:20px 0 24px;">
      <div style="display:flex; align-items:center; gap:9px; min-width:760px;">{track}</div>
    </div>

    <div class="split slim">
      <div>
        <div style="border:1px solid {RUN}; background:{NODE}; padding:18px 20px;">
          <div class="lb" style="padding-bottom:10px;">Current stage</div>
          <div style="font-size:15px; font-weight:500;">Mapping semantic ports</div>
          <div style="font-size:12.5px; color:{INK2}; padding-top:6px;">
            Grounded on {a["evidence"]} evidence excerpts. Nothing is written until the
            proposal validates.</div>
          <div class="m" style="font-size:10.5px; color:{INK3}; padding-top:12px;">
            forge.analysis.v1 &middot; elapsed 01:42</div>
        </div>

        <div style="border:1px solid {LINE}; background:{NODE}; padding:18px 20px;
                    margin-top:18px;">
          <div class="lb" style="padding-bottom:12px;">Deterministic scaffold</div>
          <div style="display:flex; gap:34px; padding-bottom:16px;">
            <div><div style="font-size:22px; font-weight:600;">{a["facts"]}</div>
              <div class="m" style="font-size:10px; color:{INK3};">facts read</div></div>
            <div><div style="font-size:22px; font-weight:600; color:{FAULT};">{a["holes"]}</div>
              <div class="m" style="font-size:10px; color:{INK3};">holes open</div></div>
            <div><div style="font-size:22px; font-weight:600; color:{PEA};">1</div>
              <div class="m" style="font-size:10px; color:{INK3};">container pinned</div></div>
          </div>
          <div style="display:flex; flex-direction:column; gap:9px;">
            <div class="lift" style="display:flex; gap:10px; align-items:baseline;
                        padding:7px 9px; border-left:2px solid {FAULT}; cursor:pointer;">
              <span class="m" style="font-size:10.5px; color:{INK3}; flex:0 0 168px;">
                consumes.seq.type_id</span>
              <span style="font-size:12px; flex:1;">what does this input carry?</span>
              <span class="m" style="font-size:10px; color:{LINK};">E004 &middot; ports.semantic-type.v1</span>
            </div>
            <div class="lift" style="display:flex; gap:10px; align-items:baseline;
                        padding:7px 9px; border-left:2px solid {FAULT}; cursor:pointer;">
              <span class="m" style="font-size:10.5px; color:{INK3}; flex:0 0 168px;">
                produces.genes.type_id</span>
              <span style="font-size:12px; flex:1;">what does this output carry?</span>
              <span class="m" style="font-size:10px; color:{LINK};">E011 &middot; ports.semantic-type.v1</span>
            </div>
          </div>
        </div>
      </div>

      <div>
        <div class="lb" style="padding-bottom:11px;">Activity</div>
        <div style="border:1px solid {LINE}; background:{NODE}; padding:6px 14px 10px;">
{activity}        </div>
        <div class="m" style="font-size:10px; color:{NOTE}; padding-top:10px; line-height:1.5;">
          Durable events only. The model's intermediate reasoning is not streamed here &mdash;
          what is recorded is what happened.</div>
      </div>
    </div>
"""
    return page(body, HEIGHT["adaptation"])


# ── 5. Review ─────────────────────────────────────────────────────────────────────────
def review() -> str:
    r = F["review"]
    passed, total = r["checks"]
    rungs = "".join(
        f"""          <div style="display:flex; align-items:center; gap:9px; padding:7px 0;">
            <span class="dot done"></span>
            <span style="font-size:12.5px;">{name}</span>
          </div>
"""
        for name, ok in r["rungs"]
    )
    chat = ""
    for who, text in r["chat"]:
        curator = who == "curator"
        chat += f"""          <div style="padding:11px 0; border-bottom:1px solid {SOFT};">
            <div class="m" style="font-size:9.5px; letter-spacing:.14em; text-transform:uppercase;
                        color:{INK3 if curator else LINK}; padding-bottom:5px;">
              {"You" if curator else "Assistant"}</div>
            <div style="font-size:12.5px; color:{INK if curator else INK2}; line-height:1.55;">
              {text}</div>
          </div>
"""

    body = f"""    <div class="settle" style="padding:22px 0 16px; border-bottom:1px solid {LINE};">
      <div style="display:flex; align-items:baseline; justify-content:space-between;">
        <div style="display:flex; align-items:baseline; gap:14px;">
          <span style="font-size:22px; font-weight:600; letter-spacing:-.025em;">{r["tool"]}</span>
          <span style="display:inline-flex; align-items:center; gap:7px;">
            <span class="dot review"></span>
            <span class="m" style="font-size:11px; color:{MEAS}; letter-spacing:.1em;">
              READY FOR REVIEW</span></span>
          <span class="m" style="font-size:11px; color:{INK3};">revision {r["revision"]}</span>
        </div>
        <div style="display:flex; gap:10px;">
          <button class="btn">Request changes</button>
          <button class="btn go">Approve and publish</button>
        </div>
      </div>
      <div style="font-size:12.5px; color:{INK2}; padding-top:9px;">
        {r["files"]} files changed &middot;
        <span style="color:{PEA};">{passed}/{total} checks pass</span> &middot;
        {r["unresolved"]} unresolved</div>
    </div>

    <div style="display:flex; gap:2px; padding:12px 0 0; border-bottom:1px solid {SOFT};">
      <button class="seg" aria-current="true">Overview</button>
      <button class="seg">Diff</button>
      <button class="seg">Files</button>
      <button class="seg">Evidence</button>
      <button class="seg">Rule candidates</button>
    </div>

    <div class="split" style="padding-top:22px;">
      <div>
        <div class="lb" style="padding-bottom:13px;">Input / output</div>
        <div class="scroller" style="border:1px solid {LINE}; background:{NODE}; padding:22px 20px;">
          <div style="display:flex; align-items:center; gap:16px; min-width:640px;">
            <div class="lift" style="border:1px dashed {NODELINE}; border-left:3px solid {LINK};
                        background:#0A1418; padding:11px 13px; cursor:pointer; min-width:150px;">
              <div class="m" style="font-size:10.5px; color:{LINK};">{r["consumes"][0]}</div>
              <div class="m" style="font-size:9.5px; color:{INK3}; padding-top:4px;">
                [{r["consumes"][1]}]</div>
            </div>
            <div style="flex:0 0 44px; height:1px; background:{PORTLINE};"></div>
            <div class="lift" style="border:1px solid {NODELINE}; border-left:3px solid {RAIL};
                        background:{NODE}; padding:11px 13px; cursor:pointer; min-width:172px;">
              <div style="font-size:12.5px; font-weight:500;">{r["process"]}</div>
              <div class="m" style="font-size:9.5px; color:{LINK}; padding-top:5px;">
                {r["params"]} parameters &rsaquo;</div>
            </div>
            <div style="flex:0 0 44px; height:1px; background:{PORTLINE};"></div>
            <div class="lift" style="border:1px solid {LINK}; border-left:3px solid {LINK};
                        background:#0A1418; padding:11px 13px; cursor:pointer; min-width:150px;">
              <div class="m" style="font-size:10.5px; color:{LINK};">{r["produces"][0]}</div>
              <div class="m" style="font-size:9.5px; color:{INK3}; padding-top:4px;">
                [{r["produces"][1]}]</div>
            </div>
          </div>
          <div style="display:flex; gap:20px; padding-top:18px; border-top:1px solid {SOFT};
                      margin-top:18px;">
            <span style="display:flex; align-items:center; gap:7px; font-size:11px; color:{INK3};">
              <span style="width:11px; height:11px; background:{NODE};
                    border:1px solid {NODELINE}; border-left:3px solid {RAIL};"></span>
              from the source</span>
            <span style="display:flex; align-items:center; gap:7px; font-size:11px; color:{INK3};">
              <span style="width:11px; height:11px; background:#0A1418;
                    border:1px solid {LINK};"></span>AI proposed</span>
            <span style="display:flex; align-items:center; gap:7px; font-size:11px; color:{INK3};">
              <span style="width:11px; height:11px; background:#0A1418;
                    border:1px dashed {FAULT};"></span>unresolved</span>
          </div>
        </div>

        <div class="two" style="padding-top:22px;">
          <div style="border:1px solid {LINE}; background:{NODE}; padding:16px 18px;">
            <div class="lb" style="padding-bottom:9px;">Validation</div>
{rungs}          </div>
          <div style="border:1px solid {LINE}; background:{NODE}; padding:16px 18px;">
            <div class="lb" style="padding-bottom:12px;">Where each value came from</div>
            <div style="display:flex; gap:3px; height:9px;">
              <div class="grow" style="flex:{r["derived"]}; background:{PEA};"></div>
              <div class="grow" style="flex:{r["proposed"]}; background:{LINK};
                    animation-delay:60ms;"></div>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px; padding-top:11px;
                        font-size:12px; color:{INK2};">
              <span>{r["derived"]} derived from the source</span>
              <span>{r["proposed"]} proposed by the model</span>
              <span style="color:{NOTE};">{r["human"]} edited by hand</span>
            </div>
          </div>
        </div>
      </div>

      <div style="border:1px solid {LINE}; background:{NODE};">
        <div style="padding:14px 16px 0;">
          <div class="lb" style="padding-bottom:4px;">Ask about this revision</div>
        </div>
        <div style="padding:0 16px;">
{chat}        </div>
        <div style="padding:12px 16px 16px;">
          <div style="border:1px solid {LINE2}; background:{PAPER}; padding:9px 11px;
                      font-size:12.5px; color:{INK3};">Ask about this revision&hellip;</div>
          <div style="display:flex; align-items:center; justify-content:space-between;
                      padding-top:10px;">
            <span class="m" style="font-size:10px; color:{NOTE};">
              answers cite evidence or file lines</span>
            <button class="btn" style="padding:5px 13px; font-size:11.5px;">Ask</button>
          </div>
        </div>
      </div>
    </div>
"""
    return page(body, HEIGHT["review"])


# ── 6. Review — requesting changes, and a stale base ───────────────────────────────────
def review_changes() -> str:
    r = F["review"]
    body = f"""    <div class="settle" style="padding:22px 0 16px; border-bottom:1px solid {LINE};">
      <div style="display:flex; align-items:baseline; justify-content:space-between;">
        <div style="display:flex; align-items:baseline; gap:14px;">
          <span style="font-size:22px; font-weight:600; letter-spacing:-.025em;">{r["tool"]}</span>
          <span style="display:inline-flex; align-items:center; gap:7px;">
            <span class="dot review"></span>
            <span class="m" style="font-size:11px; color:{MEAS}; letter-spacing:.1em;">
              READY FOR REVIEW</span></span>
          <span class="m" style="font-size:11px; color:{INK3};">revision {r["revision"]}</span>
        </div>
        <div style="display:flex; gap:10px;">
          <button class="btn" style="border-color:{MEAS}; color:{MEAS};">Request changes</button>
          <button class="btn off" disabled>Approve and publish</button>
        </div>
      </div>
      <div style="display:flex; align-items:flex-start; gap:9px; padding-top:12px;">
        <span class="dot fail" style="margin-top:4px;"></span>
        <div>
          <div style="font-size:12.5px; color:{FAULT};">
            The registry moved since this was validated.</div>
          <div class="m" style="font-size:10.5px; color:{INK3}; padding-top:4px;">
            validated against 41a9&hellip; &middot; the registry is now 8c07&hellip; &mdash;
            re-validate before approving</div>
        </div>
      </div>
    </div>

    <div class="split" style="padding-top:22px;">
      <div>
        <div style="border:1px solid {MEAS}; background:{NODE}; padding:20px 22px;">
          <div style="font-size:16px; font-weight:600; letter-spacing:-.02em;">
            Request changes</div>
          <div style="font-size:12.5px; color:{INK2}; padding:7px 0 18px;">
            This is not rejection. The candidate is kept and another attempt is queued against
            the same scaffold.</div>

          <div class="lb" style="padding-bottom:8px;">What should change &mdash; required</div>
          <div style="border:1px solid {LINE2}; background:{PAPER}; padding:11px 13px;
                      font-size:12.5px; min-height:78px; color:{INK};">
            The output state is a guess. `samtools sort` with no <span class="m"
            style="color:{LINK};">-n</span> is coordinate order, but nothing in the evidence
            says the input is unsorted &mdash; leave it open rather than claiming it.</div>

          <div class="lb" style="padding:16px 0 8px;">Point at a field or file &mdash; optional</div>
          <div style="display:flex; gap:8px; flex-wrap:wrap;">
            <span class="m" style="font-size:10.5px; color:{LINK}; border:1px solid #1E3A4E;
                  padding:5px 10px;">consumes[0].state &times;</span>
            <span class="m" style="font-size:10.5px; color:{INK3}; border:1px solid {LINE2};
                  padding:5px 10px;">+ add a reference</span>
          </div>

          <div style="display:flex; align-items:center; justify-content:space-between;
                      padding-top:20px; border-top:1px solid {SOFT}; margin-top:20px;">
            <span class="m" style="font-size:10px; color:{NOTE};">
              freezes revision {r["revision"]} &middot; queues another attempt &middot;
              you stay on this page</span>
            <div style="display:flex; gap:10px;">
              <button class="btn">Cancel</button>
              <button class="btn" style="border-color:{MEAS}; color:{MEAS};">
                Send back for changes</button>
            </div>
          </div>
        </div>

        <div style="border:1px solid {LINE}; background:{NODE}; padding:16px 18px;
                    margin-top:18px;">
          <div class="lb" style="padding-bottom:10px;">Why approve is unavailable</div>
          <div style="display:flex; flex-direction:column; gap:9px;">
            <span style="display:flex; gap:9px; align-items:baseline; font-size:12.5px;">
              <span class="dot fail" style="margin-top:4px;"></span>
              <span>The registry base moved &mdash; re-validate against 8c07&hellip;</span></span>
            <span style="display:flex; gap:9px; align-items:baseline; font-size:12.5px;
                        color:{NOTE};">
              <span class="dot done" style="margin-top:4px;"></span>
              <span>Validation is green &middot; no unresolved holes &middot; you are named</span></span>
          </div>
          <div class="m" style="font-size:10px; color:{NOTE}; padding-top:13px; line-height:1.55;">
            Every unmet condition is listed at once. Approval needs all of them, and a green
            verdict describes the layer that was read at the time.</div>
        </div>
      </div>

      <div style="border:1px solid {LINE}; background:{NODE};">
        <div style="padding:14px 16px 0;">
          <div class="lb" style="padding-bottom:4px;">Ask about this revision</div>
        </div>
        <div style="padding:0 16px;">
          <div style="padding:11px 0; border-bottom:1px solid {SOFT};">
            <div class="m" style="font-size:9.5px; letter-spacing:.14em; text-transform:uppercase;
                        color:{INK3}; padding-bottom:5px;">You</div>
            <div style="font-size:12.5px; line-height:1.55;">
              Is there anything in the source that says the input is unsorted?</div>
          </div>
          <div style="padding:11px 0; border-bottom:1px solid {SOFT};">
            <div style="display:flex; align-items:center; gap:8px;">
              <span class="dot run"></span>
              <span class="m" style="font-size:10.5px; color:{INK3};">
                queued &mdash; position 2, behind one generation</span>
            </div>
          </div>
        </div>
        <div style="padding:12px 16px 16px;">
          <div style="border:1px solid {LINE2}; background:{PAPER}; padding:9px 11px;
                      font-size:12.5px; color:{INK3};">Ask about this revision&hellip;</div>
          <div style="display:flex; align-items:center; justify-content:space-between;
                      padding-top:10px;">
            <span class="m" style="font-size:10px; color:{NOTE};">
              asking does not change the candidate</span>
            <button class="btn" style="padding:5px 13px; font-size:11.5px;">Ask</button>
          </div>
        </div>
      </div>
    </div>
"""
    return page(body, HEIGHT["review_changes"])


# ── the review tab strip, shared by four boards ───────────────────────────────────────
def review_head(current: str, *, disabled: bool = False) -> str:
    r = F["review"]
    passed, total = r["checks"]
    approve = (
        '<button class="btn off" disabled>Approve and publish</button>'
        if disabled
        else '<button class="btn go">Approve and publish</button>'
    )
    tabs = "".join(
        f'<button class="seg" aria-current="{str(name == current).lower()}">{name}</button>'
        for name in ["Overview", "Diff", "Files", "Parameters", "Evidence", "Rule candidates"]
    )
    return f"""    <div class="settle" style="padding:22px 0 16px; border-bottom:1px solid {LINE};">
      <div style="display:flex; align-items:baseline; justify-content:space-between;">
        <div style="display:flex; align-items:baseline; gap:14px;">
          <span style="font-size:22px; font-weight:600; letter-spacing:-.025em;">{r["tool"]}</span>
          <span style="display:inline-flex; align-items:center; gap:7px;">
            <span class="dot review"></span>
            <span class="m" style="font-size:11px; color:{MEAS}; letter-spacing:.1em;">
              READY FOR REVIEW</span></span>
          <span class="m" style="font-size:11px; color:{INK3};">revision {r["revision"]}</span>
        </div>
        <div style="display:flex; gap:10px;">
          <button class="btn">Request changes</button>
          {approve}
        </div>
      </div>
      <div style="font-size:12.5px; color:{INK2}; padding-top:9px;">
        {r["files"]} files changed &middot;
        <span style="color:{PEA};">{passed}/{total} checks pass</span> &middot;
        {r["unresolved"]} unresolved</div>
    </div>
    <div class="scroller" style="border-bottom:1px solid {SOFT};">
      <div style="display:flex; gap:2px; padding:12px 0 0; min-width:600px;">{tabs}</div>
    </div>
"""


# ── 7. Review — the code being approved ───────────────────────────────────────────────
ORIGIN = {
    "s": (RAIL, "S", "from the source, copied unchanged"),
    "d": (PEA, "D", "derived — arithmetic over declared data"),
    "a": (LINK, "A", "proposed by the model"),
    "h": (MEAS, "H", "edited by a person"),
}


def code_pane(title: str, subtitle: str, lines: list) -> str:
    """One file, with its origin in the gutter.

    **The gutter is the point of this pane, not decoration.** A reviewer scanning an nf-core
    module should see an unbroken column of `S`; a block of `A` is then loud without anybody
    having been told what to look for. The letter carries it and the colour agrees — §8's
    *label + shape, never colour alone*, applied to a file rather than to a status chip.
    """
    rendered = ""
    for i, (origin, text) in enumerate(lines, 1):
        if not text:
            # The rail runs THROUGH a blank line. Breaking it turned the solid column this
            # pane exists to show into a dashed one, which is the opposite of the signal.
            colour = ORIGIN[lines[i - 2][0]][0] if i > 1 else RAIL
            rendered += (
                f'<div style="display:flex; height:18px;">'
                f'<span style="flex:0 0 30px;"></span>'
                f'<span style="flex:0 0 3px; background:{colour}; opacity:.5;"></span>'
                f'</div>'
            )
            continue
        colour, letter, _ = ORIGIN[origin]
        shown = (
            text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        rendered += f"""<div class="lift" style="display:flex; align-items:baseline; cursor:pointer;">
              <span class="m" style="flex:0 0 30px; font-size:9.5px; color:{NOTE};
                    text-align:right; padding-right:9px;">{i}</span>
              <span style="flex:0 0 3px; align-self:stretch; background:{colour};"></span>
              <span class="m" style="flex:0 0 20px; font-size:9px; color:{colour};
                    text-align:center;">{letter}</span>
              <span class="m" style="font-size:11px; white-space:pre; color:{INK};">{shown}</span>
            </div>"""
    return f"""      <div style="border:1px solid {LINE}; background:{NODE}; min-width:0;">
        <div style="display:flex; align-items:baseline; justify-content:space-between;
                    padding:12px 14px; border-bottom:1px solid {LINE};">
          <span class="m" style="font-size:11.5px; color:{INK};">{title}</span>
          <span class="m" style="font-size:10px; color:{INK3};">{subtitle}</span>
        </div>
        <div class="scroller" style="padding:10px 0 12px;">
          <div style="min-width:440px;">
{rendered}          </div>
        </div>
      </div>"""


def review_code() -> str:
    key = "".join(
        f"""        <span style="display:flex; align-items:center; gap:7px; font-size:11px;
                    color:{INK3};">
          <span style="width:3px; height:13px; background:{colour};"></span>
          <span class="m" style="font-size:9.5px; color:{colour};">{letter}</span>
          {what}</span>
"""
        for colour, letter, what in ORIGIN.values()
    )
    body = f"""{review_head("Files")}
    <div style="display:flex; flex-wrap:wrap; gap:20px; padding:16px 0 18px;">
{key}    </div>

    <div class="two">
{code_pane("contract.yml", "24 lines &middot; 8 proposed", F["contract_yml"])}
{code_pane("main.nf", "26 lines &middot; copied unchanged", F["main_nf"])}
    </div>

    <div style="display:flex; align-items:flex-start; gap:10px; padding:20px 0 0;">
      <span class="dot done" style="margin-top:4px;"></span>
      <div>
        <div style="font-size:12.5px;">
          The module is upstream's, byte for byte &mdash; digest
          <span class="m" style="color:{INK2};">e4c1&hellip;</span> matches the vendored copy.</div>
        <div class="m" style="font-size:10.5px; color:{INK3}; padding-top:4px;">
          A source that ships Nextflow gets a contract bound to its process; nothing downstream
          may author one. A block of A in the right-hand pane would be that rule broken.</div>
      </div>
    </div>
"""
    return page(body, HEIGHT["review_code"])


# ── 8. Review — parameters and rule candidates ────────────────────────────────────────
def review_params() -> str:
    rows = ""
    for name, route, default, why, evidence, ok in F["params"]:
        route_cell = (
            f'<span class="m" style="font-size:11px; color:{INK2};">{route}</span>'
            if ok
            else f'<span class="m" style="font-size:11px; color:{FAULT};">{route} no route</span>'
        )
        cite = (
            f'<a class="m" href="#" style="font-size:10.5px;">{evidence}</a>'
            if evidence
            else f'<span class="m" style="font-size:10.5px; color:{NOTE};">no evidence</span>'
        )
        rows += f"""            <tr class="lift" style="cursor:pointer;">
              <td style="width:32px;"><span class="dot {"done" if ok else "fail"}"></span></td>
              <td style="width:168px;"><span class="m" style="font-size:11.5px;">{name}</span></td>
              <td style="width:150px;">{route_cell}</td>
              <td style="width:120px;"><span class="m" style="font-size:11px;
                    color:{INK2};">{default}</span></td>
              <td style="color:{INK2}; padding-right:20px;">{why}</td>
              <td style="width:86px; text-align:right;">{cite}</td>
            </tr>
"""

    cards = ""
    for rule in F["rules"]:
        box = (
            f'<span style="width:14px; height:14px; flex:0 0 14px; border:1px solid {LINE2};'
            f' background:{PAPER};"></span>'
            if rule["ok"]
            else f'<span style="width:14px; height:14px; flex:0 0 14px;'
            f' border:1px solid {LINE}; background:{PAPER}; opacity:.4;"></span>'
        )
        cite = (
            f'<a class="m" href="#" style="font-size:10.5px;">{rule["cite"]}</a>'
            if rule["cite"]
            else f'<span class="m" style="font-size:10.5px; color:{FAULT};">'
            f'no citation &mdash; not checkable</span>'
        )
        border = LINE if rule["ok"] else FAULT
        cards += f"""      <div style="border:1px solid {border}; background:{NODE}; padding:16px 18px;
                  display:flex; gap:13px; align-items:flex-start;
                  {"" if rule["ok"] else "opacity:.78;"}">
        {box}
        <div style="flex:1;">
          <div style="display:flex; gap:9px; align-items:baseline; padding-bottom:8px;">
            <span class="lb" style="flex:0 0 58px;">when</span>
            <span class="m" style="font-size:11.5px; color:{INK};">{rule["premise"]}</span>
          </div>
          <div style="display:flex; gap:9px; align-items:baseline; padding-bottom:8px;">
            <span class="lb" style="flex:0 0 58px;">then</span>
            <span style="font-size:12.5px;">{rule["effect"]}</span>
          </div>
          <div style="display:flex; gap:9px; align-items:baseline; padding-bottom:8px;">
            <span class="lb" style="flex:0 0 58px;">for</span>
            <span class="m" style="font-size:11.5px; color:{INK2};">{rule["row"]}</span>
          </div>
          <div style="display:flex; gap:9px; align-items:baseline;">
            <span class="lb" style="flex:0 0 58px;">because</span>
            {cite}
          </div>
        </div>
      </div>
"""

    body = f"""{review_head("Parameters")}
    <div style="padding:22px 0 10px;">
      <div class="lb" style="padding-bottom:5px;">Parameters</div>
      <div style="font-size:12.5px; color:{INK2}; padding-bottom:14px;">
        A parameter is a value somebody varies across analyses. Everything else is plumbing,
        and a parameter with no route resolves and reaches nothing.</div>
      <div class="scroller">
        <table style="min-width:760px;">
          <thead><tr>
            <th></th><th>name</th><th>route</th><th>default</th>
            <th>why it is exposed</th><th>evidence</th>
          </tr></thead>
          <tbody>
{rows}          </tbody>
        </table>
      </div>
    </div>

    <div style="display:flex; align-items:flex-start; gap:10px; padding:14px 0 26px;">
      <span class="dot fail" style="margin-top:4px;"></span>
      <div style="font-size:12.5px; color:{INK2};">
        <span style="color:{INK};">temp_prefix has no route.</span>
        It would appear in the artifact, resolve at build time, and reach no tool &mdash;
        emptiness and deadness are different problems, and this is the second.</div>
    </div>

    <div style="padding-top:6px; border-top:1px solid {LINE};">
      <div class="lb" style="padding:20px 0 5px;">Rule candidates</div>
      <div style="font-size:12.5px; color:{INK2}; padding-bottom:16px;">
        A rule is scientific policy, not metadata. Each starts unchecked; approving the
        contract does not accept them.</div>
      <div style="display:flex; flex-direction:column; gap:14px;">
{cards}      </div>
      <div class="m" style="font-size:10.5px; color:{NOTE}; padding-top:14px; line-height:1.55;">
        The second cannot be checked. Its premise and effect are plausible and nothing was
        cited &mdash; a rule with an invented citation is worse than no rule, because it will
        be followed and the reason given for following it will not survive being checked.</div>
    </div>
"""
    return page(body, HEIGHT["review_params"])


# ── 9. Answering a hole by hand ───────────────────────────────────────────────────────
def answer_hole() -> str:
    h = F["hole"]
    choices = ""
    for value, note, chosen in h["candidates"]:
        mark = (
            f'<span style="width:13px; height:13px; flex:0 0 13px; border-radius:50%;'
            f' border:1px solid {LINK}; background:{PAPER}; position:relative;">'
            f'<span style="position:absolute; inset:3px; border-radius:50%;'
            f' background:{LINK};"></span></span>'
            if chosen
            else f'<span style="width:13px; height:13px; flex:0 0 13px; border-radius:50%;'
            f' border:1px solid {PORTLINE}; background:{PAPER};"></span>'
        )
        border = LINK if chosen else LINE
        badge = (
            f'<span class="m" style="font-size:9.5px; color:{LINK}; letter-spacing:.1em;">'
            f'MODEL&rsquo;S ANSWER</span>'
            if chosen
            else ""
        )
        choices += f"""        <label class="lift" style="display:flex; align-items:center; gap:12px;
                    border:1px solid {border}; background:{NODE}; padding:12px 14px;
                    cursor:pointer;">
          {mark}
          <span class="m" style="font-size:12px; flex:1;">{value}</span>
          {badge}
          <span class="m" style="font-size:10.5px; color:{INK3};">{note}</span>
        </label>
"""

    evidence = "".join(
        f"""        <div class="lift" style="border-left:2px solid {LINK}; padding:9px 0 9px 13px;
                    cursor:pointer;">
          <div style="display:flex; align-items:baseline; gap:10px;">
            <span class="m" style="font-size:10.5px; color:{LINK};">{eid}</span>
            <span class="m" style="font-size:9.5px; color:{NOTE};">{where}</span>
          </div>
          <div class="m" style="font-size:10.5px; color:{INK2}; padding-top:5px;
                      white-space:pre-wrap; line-height:1.5;">{quote}</div>
        </div>
"""
        for eid, where, quote in h["evidence"]
    )

    body = f"""    <div class="settle" style="padding:22px 0 16px; border-bottom:1px solid {LINE};">
      <div style="display:flex; align-items:baseline; gap:14px;">
        <span style="font-size:22px; font-weight:600; letter-spacing:-.025em;">
          {F["review"]["tool"]}</span>
        <span class="m" style="font-size:11px; color:{INK3};">
          revision {F["review"]["revision"]} &middot; answering one hole</span>
      </div>
    </div>

    <div class="split narrow" style="padding-top:24px;">
      <div>
        <div style="border:1px solid {LINE}; background:{NODE}; padding:20px 22px;">
          <div class="m" style="font-size:10.5px; color:{INK3}; padding-bottom:9px;">
            {h["id"]}</div>
          <div style="font-size:17px; font-weight:600; letter-spacing:-.02em;">
            {h["question"]}</div>
          <div style="font-size:12.5px; color:{INK2}; padding:9px 0 4px; line-height:1.55;">
            <span class="lb" style="display:block; padding-bottom:5px;">Open because</span>
            {h["why_open"]}</div>
          <div class="m" style="font-size:10px; color:{NOTE}; padding-top:12px;">
            {h["hint"]} &mdash; the instruction the model was given for this kind of question</div>

          <div style="height:1px; background:{SOFT}; margin:20px 0 18px;"></div>

          <div style="display:flex; align-items:baseline; justify-content:space-between;
                      padding-bottom:12px;">
            <span class="lb">These are the only legal answers</span>
            <span class="m" style="font-size:10px; color:{NOTE};">
              ranked, not alphabetical</span>
          </div>
          <div style="display:flex; flex-direction:column; gap:9px;">
{choices}          </div>

          <div style="display:flex; align-items:flex-start; gap:10px; padding:16px 0 0;">
            <span class="m" style="color:{LINK}; font-size:13px; line-height:1.2;">+</span>
            <div style="font-size:12.5px; color:{INK2};">
              <a href="#" style="font-weight:500;">None of these is right?</a>
              Propose a new state &mdash; it goes to the vocabulary queue as a reviewed data
              change, and this hole stays open until it lands.</div>
          </div>
        </div>

        <div style="border:1px solid {MEAS}; background:{NODE}; padding:20px 22px;
                    margin-top:20px;">
          <div style="display:flex; align-items:baseline; gap:10px; padding-bottom:6px;">
            <span class="dot review"></span>
            <span style="font-size:15px; font-weight:600;">You are overriding the model</span>
          </div>
          <div style="font-size:12.5px; color:{INK2}; padding-bottom:16px;">
            It answered <span class="m" style="color:{LINK};">{h["answered"]}</span> from
            <span class="m">{h["answered_by"]}</span>. Changing it records who decided and why,
            and a later re-run replays your answer rather than asking again.</div>

          <div class="lb" style="padding-bottom:8px;">Why &mdash; required</div>
          <div style="border:1px solid {LINE2}; background:{PAPER}; padding:11px 13px;
                      font-size:12.5px; min-height:62px; color:{INK};">
            The meta.yml says the tool sorts by coordinate <em>or</em> read name. Nothing states
            the input is unsorted &mdash; a BAM arriving from an aligner usually is, but that is
            my knowledge and not this tool&rsquo;s evidence.</div>

          <div style="display:flex; align-items:center; justify-content:space-between;
                      padding-top:18px;">
            <span class="m" style="font-size:10px; color:{NOTE};">
              recorded as human &middot; R. Correia</span>
            <div style="display:flex; gap:10px;">
              <button class="btn">Leave it open</button>
              <button class="btn go">Save this answer</button>
            </div>
          </div>
        </div>
      </div>

      <div>
        <div class="lb" style="padding-bottom:12px;">Evidence for this hole</div>
        <div style="display:flex; flex-direction:column; gap:14px;">
{evidence}        </div>
        <div class="m" style="font-size:10px; color:{NOTE}; padding-top:16px; line-height:1.55;">
          Every excerpt is quoted from the source at the pinned revision. A claim with no
          evidence id behind it is a claim nobody can follow.</div>

        <div style="height:1px; background:{SOFT}; margin:20px 0;"></div>

        <div class="lb" style="padding-bottom:10px;">Still open on this revision</div>
        <div style="display:flex; flex-direction:column; gap:8px;">
          <div class="lift" style="display:flex; align-items:center; gap:9px; padding:7px 0;
                      cursor:pointer;">
            <span class="dot fail"></span>
            <span class="m" style="font-size:10.5px; flex:1;">consumes.bam.state</span>
            <span class="m" style="font-size:9.5px; color:{MEAS};">this one</span>
          </div>
          <div class="lift" style="display:flex; align-items:center; gap:9px; padding:7px 0;
                      cursor:pointer;">
            <span class="dot open"></span>
            <span class="m" style="font-size:10.5px; color:{INK2}; flex:1;">
              produces.versions.type_id</span>
            <span class="m" style="font-size:9.5px; color:{NOTE};">optional</span>
          </div>
        </div>
      </div>
    </div>
"""
    return page(body, HEIGHT["answer_hole"])


BOARDS = {
    "ForgeOverview.dc.html": overview,
    "ForgeCatalogue.dc.html": catalogue,
    "ForgeWork.dc.html": work,
    "ForgeAdaptation.dc.html": adaptation,
    "ForgeReview.dc.html": review,
    "ForgeReviewChanges.dc.html": review_changes,
    "ForgeReviewCode.dc.html": review_code,
    "ForgeReviewParams.dc.html": review_params,
    "ForgeAnswerHole.dc.html": answer_hole,
}

CANVAS = {
    "artboards": [
        {"file": "ForgeOverview.dc.html", "x": 0, "y": 0, "w": 1400, "h": 848,
         "title": "Overview — /forge"},
        {"file": "ForgeCatalogue.dc.html", "x": 1520, "y": 0, "w": 1400, "h": 772,
         "title": "Catalogue — /forge/catalogue"},
        {"file": "ForgeWork.dc.html", "x": 3040, "y": 0, "w": 1400, "h": 1020,
         "title": "Work queue — /forge/work"},
        {"file": "ForgeAdaptation.dc.html", "x": 0, "y": 1240, "w": 1400, "h": 646,
         "title": "Adaptation, running — /forge/adaptations/:id"},
        {"file": "ForgeReview.dc.html", "x": 1520, "y": 1240, "w": 1400, "h": 691,
         "title": "Review — same route"},
        {"file": "ForgeReviewChanges.dc.html", "x": 3040, "y": 1240, "w": 1400, "h": 757,
         "title": "Request changes, stale base"},
        {"file": "ForgeReviewCode.dc.html", "x": 0, "y": 2500, "w": 1400, "h": 854,
         "title": "Files — what is actually being approved"},
        {"file": "ForgeReviewParams.dc.html", "x": 1520, "y": 2500, "w": 1400, "h": 982,
         "title": "Parameters and rule candidates"},
        {"file": "ForgeAnswerHole.dc.html", "x": 3040, "y": 2500, "w": 1400, "h": 968,
         "title": "Answering a hole by hand"},
    ],
    "annotations": [
        {"id": "brief", "x": 0, "y": -230, "w": 460,
         "text": "Forge MVP §8 — six boards, one fixture.\n\nEvery count, status and revision "
                 "comes from one dict in .design/build_forge.py, so the overview's \"5 ready "
                 "for review\" and the work queue's five rows cannot disagree.\n\nObservatory "
                 "palette lifted by value from frontend/src/tokens.css — no second Forge theme."},
        {"id": "status-rule", "x": 1520, "y": -230, "w": 440,
         "text": "Status is a SHAPE plus a label, never colour alone.\n\nsquare = adapted · "
                 "triangle = in review · diamond = failed · circle = running · outline = not "
                 "adapted. Each carries its word beside it."},
        {"id": "review-row", "x": 0, "y": 2270, "w": 900,
         "text": "The three boards this row adds are all the SAME route as Review — tabs on "
                 "/forge/adaptations/:id, not new pages.\n\nThe last one is the product's "
                 "whole claim made reachable: typed questions a person closes. Nothing on the "
                 "first six let anybody answer a hole, and there was no other screen where "
                 "they could."},
        {"id": "edge-cases", "x": 3040, "y": -230, "w": 440,
         "text": "Edge cases carried on purpose:\n\n· a tool name long enough to need wrapping "
                 "(subread/featurecounts)\n· \"version unresolved\" where nothing proved one\n"
                 "· a stale source with its sync error (pegi3s, MI0104)\n· failed validation and "
                 "a moved registry base (ReviewChanges)\n· tables scroll inside themselves; the "
                 "page never scrolls sideways"},
    ],
    "launch": {"view": "canvas"},
}


def main() -> None:
    for name, build in BOARDS.items():
        # `Main.dc.html` is the entry artboard and must exist; the overview is the front door,
        # so it is Main and keeps its Forge name as a second copy for the repository's own
        # `.design/Forge*.dc.html` convention in §8.6.
        # **No `Main.dc.html`.** `.design/Main.dc.html` belongs to the 2026-08-29 canvas and
        # is cited by path from live documents; writing the overview there would clobber it.
        # §8.6 names these six flat, so they stay flat and the canvas launches on the whole
        # board rather than on an entry artboard.
        (OUT / name).write_text(build())
    (OUT / "canvas.forge.json").write_text(json.dumps(CANVAS, indent=2) + "\n")
    print(f"wrote {len(BOARDS)} boards + canvas.forge.json")


if __name__ == "__main__":
    main()
