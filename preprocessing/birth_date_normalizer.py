# ./preprocessing/birth_date_normalizer.py

import json
import re
from typing import Dict, Optional, Tuple
from datetime import datetime
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("birth_date_normalizer", log_file="logs/preprocessing/birth_date_normalizer.log")

class BirthDateNormalizer:
    """Class to normalize birth_date field from politicians_data.json"""
    
    def __init__(self):
        self.stats = {
            'total_processed': 0,
            'birth_date_found': 0,
            'birth_date_normalized': 0,
            'birth_date_failed': 0,
            'death_date_found': 0,
            'death_date_normalized': 0,
            'death_date_failed': 0,
            'patterns_used': {}
        }
    
    def extract_date_from_template(self, text: str) -> Optional[Tuple[int, int, int]]:
        """
        Extract year, month, day from Vietnamese date templates
        Works for both birth_date and death_date
        Returns (year, month, day) or None
        """
        if not text or not isinstance(text, str):
            return None
        
        # Pattern 1: {{ngày sinh và tuổi|YYYY|MM|DD}} or {{ngày chết và tuổi|YYYY|MM|DD}} or {{ngày mất và tuổi|YYYY|MM|DD}}
        pattern1 = r'\{\{ngày\s+(?:sinh|chết|mất)\s+và\s+tuổi\|(\d{4})\|(\d{1,2})\|(\d{1,2})'
        match = re.search(pattern1, text, re.IGNORECASE)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            self.stats['patterns_used']['ngày sinh/chết/mất và tuổi'] = self.stats['patterns_used'].get('ngày sinh/chết/mất và tuổi', 0) + 1
            return (year, month, day)
        
        # Pattern 2: {{birth date and age|df=yes|YYYY|MM|DD}} or {{death date and age|df=yes|YYYY|MM|DD|...}}
        # Bỏ qua df=yes và các tham số phía sau
        pattern2 = r'\{\{(?:birth|death)\s+date\s+and\s+age\|(?:df=yes\|)?(\d{4})\|(\d{1,2})\|(\d{1,2})'
        match = re.search(pattern2, text, re.IGNORECASE)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            self.stats['patterns_used']['birth/death date and age'] = self.stats['patterns_used'].get('birth/death date and age', 0) + 1
            return (year, month, day)
        
        # Pattern 3: {{birth date|df=yes|YYYY|MM|DD}} or {{death date|df=yes|YYYY|MM|DD}}
        pattern3 = r'\{\{(?:birth|death)\s+date\|(?:df=yes\|)?(\d{4})\|(\d{1,2})\|(\d{1,2})'
        match = re.search(pattern3, text, re.IGNORECASE)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            self.stats['patterns_used']['birth/death date'] = self.stats['patterns_used'].get('birth/death date', 0) + 1
            return (year, month, day)
        
        # Pattern 4: {{ngày sinh|YYYY|MM|DD}} or {{ngày chết|YYYY|MM|DD}} or {{ngày mất|YYYY|MM|DD}}
        pattern4 = r'\{\{ngày\s+(?:sinh|chết|mất)\|(\d{4})\|(\d{1,2})\|(\d{1,2})'
        match = re.search(pattern4, text, re.IGNORECASE)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            self.stats['patterns_used']['ngày sinh/chết/mất'] = self.stats['patterns_used'].get('ngày sinh/chết/mất', 0) + 1
            return (year, month, day)
        
        # Pattern 5: DD/MM/YYYY or DD-MM-YYYY
        pattern5 = r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b'
        match = re.search(pattern5, text)
        if match:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            self.stats['patterns_used']['DD/MM/YYYY'] = self.stats['patterns_used'].get('DD/MM/YYYY', 0) + 1
            return (year, month, day)
        
        # Pattern 6: YYYY-MM-DD (ISO format)
        pattern6 = r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b'
        match = re.search(pattern6, text)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            self.stats['patterns_used']['YYYY-MM-DD'] = self.stats['patterns_used'].get('YYYY-MM-DD', 0) + 1
            return (year, month, day)
        
        # Pattern 7: Just year {{YYYY}} or plain YYYY
        pattern7 = r'\{\{(\d{4})\}\}|\b(\d{4})\b'
        match = re.search(pattern7, text)
        if match:
            year = int(match.group(1) or match.group(2))
            # Only accept years in reasonable range
            if 1900 <= year <= datetime.now().year:
                self.stats['patterns_used']['year only'] = self.stats['patterns_used'].get('year only', 0) + 1
                return (year, 1, 1)  # Default to January 1st
        
        return None
    
    def format_date(self, year: int, month: int, day: int) -> Optional[str]:
        """
        Format date to YYYY-MM-DD
        Validate date before formatting
        """
        try:
            # Validate date
            date_obj = datetime(year, month, day)
            # Format to YYYY-MM-DD
            return date_obj.strftime('%Y-%m-%d')
        except ValueError as e:
            log.error(f"Invalid date: {year}-{month}-{day}, error: {e}")
            return None
    
    def normalize_birth_date(self, raw_text: str) -> Optional[str]:
        """
        Normalize birth_date from raw text to YYYY-MM-DD format
        """
        date_tuple = self.extract_date_from_template(raw_text)
        if date_tuple:
            year, month, day = date_tuple
            formatted = self.format_date(year, month, day)
            if formatted:
                self.stats['birth_date_normalized'] += 1
                return formatted
            else:
                self.stats['birth_date_failed'] += 1
        return None
    
    def normalize_death_date(self, raw_text: str) -> Optional[str]:
        """
        Normalize death_date from raw text to YYYY-MM-DD format
        """
        date_tuple = self.extract_date_from_template(raw_text)
        if date_tuple:
            year, month, day = date_tuple
            formatted = self.format_date(year, month, day)
            if formatted:
                self.stats['death_date_normalized'] += 1
                return formatted
            else:
                self.stats['death_date_failed'] += 1
        return None
    
    def process_data(self, raw_data_path: str, normalized_data_path: str, output_path: str):
        """
        Process birth_date and death_date from raw data and update normalized data
        """
        log.info("Starting birth_date and death_date normalization...")
        
        # Load raw data
        log.info(f"Loading raw data from: {raw_data_path}")
        with open(raw_data_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        # Load normalized data
        log.info(f"Loading normalized data from: {normalized_data_path}")
        with open(normalized_data_path, 'r', encoding='utf-8') as f:
            normalized_data = json.load(f)
        
        # Create mapping: (title, id) -> dates from raw data
        birth_date_map = {}
        death_date_map = {}
        
        for record in raw_data:
            title = record.get('title', '')
            record_id = str(record.get('id', ''))
            infobox = record.get('infobox', {})
            key = (title, record_id)
            
            # Process birth_date
            birth_date_raw = infobox.get('birth_date', infobox.get('ngày_sinh', ''))
            if birth_date_raw and isinstance(birth_date_raw, str):
                self.stats['birth_date_found'] += 1
                normalized_date = self.normalize_birth_date(birth_date_raw)
                if normalized_date:
                    birth_date_map[key] = normalized_date
                    log.debug(f"Normalized birth_date for {title} (id={record_id}): {birth_date_raw} -> {normalized_date}")
            
            # Process death_date
            death_date_raw = infobox.get('death_date', infobox.get('ngày_chết', infobox.get('ngày_mất', '')))
            if death_date_raw and isinstance(death_date_raw, str):
                self.stats['death_date_found'] += 1
                normalized_date = self.normalize_death_date(death_date_raw)
                if normalized_date:
                    death_date_map[key] = normalized_date
                    log.debug(f"Normalized death_date for {title} (id={record_id}): {death_date_raw} -> {normalized_date}")
        
        # Update normalized data
        log.info("Updating normalized data with birth_date and death_date...")
        updated_birth_count = 0
        updated_death_count = 0
        
        for record in normalized_data:
            self.stats['total_processed'] += 1
            title = record.get('title', '')
            record_id = str(record.get('id', ''))
            key = (title, record_id)
            
            # Ensure infobox exists
            if 'infobox' not in record:
                record['infobox'] = {}
            
            # Update birth_date
            if key in birth_date_map:
                record['infobox']['birth_date'] = birth_date_map[key]
                updated_birth_count += 1
                log.debug(f"Updated birth_date for {title} (id={record_id})")
            
            # Update death_date
            if key in death_date_map:
                record['infobox']['death_date'] = death_date_map[key]
                updated_death_count += 1
                log.debug(f"Updated death_date for {title} (id={record_id})")
        
        # Save updated data
        log.info(f"Saving updated data to: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(normalized_data, f, ensure_ascii=False, indent=2)
        
        # Print statistics
        log.info("=" * 60)
        log.info("Birth Date and Death Date Normalization Statistics:")
        log.info(f"Total records processed: {self.stats['total_processed']}")
        log.info(f"\nBirth Date:")
        log.info(f"  Found in raw data: {self.stats['birth_date_found']}")
        log.info(f"  Successfully normalized: {self.stats['birth_date_normalized']}")
        log.info(f"  Failed to normalize: {self.stats['birth_date_failed']}")
        log.info(f"  Records updated: {updated_birth_count}")
        log.info(f"\nDeath Date:")
        log.info(f"  Found in raw data: {self.stats['death_date_found']}")
        log.info(f"  Successfully normalized: {self.stats['death_date_normalized']}")
        log.info(f"  Failed to normalize: {self.stats['death_date_failed']}")
        log.info(f"  Records updated: {updated_death_count}")
        log.info(f"\nPatterns used:")
        for pattern, count in self.stats['patterns_used'].items():
            log.info(f"  {pattern}: {count}")
        log.info("=" * 60)


def main():
    """Main function"""
    normalizer = BirthDateNormalizer()
    
    raw_data_path = "data/processed/infobox/politicians_data.json"
    normalized_data_path = "data/processed/infobox/politicians_data_normalized.json"
    output_path = "data/processed/infobox/politicians_data_normalized.json"
    
    normalizer.process_data(raw_data_path, normalized_data_path, output_path)


if __name__ == "__main__":
    main()
