# Test script to examine XML structure

import xml.sax

class TestHandler(xml.sax.ContentHandler):
    """
    SAX Handler to extract one page and examine its structure.
    """
    
    def __init__(self, target_title: str):
        super().__init__()
        self.target_title = target_title
        self.found = False
        self._current_tag = ""
        self._in_page = False
        self._in_revision = False
        self._title = ""
        self._text_chunks = []
        self._page_id = ""
        self.result_text = ""

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
            # Check if this is the page we want
            if self._title == self.target_title:
                self.result_text = "".join(self._text_chunks)
                self.found = True
                print(f"\n{'='*80}")
                print(f"Found page: {self._title}")
                print(f"Page ID: {self._page_id}")
                print(f"{'='*80}")
                print(f"\nFull text content (first 5000 characters):\n")
                print(self.result_text[:5000])
                print(f"\n{'='*80}")
                # Stop parsing after finding the page
                raise StopIteration("Found target page")
            
            # Reset
            self._in_page = False
            self._title = ""
            self._text_chunks = []
            self._page_id = ""

        self._current_tag = ""

def extract_one_page(xml_file: str, target_title: str):
    """
    Extract one page to examine structure.
    """
    print(f"Searching for page: {target_title}")
    print(f"In XML file: {xml_file}\n")
    
    handler = TestHandler(target_title)
    parser = xml.sax.make_parser()
    parser.setFeature(xml.sax.handler.feature_namespaces, 0)
    parser.setContentHandler(handler)
    
    try:
        parser.parse(xml_file)
    except StopIteration:
        print("\n Successfully extracted page")
    except Exception as e:
        print(f"\n Error: {e}")
    
    if not handler.found:
        print(f"\n Page '{target_title}' not found in XML")
    
    return handler.result_text if handler.found else None

if __name__ == "__main__":
    xml_file = "./data/raw/viwiki-latest-pages-articles.xml"
    
    # Test with Tô Lâm
    target_title = "Tô Lâm"
    
    result = extract_one_page(xml_file, target_title)
    
    if result:
        # Save to file for easier viewing
        output_file = ".\data\mess\xml_output.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Title: {target_title}\n")
            f.write("="*80 + "\n\n")
            f.write(result)
        
        print(f"\n Full content saved to: {output_file}")
