"""Every backticked repository path in the agent brief and its two companions exists (#118).

`make links` checks Markdown links, and CLAUDE.md cites paths in backticks, which is how 29 dead
references to docs deleted on 2026-09-02 went unseen. This checks those.

**Only tokens that look like paths**, and the exclusions are the ones `check_links.py` learned the
hard way: a checker whose output is mostly noise is a checker people stop reading. A token with a
space is a command line, `*` or `{}` is a glob, `<>` is a template, `$` or `^` is shell or a git
revision, and `://` is a URL. A `module.attribute` has no slash and no file extension.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["CLAUDE.md", "docs/notes/now.md", "docs/design/invariants.md"]
_TICK = re.compile(r"`([^`\n]+)`")
_LINE_REF = re.compile(r":\d+(-\d+)?$")
_EXT = (".md", ".py", ".yml", ".yaml", ".toml", ".ts", ".tsx", ".json", ".nf", ".html", ".sh")


def _looks_like_path(token: str) -> bool:
    if any(c in token for c in " *{}<>$^") or "://" in token or token.startswith(("-", "~", "/")):
        return False
    if re.fullmatch(r"\.[A-Za-z0-9]+", token):
        return False  # a bare extension — `.nf`, `.pyi` — names a kind of file, not a file
    bare = _LINE_REF.sub("", token)
    return "/" in bare or bare.endswith(_EXT)


def tracked_names(root: Path) -> set[str]:
    """Every tracked file's name, for a bare filename written without its directory."""
    out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True)
    if out.returncode != 0:
        return set()  # not a repository: nothing is tracked, so only real paths resolve
    return {Path(line).name for line in out.stdout.splitlines()}


def _exists(token: str, root: Path, names: set[str]) -> bool:
    bare = _LINE_REF.sub("", token).rstrip("/")
    if "/" not in bare:
        # **A bare filename is live if the repository has a file by that name.** `tokens.test.ts`
        # is a reference; `wiener.md`, deleted on 2026-09-02, exists nowhere and is dead.
        return bare in names or (root / bare).exists()
    if (root / bare).exists():
        return True
    return any((src / bare).exists() for src in root.glob("packages/*/src"))


def dead_paths(text: str, root: Path, names: set[str] | None = None) -> list[tuple[int, str]]:
    names = tracked_names(root) if names is None else names
    dead = []
    for number, line in enumerate(text.splitlines(), start=1):
        for token in _TICK.findall(line):
            if _looks_like_path(token) and not _exists(token, root, names):
                dead.append((number, token))
    return dead


def main() -> int:
    failed = 0
    for name in FILES:
        path = ROOT / name
        if not path.exists():
            continue
        for number, token in dead_paths(path.read_text(), ROOT):
            print(f"{name}:{number}: `{token}` does not exist")
            failed += 1
    if failed:
        print(f"{failed} dead path(s). Fix the path, or cite a removed file as "
              "`git show <commit>^:<path>`.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
