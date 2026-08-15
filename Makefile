.PHONY: help check verify slow guards residue drift links test lint fmt types docs static stub profile clean

# A sibling checkout of github.com/comeni-project/comeni-registry, if you have one.
# `make drift` skips when it is absent rather than failing: a target that breaks over a
# missing optional checkout is a target people stop running.
# Sibling of the MAIN checkout, not of the current directory. `../comeni-registry` was
# relative to `$(CURDIR)`, so from `.worktrees/<plan>` it resolved to
# `.worktrees/comeni-registry` and never existed — and `drift` prints "skipped" rather than
# failing when the path is absent. CLAUDE.md requires every plan to be executed in a
# worktree, so this gate was structurally inert for exactly the work most likely to change
# `registry/`: Plan 1.15 Task 0 edited all twelve contracts under a green `make verify`.
# `--git-common-dir` is the main repository's `.git` from inside a worktree.
_MAIN_ROOT := $(dir $(patsubst %/.git,%,$(shell git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)))
REGISTRY ?= $(_MAIN_ROOT)comeni-registry

help:           ## show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t20

check: lint test types docs links  ## everything CI runs on a pull request (~1 min, no Docker)

verify:         ## check + slow + guards + drift — needs Docker, ~2 min. See CLAUDE.md
	@$(MAKE) --no-print-directory -j1 check
	@$(MAKE) --no-print-directory slow
	@$(MAKE) --no-print-directory guards
	@$(MAKE) --no-print-directory drift
# Sequential sub-makes rather than prerequisites: `verify: check slow guards` would let
# -j interleave them, and cheapest-first only means something if it is actually ordered.
# `-j1` on check is not a preference — MAKEFLAGS carries -j12 here and has hidden a lint
# failure before.

slow:           ## the counts-matrix tests: --gate test on real data (Docker, ~45s warm)
	uv run pytest -m slow -v

guards:         ## purity, egress and construction — the tests that hold the invariants
	uv run pytest tests/test_purity.py tests/test_purity_runtime.py \
	  tests/test_egress.py tests/test_construction.py -v

residue:        ## how much of A14 is left, counted per guard (A69). --list for the names
	@uv run python tools/guard_residue.py $(ARGS)

drift:          ## registry/ against a comeni-registry checkout, if one is present
	@if [ -d "$(REGISTRY)" ]; then \
	  uv run python tools/check_registry_drift.py "$(REGISTRY)"; \
	else \
	  echo "drift: skipped, no checkout at $(REGISTRY) — REGISTRY=<path> make drift"; \
	fi

test:           ## run the test suite
	uv run pytest -v

lint:           ## ruff, line length 100
	uv run ruff check .

fmt:            ## format in place
	uv run ruff format .

types:          ## fail if the generated measurement stub is stale
	uv run python tools/generate_types.py --check

links:          ## every relative markdown link in docs/ and the root resolves
	uv run python tools/check_links.py

docs:           ## fail if docs/reference/diagnostics.md is stale
	uv run python tools/generate_diagnostics_doc.py --check

static:         ## conformance + lint + preview — everything checkable without Docker
	uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate lint
	uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate preview

stub:           ## build the RNA-seq spine and run the stub gate (needs Docker + Nextflow)
	uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub

profile:        ## emit a pipeline that measures the input data
	uv run mendel profile --have fastq.reads --out profile-build/

clean:          ## remove build outputs
	rm -rf build/ profile-build/ dist/ .pytest_cache/ .ruff_cache/
