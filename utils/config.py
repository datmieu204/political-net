# ./utils/config.py

class Settings():
    OUTPUT_DIR = "./data/processed"

    # Crawl names settings
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    URL_CRAWL_NAME = "https://vi.wikipedia.org/wiki/Ban_Chấp_hành_Trung_ương_Đảng_Cộng_sản_Việt_Nam_khóa_"
    OUTPUT_DIR_CRAWL_NAMES = OUTPUT_DIR + "/politicians_names.txt"

    # Crawl infobox settings
    VIWIKI_XML_DUMP_DIR = "data/raw/viwiki-latest-pages-articles.xml"
    INPUT_DIR_CRAWL_INFOBOX = OUTPUT_DIR_CRAWL_NAMES
    OUTPUT_DIR_CRAWL_INFOBOX = OUTPUT_DIR + "/politicians_infoboxes.json"

settings = Settings()
