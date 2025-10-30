# preprocessing/party_normalizer.py


import json
import re

from typing import List, Dict, Any, Union
from collections import defaultdict

from utils.config import settings
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("party_normalizer", log_file="logs/preprocessing/party_normalizer.log")

class PartyNormalizer:    
    def __init__(self):
        self.stats = defaultdict(int)
        
        self.party_normalization = {
            'Đảng Cộng sản Việt Nam': 'Đảng Cộng sản Việt Nam',
            'Đảng Cộng Sản Việt Nam': 'Đảng Cộng sản Việt Nam',
            'Dang Cong san Viet Nam': 'Đảng Cộng sản Việt Nam',
            'ĐCSVN': 'Đảng Cộng sản Việt Nam',
            'Đảng Lao động Việt Nam': 'Đảng Lao động Việt Nam',
            'Không': 'Không đảng phái',
            'không': 'Không đảng phái',
            'Không có': 'Không đảng phái',
        }
    
    def normalize_party_name(self, party: str) -> str:
        if not party or not isinstance(party, str):
            return ""
        
        party = party.strip()
        
        khai_tru_keywords = [
            'khai trừ', 'khai trư', 'khai tru',
            'bị khai trừ', 'bi khai tru',
            'đã khai trừ', 'da khai tru',
            'khai trừ khỏi đảng', 'khai tru khoi dang'
        ]
        
        party_lower = party.lower()
        for keyword in khai_tru_keywords:
            if keyword in party_lower:
                self.stats['party_expelled'] += 1
                return "Đã bị khai trừ khỏi Đảng"
        
        if party in self.party_normalization:
            normalized = self.party_normalization[party]
            if normalized != party:
                self.stats['party_name_normalized'] += 1
            return normalized
        
        return party
    
    def split_and_normalize_party(self, party_text: str) -> Union[str, List[str]]:
        if not party_text or not isinstance(party_text, str):
            return ""
        
        party_text = party_text.strip()
        
        if not party_text:
            return ""
        
        segments = re.split(r'[,;]\s*|\n', party_text)
        
        party_list = []
        for segment in segments:
            segment = ' '.join(segment.split()).strip()
            
            if not segment or len(segment) < 2:
                continue
            
            normalized = self.normalize_party_name(segment)
            
            if normalized:
                party_list.append(normalized)
        
        seen = set()
        unique_parties = []
        for party in party_list:
            if party not in seen:
                seen.add(party)
                unique_parties.append(party)
        
        if len(unique_parties) == 0:
            return ""
        elif len(unique_parties) == 1:
            return unique_parties[0]
        else:
            self.stats['party_multiple'] += 1
            return unique_parties
    
    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if not record or 'infobox' not in record:
            return record
        
        infobox = record['infobox']
        
        if 'party' in infobox:
            party_value = infobox['party']
            
            if isinstance(party_value, str):
                normalized_party = self.split_and_normalize_party(party_value)
                
                if normalized_party:
                    infobox['party'] = normalized_party
                    self.stats['party_normalized'] += 1
                else:
                    del infobox['party']
                    self.stats['party_removed'] += 1
            elif isinstance(party_value, list):
                normalized_list = []
                for p in party_value:
                    if isinstance(p, str):
                        normalized = self.normalize_party_name(p)
                        if normalized:
                            normalized_list.append(normalized)
                
                seen = set()
                unique = []
                for p in normalized_list:
                    if p not in seen:
                        seen.add(p)
                        unique.append(p)
                
                if unique:
                    if len(unique) == 1:
                        infobox['party'] = unique[0]
                    else:
                        infobox['party'] = unique
                    self.stats['party_already_array'] += 1
                else:
                    del infobox['party']
                    self.stats['party_removed'] += 1
        else:
            self.stats['no_party_field'] += 1
        
        return record
    
    def normalize_file(self, input_file: str, output_file: str):
        log.info(f"\nReading input file...")
        with open(input_file, 'r', encoding='utf-8') as f:
            politicians_data = json.load(f)
        
        total = len(politicians_data)
        
        log.info(f"\nNormalizing party fields...")
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
    normalizer = PartyNormalizer()
    normalizer.normalize_file(settings.INPUT_FINAL_POLITICIAN_FILE, settings.OUTPUT_FINAL_POLITICIAN_FILE)
