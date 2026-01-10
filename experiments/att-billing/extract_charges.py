#!/usr/bin/env python3
"""
Extract ATT family plan line charges using browser-use.

Run:
    uv run experiments/att-billing/extract_charges.py
    uv run experiments/att-billing/extract_charges.py --model gpt-4o-mini --no-vision
    uv run experiments/att-billing/extract_charges.py --model o3-mini --vision --max-steps 50
"""
import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

DOWNLOADS_DIR = Path(__file__).parent / "downloads"
LOGS_DIR = Path(__file__).parent / "logs"


# Global usage tracker - will be populated by monkey-patching
usage_data = {
    "invocations": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "reasoning_tokens": 0,
    "cached_tokens": 0,
    "per_call": [],
}


async def run(model: str = "o3", use_vision: bool = True, max_steps: int = 150):
    from browser_use import Agent, BrowserProfile, BrowserSession, ChatOpenAI
    from openai.types.chat.chat_completion import ChatCompletion

    print(f"\n{'='*60}")
    print(f"CONFIG: model={model}, vision={use_vision}, max_steps={max_steps}")
    print(f"{'='*60}\n")

    # Monkey-patch to capture raw usage including reasoning tokens
    original_get_usage = ChatOpenAI._get_usage

    def patched_get_usage(self, response: ChatCompletion):
        global usage_data
        usage_data["invocations"] += 1

        if response.usage:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            reasoning_tokens = 0
            cached_tokens = 0

            if response.usage.completion_tokens_details:
                reasoning_tokens = response.usage.completion_tokens_details.reasoning_tokens or 0

            if response.usage.prompt_tokens_details:
                cached_tokens = response.usage.prompt_tokens_details.cached_tokens or 0

            usage_data["prompt_tokens"] += prompt_tokens
            usage_data["completion_tokens"] += completion_tokens
            usage_data["reasoning_tokens"] += reasoning_tokens
            usage_data["cached_tokens"] += cached_tokens

            usage_data["per_call"].append({
                "call": usage_data["invocations"],
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "reasoning": reasoning_tokens,
                "cached": cached_tokens,
            })

        return original_get_usage(self, response)

    ChatOpenAI._get_usage = patched_get_usage

    llm = ChatOpenAI(model=model)

    # Use persistent profile so login session survives between runs
    profile_dir = Path(__file__).parent / "browser_profile"
    profile_dir.mkdir(exist_ok=True)

    profile = BrowserProfile(
        headless=False,
        user_data_dir=str(profile_dir.resolve()),
        profile_directory="Default",
        storage_state=None,  # Don't override user_data_dir with storage_state
    )

    session = BrowserSession(browser_profile=profile)

    DOWNLOADS_DIR.mkdir(exist_ok=True)

    task = """
    Goal: Extract DAVID ROSE's monthly charges from AT&T billing for ALL months from July 2024 to present.

    You are ALREADY LOGGED IN. The browser profile has an active session.

    Target line: DAVID ROSE (phone: 205-441-8790)

    Steps:
    1. Click the Account dropdown/button in the header
    2. Click "See my bill" or similar billing link
    3. Navigate to billing history to see ALL available bills
    4. For EACH billing period from July 2024 to present (bills are labeled like "Jul 07 - Aug 06"):
       a. Expand/open that bill's details
       b. Find DAVID ROSE's line (205-441-8790)
       c. Extract his TOTAL charge for that month
       d. Note any special charges (international, roaming, surcharges)
    5. If you can't find older months, look for "View more" or pagination
    6. Do NOT repeat the same action more than twice - try something different

    REQUIRED OUTPUT FORMAT:
    | Billing Period | David Rose Total | Notes |
    |----------------|------------------|-------|
    | Jul 07 - Aug 06 | $XX.XX | any special charges |
    | Aug 07 - Sep 06 | $XX.XX | ... |
    | ... | ... | ... |

    GRAND TOTAL: $XXX.XX (sum of all months)

    Extract EVERY month available. Do not stop until you have all months from July 2024 to present.
    """

    agent = Agent(
        task=task,
        llm=llm,
        browser_session=session,
        use_vision=use_vision,
        initial_actions=[{"navigate": {"url": "https://www.att.com"}}],  # Start on AT&T
    )

    try:
        result = await agent.run(max_steps=max_steps)
        final_result = result.final_result()

        print("\n" + "=" * 60)
        print("RESULT:")
        print("=" * 60)
        print(final_result)

        # Log usage metrics (includes reasoning tokens via monkey-patch)
        print("\n" + "=" * 60)
        print("USAGE METRICS (Full):")
        print("=" * 60)
        model_name = llm.model
        vision_mode = agent.settings.use_vision
        steps = len(agent.history.history)

        total_tokens = usage_data["prompt_tokens"] + usage_data["completion_tokens"]

        print(f"Model: {model_name}")
        print(f"Vision: {vision_mode}")
        print(f"Steps: {steps}")
        print(f"LLM Invocations: {usage_data['invocations']}")
        print(f"Total tokens: {total_tokens:,}")
        print(f"  Prompt tokens: {usage_data['prompt_tokens']:,}")
        print(f"  Completion tokens: {usage_data['completion_tokens']:,}")
        print(f"  Reasoning tokens: {usage_data['reasoning_tokens']:,}")
        print(f"  Cached tokens: {usage_data['cached_tokens']:,}")

        # Also show browser-use's cost estimate if available
        bu_usage = agent.history.usage
        if bu_usage:
            print(f"\nbrowser-use cost estimate: ${bu_usage.total_cost:.4f}")

        # Save to log file
        LOGS_DIR.mkdir(exist_ok=True)
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "model": model_name,
            "vision": vision_mode,
            "steps": steps,
            "max_steps": max_steps,
            "usage": {
                "invocations": usage_data["invocations"],
                "prompt_tokens": usage_data["prompt_tokens"],
                "completion_tokens": usage_data["completion_tokens"],
                "reasoning_tokens": usage_data["reasoning_tokens"],
                "cached_tokens": usage_data["cached_tokens"],
                "total_tokens": total_tokens,
            },
            "per_call_usage": usage_data["per_call"],
            "browser_use_cost": bu_usage.total_cost if bu_usage else None,
            "result": final_result[:2000] if final_result else None,  # Truncate for log
        }
        log_file = LOGS_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{model_name}_vision{vision_mode}.json"
        with open(log_file, "w") as f:
            json.dump(log_entry, f, indent=2)
        print(f"\nLog saved to: {log_file}")

    finally:
        await session.stop()


def parse_args():
    parser = argparse.ArgumentParser(description="Extract ATT billing data with browser-use")
    parser.add_argument("--model", "-m", default="o3", help="OpenAI model to use (default: o3)")
    parser.add_argument("--vision", dest="vision", action="store_true", help="Enable vision mode")
    parser.add_argument("--no-vision", dest="vision", action="store_false", help="Disable vision mode")
    parser.add_argument("--max-steps", "-s", type=int, default=150, help="Max steps (default: 150)")
    parser.set_defaults(vision=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run(model=args.model, use_vision=args.vision, max_steps=args.max_steps))
