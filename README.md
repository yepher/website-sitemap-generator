# Website Sitemap Generator

This script is a web crawler that generates a sitemap for a given website URL. It captures page details such as page load time, HTTP status code, content size, and a full-page screenshot. The sitemap is saved as a JSON file.

## Features

- Captures page load time, HTTP status code, and content size.
- Takes full-page screenshots.
- Retrieves all links on each page and crawls them up to a specified depth.
- Supports headless browsing using Selenium and ChromeDriver.

## Requirements

- Python 3.x
- Selenium
- WebDriver Manager for Chrome
- Requests

## Installation

1. Clone this repository:
    ```sh
    git clone https://github.com/yepher/website-sitemap-generator.git
    cd website-sitemap-generator
    ```

2. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

The script can be run from the command line. You need to provide the URL of the website you want to crawl. Optionally, you can also specify the device screen width.

### Command Line Arguments

- `URL`: The website URL to crawl.
- `screen_width` (optional): The screen width of the device (e.g., 1920 for a desktop, 375 for a mobile device).

### Example

Initial setup
```sh
python -m venv ./.venv
source .venv/bin/activate
pip install --upgrade pip

pip install -r requirements.txt
```


To generate a sitemap for `https://example.com` with a default screen width:
```sh
python script.py https://example.com
```

To generate a sitemap for `https://example.com` with a specified screen width:
```sh
python script.py https://example.com 375
```

The sitemap will be saved as `sitemap.json` in the current directory.

## Typical Screen Sizes

| Device            | Screen Width (px) |
|-------------------|-------------------|
| Desktop (Full HD) | 1920              |
| Laptop            | 1366              |
| Tablet (Landscape)| 1024              |
| Tablet (Portrait) | 768               |
| Mobile (Large)    | 414               |
| Mobile (Medium)   | 375               |
| Mobile (Small)    | 320               |

## Notes

- Ensure you have Google Chrome installed on your machine, as the script uses ChromeDriver.
- The script is set to run in headless mode by default.
- The maximum crawl depth is set to 2 by default. You can modify this value in the `create_sitemap` function if needed.

## License

This project is licensed under the MIT License.

## Contributing

If you find any issues or have suggestions for improvements, feel free to open an issue or submit a pull request.

---

This README provides an overview of the script, how to set it up, and how to use it, including a table of typical screen sizes for different devices.
