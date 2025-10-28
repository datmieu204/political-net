# ./crawl/get_politicians.py

import re
import json
import xml.sax
import wikitextparser as wtp

from typing import Dict, Tuple

from .alias import COMPREHENSIVE_MAPPING
from utils.queue_based_async_logger import get_async_logger
from utils.external import PRIORITY_TEMPLATES
from utils.config import settings

log = get_async_logger("crawl_politicians", log_file="logs/crawl/crawl_politicians.log")

class PoliticianHandler(xml.sax.ContentHandler):
    """
    SAX Handler to extract politician infoboxes from Wikipedia XML dump.
    """
    
    def __init__(self):
        super().__init__()
        self.all_politicians_data = []
        self._current_tag = ""
        self._in_page = False
        self._in_revision = False
        self._title = ""
        self._text_chunks = []
        self._page_id = ""
        self.pages_processed = 0

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
                log.info(f"Processed {self.pages_processed} pages... Found {len(self.all_politicians_data)} politicians.")
            
            full_text = "".join(self._text_chunks)
            
            infobox_raw, template_name = self.extract_infobox(full_text)
            
            # if template is politician
            if template_name not in ["NOT_FOUND", "ERROR"]:
                
                # Normalize infobox
                infobox_normalized = self.normalize_infobox(infobox_raw)
                
                data_entry = {
                    "title": self._title,
                    "id": self._page_id,
                    "template": template_name,
                    "infobox": infobox_normalized 
                }
                
                self.all_politicians_data.append(data_entry)
            
            # Reset
            self._in_page = False
            self._title = ""
            self._text_chunks = []
            self._page_id = ""

        self._current_tag = ""
    
    def extract_infobox(self, text: str) -> Tuple[Dict, str]:
        try:
            parsed = wtp.parse(text)
            infobox_data = {}

            priority_templates = [name for name in PRIORITY_TEMPLATES]

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
        normalized = {}
        for key, value in infobox.items():
            normalized_key = self.normalize_key(key)
            normalized[normalized_key] = value
        return normalized

def build_politician(xml_file: str, output_db_file: str):
    """
    Run the politician extraction process from the given XML file
    """
    log.info(f"Input XML: {xml_file}")
    
    handler = PoliticianHandler()
    
    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_namespaces, 0)
    parser.setContentHandler(handler)
    
    try:
        parser.parse(xml_file)
    except Exception as e:
        log.error(f"Error parsing file: {e}")
    
    log.info(f"COMPLETED")
    log.info(f"Total pages processed: {handler.pages_processed}")
    log.info(f"Total politicians found: {len(handler.all_politicians_data)}")
    
    log.info(f"Saving database to: {output_db_file}")
    with open(output_db_file, 'w', encoding='utf-8') as f:
        json.dump(handler.all_politicians_data, f, ensure_ascii=False, indent=2)
    
    log.info(f"Successfully saved!")

if __name__ == "__main__":
    build_politician(settings.VIWIKI_XML_DUMP_DIR, settings.OUTPUT_DIR_POLITICIAN_DB)