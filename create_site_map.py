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
from selenium.common.exceptions import StaleElementReferenceException
import base64

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

def get_page_details(driver, url, screenshot_dir):
    start_time = time.time()
    driver.get(url)
    wait_for_full_page_load(driver)
    load_time = int((time.time() - start_time) * 1000)

    dimensions = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
    full_width = dimensions['contentSize']['width']
    full_height = dimensions['contentSize']['height']

    screenshot_path = os.path.join(screenshot_dir, f"{url.replace('https://', '').replace('http://', '').replace('/', '_')}.png")
    capture_full_page_screenshot(driver, screenshot_path)

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

    return sorted(hrefs), load_time, http_status_code, content_size, screenshot_path, full_width, full_height

def crawl_site(driver, url, screenshot_dir, max_depth=2, current_depth=0, visited=None):
    if visited is None:
        visited = set()
    if current_depth > max_depth or url in visited:
        return {}

    visited.add(url)
    links, load_time, http_status_code, content_size, screenshot_path, full_width, full_height = get_page_details(driver, url, screenshot_dir)
    site_map = {
        url: {
            "page_load_time_ms": load_time,
            "http_status_code": http_status_code,
            "content_size_mb": content_size,
            "screenshot_path": screenshot_path,
            "full_width": full_width,
            "full_height": full_height,
            "links": links
        }
    }

    for link in links:
        if link not in visited:
            site_map.update(crawl_site(driver, link, screenshot_dir, max_depth, current_depth + 1, visited))

    return site_map

def create_sitemap(url, max_depth=2, screen_width="1366"):
    options = Options()
    options.headless = True
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument(f'--window-size={screen_width},1080')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    screenshot_dir = f"screens_{screen_width}"
    os.makedirs(screenshot_dir, exist_ok=True)

    try:
        site_map = crawl_site(driver, url, screenshot_dir, max_depth)
    finally:
        driver.quit()

    return site_map

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <URL> [screen_width]")
        sys.exit(1)

    website_url = sys.argv[1]
    screen_width = sys.argv[2] if len(sys.argv) > 2 else "1366"

    sitemap = create_sitemap(website_url, screen_width=screen_width)
    with open('sitemap.json', 'w') as f:
        json.dump(sitemap, f, indent=4)

    print(json.dumps(sitemap, indent=4))