#!/usr/bin/env python3
"""Detailed test to understand the page structure."""

import asyncio
from playwright.async_api import async_playwright

async def test_access():
    """Test basic access and examine the page structure."""
    url = "https://mbworld.org/forums/g-class-w460-w461-w463/777971-my-g55-journey.html"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Show browser to see what's happening
        page = await browser.new_page()

        # Set a user agent to look more like a real browser
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        })

        print(f"📍 Loading: {url}")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            print("✅ Page loaded")

            # Wait a bit for any JavaScript to render
            await page.wait_for_timeout(3000)

            # Get page content
            title = await page.title()
            print(f"📄 Page title: {title}")

            # Get the raw HTML
            content = await page.content()
            print(f"📄 Page content length: {len(content)} characters")

            # Save the HTML for inspection
            with open("test_page.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("✅ HTML saved to test_page.html")

            # Check for common forum elements
            elements_to_check = [
                ("posts", "xpath=//*[contains(@id,'post')]"),
                ("quote", "xpath=//*[contains(@class,'quote')]"),
                ("message", "xpath=//*[contains(@class,'message')]"),
                ("content", "xpath=//*[contains(@class,'content')]"),
                ("thread", "xpath=//*[contains(@class,'thread')]"),
                ("postbody", "xpath=//*[contains(@class,'postbody')]"),
            ]

            for name, selector in elements_to_check:
                count = await page.locator(selector).count()
                print(f"🔍 {name}: {count} elements found")

            # Check for redirects or login pages
            current_url = page.url
            print(f"🔗 Current URL: {current_url}")

            if current_url != url:
                print(f"⚠️  Redirected from {url} to {current_url}")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_access())
