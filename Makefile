.PHONY: help check verify slow guards drift test lint fmt types docs static stub profile clean

# A sibling checkout of github.com/comeni-project/comeni-registry, if you have one.
# `make drift` skips when it is absent rather than failing: a target that breaks over a
# missing optional checkout is a target people stop running.
REGISTRY ?= ../comeni-registry

help:           ## show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t20

check: lint test types docs  ## everything CI runs on a pull request (~1 min, no Docker)

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

docs:           ## fail if the generated diagnostics table is stale
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
