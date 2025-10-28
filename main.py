# ./main.py

from utils.config import settings
from crawl.crawl_names import crawl_and_save_politician_names

if __name__ == "__main__":
    terms = ["XIII", "XII", "XI", "X", "IX", "VIII", "VII", "VI", "V", "IV", "III", "II", "I"]
    crawl_and_save_politician_names(terms, settings.OUTPUT_DIR_CRAWL_NAMES)