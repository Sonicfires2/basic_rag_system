import os
import datetime
import requests
import html2text
from urllib.parse import urlparse, quote_plus, urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

baseurl = 'https://www.altislabs.com/'
headers = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/113.0.0.0 Safari/537.36'
    )
}

OUTDIR = 'docs'
os.makedirs(OUTDIR, exist_ok=True)

# initialize markdown converter
md_converter = html2text.HTML2Text()
md_converter.ignore_links = False
md_converter.body_width = 0


def url_to_filename(url: str) -> str:
    parts = urlparse(url).path.strip('/').split('/')
    name = '_'.join(parts) or 'index'
    return quote_plus(name) + '.md'


def scrape_articles(pages: int = 3) -> list[dict]:
    """Returns a list of articles with title, url, and publication date (ISO)."""
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=headers['User-Agent'])
        page = context.new_page()

        for p in range(1, pages + 1):
            list_url = f'{baseurl}news?020cda41_page={p}'
            print(f'▶ Scraping page: {list_url}')
            page.goto(list_url, wait_until='networkidle')

            for post in page.query_selector_all('div.w--tab-active div.news__post'):
                # Title
                h4 = post.query_selector('h4.news__post-title')
                if not h4: continue
                title = h4.inner_text().strip()

                # URL
                link_el = post.query_selector('a[href]:not(.w-condition-invisible)')
                if not link_el: continue
                href = link_el.get_attribute('href')
                url = href if href.startswith(('http://','https://')) else urljoin(baseurl, href)

                # Date
                date_el = post.query_selector('h6.news__post-date')
                raw_date = date_el.inner_text().strip() if date_el else ''
                try:
                    # parse e.g. 'June 3, 2025'
                    date_obj = datetime.datetime.strptime(raw_date, '%B %d, %Y').date()
                    iso_date = date_obj.isoformat()
                except Exception:
                    iso_date = datetime.date.today().isoformat()

                results.append({'title': title, 'url': url, 'date': iso_date})

        browser.close()
    return results


if __name__ == '__main__':
    articles = scrape_articles(pages=3)
    for idx, art in enumerate(articles, start=1):
        print(f"* [{idx}/{len(articles)}] {art['date']} - {art['title']}")
        # Fetch and save
        url = art['url']
        title = art['title'].replace('"','\\"')
        date = art['date']

        # Front matter
        front_matter = (
            '---\n'
            f'title: "{title}"\n'
            f'url:   "{url}"\n'
            f'date:  "{date}"\n'
            'source: "Altis Labs News"\n'
            '---\n\n'
        )

        # Fetch body
        if url.startswith(baseurl):
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')
            main = soup.select_one('body') or soup
            body_md = md_converter.handle(str(main))
        else:
            body_md = f'# {title}\n\n'

        # Write file
        fname = url_to_filename(url)
        with open(os.path.join(OUTDIR, fname), 'w', encoding='utf-8') as f:
            f.write(front_matter)
            f.write(body_md)

    print(f'✅ Saved {len(articles)} articles to {OUTDIR}')
