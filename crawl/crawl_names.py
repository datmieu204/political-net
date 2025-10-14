# ./crawl/crawl_names.py

import os
import requests

from bs4 import BeautifulSoup
from urllib.parse import unquote

from utils.queue_based_async_logger import get_async_logger
from utils.config import settings

log = get_async_logger("crawl_names", log_file="logs/crawl/crawl_names.log")

def extract_names(term: str) -> list[str]:
    """
    Crawl List politicians from Wikipedia page for a given term (the table "Ủy viên chính thức Ban Chấp hành Trung ương").
    """

    url = settings.URL_CRAWL_NAME + term
    log.info(f"Crawling names from {url}")

    headers = {
        "User-Agent": settings.USER_AGENT
    }

    response = requests.get(url, headers=headers)
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")

    tables = soup.find_all("table", class_="wikitable")
    log.info(f"Find {len(tables)} table wikitable in {url}")

    if not tables:
        log.warning(f"Not found {url}, return empty list")
        return []
    
    table = max(tables, key=lambda t: len(t.find_all("tr")))
    
    names = []
    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) > 1:
            name_cell = cols[1]
            link = name_cell.find("a")
            if name_cell.find("br") or name_cell.find("p"):
                if link:
                    name_href = unquote(link.get("href").replace("/wiki/", "").replace("_", " "))
                    names.append(name_href)

    log.info(f"Extracted {len(names)} names from table")

    return names

def extract_multiple_terms(terms: list[str]) -> list[str]:
    """
    Crawl names from multiple terms and return unique sorted list.
    """
    all_names = []
    for term in terms:
        names = extract_names(term)
        all_names.extend(names)
    
    unique_names = sorted(set(all_names))
    log.info(f"Total {len(unique_names)} unique politician names extracted from terms: {terms}")
    return unique_names

def write_names_to_file(names, filename):
    if not names:
        log.warning("No names to write.")
        return

    if not os.path.exists(os.path.dirname(filename)):
        os.makedirs(os.path.dirname(filename), exist_ok=True)

    log.info(f"Write {len(names)} names to file {filename}")

    with open(filename, "w", encoding="utf-8") as f:
        for name_href in names:
            f.write(f"{name_href}\n")
            

def crawl_and_save_politician_names(terms, output_file):
    unique_names = extract_multiple_terms(terms)
    write_names_to_file(unique_names, output_file)
    log.info(f"Saved to file {output_file}")

if __name__ == "__main__":
    terms = ["XIII"]    
    output_file = settings.OUTPUT_DIR_CRAWL_NAMES
    crawl_and_save_politician_names(terms, output_file)