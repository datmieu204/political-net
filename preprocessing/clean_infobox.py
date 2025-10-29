import json
import re
from typing import Dict, Any
from collections import defaultdict

from utils.config import settings
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("clean_infobox", log_file="logs/preprocessing/clean_infobox.log")

class InfoboxCleaner:
    def __init__(self):
        self.stats = defaultdict(int)
        self.stats['leaked_fields_parsed'] = 0
        self.stats['promoted_leaked_fields'] = 0
        self.stats['dates_normalized'] = 0
        
        # --- START MODIFICATION ---
        # Thay thế `date_key_suffixes` bằng một pattern regex duy nhất
        # Pattern này khớp với:
        # 1. term_start, term_start1, term_start2, ...
        # 2. term_end, term_end1, term_end2, ...
        # 3. Bất cứ gì kết thúc bằng _date (vd: birth_date, death_date)
        # 4. Bất cứ gì kết thúc bằng date (vd: birthdate, deathdate, date)
        self.date_key_pattern = re.compile(
            r'(term_start\d*|term_end\d*|.*_date|.*date)', 
            re.IGNORECASE
        )
        # --- END MODIFICATION ---

        # Các pattern regex đã được biên dịch trước để chuẩn hóa ngày
        self.date_patterns = [
            (re.compile(r'(?:ngày\s+)?(\d{1,2})\s+tháng\s+(\d{1,2})(?:,\s*|\s+năm\s+)(\d{4})', re.IGNORECASE), 
             lambda m: f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"),
            (re.compile(r'tháng\s+(\d{1,2})(?:,\s*|\s+năm\s+)(\d{4})', re.IGNORECASE), 
             lambda m: f"{int(m.group(2)):04d}-{int(m.group(1)):02d}"),
            (re.compile(r'^(\d{4})-(\d{2})-(\d{2})$'), 
             lambda m: f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
            (re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})'), 
             lambda m: f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"),
            (re.compile(r'^\s*(\d{4})\s*$'), 
             lambda m: m.group(1))
        ]

    def clean_wiki_markup(self, text: str) -> str:
        """
        Làm sạch markup cơ bản của Wiki.
        Hàm này giữ nguyên như ban đầu.
        """
        if not text or not isinstance(text, str):
            return ""
        
        original_text = text
        
        text = re.sub(r'\{\{[^}]+\}\}', '', text)
        text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
        text = re.sub(r'<ref[^>]*/?>', '', text)
        text = re.sub(r'\b\d+(?:x\d+)?px\b\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(?:border|thumb|link|frameless|upright|center|left|right|none)\b\s*\|?\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[\[(?:Tập[_ ]?tin|File|Image|Hình):[^\]]+\]\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'https?://[^\s\]]+', '', text, flags=re.IGNORECASE)
        
        def replace_wikilink(match):
            content = match.group(1)
            if any(prefix in content.lower() for prefix in ['file:', 'image:', 'tập tin:', 'hình:']):
                return ''
            
            if '|' in content:
                return content.split('|')[-1].strip()
            return content.strip()
        
        text = re.sub(r'\[\[([^\]]+)\]\]', replace_wikilink, text)
        text = re.sub(r'<br\s*/?\s*>', ', ', text, flags=re.IGNORECASE)
        text = re.sub(r'\n\s*\*\s*', ', ', text)
        text = re.sub(r'\*\s*', ', ', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r',\s*,+', ',', text)
        text = re.sub(r'\s*,\s*', ', ', text)
        text = text.replace("''", '').replace('||', '').strip()
        text = text.strip(', ').strip()
        
        if text != original_text:
            self.stats['fields_cleaned'] += 1
        
        return text

    def _normalize_date(self, date_string: str) -> str:
        """
        Cố gắng chuẩn hóa chuỗi ngày tháng về dạng ISO (YYYY-MM-DD hoặc YYYY-MM hoặc YYYY).
        Nếu thất bại, trả về chuỗi gốc đã được làm sạch.
        """
        if not date_string:
            return ""
        
        original_string = date_string.strip()
        
        for pattern, formatter in self.date_patterns:
            match = pattern.search(original_string)
            if match:
                try:
                    normalized = formatter(match)
                    if normalized != original_string or pattern.search(original_string):
                         self.stats['dates_normalized'] += 1
                    return normalized
                except Exception:
                    continue
        
        return original_string

    def clean_infobox(self, infobox: Dict[str, Any]) -> Dict[str, Any]:
        """
        Làm sạch đệ quy một infobox, với logic mới để xử lý các trường "rò rỉ"
        VÀ chuẩn hóa ngày tháng.
        """
        if not infobox:
            return {}

        # Bước 1: Làm sạch nông (shallow clean) tất cả các trường
        shallow_cleaned = {}
        for key, value in infobox.items():
            if value is None:
                continue
            
            key_lower = key.lower().strip() # Kiểm tra key thường và đã strip
            
            if isinstance(value, str):
                cleaned_value = self.clean_wiki_markup(value)
                if not cleaned_value:
                    continue
                
                # --- START MODIFICATION ---
                # Kiểm tra xem key có khớp với pattern ngày tháng không
                if self.date_key_pattern.fullmatch(key_lower):
                    normalized_value = self._normalize_date(cleaned_value)
                    shallow_cleaned[key] = normalized_value
                else:
                    shallow_cleaned[key] = cleaned_value
                # --- END MODIFICATION ---
                    
            elif isinstance(value, (int, float, bool)):
                shallow_cleaned[key] = value
            elif isinstance(value, dict):
                nested = self.clean_infobox(value)
                if nested:
                    shallow_cleaned[key] = nested
            elif isinstance(value, list):
                cleaned_list = []
                for item in value:
                    if isinstance(item, str):
                        cleaned_item = self.clean_wiki_markup(item)
                        if not cleaned_item:
                            continue
                        
                        # --- START MODIFICATION ---
                        # Áp dụng logic tương tự cho list, dựa trên key của list
                        if self.date_key_pattern.fullmatch(key_lower):
                            normalized_item = self._normalize_date(cleaned_item)
                            cleaned_list.append(normalized_item)
                        else:
                            cleaned_list.append(cleaned_item)
                        # --- END MODIFICATION ---
                            
                    elif isinstance(item, dict):
                        cleaned_item = self.clean_infobox(item)
                        if cleaned_item:
                            cleaned_list.append(cleaned_item)
                    else:
                        cleaned_list.append(item)
                if cleaned_list:
                    shallow_cleaned[key] = cleaned_list
        
        # Bước 2: Xử lý sau để tìm và "thăng cấp" các trường bị rò rỉ
        final_cleaned = {}
        for key, value in shallow_cleaned.items():
            if not isinstance(value, str) or '=' not in value or '|' not in value:
                final_cleaned[key] = value
                continue

            parts = value.split('|')
            potential_main_value = self.clean_wiki_markup(parts[0])
            
            is_first_part_kv = False
            if '=' in potential_main_value:
                 kv_parts = potential_main_value.split('=', 1)
                 if len(kv_parts) == 2 and kv_parts[0].strip(): 
                       is_first_part_kv = True

            new_fields_to_add = {}
            
            if is_first_part_kv:
                all_parts = parts
            else:
                if potential_main_value:
                    final_cleaned[key] = potential_main_value
                all_parts = parts[1:]
            
            for part in all_parts:
                part = part.strip().rstrip('}')
                if '=' not in part:
                    continue
                    
                kv = part.split('=', 1)
                if len(kv) == 2:
                    new_key = kv[0].strip()
                    new_val_raw = kv[1].strip()
                    
                    new_val_cleaned = self.clean_wiki_markup(new_val_raw)
                    
                    if new_key and new_val_cleaned:
                        # --- START MODIFICATION ---
                        new_key_lower = new_key.lower()
                        # Kiểm tra date cho các trường rò rỉ được thăng cấp
                        if self.date_key_pattern.fullmatch(new_key_lower):
                            normalized_val = self._normalize_date(new_val_cleaned)
                            new_fields_to_add[new_key] = normalized_val
                        else:
                            new_fields_to_add[new_key] = new_val_cleaned
                        # --- END MODIFICATION ---
                        self.stats['promoted_leaked_fields'] += 1

            if new_fields_to_add:
                self.stats['leaked_fields_parsed'] += 1
                final_cleaned.update(new_fields_to_add)
            elif not is_first_part_kv:
                pass
            else:
                final_cleaned[key] = value
                         
        return final_cleaned

    def clean_politician(self, politician_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Làm sạch dữ liệu của một chính trị gia.
        Hàm này giữ nguyên như ban đầu.
        """
        if not politician_data:
            return None
        
        title = politician_data.get('title', '')
        if not title:
            self.stats['skipped_no_title'] += 1
            return None
        
        infobox = politician_data.get('infobox', {})
        if not infobox:
            self.stats['skipped_no_infobox'] += 1
            return None
        
        cleaned_infobox = self.clean_infobox(infobox)

        cleaned = {
            'title': title,
            'id': politician_data.get('id', ''),
            'template': politician_data.get('template', ''),
            'infobox': cleaned_infobox
        }
        
        if not cleaned_infobox:
            self.stats['skipped_empty_infobox'] += 1
            return None

        self.stats['processed'] += 1
        return cleaned

    def clean_file(self, input_file: str, output_file: str):
        """
        Đọc, làm sạch và ghi file.
        Cập nhật để log stat mới.
        """
        log.info(f"\nReading input file...")
        with open(input_file, 'r', encoding='utf-8') as f:
            politicians_data = json.load(f)
        
        total = len(politicians_data)
        log.info(f"Total records: {total}")
        
        log.info(f"\nCleaning records...")
        cleaned_data = []
        
        for i, politician in enumerate(politicians_data, 1):
            if i % 100 == 0:
                log.info(f"Progress: {i}/{total} ({i*100//total}%)")
            
            cleaned = self.clean_politician(politician)
            if cleaned:
                cleaned_data.append(cleaned)
        
        log.info(f"\nWriting output file...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=4)
        
        log.info(f"CLEANING COMPLETED")
        log.info(f"--- Stats ---")
        log.info(f"Total processed: {self.stats['processed']}")
        log.info(f"Skipped (no title): {self.stats['skipped_no_title']}")
        log.info(f"Skipped (no infobox): {self.stats['skipped_no_infobox']}")
        log.info(f"Skipped (empty infobox): {self.stats['skipped_empty_infobox']}")
        log.info(f"Total fields cleaned: {self.stats['fields_cleaned']}")
        log.info(f"Dates normalized: {self.stats['dates_normalized']}")
        log.info(f"Leaked field blocks parsed: {self.stats['leaked_fields_parsed']}")
        log.info(f"Promoted leaked fields: {self.stats['promoted_leaked_fields']}")
        log.info(f"---------------")


if __name__ == "__main__":
    cleaner = InfoboxCleaner()
    cleaner.clean_file(settings.INPUT_CLEAN_INFOBOX_FILE, settings.OUTPUT_CLEAN_INFOBOX_FILE)
    log.info(f"Data saved to: {settings.OUTPUT_CLEAN_INFOBOX_FILE}")