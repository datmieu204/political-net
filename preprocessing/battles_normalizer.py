# preprocessing/battles_normalizer.py

import json
import re

from typing import List, Dict, Any
from collections import defaultdict

from utils.config import settings
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("battles_normalizer", log_file="logs/preprocessing/battles_normalizer.log")

class BattlesNormalizer:
    def __init__(self):
        self.stats = defaultdict(int)
    
    def split_battles(self, battles_text: str) -> List[str]:
        if not battles_text or not isinstance(battles_text, str):
            return []
        
        if isinstance(battles_text, list):
            return battles_text
        
        battles_text = battles_text.strip()
        
        if not battles_text:
            return []
        
        battles_list = []
        
        segments = re.split(r'[,;]\s*|<br\s*/?\s*>|\n', battles_text)
        
        for segment in segments:
            segment = ' '.join(segment.split()).strip()
            
            if not segment or len(segment) < 3:
                continue
            
            if re.match(r'^[\d\s\.\-:;,]+$', segment):
                continue
            
            battles_list.append(segment)
        
        seen = set()
        unique_battles = []
        for battle in battles_list:
            battle_normalized = ' '.join(battle.split())
            if battle_normalized not in seen and battle_normalized:
                seen.add(battle_normalized)
                unique_battles.append(battle_normalized)
        
        return unique_battles
    
    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if not record or 'infobox' not in record:
            return record
        
        infobox = record['infobox']
        
        if 'battles' in infobox:
            battles_value = infobox['battles']
            
            if isinstance(battles_value, str):
                battles_array = self.split_battles(battles_value)
                
                if battles_array:
                    if len(battles_array) > 1:
                        infobox['battles'] = battles_array
                        self.stats['battles_normalized'] += 1
                        self.stats['total_battles_entries'] += len(battles_array)
                    else:
                        infobox['battles'] = battles_array[0]
                        self.stats['battles_kept_as_string'] += 1
                else:
                    del infobox['battles']
                    self.stats['battles_removed'] += 1
            elif isinstance(battles_value, list):
                self.stats['battles_already_array'] += 1
        else:
            self.stats['no_battles_field'] += 1
        
        return record
    
    def normalize_file(self, input_file: str, output_file: str):
        log.info(f"\nReading input file...")
        with open(input_file, 'r', encoding='utf-8') as f:
            politicians_data = json.load(f)
        
        total = len(politicians_data)
        log.info(f"Total records: {total}")
        
        log.info(f"\nNormalizing battles fields...")
        normalized_data = []
        
        for i, politician in enumerate(politicians_data, 1):
            if i % 100 == 0:
                log.info(f"Progress: {i}/{total} ({i*100//total}%)")
            
            normalized = self.normalize_record(politician)
            normalized_data.append(normalized)
        
        log.info(f"\nWriting output file...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(normalized_data, f, ensure_ascii=False, indent=2)
        
if __name__ == "__main__":
    normalizer = BattlesNormalizer()
    normalizer.normalize_file(settings.INPUT_BATTLES_NORMALIZED_FILE, settings.OUTPUT_BATTLES_NORMALIZED_FILE)
