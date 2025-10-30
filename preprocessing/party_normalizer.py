# preprocessing/party_normalizer.py

"""
Script to normalize party field
- Convert to array if contains multiple values separated by commas
- Normalize "khai trừ" variations to "Đã bị khai trừ khỏi Đảng"
"""

import json
import re
from typing import List, Dict, Any, Union
from collections import defaultdict


class PartyNormalizer:
    """Class to normalize party field"""
    
    def __init__(self):
        self.stats = defaultdict(int)
        
        # Party name normalization map
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
        """
        Normalize a single party name
        - Handle "khai trừ" variations
        - Normalize common party names
        """
        if not party or not isinstance(party, str):
            return ""
        
        party = party.strip()
        
        # Check for "khai trừ" keywords
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
        
        # Check normalization map
        if party in self.party_normalization:
            normalized = self.party_normalization[party]
            if normalized != party:
                self.stats['party_name_normalized'] += 1
            return normalized
        
        # Return as is if no normalization needed
        return party
    
    def split_and_normalize_party(self, party_text: str) -> Union[str, List[str]]:
        """
        Split party text into individual parties and normalize each
        Returns:
        - String if only one party
        - List if multiple parties
        - Empty string if no valid party
        """
        if not party_text or not isinstance(party_text, str):
            return ""
        
        # Clean up
        party_text = party_text.strip()
        
        if not party_text:
            return ""
        
        # Split by common delimiters: comma, semicolon, newline
        segments = re.split(r'[,;]\s*|\n', party_text)
        
        party_list = []
        for segment in segments:
            # Clean up whitespace
            segment = ' '.join(segment.split()).strip()
            
            # Skip empty segments
            if not segment or len(segment) < 2:
                continue
            
            # Normalize the party name
            normalized = self.normalize_party_name(segment)
            
            if normalized:
                party_list.append(normalized)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_parties = []
        for party in party_list:
            if party not in seen:
                seen.add(party)
                unique_parties.append(party)
        
        # Return based on count
        if len(unique_parties) == 0:
            return ""
        elif len(unique_parties) == 1:
            return unique_parties[0]
        else:
            self.stats['party_multiple'] += 1
            return unique_parties
    
    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a single politician record
        Convert and normalize party field
        """
        if not record or 'infobox' not in record:
            return record
        
        infobox = record['infobox']
        
        # Process party field
        if 'party' in infobox:
            party_value = infobox['party']
            
            if isinstance(party_value, str):
                # Split and normalize
                normalized_party = self.split_and_normalize_party(party_value)
                
                if normalized_party:
                    infobox['party'] = normalized_party
                    self.stats['party_normalized'] += 1
                else:
                    # Remove empty party field
                    del infobox['party']
                    self.stats['party_removed'] += 1
            elif isinstance(party_value, list):
                # Already a list - normalize each item
                normalized_list = []
                for p in party_value:
                    if isinstance(p, str):
                        normalized = self.normalize_party_name(p)
                        if normalized:
                            normalized_list.append(normalized)
                
                # Remove duplicates
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
        """
        Normalize entire politicians data file
        Normalize party fields
        """
        print(f"{'='*60}")
        print(f"NORMALIZING PARTY FIELDS")
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
        print(f"\nNormalizing party fields...")
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
        print(f"  • Party normalized: {self.stats['party_normalized']}")
        print(f"  • Party with multiple values: {self.stats['party_multiple']}")
        print(f"  • Party already in array format: {self.stats['party_already_array']}")
        print(f"  • Party name normalized: {self.stats['party_name_normalized']}")
        print(f"  • Party expelled (khai trừ): {self.stats['party_expelled']}")
        print(f"  • Party removed (empty): {self.stats['party_removed']}")
        print(f"  • Records without party field: {self.stats['no_party_field']}")
        print(f"{'='*60}\n")


def main():
    """Main function"""
    import sys
    
    # Default files
    input_file = 'data/processed/infobox/politicians_data_battles_normalized.json'
    output_file = 'data/processed/infobox/politicians_data_normalized.json'
    
    # Allow command line arguments
    if len(sys.argv) >= 2:
        input_file = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    
    normalizer = PartyNormalizer()
    normalizer.normalize_file(input_file, output_file)
    
    print(f"✓ Normalized data saved to: {output_file}")
    print(f"✓ Party fields have been normalized")
    print(f"✓ 'Khai trừ' variations converted to 'Đã bị khai trừ khỏi Đảng'")


if __name__ == "__main__":
    main()
