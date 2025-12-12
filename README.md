# browser-use-playground

Small, reproducible playground for comparing:

- **Playwright** (deterministic automation/scraping)
- **browser-use (OSS)** (LLM-driven browser operator)

This repo intentionally does **not** track generated scrape outputs (they are large + site-specific). See `.gitignore`.

## Layout

- `benchmarks/race.py` — benchmark runner (Playwright vs browser-use)
- `scripts/mbworld/` — the original MBWorld Playwright experiments/scraper
- `race_results/` — outputs (gitignored)

## Setup

1) Create a local env file:

```bash
cp .env.example .env
```

2) Fill in `OPENAI_API_KEY` in `.env`.

## Run (Playwright baseline)

MBWorld blocks headless frequently; use headful + offscreen + request blocking:

```bash
./.venv/bin/python benchmarks/race.py \\
  --method playwright \\
  --max-pages 1 \\
  --headful \\
  --offscreen \\
  --block-ads \\
  --block-assets \\
  --out race_results/outputs/playwright_fast_p1.jsonl
```

## Run (browser-use OSS)

```bash
./.venv/bin/python benchmarks/race.py \\
  --method browser-use \\
  --max-pages 1 \\
  --headful \\
  --offscreen \\
  --vision \\
  --model gpt-5-mini \\
  --out race_results/outputs/browser_use_p1.jsonl
```

Note: browser-use can be slower / less deterministic on bulk extraction tasks; this is the point of the benchmark.

