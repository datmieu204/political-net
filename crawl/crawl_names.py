# ./crawl/crawl_names.py

import re
import os
import requests

from bs4 import BeautifulSoup
from urllib.parse import unquote

from utils.config import settings
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("crawl_names", log_file="logs/crawl/crawl_names.log")

exclusion_keywords = [
    "Việt Nam", "Đảng Cộng sản Việt Nam", 
    "Ban Chấp hành Trung ương", "Danh sách", 
    "Chính phủ", "Ủy ban", "Hội đồng", 
    "Thành viên",
    "Trung ương",
    "TP", "TP.", "Thành phố", "Ban Bí thư", "Bộ Chính trị"
]

def connect_url(url: str) -> requests.Response:
    """
    Connect to a URL and return the response object.
    """
    try:
        headers = {
            "User-Agent": settings.USER_AGENT
        }
        response = requests.get(url, headers=headers)
        response.encoding = "utf-8"
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        log.error(f"Error fetching {url}: {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        return None

def extract_names(term: str) -> list[str]:
    """
    Crawl List politicians from Wikipedia page for a given term (the table "Ủy viên chính thức Ban Chấp hành Trung ương").
    """
    url = settings.URL_CRAWL_NAME + term
    log.info(f"Crawling names from {url}")

    response = connect_url(url)
    if response is None:
        return []

    try:
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        log.error(f"Error parsing HTML: {e}")
        return []

    try:
        tables = soup.find_all("table", class_="wikitable")
        ordered_lists = soup.find_all("ol")
        
        log.info(f"Find {len(tables)} table wikitable and {len(ordered_lists)} ordered lists in {url}")

        if not tables and not ordered_lists:
            log.warning(f"Not found tables or lists in {url}, return empty list")
            return []
    
        top_level_tables = []
        for table in tables:
            parent_table = table.find_parent("table", class_="wikitable")
            if parent_table is None:
                top_level_tables.append(table)
        
        log.info(f"Found {len(top_level_tables)} top-level tables and {len(ordered_lists)} ordered lists")

    except Exception as e:
        log.exception(f"Error finding tables/lists: {e}")
        return []
    
    names = []

    try:
        for table in top_level_tables:
            rows = table.find("tbody").find_all("tr", recursive=False) if table.find("tbody") else table.find_all("tr", recursive=False)
            
            log.info(f"Processing table with {len(rows)} direct rows")
            
            for row in rows:
                cols = row.find_all("td", recursive=False)
                
                if len(cols) > 1:
                    name_cell = cols[1]
                    
                    nested_table = name_cell.find("table", class_="wikitable")
                    
                    if nested_table:
                        log.info(f"Found nested table in row, processing nested table")
                        nested_rows = nested_table.find("tbody").find_all("tr", recursive=False) if nested_table.find("tbody") else nested_table.find_all("tr", recursive=False)
                        
                        for nested_row in nested_rows:
                            nested_cols = nested_row.find_all("td", recursive=False)
                            if len(nested_cols) > 1:
                                nested_name_cell = nested_cols[1]
                                nested_link = nested_name_cell.find("a")
                                
                                if nested_link:
                                    try:
                                        name_href = unquote(nested_link.get("href").replace("/wiki/", "").replace("_", " "))

                                        if name_href.startswith("/w/index.php?title="):
                                            match = re.search(r"/w/index\.php\?title=([^&]+)", name_href)
                                            if match:
                                                name_href = unquote(match.group(1)).replace("_", " ")

                                        if name_href.startswith("#cite") or name_href.isdigit():
                                            continue

                                        if any(keyword in name_href for keyword in exclusion_keywords):
                                            continue

                                        names.append(name_href)

                                    except Exception as e:
                                        log.warning(f"Error extracting name from nested link {nested_link}: {e}")
                    else:
                        link = name_cell.find("a")

                        if name_cell.find("br") or name_cell.find("p"):
                            if link:
                                try:
                                    name_href = unquote(link.get("href").replace("/wiki/", "").replace("_", " "))

                                    if name_href.startswith("/w/index.php?title="):
                                        match = re.search(r"/w/index\.php\?title=([^&]+)", name_href)
                                        if match:
                                            name_href = unquote(match.group(1)).replace("_", " ")

                                    if name_href.startswith("#cite") or name_href.isdigit():
                                        continue

                                    if any(keyword in name_href for keyword in exclusion_keywords):
                                        continue

                                    names.append(name_href)

                                except Exception as e:
                                    log.warning(f"Error extracting name from link {link}: {e}")

                        elif not name_cell.find("br") and not name_cell.find("p") and link and len(name_cell.find_all("a")) == 1:
                            if link:
                                try:
                                    name_href = unquote(link.get("href").replace("/wiki/", "").replace("_", " "))

                                    if name_href.startswith("/w/index.php?title="):
                                        match = re.search(r"/w/index\.php\?title=([^&]+)", name_href)
                                        if match:
                                            name_href = unquote(match.group(1)).replace("_", " ")

                                    if name_href.startswith("#cite") or name_href.isdigit():
                                        continue

                                    if any(keyword in name_href for keyword in exclusion_keywords):
                                        continue

                                    names.append(name_href)

                                except Exception as e:
                                    log.warning(f"Error extracting name from link {link}: {e}")
        
        for ol in ordered_lists:
            list_items = ol.find_all("li", recursive=False)
            log.info(f"Processing ordered list with {len(list_items)} items")
            
            for li in list_items:
                link = li.find("a")
                if link:
                    try:
                        name_href = unquote(link.get("href").replace("/wiki/", "").replace("_", " "))

                        if name_href.startswith("/w/index.php?title="):
                            match = re.search(r"/w/index\.php\?title=([^&]+)", name_href)
                            if match:
                                name_href = unquote(match.group(1)).replace("_", " ")

                        if name_href.startswith("#cite") or name_href.isdigit():
                            continue

                        if any(keyword in name_href for keyword in exclusion_keywords):
                            continue

                        names.append(name_href)

                    except Exception as e:
                        log.warning(f"Error extracting name from list link {link}: {e}")
        
        log.info(f"Successfully extracted {len(names)} politician names from {len(top_level_tables)} table(s) and {len(ordered_lists)} list(s)")
    except Exception as e:
        log.exception(f"Error processing table rows: {e}")
        return []

    log.info(f"Total politician names found: {len(names)}")
    return names

def extract_multiple_terms(terms: list[str]) -> list[str]:
    """
    Crawl names from multiple terms and return unique sorted list.
    """
    all_names = []
    for term in terms:
        try:
            names = extract_names(term)
            all_names.extend(names)
        except Exception as e:
            log.warning(f"Error extracting names for term '{term}': {e}")
            continue
    
    try:
        unique_names = sorted(set(all_names))
        log.info(f"Total {len(unique_names)} unique politician names extracted from terms: {terms}")
        return unique_names
    except Exception as e:
        log.error(f"Error processing all names: {e}")
        return []

def write_names_to_file(names, filename):
    if not names:
        log.warning("No names to write.")
        return

    if not os.path.exists(os.path.dirname(filename)):
        os.makedirs(os.path.dirname(filename), exist_ok=True)

    log.info(f"Write {len(names)} names to file {filename}")

    try:
        with open(filename, "w", encoding="utf-8") as f:
            for name_href in names:
                f.write(f"{name_href}\n")
    except Exception as e:
        log.error(f"Error writing names to file {filename}: {e}")

def crawl_and_save_politician_names(terms, output_file):
    try:
        unique_names = extract_multiple_terms(terms)
        write_names_to_file(unique_names, output_file)
        log.info(f"Saved to file {output_file}")
    except Exception as e:
        log.error(f"Error in crawl_and_save_politician_names: {e}")