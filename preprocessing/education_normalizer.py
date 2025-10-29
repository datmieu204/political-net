# preprocessing/education_normalizer.py

"""
Script to normalize education and alma_mater fields from string to array
Splits education/alma_mater text into individual entries
"""

import json
import re
from typing import List, Dict, Any
from collections import defaultdict


class EducationNormalizer:
    """Class to normalize education and alma_mater fields"""
    
    def __init__(self):
        self.stats = defaultdict(int)
    
    def split_education(self, education_text: str) -> List[str]:
        """
        Split education text into individual education entries
        Handles cases like:
        - "Thạc sĩ Hành chính công, Cao cấp lý luận chính trị"
        - "Tiến sĩ Luật học; Thạc sĩ Kinh tế"
        - "Cử nhân Kinh tế, Thạc sĩ Quản trị kinh doanh, Tiến sĩ Kinh tế"
        """
        if not education_text or not isinstance(education_text, str):
            return []
        
        # If already a list, return as is
        if isinstance(education_text, list):
            return education_text
        
        # Clean up the text
        education_text = education_text.strip()
        
        if not education_text:
            return []
        
        education_list = []
        
        # Split by common delimiters: comma, semicolon, newline, <br>
        segments = re.split(r'[,;]\s*|<br\s*/?\s*>|\n', education_text)
        
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
            education_list.append(segment)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_education = []
        for edu in education_list:
            # Normalize for comparison
            edu_normalized = ' '.join(edu.split())
            if edu_normalized not in seen and edu_normalized:
                seen.add(edu_normalized)
                unique_education.append(edu_normalized)
        
        return unique_education
    
    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a single politician record
        Convert education and alma_mater fields from string to array
        """
        if not record or 'infobox' not in record:
            return record
        
        infobox = record['infobox']
        
        # Process education field
        if 'education' in infobox:
            education_value = infobox['education']
            
            if isinstance(education_value, str):
                # Split into array
                education_array = self.split_education(education_value)
                
                if education_array:
                    # Only convert to array if there are multiple items
                    if len(education_array) > 1:
                        infobox['education'] = education_array
                        self.stats['education_normalized'] += 1
                        self.stats['total_education_entries'] += len(education_array)
                    else:
                        # Keep as string if only one item
                        infobox['education'] = education_array[0]
                        self.stats['education_kept_as_string'] += 1
                else:
                    # If no valid education found, remove the field
                    del infobox['education']
                    self.stats['education_removed'] += 1
            elif isinstance(education_value, list):
                # Already an array
                self.stats['education_already_array'] += 1
        else:
            self.stats['no_education_field'] += 1
        
        # Process alma_mater field
        if 'alma_mater' in infobox:
            alma_mater_value = infobox['alma_mater']
            
            if isinstance(alma_mater_value, str):
                # Split into array
                alma_mater_array = self.split_education(alma_mater_value)
                
                if alma_mater_array:
                    # Only convert to array if there are multiple items
                    if len(alma_mater_array) > 1:
                        infobox['alma_mater'] = alma_mater_array
                        self.stats['alma_mater_normalized'] += 1
                        self.stats['total_alma_mater_entries'] += len(alma_mater_array)
                    else:
                        # Keep as string if only one item
                        infobox['alma_mater'] = alma_mater_array[0]
                        self.stats['alma_mater_kept_as_string'] += 1
                else:
                    # If no valid alma_mater found, remove the field
                    del infobox['alma_mater']
                    self.stats['alma_mater_removed'] += 1
            elif isinstance(alma_mater_value, list):
                # Already an array
                self.stats['alma_mater_already_array'] += 1
        else:
            self.stats['no_alma_mater_field'] += 1
        
        return record
    
    def normalize_file(self, input_file: str, output_file: str):
        """
        Normalize entire politicians data file
        Convert education and alma_mater fields from string to array
        """
        print(f"{'='*60}")
        print(f"NORMALIZING EDUCATION & ALMA_MATER FIELDS")
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
        print(f"\nNormalizing education and alma_mater fields...")
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
        print(f"\nEducation field:")
        print(f"  • Normalized (string → array): {self.stats['education_normalized']}")
        print(f"  • Kept as string (single entry): {self.stats['education_kept_as_string']}")
        print(f"  • Already in array format: {self.stats['education_already_array']}")
        print(f"  • Removed (empty): {self.stats['education_removed']}")
        print(f"  • Records without education field: {self.stats['no_education_field']}")
        print(f"  • Total education entries extracted: {self.stats['total_education_entries']}")
        if self.stats['education_normalized'] > 0:
            avg_education = self.stats['total_education_entries'] / self.stats['education_normalized']
            print(f"  • Average education entries per politician: {avg_education:.2f}")
        
        print(f"\nAlma Mater field:")
        print(f"  • Normalized (string → array): {self.stats['alma_mater_normalized']}")
        print(f"  • Kept as string (single entry): {self.stats['alma_mater_kept_as_string']}")
        print(f"  • Already in array format: {self.stats['alma_mater_already_array']}")
        print(f"  • Removed (empty): {self.stats['alma_mater_removed']}")
        print(f"  • Records without alma_mater field: {self.stats['no_alma_mater_field']}")
        print(f"  • Total alma_mater entries extracted: {self.stats['total_alma_mater_entries']}")
        if self.stats['alma_mater_normalized'] > 0:
            avg_alma_mater = self.stats['total_alma_mater_entries'] / self.stats['alma_mater_normalized']
            print(f"  • Average alma_mater entries per politician: {avg_alma_mater:.2f}")
        print(f"{'='*60}\n")


def main():
    """Main function"""
    import sys
    
    # Default files
    input_file = 'data/processed/infobox/politicians_data_awards_normalized.json'
    output_file = 'data/processed/infobox/politicians_data_education_normalized.json'
    
    # Allow command line arguments
    if len(sys.argv) >= 2:
        input_file = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    
    normalizer = EducationNormalizer()
    normalizer.normalize_file(input_file, output_file)
    
    print(f"✓ Normalized data saved to: {output_file}")
    print(f"✓ Education and alma_mater fields have been converted from strings to arrays (where applicable)")


if __name__ == "__main__":
    main()
