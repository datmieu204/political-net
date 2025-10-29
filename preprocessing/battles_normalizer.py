# preprocessing/battles_normalizer.py

"""
Script to normalize battles field from string to array
Splits battles text into individual battle entries
"""

import json
import re
from typing import List, Dict, Any
from collections import defaultdict


class BattlesNormalizer:
    """Class to normalize battles field"""
    
    def __init__(self):
        self.stats = defaultdict(int)
    
    def split_battles(self, battles_text: str) -> List[str]:
        """
        Split battles text into individual battle entries
        Handles cases like:
        - "Chiến dịch Hồ Chí Minh, Chiến tranh biên giới Tây Nam"
        - "Chiến dịch Điện Biên Phủ; Chiến dịch Hồ Chí Minh"
        """
        if not battles_text or not isinstance(battles_text, str):
            return []
        
        # If already a list, return as is
        if isinstance(battles_text, list):
            return battles_text
        
        # Clean up the text
        battles_text = battles_text.strip()
        
        if not battles_text:
            return []
        
        battles_list = []
        
        # Split by common delimiters: comma, semicolon, newline, <br>
        segments = re.split(r'[,;]\s*|<br\s*/?\s*>|\n', battles_text)
        
        for segment in segments:
            # Clean up whitespace
            segment = ' '.join(segment.split()).strip()
            
            # Skip empty or very short segments
            if not segment or len(segment) < 3:
                continue
            
            # Skip segments that are just punctuation or numbers
            if re.match(r'^[\d\s\.\-:;,]+$', segment):
                continue
            
            # Add to list
            battles_list.append(segment)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_battles = []
        for battle in battles_list:
            # Normalize for comparison
            battle_normalized = ' '.join(battle.split())
            if battle_normalized not in seen and battle_normalized:
                seen.add(battle_normalized)
                unique_battles.append(battle_normalized)
        
        return unique_battles
    
    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a single politician record
        Convert battles field from string to array
        """
        if not record or 'infobox' not in record:
            return record
        
        infobox = record['infobox']
        
        # Process battles field
        if 'battles' in infobox:
            battles_value = infobox['battles']
            
            if isinstance(battles_value, str):
                # Split into array
                battles_array = self.split_battles(battles_value)
                
                if battles_array:
                    # Only convert to array if there are multiple items
                    if len(battles_array) > 1:
                        infobox['battles'] = battles_array
                        self.stats['battles_normalized'] += 1
                        self.stats['total_battles_entries'] += len(battles_array)
                    else:
                        # Keep as string if only one item
                        infobox['battles'] = battles_array[0]
                        self.stats['battles_kept_as_string'] += 1
                else:
                    # If no valid battles found, remove the field
                    del infobox['battles']
                    self.stats['battles_removed'] += 1
            elif isinstance(battles_value, list):
                # Already an array
                self.stats['battles_already_array'] += 1
        else:
            self.stats['no_battles_field'] += 1
        
        return record
    
    def normalize_file(self, input_file: str, output_file: str):
        """
        Normalize entire politicians data file
        Convert battles fields from string to array
        """
        print(f"{'='*60}")
        print(f"NORMALIZING BATTLES FIELDS")
        print(f"{'='*60}")
        print(f"Input file: {input_file}")
        print(f"Output file: {output_file}")
        
        # Read input file
        print(f"\nReading input file...")
        with open(input_file, 'r', encoding='utf-8') as f:
            politicians_data = json.load(f)
        
        total = len(politicians_data)
        print(f"Total records: {total}")
        
        # Normalize each record
        print(f"\nNormalizing battles fields...")
        normalized_data = []
        
        for i, politician in enumerate(politicians_data, 1):
            if i % 100 == 0:
                print(f"  Progress: {i}/{total} ({i*100//total}%)")
            
            normalized = self.normalize_record(politician)
            normalized_data.append(normalized)
        
        # Write output file
        print(f"\nWriting output file...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(normalized_data, f, ensure_ascii=False, indent=2)
        
        # Print statistics
        print(f"\n{'='*60}")
        print(f"NORMALIZATION COMPLETED")
        print(f"{'='*60}")
        print(f"Statistics:")
        print(f"  • Total records: {total}")
        print(f"\nBattles field:")
        print(f"  • Normalized (string → array): {self.stats['battles_normalized']}")
        print(f"  • Kept as string (single entry): {self.stats['battles_kept_as_string']}")
        print(f"  • Already in array format: {self.stats['battles_already_array']}")
        print(f"  • Removed (empty): {self.stats['battles_removed']}")
        print(f"  • Records without battles field: {self.stats['no_battles_field']}")
        print(f"  • Total battles entries extracted: {self.stats['total_battles_entries']}")
        if self.stats['battles_normalized'] > 0:
            avg_battles = self.stats['total_battles_entries'] / self.stats['battles_normalized']
            print(f"  • Average battles entries per politician: {avg_battles:.2f}")
        print(f"{'='*60}\n")


def main():
    """Main function"""
    import sys
    
    # Default files
    input_file = 'data/processed/infobox/politicians_data_education_normalized.json'
    output_file = 'data/processed/infobox/politicians_data_battles_normalized.json'
    
    # Allow command line arguments
    if len(sys.argv) >= 2:
        input_file = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    
    normalizer = BattlesNormalizer()
    normalizer.normalize_file(input_file, output_file)
    
    print(f"✓ Normalized data saved to: {output_file}")
    print(f"✓ Battles fields have been converted from strings to arrays (where applicable)")


if __name__ == "__main__":
    main()
