# ./utils/config.py

class Settings():
    OUTPUT_DIR = "./data"

    # Crawl names settings
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    URL_CRAWL_NAME = "https://vi.wikipedia.org/wiki/Ban_Chấp_hành_Trung_ương_Đảng_Cộng_sản_Việt_Nam_khóa_"
    OUTPUT_DIR_CRAWL_NAMES = OUTPUT_DIR + ""
    "/politicians_names.txt"

    # Crawl infobox settings
    VIWIKI_XML_DUMP_DIR = "data/raw/viwiki-latest-pages-articles.xml"
    INPUT_DIR_CRAWL_INFOBOX = OUTPUT_DIR_CRAWL_NAMES
    OUTPUT_DIR_POLITICIAN_DB = OUTPUT_DIR + "/database/politicians_db.json"
    
    INPUT_SEED_TITLES_FILE = OUTPUT_DIR + "/mess/seed_politicians.txt"
    INPUT_POLITICIAN_DB_FILE = OUTPUT_DIR_POLITICIAN_DB
    OUTPUT_POLITICIAN_INFOBOX = OUTPUT_DIR + "/processed/infobox/politicians_data.json"

    # Preprocessing settings
    INPUT_CLEAN_INFOBOX_FILE = OUTPUT_POLITICIAN_INFOBOX
    OUTPUT_CLEAN_INFOBOX_FILE = OUTPUT_DIR + "/processed/infobox/politicians_data_cleaned.json"
    INPUT_PROVINCE_NORMALIZED_FILE = OUTPUT_CLEAN_INFOBOX_FILE
    OUTPUT_PROVINCE_NORMALIZED_FILE = OUTPUT_DIR + "/processed/infobox/politicians_data_provinces_normalized.json"

    # Neo4j settings
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

settings = Settings()
