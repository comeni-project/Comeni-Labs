# Render artboards to PNG, so a board can be LOOKED AT rather than read.
#
# **Reading finds wrong strings; it does not find wrong pictures** — the 2026-09-01 lesson, and
# it earned itself again on 2026-09-05: a status shape that collapsed to nothing inside a table
# cell, a flow connector that rendered as empty space, a chat rail that ran off the edge at
# tablet width. Every one of those is invisible in the HTML and obvious in a screenshot.
#
#     python3 _prev.py                       # every board matching the default glob
#     python3 _prev.py ForgeOverview         # named boards
#     python3 _prev.py --glob 'Forge*'       # a different set
#     python3 _prev.py --width 900           # one width; repeatable
#     python3 _prev.py --dir living-pipeline --glob 'Living*'   # a canvas in a subdirectory
#
# Widths default to 1400 and 900 — the desktop and tablet targets §8 names. **The 900 pass is
# not optional**: a two-column layout with no breakpoint looks correct at 1400 and loses its
# right-hand column entirely at 900, which is what happened to the review rail.
import argparse
import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).parent
# **Under `build/`, which is gitignored and anchored.** This wrote into a hardcoded
# `/tmp/claude-1000/…/<a session id>/scratchpad/prev` until 2026-09-05 — a path belonging to
# whichever session last edited this file, so a later run either failed or quietly filled a
# stranger's directory. A path derived from the repository cannot rot that way.
OUT = HERE.parent / "build" / "prev"


def flatten(source: pathlib.Path) -> tuple[str, int]:
    """A `.dc.html` artboard as a page a browser can open, and its declared height.

    The runtime's `<script src="./support.js">` and any `data-dc-script` block are stripped —
    neither exists outside the canvas — and the `<x-dc>`/`<helmet>` wrappers come off so the
    styles land in the document head.
    """
    text = source.read_text()
    text = text.replace('{{ t.sans }}', '"Geist", system-ui, sans-serif')
    text = text.replace('{{ t.mono }}', '"Geist Mono", ui-monospace, monospace')
    text = re.sub(r'<script src="\./support\.js"></script>', "", text)
    text = re.sub(r"<script data-dc-script.*?</script>", "", text, flags=re.S)
    for tag in ("<x-dc>", "</x-dc>", "<helmet>", "</helmet>"):
        text = text.replace(tag, "")
    found = re.search(r"min-height:(\d+)px", text)
    return text, int(found.group(1)) if found else 1400


def content_height(page: pathlib.Path, width: int) -> int:
    """What the board actually needs at this width, measured rather than guessed.

    Every Forge board first shipped 100–350px taller than its content, and no amount of reading
    would have shown it. This asks the browser for the deepest laid-out element, with the
    container's `min-height` removed so it cannot answer with the guess it was given.
    """
    probe = OUT / "_probe.html"
    text = re.sub(r"min-height:\d+px", "min-height:0", page.read_text())
    probe.write_text(
        text.replace(
            "</body>",
            '<script>var d=document.querySelectorAll("div");var b=0;'
            "for(var i=0;i<d.length;i++){var r=d[i].getBoundingClientRect();"
            'if(getComputedStyle(d[i]).position!=="absolute"&&r.bottom>b)b=r.bottom;}'
            'document.title="H"+Math.round(b);</script></body>',
        )
    )
    done = subprocess.run(
        ["google-chrome-stable", "--headless", "--disable-gpu", "--no-sandbox",
         "--virtual-time-budget=2500", f"--window-size={width},4000", "--dump-dom",
         f"file://{probe}"],
        capture_output=True, text=True,
    )
    seen = re.search(r"<title>H(\d+)</title>", done.stdout)
    return int(seen.group(1)) + 40 if seen else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="board stems, without .dc.html")
    parser.add_argument("--glob", default="Run*", help="which boards when none are named")
    parser.add_argument("--width", type=int, action="append", dest="widths")
    # **A canvas may live in a subdirectory**, which `.design/README.md` reserves for a
    # superseded one — and a NEW canvas has no citations to rot, so it starts there rather than
    # adding a fourth set of boards to an already crowded root.
    parser.add_argument("--dir", default=".", help="board directory, relative to .design/")
    args = parser.parse_args()

    src = (HERE / args.dir).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    widths = args.widths or [1400, 900]
    names = args.names or sorted(
        p.name.replace(".dc.html", "") for p in src.glob(f"{args.glob}.dc.html")
    )
    if not names:
        raise SystemExit(f"no boards matched {args.glob!r} — nothing to render")

    for name in names:
        text, declared = flatten(src / f"{name}.dc.html")
        page = OUT / f"{name}.html"
        page.write_text(text)
        for width in widths:
            # The declared height is right at the width the board was authored for; at a
            # narrower one the layout stacks and needs more, so measure rather than crop.
            tall = declared if width >= 1400 else (content_height(page, width) or declared)
            suffix = "" if width == 1400 else f"-{width}"
            subprocess.run(
                ["google-chrome-stable", "--headless", "--disable-gpu", "--no-sandbox",
                 "--hide-scrollbars", "--virtual-time-budget=4000",
                 f"--window-size={width},{tall}",
                 f"--screenshot={OUT}/{name}{suffix}.png", f"file://{page}"],
                capture_output=True,
            )
            print(f"shot {name} {width}×{tall}")
    print(f"\n{OUT}")


if __name__ == "__main__":
    main()
