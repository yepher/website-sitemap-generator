import platform
import subprocess
import json
import time
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
import hashlib
import requests
from requests.exceptions import ConnectionError, Timeout
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
import base64
import html2text
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from webdriver_manager.core.os_manager import ChromeType
import re
import urllib.parse

# Create a session and add the cookie
session = requests.Session()
session.cookies.set('privacy-policy', '1,XXXXXXXXXXXXXXXXXXXXXX')

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
    h = html2text.HTML2Text()
    h.body_width = 0  # Disable line wrapping
    markdown_content = h.handle(html_content)
    
    # Remove extra newlines between URL and its text
    markdown_content = markdown_content.replace(']\n(', '](')
    
    # Fix image URLs
    def fix_image_url(match):
        alt_text = match.group(1)
        url = match.group(2)
        decoded_url = urllib.parse.unquote(url)
        # Extract the actual image URL from the query parameter
        actual_url = urllib.parse.parse_qs(urllib.parse.urlparse(decoded_url).query).get('url', [None])[0]
        if actual_url:
            return f'![{alt_text}]({actual_url})'
        else:
            return f'![{alt_text}]({url})'

    markdown_content = re.sub(r'!\[(.*?)\]\((/_next/image\?.*?)\)', fix_image_url, markdown_content)
    
    # Remove multiple consecutive blank lines
    markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
    
    # Ensure proper spacing around headers
    markdown_content = re.sub(r'(\n#+.*)\n+', r'\1\n\n', markdown_content)
    
    # Remove spaces before newlines
    markdown_content = re.sub(r' +\n', '\n', markdown_content)
    
    return markdown_content

def extract_text_from_page(driver, url, text_dir):
    driver.get(url)
    wait_for_full_page_load(driver)
    accept_cookies(driver)
    
    # Get the full HTML content
    html_content = driver.page_source
    
    # Parse the HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the main content
    main_content = soup.find('main')
    
    if main_content:
        # Remove header and footer if they exist within main
        for tag in main_content.find_all(['header', 'footer']):
            tag.decompose()
        
        # Convert the main content to markdown
        markdown_content = convert_html_to_markdown(str(main_content))
    else:
        # If no main tag is found, use the body content as fallback
        body_content = soup.find('body')
        if body_content:
            # Remove header and footer from body
            for tag in body_content.find_all(['header', 'footer']):
                tag.decompose()
            markdown_content = convert_html_to_markdown(str(body_content))
        else:
            markdown_content = "No content found"

    # Add the source line at the top of the markdown content
    markdown_content = f"[source]({url})\n\n{markdown_content}"

    # Create the file path
    text_file_path = os.path.join(text_dir, f"{url.replace('https://', '').replace('http://', '').replace('/', '_')}.md")

    # Write the markdown content to the file
    with open(text_file_path, "w", encoding='utf-8') as file:
        file.write(markdown_content)

    return text_file_path

def get_page_details(driver, url, screenshot_dir, text_dir):
    start_time = time.time()
    driver.get(url)
    wait_for_full_page_load(driver)
    accept_cookies(driver)
    load_time = int((time.time() - start_time) * 1000)

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

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

    # Retry mechanism for the request
    retries = 3
    for attempt in range(retries):
        try:
            response = session.get(url)  # Use the session with the cookie
            content_size = len(response.content) / (1024 * 1024)
            http_status_code = response.status_code

            # Log any "Set-Cookie" headers
            if 'Set-Cookie' in response.headers:
                print(f"Set-Cookie headers from {url}: {response.headers['Set-Cookie']}")

            return sorted(hrefs), load_time, http_status_code, content_size, screenshot_path, text_file_path, full_width, full_height
        except (ConnectionError, Timeout) as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break

    # If all retries fail, return default values
    return sorted(hrefs), load_time, None, None, screenshot_path, text_file_path, full_width, full_height

def crawl_site(driver, url, screenshot_dir, text_dir, base_domain, max_depth=2, current_depth=0, visited=None, exclude_translations=False):
    if visited is None:
        visited = set()
    if current_depth > max_depth or url in visited:
        return {}

    parsed_url = urlparse(url)
    if not (parsed_url.netloc == base_domain or parsed_url.netloc.endswith('.' + base_domain)):
        return {}

    # Check if the URL should be excluded based on translation
    if exclude_translations and is_translated_url(parsed_url.path):
        print(f"Skipping translated page: {url}")
        return {}

    visited.add(url)
    print(f"Crawling {url}...")
    try:
        links, load_time, http_status_code, content_size, screenshot_path, text_file_path, full_width, full_height = get_page_details(driver, url, screenshot_dir, text_dir)
    except WebDriverException as e:
        if 'net::ERR_CONNECTION_REFUSED' in str(e):
            print(f"Failed to crawl {url}: Connection refused.")
        else:
            print(f"Failed to crawl {url}: {e}")
        return {}
    
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
            # Pass the exclude_translations parameter to recursive calls
            site_map.update(crawl_site(driver, link, screenshot_dir, text_dir, base_domain, max_depth, current_depth + 1, visited, exclude_translations))

    return site_map

def is_arm_mac():
    if platform.system() != "Darwin":
        return False
    try:
        output = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode("utf-8")
        return "Apple" in output
    except:
        return False
    
def get_driver(screen_width):
    options = Options()
    options.headless = True
    options.add_argument("--headless")
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--window-size={screen_width},1080')

    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3')

    if not is_arm_mac():
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver

    #Use ChromeType.CHROMIUM for ARM64 Macs
    driver_path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    service = Service(driver_path)
    try:
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"Error initializing Chrome driver: {e}")
        print("Attempting to use Selenium Manager...")
        options.add_argument("--use-selenium-manager")
        driver = webdriver.Chrome(options=options)

    return driver

def create_sitemap(url, max_depth=2, screen_width="1366", exclude_translations=False):
    driver = get_driver(screen_width)

    parsed_url = urlparse(url)
    base_domain = parsed_url.netloc
    base_dir = os.path.join("scrape", f"{base_domain.replace('.', '_')}")
    screenshot_dir = os.path.join(base_dir, f"screens_{screen_width}")
    text_dir = os.path.join(base_dir, f"texts_{screen_width}")
    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(text_dir, exist_ok=True)

    try:
        site_map = crawl_site(driver, url, screenshot_dir, text_dir, base_domain, max_depth, exclude_translations=exclude_translations)
    finally:
        driver.quit()

    return site_map

def load_additional_pages_from_sitemap(driver, base_url, site_map, visited, screenshot_dir, text_dir, base_domain, exclude_translations):
    sitemap_url = os.path.join(base_url, 'sitemap.xml')
    response = session.get(sitemap_url)  # Use the session with the cookie
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        for url_element in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            url = url_element.text
            parsed_url = urlparse(url)
            if url not in visited and (not exclude_translations or not is_translated_url(parsed_url.path)):
                site_map.update(crawl_site(driver, url, screenshot_dir, text_dir, base_domain, max_depth=1, visited=visited, exclude_translations=exclude_translations))

def is_translated_url(path):
    # This function checks if the URL path indicates a translated page
    # You can customize this based on your site's URL structure
    language_codes = [
        'fr', 'es', 'de', 'it', 'ja', 'ko', 'zh',
        'sg', 'id', 'th', 'vi', 'ms', 'ar', 'hi', 
        'bn', 'ur', 'fa', 'tr', 'nl', 'pl', 'cs', 
        'sk', 'hu', 'ro', 'bg', 'sr', 'hr', 'sl', 
        'mk', 'bg', 'sr', 'hr', 'sl', 'mk', 'en-nl',
        'pl', 'nl-nl', 'en-es', 'id-id', 'nl-nl',
        'fr-fr', 'en-fr', 'en-ca', 'en-gb', 'en-au', 
        'en-nz', 'en-sg', 'en-hk', 'en-in', 'en-ph', 
        'en-id', 'en-my', 'en-th', 'en-tw', 'en-kr', 
        'en-jp', 'en-cn', 'en-tr', 'en-ae', 'en-sa', 
        'en-eg', 'en-il', 'en-ng', 'en-za', 'en-ke', 
        'en-ug', 'en-zm', 'en-zw', 'en-gh', 'en-ng', 
        'en-za', 'en-ke', 'en-ug', 'en-zm', 'en-zw', 
        'en-gh'
    ]
    parts = path.split('/')
    return any(part in language_codes for part in parts)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <URL> [screen_width] [exclude_translations]")
        sys.exit(1)

    website_url = sys.argv[1]
    screen_width = sys.argv[2] if len(sys.argv) > 2 else "1366"
    exclude_translations = sys.argv[3].lower() == 'true' if len(sys.argv) > 3 else False
    if exclude_translations:
        print("Excluding translated pages")

    sitemap = create_sitemap(website_url, screen_width=screen_width, exclude_translations=exclude_translations)
    base_dir = f"{urlparse(website_url).netloc.replace('.', '_')}"
    base_dir = os.path.join("scrape", base_dir)
    
    # Create the base directory if it doesn't exist
    os.makedirs(base_dir, exist_ok=True)
    
    sitemap_path = os.path.join(base_dir, 'sitemap.json')
    with open(sitemap_path, 'w') as f:
        json.dump(sitemap, f, indent=4)

    print(json.dumps(sitemap, indent=4))

    driver = get_driver(screen_width)

    try:
        visited = set(sitemap.keys())
        parsed_url = urlparse(website_url)
        base_domain = parsed_url.netloc
        load_additional_pages_from_sitemap(driver, website_url, sitemap, visited, os.path.join(base_dir, f"screens_{screen_width}"), os.path.join(base_dir, f"texts_{screen_width}"), base_domain, exclude_translations)
    finally:
        driver.quit()

    with open(sitemap_path, 'w') as f:
        json.dump(sitemap, f, indent=4)

    file_checksums = {}
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    file_checksum = hashlib.md5(file_content).hexdigest()

                    if file_checksum in file_checksums:
                        # If this checksum already exists, compare file names
                        existing_file = file_checksums[file_checksum]
                        if len(file) < len(existing_file):
                            # Current file has a shorter name, delete the existing one
                            os.remove(os.path.join(root, existing_file))
                            file_checksums[file_checksum] = file
                        else:
                            # Existing file has a shorter or equal length name, delete the current one
                            os.remove(file_path)
                    else:
                        # New checksum, add to dictionary
                        file_checksums[file_checksum] = file

    print(json.dumps(sitemap, indent=4))
