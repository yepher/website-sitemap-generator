import json
import time
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import requests
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
import base64
import html2text
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

def capture_full_page_screenshot(driver, screenshot_path):
    driver.execute_cdp_cmd("Page.enable", {})
    screenshot_data = driver.execute_cdp_cmd("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
    screenshot_bytes = base64.b64decode(screenshot_data['data'])

    with open(screenshot_path, "wb") as file:
        file.write(screenshot_bytes)

def wait_for_full_page_load(driver, timeout=30):
    driver.execute_async_script("""
        var callback = arguments[arguments.length - 1];
        if (document.readyState === 'complete') {
            callback();
        } else {
            window.addEventListener('load', callback);
        }
    """)

    driver.execute_async_script("""
        var callback = arguments[arguments.length - 1];
        var maxTimeout = %d;
        var checkInterval = 100;
        var elapsed = 0;

        function checkNetworkIdle() {
            if (elapsed >= maxTimeout) {
                callback();
            } else if (performance.getEntriesByType('resource').some(e => !e.responseEnd)) {
                setTimeout(checkNetworkIdle, checkInterval);
                elapsed += checkInterval;
            } else {
                callback();
            }
        }

        checkNetworkIdle();
    """ % (timeout * 1000))

def accept_cookies(driver):
    try:
        cookie_button = driver.find_element(By.CSS_SELECTOR, "button.accept-cookies")  # Update the selector as needed
        cookie_button.click()
    except NoSuchElementException:
        pass

def convert_html_to_markdown(html_content):
    markdown_content = html2text.html2text(html_content)
    return markdown_content

def extract_text_from_page(driver, url, text_dir):
    driver.get(url)
    wait_for_full_page_load(driver)
    accept_cookies(driver)
    html_content = driver.find_element(By.TAG_NAME, 'body').get_attribute('outerHTML')
    markdown_content = convert_html_to_markdown(html_content)
    text_file_path = os.path.join(text_dir, f"{url.replace('https://', '').replace('http://', '').replace('/', '_')}.md")
    with open(text_file_path, "w") as file:
        file.write(markdown_content)
    return text_file_path

def get_page_details(driver, url, screenshot_dir, text_dir):
    start_time = time.time()
    driver.get(url)
    wait_for_full_page_load(driver)
    accept_cookies(driver)
    load_time = int((time.time() - start_time) * 1000)

    dimensions = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
    full_width = dimensions['contentSize']['width']
    full_height = dimensions['contentSize']['height']

    screenshot_path = os.path.join(screenshot_dir, f"{url.replace('https://', '').replace('http://', '').replace('/', '_')}.png")
    capture_full_page_screenshot(driver, screenshot_path)

    text_file_path = extract_text_from_page(driver, url, text_dir)

    links = driver.find_elements(By.TAG_NAME, 'a')
    hrefs = set()  # Use a set to store unique hrefs
    for link in links:
        try:
            href = link.get_attribute('href')
            if href is not None and href.startswith('http'):
                hrefs.add(href)
        except StaleElementReferenceException:
            continue

    response = requests.get(url)
    content_size = len(response.content) / (1024 * 1024)
    http_status_code = response.status_code

    return sorted(hrefs), load_time, http_status_code, content_size, screenshot_path, text_file_path, full_width, full_height

def crawl_site(driver, url, screenshot_dir, text_dir, max_depth=2, current_depth=0, visited=None):
    if visited is None:
        visited = set()
    if current_depth > max_depth or url in visited:
        return {}

    visited.add(url)
    links, load_time, http_status_code, content_size, screenshot_path, text_file_path, full_width, full_height = get_page_details(driver, url, screenshot_dir, text_dir)
    site_map = {
        url: {
            "page_load_time_ms": load_time,
            "http_status_code": http_status_code,
            "content_size_mb": content_size,
            "screenshot_path": screenshot_path,
            "text_file_path": text_file_path,
            "full_width": full_width,
            "full_height": full_height,
            "links": links
        }
    }

    for link in links:
        if link not in visited:
            site_map.update(crawl_site(driver, link, screenshot_dir, text_dir, max_depth, current_depth + 1, visited))

    return site_map

def create_sitemap(url, max_depth=2, screen_width="1366"):
    options = Options()
    options.headless = True
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument(f'--window-size={screen_width},1080')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    parsed_url = urlparse(url)
    base_dir = f"{parsed_url.netloc.replace('.', '_')}"
    screenshot_dir = os.path.join(base_dir, f"screens_{screen_width}")
    text_dir = os.path.join(base_dir, f"texts_{screen_width}")
    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(text_dir, exist_ok=True)

    try:
        site_map = crawl_site(driver, url, screenshot_dir, text_dir, max_depth)
    finally:
        driver.quit()

    return site_map

def load_additional_pages_from_sitemap(driver, base_url, site_map, visited, screenshot_dir, text_dir):
    sitemap_url = os.path.join(base_url, 'sitemap.xml')
    response = requests.get(sitemap_url)
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        for url_element in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            url = url_element.text
            if url not in visited:
                site_map.update(crawl_site(driver, url, screenshot_dir, text_dir, max_depth=1, visited=visited))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <URL> [screen_width]")
        sys.exit(1)

    website_url = sys.argv[1]
    screen_width = sys.argv[2] if len(sys.argv) > 2 else "1366"

    sitemap = create_sitemap(website_url, screen_width=screen_width)
    base_dir = f"{urlparse(website_url).netloc.replace('.', '_')}"
    sitemap_path = os.path.join(base_dir, 'sitemap.json')
    with open(sitemap_path, 'w') as f:
        json.dump(sitemap, f, indent=4)

    print(json.dumps(sitemap, indent=4))

    # Load additional pages from sitemap.xml
    options = Options()
    options.headless = True
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument(f'--window-size={screen_width},1080')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        visited = set(sitemap.keys())
        load_additional_pages_from_sitemap(driver, website_url, sitemap, visited, os.path.join(base_dir, f"screens_{screen_width}"), os.path.join(base_dir, f"texts_{screen_width}"))
    finally:
        driver.quit()

    with open(sitemap_path, 'w') as f:
        json.dump(sitemap, f, indent=4)

    print(json.dumps(sitemap, indent=4))