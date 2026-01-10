# ATT Billing Extraction - Post Mortem

Date: 2025-01-09 (updated 2026-01-09)

## Goal
Extract per-line charges from AT&T family plan billing for all months since June 2024.

---

## Experiment Summary

| Run | Model | Vision | Max Steps | Result |
|-----|-------|--------|-----------|--------|
| 1 | gpt-4o | on | 50 | Rejected - "ancient model" |
| 2 | gpt-5.2 | on | 50 | **FAILED** - JSON parsing bug |
| 3 | o3 | on | 50 | **PARTIAL** - Extracted 1 of 5 lines, scroll hell |
| 4 | o3 | off | 50 | **SUCCESS** - All 5 lines extracted (1 month) |
| 5 | gpt-4o | off | 150 | **PARTIAL** - Got some data, stuck in toggle loop |
| 6 | gpt-5-mini | off | 150 | **FAILED** - Stuck in wait_for_login loop |
| 7 | gpt-5-nano | on | 150 | **FAILED** - Stuck searching literal "June 2024" text |
| 8 | gpt-5-nano | off | 150 | **FAILED** - Wrong URL, auth token error, stuck waiting |
| 9 | o3 | off | 150 | **PARTIAL** - Got 3 months, scroll hell on Oct bill |
| 10 | o3 | on | 150 | **PARTIAL** - Got 4 months, completed! Best result |

---

## Detailed Findings

### Run 2: gpt-5.2 with Vision

**Configuration:**
- Model: `gpt-5.2`
- Vision: enabled
- `reasoning_effort`: `"none"`

**Result:** Complete failure

**Error:**
```
Trailing characters at line 2 column 1
```

**Root Cause:** Known bug where GPT-5 family models output duplicate JSON objects. Confirmed via web search - multiple GitHub issues report this.

**Lesson:** gpt-5.2 is currently broken for structured output tasks in browser-use.

---

### Run 3: o3 with Vision (50 steps)

**Configuration:**
- Model: `o3` (browser-use recommended)
- Vision: enabled
- Max steps: 50

**Result:** Partial success - only extracted 1 of 5 lines

**Behavior:**
- Successfully logged in (with manual MFA)
- Found billing page
- Downloaded PDF (but it was summary, not detailed)
- Found 5 subscriber lines
- **Spent ~30 steps scrolling up/down** trying to find Monthly charges sections
- Hit step limit before extracting all lines

**Extracted Data (Sep 07-Oct 06, incomplete):**
| Phone | Monthly Plan | Device | Insurance | Taxes | Subtotal |
|-------|--------------|--------|-----------|-------|----------|
| 470-874-1166 | Apple Watch | $22.23 | -$40.00 | -$0.05 | -$26.15 |
| 770-316-3103 | (collapsed) | - | - | -$0.07 | -$12.57 |
| 404-376-9093 | (collapsed) | - | - | -$0.07 | -$12.57 |
| 205-441-8790 | (collapsed) | - | - | -$0.12 | -$12.62 |

**Lesson:** Vision mode may cause spatial reasoning confusion. Agent kept scrolling to "see" things instead of using DOM navigation.

---

### Run 4: o3 without Vision (50 steps)

**Configuration:**
- Model: `o3`
- Vision: **disabled**
- Max steps: 50

**Result:** SUCCESS - All 5 lines extracted for one month

**Data Extracted (Sep 07-Oct 06):**
| Line (Name) | Phone # | Monthly Plan | Device Payment | Insurance | Taxes |
|-------------|---------|--------------|----------------|-----------|-------|
| David Rose | 205-441-8790 | -$12.50 | $0.00 | $0.00 | -$0.12 |
| Maddie McBrayer | 404-376-9093 | -$12.50 | $0.00 | $0.00 | -$0.07 |
| Richard McBrayer | 470-874-1166 | -$8.33 | $22.23 | -$40.00 | -$0.05 |
| Richard McBrayer | 770-316-3103 | -$12.50 | $0.00 | $0.00 | -$0.07 |
| Richard McBrayer | 470-874-0548 | -$8.33 | $0.00 | $0.00 | -$0.05 |

**Note:** This data was from a credit/adjustment month - all values negative. Not the detailed charges user needed.

**Lesson:** Disabling vision improved task completion. DOM-only navigation was more reliable.

---

### Run 5: gpt-4o without Vision (150 steps, multi-month)

**Configuration:**
- Model: `gpt-4o` (faster)
- Vision: disabled
- Max steps: 150
- Task: Extract ALL months since June 2024

**Result:** Partial - got some good data, then stuck in loop

**Bills Found:**
| Period | Total |
|--------|-------|
| Jun 07 - Jul 06 | $526.79 |
| Jul 07 - Aug 06 | $465.40 |
| Aug 07 - Sep 06 | $149.88 |
| Sep 07 - Oct 06 | -$155.24 |
| Oct 07 - Nov 06 | $0.00 |

**Best Extraction (Jun 07 - Jul 06):**
| Name | Phone | Monthly Charge | Discount |
|------|-------|----------------|----------|
| **DAVID ROSE** | 205.441.8790 | **$146.64** | $25.00 |
| MADDIE MCBRAYER | 404.376.9093 | $115.41 | $25.00 |
| RICHARD MCBRAYER | 470.874.0548 | $17.48 | - |
| RICHARD MCBRAYER | 470.874.1166 | $88.02 | - |
| RICHARD MCBRAYER | 770.316.3103 | $59.70 | $25.00 |

**David Rose's $146.64** aligns with user's expectation of ~$146 for expensive months (international charges).

**Failure Mode:** Steps 52-70+ were stuck toggling the same accordion (Jul 07 - Aug 06) open/closed repeatedly without extracting data.

**Lesson:** gpt-4o is faster but less capable at complex multi-step UI navigation. Gets stuck in repetitive loops.

---

### Run 6: gpt-5-mini without Vision (150 steps, multi-month)

**Configuration:**
- Model: `gpt-5-mini`
- Vision: disabled
- Max steps: 150

**Result:** Complete failure - never reached billing page

**Behavior:**
- Navigated to billing URL repeatedly
- Kept triggering `wait_for_login` action in a loop
- Never tried alternative navigation (clicking Account button)
- Burned through 5+ steps just repeating the same pattern

**Failure Mode:** The model wasn't smart enough to realize it needed to click the Account button to initiate login flow. Kept directly navigating to the billing URL which redirected to homepage.

**Lesson:** gpt-5-mini lacks the problem-solving ability to try alternative approaches when the direct path fails. Not suitable for complex UI navigation.

---

### Runs 7-8: gpt-5-nano (both vision configs)

**Configuration:**
- Model: `gpt-5-nano`
- Vision: tested both ON and OFF
- Max steps: 150
- Note: Login action removed (profile already authenticated)

**Run 7 (Vision ON) Result:** Failed at ~35 steps

**Behavior:**
- Successfully clicked Account dropdown
- Navigated to billing history page (`att.com/acctmgmt/billing/history`)
- Repeatedly searched for literal text "June 2024"
- AT&T uses format "Jun 07 - Jul 06" not "June 2024"
- Stuck in loop: find_text → scroll → search box → repeat
- Never adapted search strategy despite repeated failures

**Run 8 (Vision OFF) Result:** Failed at ~35 steps

**Behavior:**
- Navigated directly to `my.att.com/billing` instead of clicking Account dropdown
- Hit "Missing Authentication Token" error
- Opened 3 tabs all with same auth error
- Stuck in wait loop asking for "re-authentication guidance"
- Never tried alternative URLs or navigation paths

**Failure Modes:**
1. **Literal interpretation** - Searched exact text from task instead of adapting to page format
2. **No adaptation** - Repeated same failing actions without trying alternatives
3. **Wrong URL** - Vision OFF chose direct URL instead of following task steps

**Lesson:** gpt-5-nano is too small for complex UI navigation. Lacks problem-solving ability to adapt when things don't work as expected. Not suitable for browser-use tasks.

---

### Run 9: o3 without Vision (150 steps, focused David Rose task)

**Configuration:**
- Model: `o3`
- Vision: disabled
- Max steps: 150
- Task: Focused on extracting DAVID ROSE charges only (phone 205-441-8790) for all months July 2024 to present
- Note: Login action removed (profile already authenticated)

**Result:** Partial - extracted 3 months, then scroll hell

**Data Extracted:**
| Billing Period | David Rose Total |
|----------------|------------------|
| Jul 07 - Aug 06 | $146.64 |
| Aug 07 - Sep 06 | $146.64 |
| Sep 07 - Oct 06 | -$12.62 |

**Behavior:**
- Successfully navigated to billing history
- Expanded bills and found David Rose line items
- Extracted 3 months of data correctly
- Hit Oct 07 - Nov 06 bill (which was likely $0.00 with no line items)
- Spent ~30 steps scrolling up/down trying to find David Rose line that didn't exist
- Never gave up or moved on to later months
- Killed at step ~48

**Failure Mode:** Classic scroll hell. Model bounced between scrolling up 0.4-0.8 pages and down 0.3-0.6 pages repeatedly, never recognizing that the target element didn't exist.

**Prompt included anti-loop instruction:** "Do NOT repeat the same action more than twice" - completely ignored.

**Lesson:** Even o3 (browser-use's recommended model) hits scroll hell on complex accordion UIs. This is a fundamental limitation of the browser-use + LLM combination, not something that can be prompt-engineered away. The model lacks the meta-cognition to recognize when it's stuck and try something different.

---

### Run 10: o3 WITH Vision (150 steps, focused David Rose task)

**Configuration:**
- Model: `o3`
- Vision: **enabled**
- Max steps: 150
- Task: Same focused David Rose task as Run 9
- Usage tracking: Monkey-patched to capture reasoning tokens

**Result:** Best result so far - 4 months extracted, agent completed!

**Data Extracted:**
| Billing Period | David Rose Total | Notes |
|----------------|------------------|-------|
| Jul 07 - Aug 06 | $146.64 | Monthly access $40, $25 discount |
| Aug 07 - Sep 06 | $146.64 | **$120 International Day Pass (10 × $12)** |
| Sep 07 - Oct 06 | -$12.62 | Monthly access $40 – $25 discount – prorated credit |
| Oct 07 - Nov 06 | $0.00 | No device charges |

**GRAND TOTAL: $280.66**

**Behavior:**
- Successfully navigated to billing history
- Extracted 4 months of David Rose charges
- Found the international charges! ($120 = 10 × $12 International Day Pass)
- Hit Oct bill ($0.00) and eventually recognized no line items existed
- **Completed and returned results** (unlike vision OFF which got stuck)
- Judge flagged incomplete (only 4 months, not all months to present)

**Completed in:** 57 steps

**Key Difference from Vision OFF:** Vision ON was willing to accept partial information (Oct = $0 from account summary) and move on to return results. Vision OFF kept scrolling forever trying to find a line item that didn't exist.

**Lesson:** Vision ON may actually perform BETTER for some tasks - it enables the model to "see" and accept visual cues like "$0.00" summaries instead of insisting on finding specific DOM elements. Previous assumption that "vision OFF is always better" was wrong.

---

## Technical Issues Encountered

### 1. browser-use API Drift
- `chrome_instance_path` no longer exists
- Correct params: `user_data_dir`, `profile_directory`, `executable_path`
- `browser.close()` → `browser.stop()` (later `session.stop()`)

### 2. Profile Persistence Bug
- Path containing "chrome" triggers copy-to-temp behavior
- Fix: Rename `chrome_profile` → `browser_profile`
- Must use `BrowserProfile` + `BrowserSession`, not just `Browser()`

### 3. AT&T Session Cookies Don't Persist
- Even with persistent profile, AT&T invalidates sessions on browser close
- This is AT&T's security feature, not a bug
- User must log in each run

### 4. CDP Timeout Errors
- Intermittent `TimeoutError: CDP requests failed or timed out: ax_tree`
- Agent recovers by waiting, but wastes steps

---

## Model Comparison

| Model | Speed | Accuracy | Failure Mode |
|-------|-------|----------|--------------|
| gpt-5.2 | - | 0% | JSON parsing bug |
| gpt-5-mini | Fast | 0% | Navigation loops |
| gpt-5-nano | Fast | 0% | Literal interpretation, no adaptation |
| o3 + vision | Slow | **~70%** | Completed with partial data |
| o3 - vision | Slow | ~50% | Scroll hell (never completes) |
| gpt-4o - vision | Fast | ~60% | Toggle loops |

**Recommendation:** `o3` WITH vision is actually best for this task - it completes and returns data. Vision OFF gets stuck in perfectionist loops.

**Model Hierarchy (for browser-use tasks):**
1. **o3 + vision** - Best for complex UIs, willing to accept partial info and complete
2. **o3 - vision** - Gets stuck trying to find elements that don't exist
3. **gpt-4o** - Faster but gets stuck in toggle loops
4. **gpt-5-mini** - Too dumb for complex navigation
5. **gpt-5-nano** - Even dumber, literal interpretation
6. **gpt-5.2** - Broken (JSON bug)

**Key Finding:** Vision ON may be better than vision OFF for accordion UIs - it allows the model to read visual summaries (like "$0.00") instead of insisting on finding specific DOM elements that may not exist.

---

## Comparison: browser-use vs DIY (pixel-pilot)

User has their own AI browser agent (`~/git/pixel-pilot`) built with Playwright + OpenAI.

| Aspect | browser-use | pixel-pilot |
|--------|-------------|-------------|
| DOM awareness | Yes (element refs) | No (pixel coordinates) |
| Transparency | Black box prompts | Full visibility |
| Debugging | Hard | Easy |
| Framework churn | High (breaking changes) | You control it |
| Multi-path | Browser only | Terminal + Visual |

**Verdict:** browser-use adds DOM extraction but loses visibility. For known sites like AT&T, DIY might be better.

---

## What Actually Worked

1. **o3 model** - browser-use's recommended model
2. **Vision OFF** - DOM-only navigation more reliable
3. **Persistent profile** (path without "chrome") - saves non-auth state
4. **Manual login** via custom `wait_for_login` action
5. **`extract` action** - successfully pulled structured data when it found the right page

---

## Recommendations for Future

1. **Use o3 without vision** for complex extraction tasks
2. **Consider PDF-first strategy** - download detailed PDFs and parse externally
3. **Increase max_steps** for multi-month tasks (150+ minimum)
4. **Add loop detection** - if same action repeated 3x, try something different
5. **For AT&T specifically:** Accept login each run, or keep browser open with `keep_alive=True`

---

## Files

- Script: `experiments/att-billing/extract_charges.py`
- Profile: `experiments/att-billing/browser_profile/`
- Downloaded PDFs: `/private/tmp/browser-use-downloads-*/`
