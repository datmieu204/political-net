# ./crawl/crawl_expand.py

import re
import json
import xml.sax
from typing import Optional

from utils.queue_based_async_logger import get_async_logger
from utils.config import settings

log = get_async_logger("crawl_expand", log_file="logs/crawl/crawl_expand.log")

class SummaryHandler(xml.sax.ContentHandler):
    
    def __init__(self, target_titles: set):
        super().__init__()
        self.target_titles = target_titles
        self.summaries = {}
        self._current_tag = ""
        self._in_page = False
        self._in_revision = False
        self._title = ""
        self._text_chunks = []
        self.pages_processed = 0
        self.found_count = 0

    def startElement(self, tag, attributes):
        self._current_tag = tag
        if tag == "page":
            self._in_page = True
            self._title = ""
            self._text_chunks = []
        elif tag == "revision":
            self._in_revision = True

    def characters(self, content):
        if self._in_page:
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
                log.info(f"Processed {self.pages_processed} pages... Found {self.found_count}/{len(self.target_titles)} summaries.")
            
            if self._title in self.target_titles:
                full_text = "".join(self._text_chunks)
                summary = self.extract_summary(full_text, self._title)
                
                if summary:
                    self.summaries[self._title] = summary
                    self.found_count += 1
                    log.info(f"Found summary for: {self._title} ({self.found_count}/{len(self.target_titles)})")
            
            self._in_page = False
            self._title = ""
            self._text_chunks = []
        self._current_tag = ""
    
    def extract_summary(self, text: str, title: str) -> Optional[str]:
        try:
            clean_title = re.sub(r'\s*\([^)]*\)', '', title).strip()
            escaped_title = re.escape(clean_title)
            pattern = rf"'''[^\n]*{escaped_title}[^\n]*'''(?:\s|\(|<ref>)"
            start_match = re.search(pattern, text)
            
            if start_match:
                text = text[start_match.start():]
                
                match = re.search(r'\n\s*==\s*[^=]', text)
                if match:
                    summary_text = text[:match.start()]
                else:
                    summary_text = text[:3000]
                
                summary_text = self.clean_summary(summary_text)
                return summary_text.strip() if summary_text.strip() else None
            else:
                return None
        except Exception as e:
            log.error(f"Error extracting summary: {e}")
            return None
    
    def clean_summary(self, text: str) -> str:
        text = re.sub(r'\[\[(Tập tin|File|Hình|Image):[^\]]*\]\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<ref[^/>]*/>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '', text)
        
        while True:
            old_text = text
            text = re.sub(r'\{\{[^\{\}]*\}\}', '', text)
            if old_text == text:
                break
        
        text = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]+)\]\]', r'\1', text)
        text = re.sub(r'\[http[^\s\]]+\s+([^\]]+)\]', r'\1', text)
        text = re.sub(r'\[http[^\]]+\]', '', text)
        text = re.sub(r"'{2,}", '', text)
        text = re.sub(r'\n\n+', '. ', text)
        text = re.sub(r'\n', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\.\s*\.+', '.', text)
        text = text.replace('\"', '')
        
        return text.strip()

def expand_with_summary(input_file: str, xml_file: str, output_file: str):
    log.info(f"Loading politician data from: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        politicians_data = json.load(f)
    
    log.info(f"Loaded {len(politicians_data)} politicians")
    
    target_titles = {p['title'] for p in politicians_data if 'title' in p}
    log.info(f"Will search for {len(target_titles)} titles in XML dump")
    
    handler = SummaryHandler(target_titles)
    
    log.info(f"Parsing XML file: {xml_file}")
    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_namespaces, 0)
    parser.setContentHandler(handler)
    
    try:
        parser.parse(xml_file)
    except Exception as e:
        log.error(f"Error parsing XML file: {e}")
    
    log.info(f"XML parsing completed")
    log.info(f"Total pages processed: {handler.pages_processed}")
    log.info(f"Summaries found: {handler.found_count}/{len(target_titles)}")
    
    log.info("Adding summaries to politician data...")
    for politician in politicians_data:
        title = politician.get('title', '')
        if title in handler.summaries:
            politician['summary'] = handler.summaries[title]
        else:
            politician['summary'] = ""
            log.warning(f"No summary found for: {title}")
    
    log.info(f"Saving expanded data to: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(politicians_data, f, ensure_ascii=False, indent=2)
    
    log.info("Successfully saved expanded data!")
    
    with_summary = sum(1 for p in politicians_data if p.get('summary', '').strip())
    log.info(f"Final statistics: {with_summary}/{len(politicians_data)} politicians have summaries")

if __name__ == "__main__":
    expand_with_summary(
        settings.INPUT_EXPAND_POLITICIAN_FILE,
        settings.VIWIKI_XML_DUMP_DIR,
        settings.OUTPUT_EXPAND_POLITICIAN_FILE
    )