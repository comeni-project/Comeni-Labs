.PHONY: help registry-present check verify slow guards residue links test lint fmt types docs static stub profile clean

registry-present:  ## refuse early if the registry submodule was not checked out
	@if [ ! -d registry/contracts ]; then \
	  echo "registry/ holds no registry data — it is a git submodule and was not checked out."; \
	  echo; \
	  echo "    git submodule update --init"; \
	  echo; \
	  echo "'git clone --recurse-submodules' avoids this. See docs/guides/contributing.md."; \
	  exit 1; \
	fi
# Here as well as in `layers.load()` because a contributor's first command is `make check`,
# not a pytest invocation — and thirty-three failures about missing contracts is not a
# diagnosis. Same sentence in both places on purpose.

help:           ## show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t20

check: registry-present lint test types docs links  ## everything CI runs on a pull request (~1 min, no Docker)

verify:         ## check + slow + guards — needs Docker, ~2 min. See CLAUDE.md
	@$(MAKE) --no-print-directory -j1 check
	@$(MAKE) --no-print-directory slow
	@$(MAKE) --no-print-directory guards
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
