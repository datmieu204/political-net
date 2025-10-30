# preprocessing/education_normalizer.py

import json
import re

from typing import List, Dict, Any
from collections import defaultdict

from utils.config import settings
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("education_normalizer", log_file="logs/preprocessing/education_normalizer.log")

class EducationNormalizer:    
    def __init__(self):
        self.stats = defaultdict(int)
    
    def split_education(self, education_text: str) -> List[str]:
        if not education_text or not isinstance(education_text, str):
            return []
        
        if isinstance(education_text, list):
            return education_text
        
        education_text = education_text.strip()
        
        if not education_text:
            return []
        
        education_list = []
        
        segments = re.split(r'[,;]\s*|<br\s*/?\s*>|\n', education_text)
        
        for segment in segments:
            segment = ' '.join(segment.split()).strip()
            
            if not segment or len(segment) < 3:
                continue
            
            if re.match(r'^[\d\s\.\-:;,]+$', segment):
                continue
            
            education_list.append(segment)
        
        seen = set()
        unique_education = []
        for edu in education_list:
            edu_normalized = ' '.join(edu.split())
            if edu_normalized not in seen and edu_normalized:
                seen.add(edu_normalized)
                unique_education.append(edu_normalized)
        
        return unique_education
    
    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if not record or 'infobox' not in record:
            return record
        
        infobox = record['infobox']
        
        if 'education' in infobox:
            education_value = infobox['education']
            
            if isinstance(education_value, str):
                education_array = self.split_education(education_value)
                
                if education_array:
                    if len(education_array) > 1:
                        infobox['education'] = education_array
                        self.stats['education_normalized'] += 1
                        self.stats['total_education_entries'] += len(education_array)
                    else:
                        infobox['education'] = education_array[0]
                        self.stats['education_kept_as_string'] += 1
                else:
                    del infobox['education']
                    self.stats['education_removed'] += 1
            elif isinstance(education_value, list):
                self.stats['education_already_array'] += 1
        else:
            self.stats['no_education_field'] += 1
        
        if 'alma_mater' in infobox:
            alma_mater_value = infobox['alma_mater']
            
            if isinstance(alma_mater_value, str):
                alma_mater_array = self.split_education(alma_mater_value)
                
                if alma_mater_array:
                    if len(alma_mater_array) > 1:
                        infobox['alma_mater'] = alma_mater_array
                        self.stats['alma_mater_normalized'] += 1
                        self.stats['total_alma_mater_entries'] += len(alma_mater_array)
                    else:
                        infobox['alma_mater'] = alma_mater_array[0]
                        self.stats['alma_mater_kept_as_string'] += 1
                else:
                    del infobox['alma_mater']
                    self.stats['alma_mater_removed'] += 1
            elif isinstance(alma_mater_value, list):
                self.stats['alma_mater_already_array'] += 1
        else:
            self.stats['no_alma_mater_field'] += 1
        
        return record
    
    def normalize_file(self, input_file: str, output_file: str):
        # Read input file
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
    normalizer = EducationNormalizer()
    normalizer.normalize_file(settings.INPUT_EDUCATION_NORMALIZED_FILE, settings.OUTPUT_EDUCATION_NORMALIZED_FILE)
