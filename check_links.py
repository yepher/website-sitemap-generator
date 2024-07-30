import json
import requests
import logging

# Configure logging
logging.basicConfig(filename='link_checker.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_links(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    
    visited_links = set()
    total_links = sum(len(details.get('links', [])) for details in data.values())
    checked_links = 0
    
    for site, details in data.items():
        links = details.get('links', [])
        for link in links:
            if link in visited_links:
                continue
            visited_links.add(link)
            checked_links += 1
            print(f"Checking link {checked_links}/{total_links}: {link}")
            try:
                response = requests.get(link)
                if response.status_code != 200:
                    logging.info(f"URL: {link} - Status Code: {response.status_code} - Message: {response.reason}")
            except requests.RequestException as e:
                logging.error(f"Error occurred for URL: {link} - Error: {e}")

if __name__ == "__main__":
    check_links('sitemap.json')