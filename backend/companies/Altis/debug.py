from playwright.sync_api import sync_playwright
from urllib.parse import urljoin

baseurl = 'https://www.altislabs.com/'
headers = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/113.0.0.0 Safari/537.36'
    )
}


def debug_links(pages=3):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=headers['User-Agent'])
        page = context.new_page()

        for p in range(1, pages + 1):
            list_url = f'{baseurl}news?020cda41_page={p}'
            print(f"▶️  Debugging: {list_url}")
            page.goto(list_url, wait_until='networkidle')

            # Iterate through each post and print all <a> hrefs and their classes
            for post in page.query_selector_all('div.w--tab-active div.news__post'):
                for link in post.query_selector_all('a[href]'):
                    href = link.get_attribute('href')
                    classes = link.get_attribute('class') or ''
                    print(f"→ link: {href}, classes={classes}")

        browser.close()


if __name__ == '__main__':
    debug_links()