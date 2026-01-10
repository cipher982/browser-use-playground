# ATT Billing Extraction - Handoff Document

**Last Updated:** 2026-01-09

## Goal
Extract DAVID ROSE's monthly charges from AT&T family plan billing for all months since July 2024, including international/roaming charges.

Target line: **David Rose (205-441-8790)** - had expensive international charges (~$146/month early on, including $120 International Day Pass)

---

## Current State (as of 2026-01-09)

### What's Working Now
- **Login persists!** Profile at `browser_profile/` maintains AT&T session
- No need for `wait_for_login` action anymore
- Script has **full usage tracking** including reasoning tokens (via monkey-patch)

### Best Result So Far
**o3 + vision ON** extracted 4 months:

| Billing Period | David Rose Total | Notes |
|----------------|------------------|-------|
| Jul 07 - Aug 06 | $146.64 | Monthly access $40, $25 discount |
| Aug 07 - Sep 06 | $146.64 | **$120 International Day Pass (10 × $12)** + monthly |
| Sep 07 - Oct 06 | -$12.62 | Credit/adjustment month |
| Oct 07 - Nov 06 | $0.00 | No charges |

**GRAND TOTAL: $280.66**

The international charges were found! $120 = 10 × $12 International Day Pass in the Aug billing period.

---

## How to Run

```bash
cd ~/git/browser-playground
uv run experiments/att-billing/extract_charges.py
```

Browser opens automatically. Profile is already logged in - agent should navigate directly to billing.

### Changing Config
Edit `extract_charges.py`:
```python
llm = ChatOpenAI(model="o3")  # Change model here
use_vision=True,              # Toggle vision ON/OFF
max_steps=150                 # Increase for more months
```

---

## How to Interpret Results

### Three Types of "Success/Failure"

1. **Agent completion** - Did the agent return a `done` action with results?
   - Check for "Task completed successfully" in output
   - This means the agent thinks it finished

2. **Judge evaluation** - browser-use has a built-in judge that grades the result
   - Look for "Judge Verdict: FAIL/PASS" in output
   - Judge may fail even if agent returned data (e.g., incomplete)

3. **Manual kill** - We killed the run before it finished
   - No results returned
   - Only see partial data in step-by-step logs

**Example from this session:**
- o3 + vision ON: Agent completed ✅, Judge failed ❌ (only 4 months, not all)
- o3 + vision OFF: We killed it (scroll hell), no results returned

### Reading Step Logs
Each step shows:
- `Eval:` - Agent's assessment of last action
- `Memory:` - What data it's collected so far (look here for partial results!)
- `Next goal:` - What it's about to try
- `▶️` - The actual action taken

**Scroll hell signature:** Repeated `scroll down 0.X pages` then `scroll up 0.X pages` bouncing back and forth.

---

## Usage Tracking

The script tracks full token usage including **reasoning tokens** (crucial for o3 cost):

```
USAGE METRICS (Full):
Model: o3
Vision: True
Steps: 57
LLM Invocations: 57
Total tokens: X,XXX
  Prompt tokens: X,XXX
  Completion tokens: X,XXX
  Reasoning tokens: X,XXX  <-- This is the big one for o3!
  Cached tokens: X,XXX
```

Logs are saved to `experiments/att-billing/logs/` as JSON files.

### How Usage Tracking Works
browser-use doesn't track reasoning tokens natively. We monkey-patch `ChatOpenAI._get_usage`:
```python
def patched_get_usage(self, response: ChatCompletion):
    if response.usage.completion_tokens_details:
        reasoning_tokens = response.usage.completion_tokens_details.reasoning_tokens or 0
    # ... capture and log
    return original_get_usage(self, response)
```

**Note:** browser-use may have a bug where it ADDS reasoning tokens to completion tokens (double counting). Our tracking captures the raw values before this.

---

## Model Results Summary

| Model | Vision | Result | Notes |
|-------|--------|--------|-------|
| o3 | ON | **4 months extracted** | Best result! Actually completed |
| o3 | OFF | 3 months, killed | Scroll hell on Oct bill |
| gpt-5-nano | ON | Failed | Stuck searching literal "June 2024" |
| gpt-5-nano | OFF | Failed | Wrong URL, auth errors |
| gpt-5-mini | OFF | Failed | Navigation loops |
| gpt-5.2 | ON | Failed | JSON parsing bug |
| gpt-4o | OFF | Partial | Toggle loops |
| gpt-4.1-nano | OFF | Failed | Nav loops, 547K tokens wasted |

**Key Finding:** Vision ON actually performed BETTER for o3 in latest test - it was willing to accept partial info and move on. Vision OFF got stuck in perfectionist scroll loops.

---

## Known Issues

### Scroll Hell
All models eventually get stuck scrolling up/down trying to find elements that may not exist (e.g., $0 bills have no line items). No amount of prompt engineering fixes this - it's a fundamental limitation.

### Oct Bill Edge Case
Oct 07 - Nov 06 is $0.00 with no line items to display. Models waste many steps trying to find David Rose's line when it doesn't exist. Vision ON eventually gave up and used account summary. Vision OFF never gave up.

### browser-use ChatOpenAI vs langchain_openai ChatOpenAI
browser-use has its own `ChatOpenAI` class (not langchain's). You MUST use browser-use's version:
```python
from browser_use import ChatOpenAI  # Correct
# NOT: from langchain_openai import ChatOpenAI
```

### Profile Directory Naming
Directory name must NOT contain "chrome" or browser-use copies it to temp. Use `browser_profile/` not `chrome_profile/`.

---

## Key Files

| File | Purpose |
|------|---------|
| `extract_charges.py` | Main script with usage tracking |
| `browser_profile/` | Persistent browser profile (has login) |
| `logs/` | JSON logs from runs with full usage data |
| `POST_MORTEM.md` | Detailed results from all experiments |
| `HANDOFF.md` | This file |

---

## Next Steps to Try

### 1. Try Claude Models (Untested)
```python
from langchain_anthropic import ChatAnthropic
llm = ChatAnthropic(model="claude-sonnet-4-20250514")
```
Different model family might handle scrolling differently.

### 2. Get Remaining Months
Current best run got Jul-Oct 2024. Need Nov 2024 - Jan 2026. May need to:
- Increase max_steps
- Paginate through billing history
- Or accept this is the limit

### 3. PDF-First Strategy
Skip UI entirely:
1. Navigate to billing history
2. Download PDFs for each month
3. Parse PDFs with pdfplumber externally

---

## Environment

```bash
# Dependencies (in pyproject.toml)
browser-use==0.11.2
langchain-openai
langchain-core
python-dotenv

# Required env vars (in .env)
OPENAI_API_KEY=...
```

---

## Quick Reference

**Run:** `uv run experiments/att-billing/extract_charges.py`

**Change model:** Edit `llm = ChatOpenAI(model="...")`

**Change vision:** Edit `use_vision=True/False`

**Check results:** Look for "Final Result:" in output, or read `logs/*.json`

**Read partial data:** Search step logs for `Memory:` lines

**Access agent settings:** `agent.settings.use_vision` (not `agent.use_vision`)
