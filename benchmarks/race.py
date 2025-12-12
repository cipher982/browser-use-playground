#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_URL = "https://mbworld.org/forums/g-class-w460-w461-w463/777971-my-g55-journey.html"


REAL_POST_ID_RE = re.compile(r"^post\d{6,}$")


@dataclass(frozen=True)
class RunMetrics:
	method: str
	url: str
	max_pages: int
	seconds: float
	total_lines: int
	real_post_lines: int
	non_post_lines: int
	json_parse_failures: int


def _iter_json_objects_from_text(text: str) -> Iterable[dict[str, Any]]:
	"""
	Extract JSON objects from a model response.
	We accept either:
	  - raw JSONL (one object per line), or
	  - a markdown fenced block containing JSONL/JSON.
	"""
	if not text:
		return

	# Prefer fenced blocks if present.
	fence_re = re.compile(r"```(?:jsonl|json)?\\s*(.*?)```", re.DOTALL | re.IGNORECASE)
	m = fence_re.search(text)
	if m:
		text = m.group(1)

	for line in text.splitlines():
		line = line.strip()
		if not line:
			continue
		if not (line.startswith("{") and line.endswith("}")):
			continue
		try:
			yield json.loads(line)
		except json.JSONDecodeError:
			continue


def _write_jsonl(path: Path, objects: Iterable[dict[str, Any]]) -> int:
	path.parent.mkdir(parents=True, exist_ok=True)
	n = 0
	with path.open("w", encoding="utf-8") as f:
		for obj in objects:
			f.write(json.dumps(obj, ensure_ascii=False) + "\n")
			n += 1
	return n


def _compute_metrics(method: str, url: str, max_pages: int, seconds: float, out_path: Path) -> RunMetrics:
	total_lines = 0
	real_post_lines = 0
	non_post_lines = 0
	json_parse_failures = 0

	with out_path.open("r", encoding="utf-8") as f:
		for line in f:
			line = line.strip()
			if not line:
				continue
			total_lines += 1
			try:
				obj = json.loads(line)
			except json.JSONDecodeError:
				json_parse_failures += 1
				continue

			post_id = obj.get("post_id")
			if isinstance(post_id, str) and REAL_POST_ID_RE.match(post_id):
				real_post_lines += 1
			else:
				non_post_lines += 1

	return RunMetrics(
		method=method,
		url=url,
		max_pages=max_pages,
		seconds=seconds,
		total_lines=total_lines,
		real_post_lines=real_post_lines,
		non_post_lines=non_post_lines,
		json_parse_failures=json_parse_failures,
	)


async def _run_playwright(
	url: str,
	max_pages: int,
	out_path: Path,
	headless: bool,
	block_ads: bool,
	block_assets: bool,
	offscreen: bool,
) -> None:
	from playwright.async_api import async_playwright

	def absolutize(base: str, href: str) -> str:
		from urllib.parse import urljoin

		return urljoin(base, href)

	async with async_playwright() as p:
		launch_args: list[str] = []
		if not headless and offscreen:
			# Try to keep the window out of your way (macOS typically has a large coordinate space).
			launch_args += ["--window-position=4000,0", "--window-size=900,700"]

		browser = await p.chromium.launch(headless=headless, args=launch_args or None)
		context = await browser.new_context(
			user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
		)

		if block_ads or block_assets:
			AD_HOST_RE = re.compile(
				r"(doubleclick|googlesyndication|googleadservices|adservice|adsystem|adnxs|taboola|outbrain|criteo|pubmatic|rubiconproject|scorecardresearch|quantserve|hotjar|segment|amplitude|sentry|datadog|newrelic)",
				re.IGNORECASE,
			)

			async def _route(route):
				try:
					u = route.request.url
					rt = route.request.resource_type
					if block_ads and AD_HOST_RE.search(u):
						await route.abort()
					elif block_assets and rt in {"image", "media", "font"}:
						await route.abort()
					else:
						await route.continue_()
				except Exception:
					await route.continue_()

			await context.route("**/*", _route)
		page = await context.new_page()

		current_url = url
		visited = set()
		page_number = 1

		out_path.parent.mkdir(parents=True, exist_ok=True)
		with out_path.open("w", encoding="utf-8") as f:
			while current_url and current_url not in visited and page_number <= max_pages:
				visited.add(current_url)
				await page.goto(current_url, wait_until="domcontentloaded", timeout=60_000)
				try:
					await page.wait_for_selector("[id^='post']", state="attached", timeout=20_000)
				except Exception:
					# Some bot-defended sites may still render; give a small grace period.
					await page.wait_for_timeout(2000)

				# Find only actual user posts (avoid menus/share/thanks/etc).
				posts = await page.locator(
					"xpath=//*[starts-with(@id,'post') and not(contains(@id,'menu') or contains(@id,'share') or contains(@id,'count') or contains(@id,'message') or contains(@id,'thanks') or contains(@id,'_button'))]"
				).all()
				for post in posts:
					post_id = await post.get_attribute("id")
					if not post_id or not REAL_POST_ID_RE.match(post_id):
						continue
					author = None
					author_loc = post.locator(".bigusername, .postusername, a[href*='member']").first
					if await author_loc.count():
						author = (await author_loc.inner_text()).strip() or None

					# MBWorld tends to have the timestamp in the post header text.
					timestamp_raw = None
					date_loc = post.locator("xpath=.//*[contains(@class,'trow')][1]").first
					if await date_loc.count():
						timestamp_raw = (await date_loc.inner_text()).strip() or None

					content_html = None
					for sel in [
						"#post_message_" + post_id.removeprefix("post"),
						".postcontent",
						".content",
						".messageContent",
						".message-body",
						".post_body",
					]:
						loc = post.locator(sel).first
						if await loc.count():
							content_html = await loc.inner_html()
							break

					content_text = re.sub(r"\\s+", " ", (await post.inner_text())).strip()

					# Extract images but skip likely UI/avatars.
					image_urls: list[str] = []
					imgs = post.locator("img")
					for i in range(await imgs.count()):
						img = imgs.nth(i)
						src = await img.get_attribute("src")
						if not src:
							continue
						if any(x in src for x in ["avatar", "smilies", "statusicon", "icon", "badge"]):
							continue
						image_urls.append(absolutize(current_url, src))

					record = {
						"page_url": current_url,
						"page_number": page_number,
						"post_id": post_id,
						"author": author,
						"timestamp_raw": timestamp_raw,
						"content_html": content_html,
						"content_text": content_text,
						"image_urls": image_urls,
					}
					f.write(json.dumps(record, ensure_ascii=False) + "\n")

				# Pagination: try rel=next, then a link containing "Next".
				next_href = None
				next_link = page.locator("a[rel='next']").first
				if await next_link.count():
					next_href = await next_link.get_attribute("href")
				if not next_href:
					next_link = page.get_by_role("link", name=re.compile("Next", re.IGNORECASE)).first
					if await next_link.count():
						next_href = await next_link.get_attribute("href")

				current_url = absolutize(current_url, next_href) if next_href else None
				page_number += 1

		await context.close()
		await browser.close()


async def _run_browser_use(
	url: str,
	max_pages: int,
	out_path: Path,
	model: str,
	headless: bool,
	offscreen: bool,
	use_vision: bool,
	reasoning_effort: str,
) -> float:
	from browser_use import Agent, Browser, ChatOpenAI

	# Load local env files if present (never create them here).
	try:
		from dotenv import load_dotenv

		load_dotenv(dotenv_path=Path(".env.local"), override=False)
		load_dotenv(dotenv_path=Path(".env"), override=False)
	except Exception:
		pass

	api_key = os.environ.get("OPENAI_API_KEY")
	if not api_key:
		raise SystemExit("OPENAI_API_KEY is not set; Browser Use needs an LLM configured to run this benchmark.")

	llm = ChatOpenAI(model=model, reasoning_effort=reasoning_effort)
	browser = Browser(
		headless=headless,
		is_local=True,
		window_position={"x": 4000, "y": 0, "width": 900, "height": 700} if (not headless and offscreen) else None,
		window_size={"width": 900, "height": 700} if (not headless and offscreen) else None,
	)

	out_path = out_path.resolve()

	task = f"""
You are scraping a forum thread to JSON Lines.

Goal:
- Start at: {url}
- Extract ONLY real forum posts whose DOM id matches /^post\\d{{6,}}$/.
- Only scrape the first {max_pages} page(s). Do not navigate past that even if you find more pages.
- For each post, output ONE JSON object per line with keys:
  - page_url (string)
  - page_number (int)
  - post_id (string)
  - author (string|null)
  - timestamp_raw (string|null)
  - content_html (string|null) : the message HTML if possible
  - content_text (string) : plain text
  - image_urls (array of strings) : images inside the post, excluding avatars/smilies/icons

Rules:
- Write the results to the file path: {out_path}
  Use the write_file tool. Write JSONL (one JSON object per line). Do not wrap in a JSON array.
- In the final response, only say: "WROTE_FILE" (no other text).
- Do not fabricate placeholder values. If you cannot extract a field, use null/[] but keep real post_id/page_url.

Extraction strategy (important):
- First, gather ALL matching post element ids on the page (ids like post8013078) by using the extract tool.
- The extract tool may truncate output; if you see truncation or only a partial list, call extract again with a higher start_from_char and continue until you have the full list.
- Then, for each post id you found, extract the required fields for that exact post (so you don't miss most posts).
- Append each post as one JSON object line to {out_path}.
"""

	agent = Agent(
		task=task,
		llm=llm,
		browser=browser,
		use_vision=use_vision,
		max_actions_per_step=8,
		step_timeout=120,
		file_system_path=str(Path.cwd()),
		available_file_paths=[str(out_path)],
		display_files_in_done_text=False,
	)
	start = time.time()
	try:
		history = await agent.run(max_steps=80)
		seconds = time.time() - start

		final_text = (history.final_result() or "").strip()
		if final_text != "WROTE_FILE":
			raw_path = out_path.with_suffix(".raw.txt")
			raw_path.write_text(history.final_result() or "", encoding="utf-8")
			raise RuntimeError(f"Agent did not confirm write; got {final_text!r}. Raw saved to {raw_path}")

		if not out_path.exists():
			raise RuntimeError(f"Agent claimed success but {out_path} does not exist")

		metrics = _compute_metrics("browser-use", url, max_pages, seconds, out_path)
		if metrics.total_lines < 10 or metrics.non_post_lines > 0 or metrics.json_parse_failures > 0:
			raise RuntimeError(f"Agent wrote low-quality output: {metrics}")

		return seconds
	finally:
		close = getattr(browser, "close", None)
		if callable(close):
			maybe = close()
			if asyncio.iscoroutine(maybe):
				await maybe


def main() -> None:
	parser = argparse.ArgumentParser(description="Race Playwright vs Browser Use (local OSS) on a scraping task.")
	parser.add_argument("--url", default=DEFAULT_URL)
	parser.add_argument("--method", choices=["playwright", "browser-use"], required=True)
	parser.add_argument("--max-pages", type=int, default=2)
	parser.add_argument("--out", default=None)
	parser.add_argument("--headful", action="store_true", help="Run non-headless (helps on bot-defended sites)")
	parser.add_argument("--offscreen", action="store_true", help="Headful only: try to move the window off-screen")
	parser.add_argument("--block-ads", action="store_true", help="Playwright only: block common ad/tracker requests")
	parser.add_argument("--block-assets", action="store_true", help="Playwright only: block images/media/fonts")
	parser.add_argument("--vision", action="store_true", help="Browser Use only: enable vision mode (screenshot-based)")
	parser.add_argument(
		"--reasoning-effort",
		default=os.environ.get("BROWSER_USE_REASONING_EFFORT", "minimal"),
		choices=["minimal", "low", "medium", "high"],
		help="Browser Use only: reasoning effort (faster=lower)",
	)
	parser.add_argument("--model", default=os.environ.get("BROWSER_USE_MODEL", "gpt-5-mini"), help="Browser Use only")
	args = parser.parse_args()

	out_path = Path(args.out) if args.out else Path("race_results") / f"{args.method}_p{args.max_pages}.jsonl"

	start = time.time()
	if args.method == "playwright":
		asyncio.run(
			_run_playwright(
				args.url,
				args.max_pages,
				out_path,
				headless=not args.headful,
				block_ads=args.block_ads,
				block_assets=args.block_assets,
				offscreen=args.offscreen,
			)
		)
		seconds = time.time() - start
	else:
		seconds = asyncio.run(
			_run_browser_use(
				args.url,
				args.max_pages,
				out_path,
				model=args.model,
				headless=not args.headful,
				offscreen=args.offscreen,
				use_vision=args.vision,
				reasoning_effort=args.reasoning_effort,
			)
		)

	metrics = _compute_metrics(args.method, args.url, args.max_pages, seconds, out_path)
	print(json.dumps(metrics.__dict__, indent=2))
	print(f"Wrote: {out_path}")


if __name__ == "__main__":
	main()
