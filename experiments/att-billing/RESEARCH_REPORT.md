# OpenAI Model Comparison for browser-use

**Date:** 2026-01-10
**Task:** Extract billing data from AT&T website (accordion UI navigation)

## Background

We tested 14 configurations of modern OpenAI models with [browser-use](https://github.com/browser-use/browser-use) v0.11.2 for a complex web scraping task. The goal was to extract a specific user's (DAVID ROSE) monthly charges from AT&T's billing portal.

### Why This Task is Hard

- **Login session management** - Must use existing authenticated session
- **Complex SPA** - AT&T billing is a React app with dynamic loading
- **Accordion UI** - Bills are collapsed by default, must expand each one
- **Nested data** - Line items are inside expanded bill sections
- **Multi-step navigation** - Account menu → See my bill → See all statements → Expand each month → Find specific line

### The Correct Answer

| Billing Period | David Rose Total | Notes |
|----------------|------------------|-------|
| Jul 07 - Aug 06 | $146.64 | International Day Pass $120, surcharges $11.64 |
| Aug 07 - Sep 06 | $146.64 | International Day Pass $120, surcharges $11.64 |
| Sep 07 - Oct 06 | -$12.62 | Partial month credit -$12.50, surcharges -$0.12 |
| Oct 07 - Nov 06 | $0.00 | No charges (service canceled) |

**GRAND TOTAL: $280.66**

---

## Results Summary

| Model | Tokens | Answer | Correct? |
|-------|--------|--------|----------|
| **gpt-4.1** | 137K | **$280.66** | ✓ |
| **o4-mini** | 216K | **$280.66** | ✓ |
| **gpt-5.1** | 227K | **$280.66** | ✓ |
| gpt-5-mini | 187K | $134.02 | ✗ (partial) |
| gpt-4.1-mini | 386K | $293.28 | ✗ (partial) |
| o3 | 294K | $293.28 | ✗ (scroll hell) |
| o3-mini | 96K | $293.28 | ✗ (stopped early) |
| gpt-5 | 450K | incomplete | ✗ (timeouts) |
| gpt-5-nano | 461K | $460.04 | ✗ (wrong data) |
| gpt-5.2 | 90K | FAILED | ✗ (JSON bug) |
| gpt-4o-mini | 692K | partial | ✗ |
| gpt-4.1-mini (vision) | 430K | partial | ✗ |
| o3-mini (vision) | 0 | FAILED | ✗ (no vision support) |
| gpt-4.1-nano | 547K | FAILED | ✗ (nav loops) |

---

## Detailed Results

| Model | Vision | Steps | LLM Calls | Tokens | Reasoning | Result | Notes |
|-------|--------|-------|-----------|--------|-----------|--------|-------|
| **gpt-4.1** | OFF | 13 | 17 | 137K | 0 | **$280.66** | Most efficient! Missed Int'l Day Pass notes |
| **o4-mini** | OFF | 20 | 22 | 216K | 7.5K | **$280.66** | Best detail extraction |
| **gpt-5.1** | OFF | 22 | 23 | 227K | 4.6K | **$280.66** | Clean execution, found all details |
| gpt-5-mini | OFF | 24 | 18 | 187K | 2.8K | $134.02 | 6 timeouts, only 2 months |
| gpt-4.1-mini | OFF | 31 | 40 | 386K | 0 | $293.28 | Good coverage but incomplete |
| o3 | OFF | 27 | 28 | 294K | 6K | $293.28 | Scroll hell, worse than o4-mini |
| o3-mini | OFF | 11 | 12 | 96K | 5.3K | $293.28 | Fast but stopped early |
| gpt-5 | OFF | 31 | 43 | 450K | 37.9K | incomplete | Multiple 60s timeouts |
| gpt-5-nano | OFF | 31 | 54 | 461K | 17.3K | $460.04 | Extracted account totals, not line items |
| gpt-5.2 | OFF | 9 | 9 | 90K | 8.4K | FAILED | JSON parsing bug |
| gpt-4o-mini | OFF | 31 | 32 | 692K | 0 | partial | High token usage |
| gpt-4.1-mini | ON | 31 | 35 | 430K | 0 | partial | Vision hurt performance |
| o3-mini | ON | 5 | 0 | 0 | 0 | FAILED | No vision support |
| gpt-4.1-nano | OFF | 51 | 52 | 547K | 0 | FAILED | Nav loops, never found billing |

---

## Key Findings

### 1. Best Models for Complex UI Navigation

**Tier 1 (Recommended):**
- **gpt-4.1** - Most token-efficient (137K). Fast execution (13 steps). Got correct total but missed detailed notes.
- **o4-mini** - Best detail extraction. Found International Day Pass charges that others missed. Good reasoning (7.5K tokens).
- **gpt-5.1** - Reliable and thorough. No bugs. Slightly higher token cost but very consistent.

**Tier 2 (Acceptable):**
- **gpt-4.1-mini** - Works but high token usage. Solid navigation.
- **o3-mini** - Very efficient (96K tokens) but stops early declaring success.

**Tier 3 (Avoid):**
- **o3** - Gets stuck in "scroll hell". Uses 294K tokens for only 2 months.
- **gpt-5** (base) - Multiple 60-second timeouts. 450K tokens for incomplete results.
- **gpt-5-mini** - Too many timeouts, partial extraction.
- **gpt-5-nano** - Completely confused, extracted wrong data (account totals instead of line items).
- **gpt-5.2** - JSON parsing bug makes it unusable.
- **gpt-4.1-nano** - Gets stuck in navigation loops, never reaches billing data. 547K tokens wasted.

### 2. Vision Mode Impact

| Model | Vision OFF | Vision ON |
|-------|------------|-----------|
| gpt-4.1-mini | 5 months (386K tokens) | 2 months (430K tokens) |
| o3-mini | 2 months (96K tokens) | FAILED (no vision support) |

**Finding:** Vision mode **hurts** performance for accordion UIs:
- Increases token usage without improving results
- Models get distracted by visual details instead of DOM structure
- o-series models don't support vision at all

### 3. Reasoning Token Usage

| Model | Reasoning Tokens | % of Completion | Result |
|-------|------------------|-----------------|--------|
| gpt-5 | 37,888 | 71% | Poor (timeouts) |
| gpt-5-nano | 17,344 | 58% | Failed (wrong data) |
| gpt-5.2 | 8,417 | 74% | Failed (JSON bug) |
| o4-mini | 7,488 | 60% | Excellent |
| o3 | 6,000 | 48% | Poor (scroll hell) |
| o3-mini | 5,312 | 65% | Good (stopped early) |
| gpt-5.1 | 4,624 | 31% | Excellent |
| gpt-5-mini | 2,816 | 22% | Poor (timeouts) |

**Finding:** More reasoning tokens ≠ better results. gpt-5 used 38K reasoning tokens but performed worse than gpt-5.1's 4.6K.

### 4. Token Efficiency

| Model | Tokens per Step | Result Quality |
|-------|-----------------|----------------|
| o3-mini | 8,734 | Good (stopped early) |
| gpt-5-mini | 7,810 | Poor (timeouts) |
| gpt-5.2 | 9,990 | Failed |
| o4-mini | 10,807 | Excellent |
| gpt-5.1 | 10,336 | Excellent |
| gpt-4.1 | 10,558 | Excellent |
| o3 | 10,889 | Poor (scroll hell) |
| gpt-4.1-nano | 10,729 | Failed (nav loops) |
| gpt-4.1-mini | 12,445 | Good |
| gpt-5 | 14,527 | Poor (timeouts) |
| gpt-5-nano | 14,871 | Failed |
| gpt-4o-mini | 22,319 | Acceptable |

### 5. Known Issues

#### gpt-5.2 JSON Parsing Bug
```
Invalid JSON: trailing characters at line 2 column 1
```
The model outputs duplicate JSON objects, breaking structured output parsing.

#### gpt-5/gpt-5-mini Timeouts
Multiple 60-second LLM call timeouts, suggesting slower inference or overly long reasoning chains.

#### gpt-5-nano Confusion
Model got confused between account-level totals and line-item totals, and thought 2024 data was from 2007.

#### o-series No Vision Support
```
Invalid content type. image_url is only supported by certain models.
```
OpenAI's reasoning models (o3, o3-mini, o4-mini) don't support vision mode.

#### o3 "Scroll Hell"
The o3 model gets stuck repeatedly scrolling up and down looking for elements, never finding them despite using 294K tokens.

#### gpt-4.1-nano Navigation Loops
The nano model gets stuck in navigation loops, repeatedly clicking Account buttons and navigating to billing URLs without ever successfully loading or extracting data. Burned 547K tokens without extracting a single billing period.

---

## Recommendations

### For browser-use Tasks

1. **Best for cost efficiency: gpt-4.1** (no vision)
   - Lowest token usage (137K) for successful completion
   - Fast execution (13 steps vs 20+ for others)
   - May miss detailed notes in extraction

2. **Best for accuracy: o4-mini** (no vision)
   - Best balance of accuracy, efficiency, and cost
   - Strong reasoning for complex navigation
   - Found edge cases other models missed

3. **Reliable alternative: gpt-5.1** (no vision)
   - No bugs, very consistent
   - Good for complex extraction tasks
   - Slightly higher token cost but thorough

4. **Budget option: o3-mini** (no vision)
   - Very efficient (96K tokens)
   - May stop early on complex tasks

**Avoid:** gpt-5 (timeouts), gpt-5-nano (confusion), gpt-5-mini (timeouts), o3 (scroll hell), gpt-5.2 (JSON bug), gpt-4.1-nano (nav loops)

### Vision Mode Guidelines

- **Default to vision OFF** for accordion/nested UIs
- o-series models don't support vision at all
- Vision increases token usage without improving results

### Token Budget Planning

For complex accordion UI extraction:
- **gpt-4.1**: ~140K tokens (most efficient)
- **o3-mini**: ~100K tokens (may stop early)
- **o4-mini/gpt-5.1**: ~220K tokens (best accuracy)
- gpt-5-mini: ~190K tokens (unreliable)
- o3: ~300K tokens (avoid)
- gpt-4.1-mini: ~400K tokens
- gpt-5/gpt-5-nano: ~450K tokens (avoid)
- gpt-4.1-nano: ~550K tokens (avoid - nav loops)
- gpt-4o-mini: ~700K tokens

---

## Test Environment

- browser-use v0.11.2
- Python 3.12
- macOS (Apple Silicon)
- AT&T billing website (complex React SPA with accordions)
- Pre-authenticated browser session

## Files

- `extract_charges.py` - Parameterized test script
- `logs/*.json` - Raw test results with full usage data (14 runs)
- `HANDOFF.md` - Session handoff document
- `POST_MORTEM.md` - Detailed run analysis
