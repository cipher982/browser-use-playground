#!/usr/bin/env python3
"""Quick test to verify we can access the MBWorld forum thread."""

import sys
import asyncio

try:
    from playwright.async_api import async_playwright
except ImportError as e:
    print(f"Error importing playwright: {e}")
    print("Make sure playwright is installed: pip install playwright")
    sys.exit(1)

async def test_access():
    """Test basic access to the forum thread."""
    url = "https://mbworld.org/forums/g-class-w460-w461-w463/777971-my-g55-journey.html"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"📍 Loading: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Take a screenshot to see what we're working with
        await page.screenshot(path="test_page.png", full_page=True)
        print("✅ Screenshot saved to test_page.png")

        # Count posts
        posts = await page.locator("xpath=//*[starts-with(@id,'post')]").all()
        print(f"📊 Found {len(posts)} posts on first page")

        # Check for pagination
        next_links = await page.locator("a[rel='next']").all()
        print(f"🔗 Found {len(next_links)} 'next' links")

        # Try to find "Next" text
        next_text = page.get_by_role("link", name="Next", exact=False)
        if await next_text.count():
            print("✅ Found 'Next' text link")
        else:
            print("❌ No 'Next' text link found")

        # Get page title
        title = await page.title()
        print(f"📄 Page title: {title}")

        await browser.close()
        print("✅ Test complete!")

if __name__ == "__main__":
    asyncio.run(test_access())
