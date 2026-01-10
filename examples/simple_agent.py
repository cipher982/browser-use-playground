#!/usr/bin/env python3
"""
Simple browser-use agent example.

Run:
    uv run examples/simple_agent.py "Search for the weather in NYC"
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


async def run_agent(task: str) -> str:
    from browser_use import Agent, Browser, ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini")
    browser = Browser(headless=False)

    agent = Agent(task=task, llm=llm, browser=browser)

    try:
        result = await agent.run(max_steps=10)
        return result.final_result() or "No result"
    finally:
        await browser.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python simple_agent.py 'your task here'")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    print(f"Task: {task}\n")

    result = asyncio.run(run_agent(task))
    print(f"\nResult: {result}")


if __name__ == "__main__":
    main()
