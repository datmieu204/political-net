# -*- coding: utf-8 -*-

"""
Thuật toán crawl đệ quy dữ liệu chính trị gia theo quan hệ successor/predecessor
"""

import xml.sax
import wikitextparser as wtp
import json
import re

from typing import Dict, Tuple, Set

from .alias import COMPREHENSIVE_MAPPING
from utils.config import settings
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("crawl_recursive", log_file="logs/crawl/crawl_recursive.log")

class RecursiveWikiContentHandler(xml.sax.ContentHandler):
    """
    Handler processing Wikipedia XML dump for recursive politician data extraction
    """
    
    def __init__(self, initial_titles):
        super().__init__()
        self.titles_to_find = set(initial_titles)
        self.found_titles = set()
        self.extracted_relations = set()
        self.extracted_data = []
        
        self._current_tag = ""
        self._in_page = False
        self._in_revision = False
        self._title = ""
        self._text_chunks = []
        self._page_id = ""
        self.pages_processed = 0
        
        self.scan_round = 1

    def startElement(self, tag, attributes):
        self._current_tag = tag
        if tag == "page":
            self._in_page = True
            self._title = ""
            self._text_chunks = []
            self._page_id = ""
        elif tag == "revision":
            self._in_revision = True

    def characters(self, content):
        if not self._in_revision and self._current_tag == "id" and self._in_page:
            self._page_id += content.strip()
        elif self._in_page:
            if self._current_tag == "title":
                self._title += content
            elif self._current_tag == "text":
                self._text_chunks.append(content)

    def endElement(self, tag):
        if tag == "revision":
            self._in_revision = False

        elif tag == "page":
            self.pages_processed += 1
            if self.pages_processed % 10000 == 0:
                log.info(f"[Round {self.scan_round}] Processed {self.pages_processed} pages...")

            if self._title in self.titles_to_find and self._title not in self.found_titles:
                log.info(f"\n{'='*60}")
                log.info(f"[Round {self.scan_round}] Found: {self._title}")
                
                full_text = "".join(self._text_chunks)
                
                infobox_raw, template_name = self.extract_infobox(full_text)
                
                infobox_normalized = self.normalize_infobox(infobox_raw)
                
                data_entry = {
                    "title": self._title,
                    "id": self._page_id,
                    "template_used": template_name,
                    "infobox": infobox_raw,
                    "infobox_normalized": infobox_normalized
                }
                
                self.extracted_data.append(data_entry)
                self.found_titles.add(self._title)
                
                log.info(f"   Template: {template_name}")
                log.info(f"   Raw fields: {len(infobox_raw)}")
                log.info(f"   Normalized fields: {len(infobox_normalized)}")
                
                new_relations = self.extract_relations(infobox_normalized)
                
                if new_relations:
                    log.info(f"   Detected {len(new_relations)} new relations:")
                    for rel in new_relations:
                        log.info(f"      → {rel}")
                    
                    self.titles_to_find.update(new_relations)
                
                log.info(f"{'='*60}")

            self._in_page = False
            self._title = ""
            self._text_chunks = []
            self._page_id = ""

        self._current_tag = ""

    def extract_infobox(self, text: str) -> Tuple[Dict, str]:
        """
        Trích xuất infobox từ wikitext
        
        Returns:
            (infobox_data dict, template_name string)
        """
        try:
            parsed = wtp.parse(text)
            infobox_data = {}
            
            priority_templates = [
                "viên chức",
                "Viên chức",
                "thông tin viên chức",
                "Thông tin viên chức",
                "infobox",
                "infobox viên chức",
                "infobox nhân vật",
                "infobox officeholder",
                "infobox officeholder 1",
                "infobox officeholder1",
                "thông tin nhân vật",
                "thông tin chính khách",
                "thông tin chức vụ",
            ]
            
            infobox_template = None
            template_name = None
            
            for priority_name in priority_templates:
                for tpl in parsed.templates:
                    tpl_name = tpl.name.strip().lower()
                    if tpl_name == priority_name:
                        infobox_template = tpl
                        template_name = tpl.name.strip()
                        break
                if infobox_template:
                    break
            
            if not infobox_template:
                for tpl in parsed.templates:
                    name_lower = tpl.name.strip().lower()
                    
                    if "infobox" in name_lower or "thông tin" in name_lower:
                        exclude_keywords = ["succession", "section", "collapsed", "/", "thứ tự"]
                        if not any(ex in name_lower for ex in exclude_keywords):
                            infobox_template = tpl
                            template_name = tpl.name.strip()
                            break
            
            if infobox_template:
                for arg in infobox_template.arguments:
                    key = arg.name.strip()
                    value = arg.value.strip()
                    if key and value:
                        infobox_data[key] = value
            else:
                template_name = "NOT_FOUND"
            
            return infobox_data, template_name
            
        except Exception as e:
            log.error(f"Error processing wikitext: {e}")
            return {}, "ERROR"

    def normalize_key(self, key: str) -> str:
        """
        Normalize a single infobox key to English using the comprehensive mapping.
        """
        match = re.match(r'^(.+?)[\s_]*(\d+)$', key)
        if match:
            base_key = match.group(1).strip()
            number = match.group(2)
        else:
            base_key = key.strip()
            number = ""
        
        base_key_lower = base_key.lower()
        
        if base_key_lower in COMPREHENSIVE_MAPPING:
            normalized_base = COMPREHENSIVE_MAPPING[base_key_lower]
        else:
            normalized_base = base_key_lower.replace(' ', '_').replace('-', '_')
        
        if number:
            return f"{normalized_base}{number}"
        else:
            return normalized_base

    def normalize_infobox(self, infobox: Dict) -> Dict:
        """
        Normalize all keys in the infobox to English.
        """
        normalized = {}
        
        for key, value in infobox.items():
            normalized_key = self.normalize_key(key)
            normalized[normalized_key] = value
        
        return normalized

    def extract_relations(self, infobox_normalized: Dict) -> Set[str]:
        """
        Extract successor/predecessor relations from the normalized infobox
        """
        new_names = set()
        
        relation_fields = [
            'successor', 'predecessor',
            'successor2', 'predecessor2',
            'successor3', 'predecessor3',
            'successor4', 'predecessor4',
            'successor5', 'predecessor5',
            'successor6', 'predecessor6',
            'successor7', 'predecessor7',
            'successor8', 'predecessor8',
            'successor9', 'predecessor9',
        ]
        
        for field in relation_fields:
            if field in infobox_normalized:
                value = infobox_normalized[field]
                # Extract names from wikilink [[Name]] or [[Name|Display]]
                names = self.extract_names_from_wikilink(value)
                new_names.update(names)
        
        # Only return names that haven't been processed yet
        return new_names - self.found_titles - self.extracted_relations

    def extract_names_from_wikilink(self, text: str) -> Set[str]:
        """
        Extract names from wikilink format in the text
        """
        names = set()
        
        # Pattern to find wikilink: [[Name]] or [[Name|Display]]
        # Exclude links to files, categories, templates
        pattern = r'\[\[([^\]|:]+?)(?:\|[^\]]+?)?\]\]'
        matches = re.findall(pattern, text)
        
        for match in matches:
            name = match.strip()
            
            # Exclude special cases
            exclude_keywords = [
                'tập tin:', 'file:', 'hình:', 'image:',
                'thể loại:', 'category:',
                'wikipedia:', 'wp:',
                'template:', 'mẫu:',
                'đầu tiên', 'first', 'none', 'vacant',
                'không có', 'chưa có', 'mới thành lập',
                'position established', 'office established'
            ]
            
            name_lower = name.lower()
            if name and not any(ex in name_lower for ex in exclude_keywords):
                if name_lower not in ["''đầu tiên''", "''cuối cùng''"]:
                    names.add(name)
        
        return names


def crawl_recursive_politicians(initial_titles_file: str, xml_file: str, output_file: str, max_rounds: int = 5):
    """
    Algorithm to recursively crawl politician data based on successor/predecessor relations.
    """
    
    log.info(f"{'='*60}")
    log.info(f"RECURSIVE POLITICIAN CRAWLING ALGORITHM")
    log.info(f"{'='*60}")
    
    with open(initial_titles_file, 'r', encoding='utf-8') as f:
        initial_titles = set(line.strip() for line in f if line.strip())
    
    log.info(f"Initial list: {len(initial_titles)} politicians")
    log.info(f"XML file: {xml_file}")
    log.info(f"Maximum rounds: {max_rounds}")
    log.info(f"{'='*60}\n")
    
    handler = RecursiveWikiContentHandler(initial_titles)
    
    for round_num in range(1, max_rounds + 1):
        handler.scan_round = round_num
        handler.pages_processed = 0
        
        log.info(f"\n{'='*60}")
        log.info(f"SCAN ROUND {round_num}/{max_rounds}")
        log.info(f"{'='*60}")
        log.info(f"To find: {len(handler.titles_to_find)} names")
        log.info(f"Found: {len(handler.found_titles)} names")
        log.info(f"Remaining: {len(handler.titles_to_find - handler.found_titles)} names")
        log.info(f"{'='*60}\n")
        
        remaining = handler.titles_to_find - handler.found_titles
        if not remaining:
            log.info(f"All names found. Stopping scan.")
            break
        
        log.info(f"Names to find in this round:")
        for name in sorted(remaining)[:20]: 
            log.info(f"   • {name}")
        if len(remaining) > 20:
            log.info(f"   ... and {len(remaining) - 20} more")
        log.info("")
        
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_namespaces, 0)
        parser.setContentHandler(handler)
        
        try:
            parser.parse(xml_file)
        except Exception as e:
            log.error(f"Error parsing file in round {round_num}: {e}")
            break
        
        log.info(f"\n{'='*60}")
        log.info(f"ROUND {round_num} RESULTS")
        log.info(f"{'='*60}")
        log.info(f"Found in this round: {len(handler.found_titles) - len(handler.extracted_relations)}")
        log.info(f"Total found: {len(handler.found_titles)}")
        log.info(f"Total names in list: {len(handler.titles_to_find)}")
        log.info(f"{'='*60}\n")
        
        handler.extracted_relations = handler.found_titles.copy()
    
    log.info(f"\n{'='*60}")
    log.info(f"RECURSIVE CRAWL COMPLETED")
    log.info(f"{'='*60}")
    log.info(f"Number of scan rounds: {handler.scan_round}")
    log.info(f"Total politicians found: {len(handler.extracted_data)}")
    log.info(f"Total names in final list: {len(handler.titles_to_find)}")
    
    templates = {}
    for item in handler.extracted_data:
        template = item.get('template_used', 'Unknown')
        templates[template] = templates.get(template, 0) + 1
    
    log.info(f"\nTEMPLATES USED:")
    for template, count in sorted(templates.items(), key=lambda x: -x[1]):
        log.info(f"   • {template}: {count}")
    
    missing = handler.titles_to_find - handler.found_titles
    if missing:
        log.info(f"\nNOT FOUND ({len(missing)}):")
        for name in sorted(missing)[:50]:
            log.info(f"   • {name}")
        if len(missing) > 50:
            log.info(f"   ... and {len(missing) - 50} more")
    
    log.info(f"\n{'='*60}")
    log.info(f"Saving results to: {output_file}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(handler.extracted_data, f, ensure_ascii=False, indent=4)
    
    log.info(f"Successfully saved!")
    log.info(f"{'='*60}\n")
    
    return handler.extracted_data


def main():
    """Main function"""
    
    initial_titles_file = 'data/processed/politicians_names.txt'
    xml_file = 'data/raw/viwiki-latest-pages-articles.xml'
    output_file = 'data/processed/politicians_data_2.json'
    max_rounds = 2
    
    crawl_recursive_politicians(
        initial_titles_file=initial_titles_file,
        xml_file=xml_file,
        output_file=output_file,
        max_rounds=max_rounds
    )


if __name__ == "__main__":
    main()
