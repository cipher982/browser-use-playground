.PHONY: help setup lint race-playwright race-browser-use clean

PY ?= ./.venv/bin/python
RACE ?= benchmarks/race.py

help:
	@echo "Targets:"
	@echo "  setup            Install deps into existing .venv (uv optional)"
	@echo "  race-playwright   Run Playwright baseline (fast, ad-blocked)"
	@echo "  race-browser-use  Run browser-use (agentic) benchmark"
	@echo "  clean            Remove local outputs"

setup:
	@$(PY) -m pip --version >/dev/null 2>&1 || true
	@command -v uv >/dev/null 2>&1 && uv pip install --python $(PY) -e . || echo "uv not found; skipping (deps assumed in .venv)"
	@$(PY) -c "import playwright" >/dev/null 2>&1 || echo "Playwright not importable in .venv"

race-playwright:
	@mkdir -p race_results/outputs
	@$(PY) $(RACE) --method playwright --max-pages 1 --headful --offscreen --block-ads --block-assets --out race_results/outputs/playwright_fast_p1.jsonl

race-browser-use:
	@mkdir -p race_results/outputs
	@$(PY) $(RACE) --method browser-use --max-pages 1 --headful --offscreen --vision --model gpt-5-mini --out race_results/outputs/browser_use_p1.jsonl

clean:
	@rm -rf race_results/outputs

