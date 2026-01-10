#!/usr/bin/env python3
"""
MBWorld Forum Thread Scraper
Scrapes all posts from a forum thread with metadata, images, and pagination support.
"""

import asyncio
import json
import os
import re
import time
import urllib.parse
import pathlib
from datetime import datetime
from typing import Dict, List, Optional
from playwright.async_api import async_playwright

# Configuration
BASE_URL = "https://mbworld.org/forums/g-class-w460-w461-w463/777971-my-g55-journey.html"
OUT_DIR = "mbworld_g55_journey"
IMG_DIR = os.path.join(OUT_DIR, "images")
JSONL_PATH = os.path.join(OUT_DIR, "posts.jsonl")

# Create output directory
os.makedirs(IMG_DIR, exist_ok=True)

def absolutize(url: str, base: str) -> str:
    """Convert relative URL to absolute URL."""
    return urllib.parse.urljoin(base, url)

def sanitize_filename(filename: str, max_length: int = 180) -> str:
    """Sanitize filename for safe saving."""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove extra spaces and dots
    filename = re.sub(r'\.+', '.', filename)
    # Truncate if too long
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length-len(ext)] + ext
    return filename

async def download_image(page, url: str, dest_path: str) -> bool:
    """Download an image from URL to dest_path. Returns True if successful."""
    # For now, just log the image URL
    # Image downloading can be added later with aiohttp/httpx
    print(f"  🖼️  Would download: {url}")
    return False  # Not actually downloading yet

async def extract_posts(page) -> List[Dict]:
    """Extract all posts from the current page."""
    # Find only actual user posts (not forum UI elements)
    # Real posts have IDs like "post8013078" (post + numbers only)
    post_elements = await page.locator("xpath=//*[starts-with(@id,'post') and not(contains(@id,'menu') or contains(@id,'share') or contains(@id,'count') or contains(@id,'message') or contains(@id,'thanks') or contains(@id,'_button'))]").all()

    results = []
    print(f"  📄 Found {len(post_elements)} actual posts on this page")

    for idx, post in enumerate(post_elements, 1):
        try:
            post_id = await post.get_attribute("id")
            if not post_id:
                continue

            # Extract author - try multiple selectors
            author = None
            for selector in [
                ".bigusername",
                ".postusername",
                "a[href*='member']",
                ".message-userDetails .username",
                ".postdetails .username"
            ]:
                author_elem = post.locator(selector).first
                if await author_elem.count():
                    author = (await author_elem.inner_text()).strip()
                    if author:
                        break

            # Extract timestamp - try multiple selectors
            timestamp_raw = None
            for selector in [
                "time",
                ".postdate",
                ".date",
                ".post-head .date",
                "span[class*='date']",
                ".postdetails"
            ]:
                ts_elem = post.locator(selector).first
                if await ts_elem.count():
                    timestamp_raw = (await ts_elem.inner_text()).strip()
                    if timestamp_raw:
                        break

            # Extract content HTML
            content_html = None
            for selector in [
                ".postcontent",
                ".content",
                ".messageContent",
                ".message-body",
                ".post_body"
            ]:
                content_elem = post.locator(selector).first
                if await content_elem.count():
                    content_html = await content_elem.inner_html()
                    break

            if not content_html:
                # Fallback to entire post HTML
                content_html = await post.inner_html()

            # Extract plain text
            content_text = re.sub(r'\s+', ' ', (await post.inner_text())).strip()

            # Extract images (including lazy-loaded)
            img_elements = post.locator("img")
            image_urls = []
            image_local_paths = []

            # Filter out forum UI images (avatars, badges, smilies, status icons)
            SKIP_PATTERNS = [
                'avatar', 'badge', 'smilies', 'statusicon', 'icon',
                'misc/amazon_icon', 'thanks', 'quote', 'bookmarks'
            ]

            for i in range(await img_elements.count()):
                img = img_elements.nth(i)

                # Skip if img is inside certain containers
                parent_avatar = img.locator("xpath=ancestor::*[contains(@class, 'avatar') or contains(@class, 'userinfo') or contains(@class, 'postbit')]")
                if await parent_avatar.count():
                    continue

                # Try different attributes for image src
                src = (await img.get_attribute("src") or
                       await img.get_attribute("data-src") or
                       await img.get_attribute("data-lazy") or
                       "")

                if src and not src.startswith("data:"):
                    abs_url = absolutize(src, page.url)

                    # Skip UI elements
                    if any(pattern in abs_url.lower() for pattern in SKIP_PATTERNS):
                        continue

                    image_urls.append(abs_url)

                    # Download image
                    parsed_url = urllib.parse.urlparse(abs_url)
                    original_name = os.path.basename(parsed_url.path)
                    if not original_name or '.' not in original_name:
                        original_name = f"{post_id}_{i}.jpg"

                    safe_name = sanitize_filename(original_name)
                    local_path = os.path.join(IMG_DIR, f"{post_id}_{safe_name}")

                    if await download_image(page, abs_url, local_path):
                        if os.path.exists(local_path):
                            image_local_paths.append(os.path.relpath(local_path, OUT_DIR))

            # Build post data
            post_data = {
                "post_id": post_id,
                "author": author,
                "timestamp_raw": timestamp_raw,
                "content_html": content_html,
                "content_text": content_text,
                "image_urls": image_urls,
                "image_local_paths": image_local_paths,
            }

            results.append(post_data)
            print(f"  ✅ {idx}/{len(post_elements)}: {post_id} by {author}")

        except Exception as e:
            print(f"  ⚠️  Error extracting post {idx}: {e}")
            continue

    return results

async def find_next_url(page) -> Optional[str]:
    """Find the next page URL. Returns None if no next page."""
    # Try to find rel=next in the page head
    next_url = await page.get_attribute('link[rel="next"]', "href")

    if next_url:
        abs_next = absolutize(next_url, page.url)
        print(f"  🔗 Found next page via rel='next': {abs_next}")
        return abs_next

    # Fallback: look for "Next" link in the page
    next_links = [
        ("link", "Next"),
        ("link", "Next >"),
        ("link", "›"),
        ("link", ">"),
    ]

    for role, name in next_links:
        try:
            locator = page.get_by_role(role, name=name, exact=False)
            if await locator.count():
                href = await locator.first.get_attribute("href")
                if href:
                    abs_next = absolutize(href, page.url)
                    print(f"  🔗 Found next page via text: {abs_next}")
                    return abs_next
        except Exception:
            continue

    print(f"  ❌ No next page found")
    return None

async def run():
    """Main scraping function."""
    print("=" * 80)
    print("🚀 MBWorld Forum Thread Scraper")
    print("=" * 80)
    print(f"📍 Target URL: {BASE_URL}")
    print(f"📁 Output directory: {OUT_DIR}")
    print(f"💾 JSONL file: {JSONL_PATH}")
    print(f"🖼️  Images directory: {IMG_DIR}")
    print("=" * 80)

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Track which pages we've visited
        visited_pages = set()
        current_url = BASE_URL
        page_num = 1
        total_posts = 0

        # Open JSONL file for writing
        with open(JSONL_PATH, "w", encoding="utf-8") as f:
            while current_url and current_url not in visited_pages:
                visited_pages.add(current_url)

                print(f"\n📄 Page {page_num}: {current_url}")
                print("-" * 80)

                try:
                    # Navigate to page
                    await page.goto(current_url, wait_until="domcontentloaded", timeout=60000)

                    # Wait for content to load
                    await page.wait_for_timeout(1000)

                    # Extract posts
                    posts = await extract_posts(page)

                    # Save posts to JSONL
                    for post in posts:
                        f.write(json.dumps({
                            "page_url": current_url,
                            "page_number": page_num,
                            **post
                        }, ensure_ascii=False) + "\n")

                    total_posts += len(posts)
                    print(f"  ✅ Extracted {len(posts)} posts from page {page_num}")
                    print(f"  📊 Total posts so far: {total_posts}")

                    # Find next page
                    next_url = await find_next_url(page)

                    if next_url and next_url not in visited_pages:
                        current_url = next_url
                        page_num += 1

                        # Politeness delay
                        await page.wait_for_timeout(1500)
                    else:
                        current_url = None

                except Exception as e:
                    print(f"  ❌ Error on page {page_num}: {e}")
                    import traceback
                    traceback.print_exc()
                    current_url = None

        await browser.close()

        print("\n" + "=" * 80)
        print("✅ Scraping complete!")
        print("=" * 80)
        print(f"📄 Total pages: {page_num}")
        print(f"📊 Total posts: {total_posts}")
        print(f"💾 JSONL saved to: {JSONL_PATH}")
        print(f"🖼️  Images saved to: {IMG_DIR}")
        print(f"🔗 Visited {len(visited_pages)} unique pages")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run())
