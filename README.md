# browser-playground

Experimental playground for agentic browser automation using [browser-use](https://github.com/browser-use/browser-use) and Playwright.

## Setup

```bash
cp .env.example .env  # add OPENAI_API_KEY
playwright install chromium  # one-time
```

## Usage

```bash
uv run examples/simple_agent.py "Search for the current weather in Tokyo"
```

## Structure

```
examples/           # Simple, reusable examples
experiments/        # Larger experiments & benchmarks
```
