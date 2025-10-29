# preprocessing/awards_normalizer.py

"""
Script to normalize awards field from string to array
Splits awards text into individual awards
"""

import json
import re
from typing import List, Dict, Any
from collections import defaultdict


class AwardsNormalizer:
    """Class to normalize awards field"""
    
    def __init__(self):
        self.stats = defaultdict(int)
    
    def split_awards(self, awards_text: str) -> List[str]:
        """
        Split awards text into individual awards
        Simple approach: split by comma, with special handling for "hạng Nhất, Nhì, Ba" patterns
        """
        if not awards_text or not isinstance(awards_text, str):
            return []
        
        # If already a list, return as is
        if isinstance(awards_text, list):
            return awards_text
        
        # Remove leading dots and clean up
        awards_text = re.sub(r'^\s*\.\s*', '', awards_text).strip()
        
        if not awards_text:
            return []
        
        awards_list = []
        
        # Step 1: Handle special pattern "hạng Nhất, Nhì, Ba" (multiple ranks for same award)
        # Example: "Huân chương Lao động hạng Nhất, Nhì, Ba" 
        # Should expand to: "Huân chương Lao động hạng Nhất", "Huân chương Lao động hạng Nhì", "Huân chương Lao động hạng Ba"
        
        # Pattern to match: [award name] hạng [rank1, rank2, rank3]
        rank_pattern = r'([^,]+?)\s+hạng\s+((?:I{1,3}|IV|V|Nhất|Nhì|Ba|Tư|Năm|Sáu|Bảy|1|2|3|4|5|6|7)(?:\s*,\s*(?:I{1,3}|IV|V|Nhất|Nhì|Ba|Tư|Năm|Sáu|Bảy|1|2|3|4|5|6|7))+)'
        
        processed_text = awards_text
        replacements = []
        
        for match in re.finditer(rank_pattern, awards_text, re.IGNORECASE):
            base_award = match.group(1).strip()
            # Remove any trailing comma from base_award
            base_award = re.sub(r',\s*$', '', base_award).strip()
            
            # Skip if base_award ends with another award keyword (false positive)
            if not base_award or base_award.lower() == 'hạng':
                continue
            
            ranks_str = match.group(2)
            
            # Extract individual ranks
            ranks = re.split(r'\s*,\s*', ranks_str)
            ranks = [r.strip() for r in ranks if r.strip()]
            
            if len(ranks) > 1:
                # Multiple ranks - expand to separate awards
                expanded_awards = [f"{base_award} hạng {rank}" for rank in ranks]
                
                # Store replacement
                replacements.append((match.group(0), ', '.join(expanded_awards)))
        
        # Apply replacements
        for old, new in replacements:
            processed_text = processed_text.replace(old, new, 1)
        
        # Step 2: Handle numbered awards with parentheses
        # Example: "Dũng sĩ diệt Mỹ (7)" -> repeat 7 times
        numbered_pattern = r'([^,(]+)\s*\((\d+)\)'
        numbered_replacements = []
        
        for match in re.finditer(numbered_pattern, processed_text):
            award_name = match.group(1).strip()
            count = int(match.group(2))
            
            # Create count copies of this award
            repeated_awards = [award_name] * count
            
            # Store replacement
            numbered_replacements.append((match.group(0), ', '.join(repeated_awards)))
        
        # Apply numbered replacements
        for old, new in numbered_replacements:
            processed_text = processed_text.replace(old, new, 1)
        
        # Step 3: Simple split by comma
        segments = processed_text.split(',')
        
        for segment in segments:
            segment = segment.strip()
            
            # Skip empty or very short segments
            if not segment or len(segment) < 3:
                continue
            
            # Skip if it's just a rank without award name
            if re.match(r'^(?:I{1,3}|IV|V|Nhất|Nhì|Ba|Tư|Năm|Sáu|Bảy|hạng|1|2|3|4|5|6|7)$', segment, re.IGNORECASE):
                continue
            
            awards_list.append(segment)
        
        # Clean up the awards list
        cleaned_awards = []
        for award in awards_list:
            # Remove extra whitespace
            award = ' '.join(award.split())
            
            # Remove leading/trailing punctuation
            award = award.strip('.,;:- ')
            
            # Skip very short or empty awards
            if len(award) < 3:
                continue
            
            # Skip if it's just a number or rank
            if re.match(r'^[\d\sIVivNhấtNhìBaTưNămmột hai ba bốn năm]+$', award):
                continue
                
            cleaned_awards.append(award)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_awards = []
        for award in cleaned_awards:
            # Normalize for comparison (remove extra spaces)
            award_normalized = ' '.join(award.split())
            if award_normalized not in seen and award_normalized:
                seen.add(award_normalized)
                unique_awards.append(award_normalized)
        
        return unique_awards
    
    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a single politician record
        Convert awards field from string to array
        """
        if not record or 'infobox' not in record:
            return record
        
        infobox = record['infobox']
        
        # Check if awards field exists and is a string
        if 'awards' in infobox:
            awards_value = infobox['awards']
            
            if isinstance(awards_value, str):
                # Split into array
                awards_array = self.split_awards(awards_value)
                
                if awards_array:
                    infobox['awards'] = awards_array
                    self.stats['awards_normalized'] += 1
                    self.stats['total_awards'] += len(awards_array)
                else:
                    # If no valid awards found, remove the field
                    del infobox['awards']
                    self.stats['awards_removed'] += 1
            elif isinstance(awards_value, list):
                # Already an array
                self.stats['awards_already_array'] += 1
        else:
            self.stats['no_awards_field'] += 1
        
        return record
    
    def normalize_file(self, input_file: str, output_file: str):
        """
        Normalize entire politicians data file
        Convert awards fields from string to array
        """
        print(f"{'='*60}")
        print(f"NORMALIZING AWARDS FIELDS")
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
        print(f"\nNormalizing awards fields...")
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
        print(f"  • Awards normalized (string → array): {self.stats['awards_normalized']}")
        print(f"  • Awards already in array format: {self.stats['awards_already_array']}")
        print(f"  • Awards removed (empty): {self.stats['awards_removed']}")
        print(f"  • Records without awards field: {self.stats['no_awards_field']}")
        print(f"  • Total awards extracted: {self.stats['total_awards']}")
        if self.stats['awards_normalized'] > 0:
            avg_awards = self.stats['total_awards'] / self.stats['awards_normalized']
            print(f"  • Average awards per politician: {avg_awards:.2f}")
        print(f"{'='*60}\n")


def main():
    """Main function"""
    import sys
    
    # Default files
    input_file = 'data/processed/infobox/politicians_data_provinces_normalized.json'
    output_file = 'data/processed/infobox/politicians_data_awards_normalized.json'
    
    # Allow command line arguments
    if len(sys.argv) >= 2:
        input_file = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    
    normalizer = AwardsNormalizer()
    normalizer.normalize_file(input_file, output_file)
    
    print(f"✓ Normalized data saved to: {output_file}")
    print(f"✓ Awards have been converted from strings to arrays")


if __name__ == "__main__":
    main()
