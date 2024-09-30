import os
import requests
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import argparse

def fetch_markdown(scraper, url):
    if scraper == 'dhr':
        print(f"Fetching markdown with dhr...")
        api_url = f"https://md.dhr.wtf/?url={url}"
    elif scraper == 'jina':
        print(f"Fetching markdown with jina...")
        api_url = f"https://r.jina.ai/{url}"
    else:
        raise ValueError("Unsupported scraper")

    response = requests.get(api_url)
    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to fetch markdown for {url}")
        return None

def extract_urls_from_markdown(markdown_content):
    # Convert Markdown to HTML
    md = MarkdownIt()
    html_content = md.render(markdown_content)
    
    # Parse HTML to extract URLs
    soup = BeautifulSoup(html_content, 'html.parser')
    return set(a['href'] for a in soup.find_all('a', href=True))

def save_markdown(url, markdown_content, base_dir):
    parsed_url = urlparse(url)
    # Remove 'www.' prefix if it exists
    domain = parsed_url.netloc.replace('www.', '').replace('.', '_')
    domain_dir = os.path.join(base_dir, domain)
    os.makedirs(domain_dir, exist_ok=True)

    # Ensure the filename ends with .md
    path = parsed_url.path.strip('/')
    if not path or path.endswith('/'):
        path = os.path.join(path, 'index.md')
    else:
        path = f"{path}.md"
    filename = os.path.join(domain_dir, path.replace('/', '_'))

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

def scrape_site(url, scraper, base_dir, scraped_urls):
    urls_to_scrape = {url}

    while urls_to_scrape:
        current_url = urls_to_scrape.pop()
        if current_url in scraped_urls:
            continue
        if url not in current_url:
            continue

        print(f"Scraping {current_url}...")
        markdown_content = fetch_markdown(scraper, current_url)
        if markdown_content:
            save_markdown(current_url, markdown_content, base_dir)
            new_urls = extract_urls_from_markdown(markdown_content)
            urls_to_scrape.update(new_urls)
        
        scraped_urls.add(current_url)

def fetch_all_sitemap_urls(base_url):
    def get_sitemap_urls_recursive(sitemap_url, collected_urls):
        response = requests.get(sitemap_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'lxml-xml')
            # Check if it's a sitemap index
            sitemap_tags = soup.find_all('sitemap')
            if sitemap_tags:
                print(f"Found sitemap index: {sitemap_url}")
                # Recursively handle sitemap index
                for sitemap in sitemap_tags:
                    child_sitemap_url = sitemap.find('loc').text
                    get_sitemap_urls_recursive(child_sitemap_url, collected_urls)
            else:
                # It's a regular sitemap with URLs
                loc_tags = soup.find_all('loc')
                for loc in loc_tags:
                    url = loc.text
                    collected_urls.add(url)
        else:
            print(f"Failed to fetch sitemap: {sitemap_url}")

    # Start by fetching the initial sitemap
    sitemap_urls = get_sitemap_urls(base_url)
    all_urls = set()

    for sitemap_url in sitemap_urls:
        get_sitemap_urls_recursive(sitemap_url, all_urls)
    
    return all_urls

def get_sitemap_urls(base_url):
    sitemap_url = urljoin(base_url, '/sitemap.xml')
    response = requests.get(sitemap_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'lxml-xml')
        return set(loc.text for loc in soup.find_all('loc'))
    else:
        print(f"Failed to fetch sitemap for {base_url}")
        return set()

def main():
    parser = argparse.ArgumentParser(description='Scrape website to Markdown.')
    parser.add_argument('url', type=str, help='The URL to scrape.')
    parser.add_argument('-s', '--scraper', type=str, choices=['dhr', 'jina'], required=True, help='Which scraper to use.')
    parser.add_argument('-o', '--output', type=str, default='scrape', help='Output directory for scraped content.')
    args = parser.parse_args()

    base_url = args.url
    scraper = args.scraper
    base_dir = args.output

    # Set to keep track of already scraped URLs
    scraped_urls = set()

    # Scrape the main site
    scrape_site(base_url, scraper, base_dir, scraped_urls)

    # Fetch and scrape from all sitemaps
    all_sitemap_urls = fetch_all_sitemap_urls(base_url)
    print(f"Found {len(all_sitemap_urls)} URLs in all sitemaps")
    for sitemap_url in all_sitemap_urls:
        if sitemap_url not in scraped_urls:
            scrape_site(sitemap_url, scraper, base_dir, scraped_urls)

if __name__ == '__main__':
    main()