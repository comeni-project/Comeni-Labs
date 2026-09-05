# Screenshot the RUNNING pages, so they can be put beside the artboards `_prev.py` renders.
#
# **Reading annotations is not visual validation** — the 2026-09-01 lesson, and the reason this
# file exists at all. `_prev.py` renders the drawing; this renders the thing that was built from
# it; `_compare.html` puts them in one viewport. All three are needed: comparing a page to its
# artboard by reading HTML found six real defects, and putting both on screen found four more —
# and those four were the ones that made the page look wrong.
#
#     python3 _shots.py                          # every page, at both widths
#     python3 _shots.py --base http://localhost:58080
#     python3 _shots.py forge-overview           # named pages
#
# **Against nginx, not Vite.** The built bundle is what a person is served; Vite's dev server
# injects a client and can differ on anything that depends on how CSS is emitted.
import argparse
import pathlib
import subprocess
import time

HERE = pathlib.Path(__file__).parent
OUT = HERE.parent / "build" / "shots"

# Each is `(name, path)`. The name matches the artboard it is compared against, minus the
# `Forge` prefix, so `_compare.html` can pair them without a second table.
PAGES = [
    ("ForgeOverview", "/forge"),
    ("ForgeCatalogue", "/forge/catalogue"),
    ("ForgeWork", "/forge/work"),
    # An adaptation in review, which is what `ForgeReview` and its three siblings draw. The id
    # comes from the walk rather than a fixture: these boards are about a *candidate*, and a
    # page with no revision behind it draws the empty state instead of the thing being compared.
    ("ForgeReview", "/forge/adaptations/ee2a5ab58ded810474f36ed1a21e97b9"),
    ("ForgeReviewCode", "/forge/adaptations/ee2a5ab58ded810474f36ed1a21e97b9?tab=Files"),
    ("ForgeReviewParams", "/forge/adaptations/ee2a5ab58ded810474f36ed1a21e97b9?tab=Fields"),
]


def shoot(base: str, name: str, path: str, width: int, tall: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    suffix = "" if width == 1400 else f"@{width}"
    subprocess.run(
        [
            "google-chrome-stable", "--headless", "--disable-gpu", "--no-sandbox",
            "--hide-scrollbars",
            # **Long enough for a query to answer.** These pages render a skeleton and then
            # their data; a budget that ended first would screenshot the loading state and the
            # comparison would be against a page nobody sees.
            "--virtual-time-budget=6000",
            f"--window-size={width},{tall}",
            f"--screenshot={OUT}/{name}{suffix}.png",
            f"{base}{path}",
        ],
        capture_output=True,
    )
    print(f"shot {name} {width}×{tall}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="page names, or all of them")
    parser.add_argument("--base", default="http://localhost:58080")
    parser.add_argument("--width", type=int, action="append")
    parser.add_argument("--tall", type=int, default=1600)
    args = parser.parse_args()

    widths = args.width or [1400, 900]
    wanted = [p for p in PAGES if not args.names or p[0] in args.names]
    for name, path in wanted:
        for width in widths:
            shoot(args.base, name, path, width, args.tall)
            time.sleep(0.2)
    print(f"\n{OUT}")


if __name__ == "__main__":
    main()
