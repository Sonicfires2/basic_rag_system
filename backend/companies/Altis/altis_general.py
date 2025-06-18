import os
import argparse
import hashlib
from collections import deque
from urllib.parse import urljoin, urlparse
from datetime import datetime

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import html2text
from openai import OpenAI

# Load environment variables and initialize OpenAI client
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set")
client = OpenAI(api_key=api_key)

# Converter: HTML → Markdown
html_converter = html2text.HTML2Text()
html_converter.ignore_links = False
html_converter.body_width = 0

def html_to_markdown(html: str) -> str:
    return html_converter.handle(html)

# Split text into chunks under max_chars
def chunk_text(text: str, max_chars: int = 2000):
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for p in paragraphs:
        if len(current) + len(p) + 2 > max_chars:
            if current:
                chunks.append(current)
            current = p
        else:
            current = (current + "\n\n" + p) if current else p
    if current:
        chunks.append(current)
    return chunks

# Summarize markdown via OpenAI

def summarize_markdown(md: str, page_url: str, base_url: str) -> str:
    prompt = f"""
You are an expert summarizer. Given the following markdown content, produce a concise summary in markdown, preserving headings and key points.

Base URL: {base_url}
Page URL: {page_url}

{md}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return resp.choices[0].message.content.strip()

# Generate filename from URL
def url_to_filename(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/") or "index"
    name = path.replace("/", "_")
    domain_hash = hashlib.md5(parsed.netloc.encode()).hexdigest()[:8]
    return f"{domain_hash}_{name}.md"

# Main BFS crawl + summarize
def full_pipeline(seed_url: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    visited = set()
    queue = deque([seed_url])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        while queue:
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            try:
                page.goto(url, wait_until="networkidle")
            except Exception as e:
                print(f"Failed to load {url}: {e}")
                continue

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else url

            # enqueue same-domain links, skip any containing '/news'
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/news" in href:
                    continue
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/"):
                    href = urljoin(seed_url, href)
                if href.startswith(seed_url) and href not in visited:
                    queue.append(href)

            # convert page to markdown and chunk
            md_full = html_to_markdown(html)
            chunks = chunk_text(md_full)

            # summarize each chunk, fallback to raw chunk if summarizer fails
            summaries = []
            for chunk in chunks:
                try:
                    summary = summarize_markdown(chunk, url, seed_url)
                except Exception as e:
                    print(f"Summarizer error on {url}: {e}")
                    summary = chunk
                summaries.append(summary)

            final_summary = "\n\n".join(summaries)

            # prepend front-matter with scrape date
            scrape_date = datetime.now().isoformat()
            front_matter = (
                "---\n"
                f"title: \"{title}\"\n"
                f"url: \"{url}\"\n"
                f"date: \"{scrape_date}\"\n"
                "---\n\n"
            )
            content = front_matter + final_summary

            # save to file
            fname = url_to_filename(url)
            path = os.path.join(output_dir, fname)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Saved summary: {path}")

        browser.close()

# CLI entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Headless BFS scraper + LLM summarizer -> markdown files"
    )
    parser.add_argument("base_url", help="Base URL to seed the crawl")
    parser.add_argument(
        "--output", default="summaries", help="Directory to save markdown summaries"
    )
    args = parser.parse_args()

    full_pipeline(args.base_url, args.output)