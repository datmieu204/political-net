# preprocessing/awards_normalizer.py

import json
import re

from typing import List, Dict, Any
from collections import defaultdict

from utils.config import settings
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("awards_normalizer", log_file="logs/preprocessing/awards_normalizer.log")

class AwardsNormalizer:
    def __init__(self):
        self.stats = defaultdict(int)
    
    def split_awards(self, awards_text: str) -> List[str]:
        if not awards_text or not isinstance(awards_text, str):
            return []
        
        if isinstance(awards_text, list):
            return awards_text
        
        awards_text = re.sub(r'^\s*\.\s*', '', awards_text).strip()
        
        if not awards_text:
            return []
        
        awards_list = []

        rank_pattern = r'([^,]+?)\s+hạng\s+((?:I{1,3}|IV|V|Nhất|Nhì|Ba|Tư|Năm|Sáu|Bảy|1|2|3|4|5|6|7)(?:\s*,\s*(?:I{1,3}|IV|V|Nhất|Nhì|Ba|Tư|Năm|Sáu|Bảy|1|2|3|4|5|6|7))+)'
        
        processed_text = awards_text
        replacements = []
        
        for match in re.finditer(rank_pattern, awards_text, re.IGNORECASE):
            base_award = match.group(1).strip()
            base_award = re.sub(r',\s*$', '', base_award).strip()
            
            if not base_award or base_award.lower() == 'hạng':
                continue
            
            ranks_str = match.group(2)
            
            ranks = re.split(r'\s*,\s*', ranks_str)
            ranks = [r.strip() for r in ranks if r.strip()]
            
            if len(ranks) > 1:
                expanded_awards = [f"{base_award} hạng {rank}" for rank in ranks]
                replacements.append((match.group(0), ', '.join(expanded_awards)))
        
        for old, new in replacements:
            processed_text = processed_text.replace(old, new, 1)
        
        numbered_pattern = r'([^,(]+)\s*\((\d+)\)'
        numbered_replacements = []
        
        for match in re.finditer(numbered_pattern, processed_text):
            award_name = match.group(1).strip()
            count = int(match.group(2))
            
            repeated_awards = [award_name] * count
            
            numbered_replacements.append((match.group(0), ', '.join(repeated_awards)))
        
        for old, new in numbered_replacements:
            processed_text = processed_text.replace(old, new, 1)
        
        segments = processed_text.split(',')
        
        for segment in segments:
            segment = segment.strip()
            
            if not segment or len(segment) < 3:
                continue
            
            if re.match(r'^(?:I{1,3}|IV|V|Nhất|Nhì|Ba|Tư|Năm|Sáu|Bảy|hạng|1|2|3|4|5|6|7)$', segment, re.IGNORECASE):
                continue
            
            awards_list.append(segment)
        
        cleaned_awards = []
        for award in awards_list:
            award = ' '.join(award.split())
            award = award.strip('.,;:- ')
            
            if len(award) < 3:
                continue
            
            if re.match(r'^[\d\sIVivNhấtNhìBaTưNămmột hai ba bốn năm]+$', award):
                continue
                
            cleaned_awards.append(award)
        
        seen = set()
        unique_awards = []
        for award in cleaned_awards:
            award_normalized = ' '.join(award.split())
            if award_normalized not in seen and award_normalized:
                seen.add(award_normalized)
                unique_awards.append(award_normalized)
        
        return unique_awards
    
    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if not record or 'infobox' not in record:
            return record
        
        infobox = record['infobox']
        
        if 'awards' in infobox:
            awards_value = infobox['awards']
            
            if isinstance(awards_value, str):
                awards_array = self.split_awards(awards_value)
                
                if awards_array:
                    infobox['awards'] = awards_array
                    self.stats['awards_normalized'] += 1
                    self.stats['total_awards'] += len(awards_array)
                else:
                    del infobox['awards']
                    self.stats['awards_removed'] += 1
            elif isinstance(awards_value, list):
                self.stats['awards_already_array'] += 1
        else:
            self.stats['no_awards_field'] += 1
        
        return record
    
    def normalize_file(self, input_file: str, output_file: str):
        log.info(f"\nReading input file...")
        with open(input_file, 'r', encoding='utf-8') as f:
            politicians_data = json.load(f)
        
        total = len(politicians_data)
        log.info(f"Total records: {total}")

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
    normalizer = AwardsNormalizer()
    normalizer.normalize_file(settings.INPUT_AWARDS_NORMALIZED_FILE, settings.OUTPUT_AWARDS_NORMALIZED_FILE)
