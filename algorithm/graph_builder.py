# ./algorithm/graph_builder.py
"""
BƯỚC 2: GRAPH BUILDER - XÂY DỰNG MẠNG LƯỚI
Đọc file "database" (JSON) đã xử lý và file hạt giống,
sau đó chạy thuật toán BFS/DFS trong bộ nhớ (in-memory)
để duyệt đồ thị và trích xuất mạng lưới.
"""

import json
import re
from typing import Dict, Set
from collections import deque

from utils.queue_based_async_logger import get_async_logger
from utils.external import EXCLUDE_KEYWORDS, VIETNAM_KEYWORDS, NON_VIETNAM_KEYWORDS, FIELDS_TO_CHECK, INVALID_KEYWORDS, VALID_KEYWORDS

log = get_async_logger("graph_builder", log_file="logs/algorithm/graph_builder.log")

def extract_names_from_wikilink(text: str) -> Set[str]:
    names = set()

    pattern = r'\[\[([^\]]+)\]\]'
    matches = re.findall(pattern, text)
    
    for match in matches:
        if '|' in match:
            name = match.split('|')[0].strip()
        else:
            name = match.strip()
        
        exclude_keywords = EXCLUDE_KEYWORDS
        name_lower = name.lower()

        if name and not any(ex in name_lower for ex in exclude_keywords):
            if name_lower not in ["''đầu tiên''", "''cuối cùng''"]:
                names.add(name)
    return names

def extract_relations(infobox_normalized: Dict, found_titles: Set[str]) -> Set[str]:
    new_names = set()

    RELATION_BASE_KEYS = {
        'successor', 'predecessor', 'deputy_name', 'leader_name', 'spouse',
    }

    key_stripper_regex = re.compile(r'^(.*?)[\s_]*\d+$')

    for key, value in infobox_normalized.items():
        match = key_stripper_regex.match(key)
        if match:
            base_key = match.group(1)
        else:
            base_key = key
        
        if base_key in RELATION_BASE_KEYS:
            names = extract_names_from_wikilink(value)
            new_names.update(names)
    
    return new_names - found_titles

def get_birth_year(infobox: Dict) -> int | None:
    if not infobox:
        return None
        
    birth_date_string = infobox.get('birth_date', '')
    if not birth_date_string:
        return None

    match = re.search(r'\b(1[89]\d{2}|20\d{2})\b', birth_date_string)
    
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None

def is_vietnamese_politician(infobox: Dict) -> bool:
    if not infobox:
        return False
    
    text_to_check = " ".join(
        str(infobox.get(field, '')).lower() for field in FIELDS_TO_CHECK
    )

    text_clean = f" {text_to_check} "

    for keyword in VIETNAM_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword.lower())}\b", text_clean):
            return True

    for keyword in NON_VIETNAM_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword.lower())}\b", text_clean):
            return False

    return True

def is_valid_politician_template(template_name: str) -> bool:
    if not template_name:
        return False
    
    template_lower = template_name.lower()
    
    invalid_keywords = INVALID_KEYWORDS
    
    for invalid in invalid_keywords:
        if invalid in template_lower:
            return False
    
    valid_keywords = VALID_KEYWORDS
    
    for valid in valid_keywords:
        if valid in template_lower:
            return True    
    return False

def build_network(initial_titles_file: str, db_file: str, output_file: str, max_depth: int = 5):
    """
    The algorithm to build the politician network (BFS):
    1. Check template of politician node.
    2. Check birth year >= 1850.
    3. Check Vietnamese politician only.
    """
    log.info(f"BƯỚC 2: XÂY DỰNG MẠNG LƯỚI (BFS)")
    log.info(f"Input DB: {db_file}")
    log.info(f"Seed file: {initial_titles_file}")
    log.info(f"Max depth: {max_depth}")

    log.info(f"Loading politician db from {db_file}...") # load db

    try:
        with open(db_file, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    except FileNotFoundError:
        log.error(f"Error: Database file {db_file} not found.")
        return
        
    politician_db = {p['title']: p for p in all_data}
    log.info(f"Loaded {len(politician_db)} politicians into memory map.")

    with open(initial_titles_file, 'r', encoding='utf-8') as f:
        initial_titles = set(line.strip() for line in f if line.strip())
    log.info(f"Loaded {len(initial_titles)} seed titles.")
    
    queue = deque()
    visited_titles = set()
    extracted_data = []

    # 4. Thêm các nút hạt giống vào hàng đợi
    for title in initial_titles:
        if title in politician_db and title not in visited_titles:
            
            # --- CHỈNH SỬA: KIỂM TRA TEMPLATE, NĂM SINH VÀ QUỐC TỊCH CỦA HẠT GIỐNG ---
            politician_data = politician_db[title]
            template = politician_data.get('template', '')
            infobox = politician_data.get('infobox', {})
            birth_year = get_birth_year(infobox)

            if not is_valid_politician_template(template):
                log.warning(f"Seed title '{title}' is filtered out (Invalid template: '{template}').")
                continue

            if birth_year and birth_year < 1850:
                log.warning(f"Seed title '{title}' is filtered out (Birth year: {birth_year} < 1850).")
                continue
            
            if not is_vietnamese_politician(infobox):
                log.warning(f"Seed title '{title}' is filtered out (Not Vietnamese politician).")
                continue

            visited_titles.add(title)
            queue.append((title, 0)) # (title, độ sâu)
            extracted_data.append(politician_data)
        elif title not in politician_db:
            log.warning(f"Seed title '{title}' not found in database.")

    log.info(f"Starting BFS crawl from {len(extracted_data)} valid seed nodes...")
    
    while queue:
        current_title, current_depth = queue.popleft()
        
        log.info(f"[Depth {current_depth}] Processing: {current_title}")

        if current_depth >= max_depth:
            log.info(f"-> Reached max depth. Stopping expansion for this node.")
            continue
        
        current_politician_data = politician_db.get(current_title)
        if not current_politician_data:
            continue 

        infobox_norm = current_politician_data.get('infobox', {})
        neighbor_titles = extract_relations(infobox_norm, visited_titles)

        for neighbor_title in neighbor_titles:
            if neighbor_title not in visited_titles:
                visited_titles.add(neighbor_title) 
                
                neighbor_data = politician_db.get(neighbor_title)
                
                if neighbor_data:
                    
                    neighbor_template = neighbor_data.get('template', '')
                    neighbor_infobox = neighbor_data.get('infobox', {})
                    birth_year = get_birth_year(neighbor_infobox)
                    
                    if not is_valid_politician_template(neighbor_template):
                        log.warning(f"-> Filtering out neighbor '{neighbor_title}' (Invalid template: '{neighbor_template}').")
                        continue
                    
                    if birth_year and birth_year < 1900:
                        log.warning(f"-> Filtering out neighbor '{neighbor_title}' (Birth year: {birth_year} < 1900).")
                        continue
                    
                    if not is_vietnamese_politician(neighbor_infobox):
                        log.warning(f"-> Filtering out neighbor '{neighbor_title}' (Not Vietnamese politician).")
                        continue

                    log.info(f"-> Found new relation: {neighbor_title} (Birth year: {birth_year or 'N/A'})")
                    extracted_data.append(neighbor_data)
                    queue.append((neighbor_title, current_depth + 1))
                else:
                    log.warning(f"-> Relation '{neighbor_title}' found in text, but no matching article in our DB.")
    
    log.info(f"BFS CRAWL COMPLETED")
    log.info(f"Total politicians found (after filtering): {len(extracted_data)}")

    log.info(f"Saving results to: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)
    
    log.info(f"Successfully saved!")

if __name__ == "__main__":
    initial_titles_file = 'data/mess/seed_politicians.txt'
    db_file = 'data/database/politicians_db.json'
    output_file = 'data/processed/infobox/politicians_data.json'
    max_depth = 4

    with open(output_file, 'r', encoding='utf-8') as f:
        output_data = json.load(f)
    log.info(f"Output file length: {len(output_data)} politicians")

    build_network(
        initial_titles_file=initial_titles_file,
        db_file=db_file,
        output_file=output_file,
        max_depth=max_depth
    )