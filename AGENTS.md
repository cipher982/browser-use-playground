# browser-playground

Experimental playground for agentic browser automation.

## Stack

- **browser-use**: LLM-driven browser automation (requires OpenAI API key)
- **Playwright**: Deterministic browser automation
- **Python 3.12+** with uv

## Structure

```
examples/           Simple standalone scripts
experiments/        Larger experiments with their own READMEs
outputs/            Generated files (gitignored)
```

## Running

```bash
uv sync                                    # Install deps
uv run examples/simple_agent.py "task"     # Run example
uv run experiments/*/some_script.py        # Run experiment
```

## Adding Experiments

1. Create `experiments/your-experiment/`
2. Add scripts and an optional README
3. Outputs go to `outputs/` (gitignored)
