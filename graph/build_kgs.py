# ./graph/build_kgs.py

import json
import re

from collections import defaultdict
from typing import List, Dict, Set, Tuple
from datetime import datetime

from utils.config import settings
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("build_kgs", log_file="logs/graph/build_kgs.log")

class KnowledgeGraphBuilder:
    def __init__(self):
        self.nodes = {
            'Politician': [],
            'Position': [],
            'Location': [],
            'Award': [],
            'MilitaryCareer': [],
            'MilitaryRank': [],
            'Campaigns': [],
            'AlmaMater': [],
            'AcademicTitle': [],
        }
        
        self.edges = {
            'SERVED_AS': [],
            'SUCCEEDED': [],
            'PRECEDED': [],
            'BORN_AT': [],
            'DIED_AT': [],
            'AWARDED': [],
            'SERVED_IN': [],
            'HAS_RANK': [],  # Politician -> MilitaryRank
            'FOUGHT_IN': [],  # Politician -> Campaigns
            'ALUMNUS_OF': [],
            'HAS_ACADEMIC_TITLE': []
        }
        
        self.unique_politicians = set()
        self.unique_positions = set()
        self.unique_locations = set()
        self.unique_awards = set()
        self.unique_military_careers = set()
        self.unique_military_ranks = set()
        self.unique_campaigns = set()
        self.unique_alma_maters = set()
        self.unique_academic_titles = set()
        
        self.node_id_map = {
            'Politician': {},
            'Position': {},
            'Location': {},
            'Award': {},
            'MilitaryCareer': {},
            'MilitaryRank': {},
            'Campaigns': {},
            'AlmaMater': {},
            'AcademicTitle': {},
        }
        self.node_counters = defaultdict(int)
        self.generated_node_ids: Set[str] = set()
    
    def _normalize_name(self, name: str) -> str:
        if not name or not isinstance(name, str):
            return ""
        return ' '.join(name.lower().split())
    
    def _extract_id_segment(self, source_id: str) -> str:
        source_str = str(source_id or '').strip()
        if not source_str:
            return '000'
        return source_str

    def _generate_node_id(self, node_type: str, source_id: str) -> str:
        prefix = node_type[:3].lower()
        segment = self._extract_id_segment(source_id)
        base_key = f"{node_type}:{segment}"
        if node_type == 'Politician':
            candidate = f"{prefix}{segment}"
            if candidate in self.generated_node_ids:
                self.node_counters[base_key] += 1
                candidate = f"{prefix}{segment}_{self.node_counters[base_key]:03d}"
        else:
            self.node_counters[base_key] += 1
            candidate = f"{prefix}{segment}_{self.node_counters[base_key]:03d}"

        while candidate in self.generated_node_ids:
            self.node_counters[base_key] += 1
            candidate = f"{prefix}{segment}_{self.node_counters[base_key]:03d}"

        self.generated_node_ids.add(candidate)
        return candidate

    def extract_text_from_wikilink(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return ""
        
        text = re.sub(r'\{\{[^}]+\}\}', '', text)
        text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
        text = re.sub(r'\b\d+(?:x\d+)?px\b\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(?:border|thumb|link|frameless|upright|center|left|right|none)\b\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[\[(?:Tập[_ ]?tin|Tập tin|File|Image|Hình):[^\]]+\]\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'https?://[^\s\]]+', '', text, flags=re.IGNORECASE)

        def replace_wikilink(match):
            content = match.group(1)
            if any(prefix in content.lower() for prefix in ['file:', 'image:', 'tập tin:', 'hình:']):
                return ''
            if '|' in content:
                return content.split('|')[-1].strip()
            return content.strip()
        
        text = re.sub(r'\[\[([^\]]+)\]\]', replace_wikilink, text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace("''", '').replace('||', '').strip()
        
        return text
    
    def extract_names_from_wikilink(self, text: str) -> List[str]:
        if not text or not isinstance(text, str):
            return []
        
        names = []
        pattern = r'\[\[([^\]]+)\]\]'
        matches = re.findall(pattern, text)
        
        for match in matches:
            if '|' in match:
                name = match.split('|')[0].strip()
            else:
                name = match.strip()
            
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
                    names.append(name)
        
        return names
    
    def detect_status_from_office(self, office_text: str) -> str:
        if not office_text:
            return ''
        
        office_lower = office_text.lower()
        
        dismissed_keywords = [
            'cách chức', 'khai trừ', 'bị xóa', 'thôi chức',
            'truất phế', 'phế truất', 'tước bỏ', 'sa thải',
            'kỷ luật cách chức', 'đuổi việc'
        ]
        
        relieved_keywords = [
            'miễn nhiệm', 'bãi nhiệm', 'bãi bỏ',
            'thôi việc', 'từ chức', 'nghỉ việc'
        ]
        
        for keyword in dismissed_keywords:
            if keyword in office_lower:
                return 'bị cách chức'
        
        for keyword in relieved_keywords:
            if keyword in office_lower:
                return 'miễn nhiệm'
        return ''
    
    def add_politician_node(self, politician_data: Dict) -> str:
        title = politician_data.get('title', '')
        if not title:
            return ""

        normalized = self._normalize_name(title)
        existing_id = self.node_id_map['Politician'].get(normalized)
        if existing_id:
            return existing_id
        
        infobox = politician_data.get('infobox_normalized', politician_data.get('infobox', {}))
        source_id = str(politician_data.get('id', '')).strip()
        node_id = self._generate_node_id('Politician', source_id)
        
        node = {
            'id': node_id,
            'type': 'Politician',
            'name': self.extract_text_from_wikilink(infobox.get('name', title)),
            'properties': {
                'birth_date': self.extract_text_from_wikilink(infobox.get('birth_date', infobox.get('ngày_sinh', ''))),
                'death_date': self.extract_text_from_wikilink(infobox.get('death_date', infobox.get('ngày_chết', ''))),
                'party': self.extract_text_from_wikilink(infobox.get('party', infobox.get('đảng', ''))) or "Đảng Cộng sản Việt Nam"
            }
        }
        
        self.nodes['Politician'].append(node)
        self.unique_politicians.add(title)
        self.node_id_map['Politician'][normalized] = node_id  
        return node_id
    
    def add_position_node(self, position_text: str, source_id: str) -> str:
        position = self.extract_text_from_wikilink(position_text)
        if not position:
            return ""
        
        normalized = self._normalize_name(position)
        existing_id = self.node_id_map['Position'].get(normalized)
        if existing_id:
            return existing_id
        
        node_id = self._generate_node_id('Position', source_id)
        
        node = {
            'id': node_id,
            'type': 'Position',
            'name': position
        }
        
        self.nodes['Position'].append(node)
        self.unique_positions.add(position)
        self.node_id_map['Position'][normalized] = node_id  
        return node_id
    
    def add_location_node(self, location_text: str, source_id: str) -> str:
        location = self.extract_text_from_wikilink(location_text)
        if not location:
            return ""
        
        normalized = self._normalize_name(location)
        existing_id = self.node_id_map['Location'].get(normalized)
        if existing_id:
            return existing_id
        
        node_id = self._generate_node_id('Location', source_id)
        
        node = {
            'id': node_id,
            'type': 'Location',
            'name': location
        }
        
        self.nodes['Location'].append(node)
        self.unique_locations.add(location)
        self.node_id_map['Location'][normalized] = node_id  
        return node_id
    
    def add_award_node(self, award_text: str, source_id: str) -> str:
        award = self.extract_text_from_wikilink(award_text)
        if not award:
            return ""
        
        normalized = self._normalize_name(award)
        existing_id = self.node_id_map['Award'].get(normalized)
        if existing_id:
            return existing_id
        
        node_id = self._generate_node_id('Award', source_id)
        
        node = {
            'id': node_id,
            'type': 'Award',
            'name': award
        }
        
        self.nodes['Award'].append(node)
        self.unique_awards.add(award)
        self.node_id_map['Award'][normalized] = node_id  
        return node_id
    
    def add_military_career_node(self, military_text: str, source_id: str) -> str:
        military = self.extract_text_from_wikilink(military_text)
        if not military:
            return ""
        
        normalized = self._normalize_name(military)
        
        existing_id = self.node_id_map['MilitaryCareer'].get(normalized)
        if existing_id:
            return existing_id
        
        node_id = self._generate_node_id('MilitaryCareer', source_id)
        
        node = {
            'id': node_id,
            'type': 'MilitaryCareer',
            'name': military
        }
        
        self.nodes['MilitaryCareer'].append(node)
        self.unique_military_careers.add(military)
        self.node_id_map['MilitaryCareer'][normalized] = node_id  
        return node_id
    
    def add_military_rank_node(self, rank_text: str, source_id: str) -> str:
        rank = self.extract_text_from_wikilink(rank_text)
        if not rank:
            return ""
        
        normalized = self._normalize_name(rank)
        existing_id = self.node_id_map['MilitaryRank'].get(normalized)
        if existing_id:
            return existing_id
        
        node_id = self._generate_node_id('MilitaryRank', source_id)
        
        node = {
            'id': node_id,
            'type': 'MilitaryRank',
            'name': rank
        }
        
        self.nodes['MilitaryRank'].append(node)
        self.unique_military_ranks.add(rank)
        self.node_id_map['MilitaryRank'][normalized] = node_id  
        return node_id
    
    def add_campaign_node(self, campaign_text: str, source_id: str) -> str:
        campaign = self.extract_text_from_wikilink(campaign_text)
        if not campaign:
            return ""
        
        normalized = self._normalize_name(campaign)
        existing_id = self.node_id_map['Campaigns'].get(normalized)
        if existing_id:
            return existing_id
        
        node_id = self._generate_node_id('Campaigns', source_id)
        
        node = {
            'id': node_id,
            'type': 'Campaigns',
            'name': campaign
        }
        
        self.nodes['Campaigns'].append(node)
        self.unique_campaigns.add(campaign)
        self.node_id_map['Campaigns'][normalized] = node_id  
        return node_id
    
    def add_served_as_edge(self, politician_id: str, position_id: str, properties: Dict = None):
        if not politician_id or not position_id:
            return
        
        edge = {
            'from': politician_id,
            'to': position_id,
            'type': 'SERVED_AS',
            'properties': properties or {}
        }
        
        self.edges['SERVED_AS'].append(edge)
    
    def add_succession_edges(self, politician_id: str, successor: str, predecessor: str, position_id: str = None):
        if predecessor:
            predecessor_names = self.extract_names_from_wikilink(predecessor)
            for pred_name in predecessor_names:
                normalized = self._normalize_name(pred_name)
                target_id = self.node_id_map['Politician'].get(normalized)
                if target_id:
                    properties = {}
                    if position_id:
                        properties['position_id'] = position_id
                    edge = {
                        'from': politician_id,
                        'to': target_id,
                        'type': 'SUCCEEDED',
                        'properties': properties
                    }
                    self.edges['SUCCEEDED'].append(edge)
        
        if successor:
            successor_names = self.extract_names_from_wikilink(successor)
            for succ_name in successor_names:
                normalized = self._normalize_name(succ_name)
                target_id = self.node_id_map['Politician'].get(normalized)
                if target_id: 
                    properties = {}
                    if position_id:
                        properties['position_id'] = position_id
                    edge = {
                        'from': politician_id,
                        'to': target_id,
                        'type': 'PRECEDED',
                        'properties': properties
                    }
                    self.edges['PRECEDED'].append(edge)
    
    def add_location_edges(self, politician_id: str, birth_location_id: str, death_location_id: str):
        if birth_location_id:
            edge = {
                'from': politician_id,
                'to': birth_location_id,
                'type': 'BORN_AT',
                'properties': {}
            }
            self.edges['BORN_AT'].append(edge)
        
        if death_location_id:
            edge = {
                'from': politician_id,
                'to': death_location_id,
                'type': 'DIED_AT',
                'properties': {}
            }
            self.edges['DIED_AT'].append(edge)
    
    def add_award_edge(self, politician_id: str, award_id: str):
        if not award_id:
            return

        edge = {
            'from': politician_id,
            'to': award_id,
            'type': 'AWARDED',
            'properties': {}
        }
        self.edges['AWARDED'].append(edge)
    
    def add_military_edge(self, politician_id: str, military_id: str, properties: Dict = None):
        if not military_id:
            return

        edge = {
            'from': politician_id,
            'to': military_id,
            'type': 'SERVED_IN',
            'properties': properties or {}
        }
        self.edges['SERVED_IN'].append(edge)
    
    def add_has_rank_edge(self, politician_id: str, rank_id: str):
        if not rank_id:
            return
        
        edge = {
            'from': politician_id,
            'to': rank_id,
            'type': 'HAS_RANK',
            'properties': {}
        }
        self.edges['HAS_RANK'].append(edge)
    
    def add_fought_in_edge(self, politician_id: str, campaign_id: str):
        if not campaign_id:
            return
        
        edge = {
            'from': politician_id,
            'to': campaign_id,
            'type': 'FOUGHT_IN',
            'properties': {}
        }
        self.edges['FOUGHT_IN'].append(edge)
    
    def add_alma_mater_node(self, alma_mater_text: str, source_id: str) -> str:
        alma_mater = self.extract_text_from_wikilink(alma_mater_text)
        if not alma_mater:
            return ""
        
        normalized = self._normalize_name(alma_mater)
        existing_id = self.node_id_map['AlmaMater'].get(normalized)
        if existing_id:
            return existing_id
        
        node_id = self._generate_node_id('AlmaMater', source_id)
        
        node = {
            'id': node_id,
            'type': 'AlmaMater',
            'name': alma_mater
        }
        
        self.nodes['AlmaMater'].append(node)
        self.unique_alma_maters.add(alma_mater)
        self.node_id_map['AlmaMater'][normalized] = node_id  
        return node_id
    
    def add_academic_title_node(self, title_text: str, source_id: str) -> str:
        title = self.extract_text_from_wikilink(title_text)
        if not title:
            return ""
        
        normalized = self._normalize_name(title)
        existing_id = self.node_id_map['AcademicTitle'].get(normalized)
        if existing_id:
            return existing_id
        
        node_id = self._generate_node_id('AcademicTitle', source_id)
        
        node = {
            'id': node_id,
            'type': 'AcademicTitle',
            'name': title  
        }
        
        self.nodes['AcademicTitle'].append(node)
        self.unique_academic_titles.add(title)
        self.node_id_map['AcademicTitle'][normalized] = node_id  
        return node_id
    
    
    def add_alumnus_of_edge(self, politician_id: str, alma_mater_id: str):
        if not alma_mater_id:
            return
        
        edge = {
            'from': politician_id,
            'to': alma_mater_id,
            'type': 'ALUMNUS_OF',
            'properties': {}
        }
        self.edges['ALUMNUS_OF'].append(edge)
    
    def add_academic_title_edge(self, politician_id: str, title_id: str):
        if not title_id:
            return
        
        edge = {
            'from': politician_id,
            'to': title_id,
            'type': 'HAS_ACADEMIC_TITLE',
            'properties': {}
        }
        self.edges['HAS_ACADEMIC_TITLE'].append(edge)

    def resolve_politician_edges(self):
        pass
    
    def process_politician(self, politician_data: Dict):
        title = politician_data.get('title', '')
        if not title:
            return
        source_id = str(politician_data.get('id', '')).strip()
        politician_id = self.add_politician_node(politician_data)
        if not politician_id:
            return

        infobox = politician_data.get('infobox_normalized', politician_data.get('infobox', {}))

        for i in range(1, 15):
            office_key = 'office' if i == 1 else f'office{i}'
            office = infobox.get(office_key, '')
            
            if office:
                position_id = self.add_position_node(office, source_id)
                if position_id:
                    term_start = self.extract_text_from_wikilink(
                        infobox.get(f'term_start{i}' if i > 1 else 'term_start', '')
                    )
                    term_end = self.extract_text_from_wikilink(
                        infobox.get(f'term_end{i}' if i > 1 else 'term_end', '')
                    )
                    
                    status = self.detect_status_from_office(office)
                    
                    properties = {
                        'term_start': term_start,
                        'term_end': term_end,
                        'status': status
                    }
                    
                    self.add_served_as_edge(politician_id, position_id, properties)
                
                predecessor_key = 'predecessor' if i == 1 else f'predecessor{i}'
                successor_key = 'successor' if i == 1 else f'successor{i}'
                
                predecessor = infobox.get(predecessor_key, '')
                successor = infobox.get(successor_key, '')
                
                self.add_succession_edges(politician_id, successor, predecessor, position_id)
        
        birth_place = infobox.get('birth_place', infobox.get('nơi_sinh', ''))
        death_place = infobox.get('death_place', infobox.get('nơi_chết', ''))

        birth_location_id = self.add_location_node(birth_place, source_id) if birth_place else ""
        death_location_id = self.add_location_node(death_place, source_id) if death_place else ""

        self.add_location_edges(politician_id, birth_location_id, death_location_id)
        
        awards_array = politician_data.get('awards', [])
        if awards_array:
            for award_item in awards_array:
                if award_item:
                    award_id = self.add_award_node(award_item, source_id)
                    self.add_award_edge(politician_id, award_id)
        else:
            award_fields = ['awards', 'giải_thưởng', 'khen_thưởng']
            for field in award_fields:
                award_value = infobox.get(field, '')
                if award_value:
                    if isinstance(award_value, list):
                        for award_item in award_value:
                            if award_item:
                                award_id = self.add_award_node(award_item, source_id)
                                self.add_award_edge(politician_id, award_id)
                    elif isinstance(award_value, str):
                        award_id = self.add_award_node(award_value, source_id)
                        self.add_award_edge(politician_id, award_id)
        
        military_fields = ['branch']
        for field in military_fields:
            military = infobox.get(field, '')
            if military:
                service_years = self.extract_text_from_wikilink(infobox.get('serviceyears', infobox.get('years_of_service', infobox.get('năm_phục_vụ', ''))))
                rank = self.extract_text_from_wikilink(infobox.get('rank', infobox.get('military_rank', infobox.get('cấp_bậc', ''))))
                
                year_start = ""
                year_end = ""
                if service_years:
                    year_pattern = r'(\d{4})\s*[-–—]\s*(\d{4}|nay|present|hiện tại)'
                    match = re.search(year_pattern, service_years, re.IGNORECASE)
                    if match:
                        year_start = match.group(1)
                        year_end_raw = match.group(2)
                        if year_end_raw.lower() not in ['nay', 'present', 'hiện tại']:
                            year_end = year_end_raw
                
                military_id = self.add_military_career_node(military, source_id)
                
                military_properties = {}
                if year_start:
                    military_properties['year_start'] = int(year_start)
                if year_end:
                    military_properties['year_end'] = int(year_end)
                
                self.add_military_edge(politician_id, military_id, military_properties)
                
                if rank:
                    rank_id = self.add_military_rank_node(rank, source_id)
                    self.add_has_rank_edge(politician_id, rank_id)
        
        battles = infobox.get('battles', '')
        if battles and isinstance(battles, list):
            for battle in battles:
                if battle:
                    campaign_id = self.add_campaign_node(battle, source_id)
                    self.add_fought_in_edge(politician_id, campaign_id)
        
        alma_mater_fields = ['alma_mater', 'trường', 'nơi_đào_tạo']
        for field in alma_mater_fields:
            alma_mater = infobox.get(field, '')
            if alma_mater:
                if isinstance(alma_mater, list):
                    schools = alma_mater
                else:
                    schools = alma_mater.split('<br>')
                
                for school in schools:
                    if isinstance(school, str):
                        school = school.strip()
                    if school:
                        alma_mater_id = self.add_alma_mater_node(school, source_id)
                        self.add_alumnus_of_edge(politician_id, alma_mater_id)
        
        education_level = infobox.get('education', infobox.get('trình_độ', ''))
        if education_level:
            if isinstance(education_level, list):
                titles = education_level
            else:
                titles = education_level.split('<br>')
            
            for title_text in titles:
                if isinstance(title_text, str):
                    title_text = title_text.strip()
                if title_text:
                    title_id = self.add_academic_title_node(title_text, source_id)
                    self.add_academic_title_edge(politician_id, title_id)
        
        honorific_prefix = infobox.get('honorific_prefix', '')
        if honorific_prefix:
            prefix_parts = honorific_prefix.split(',')
            for part in prefix_parts:
                part = part.strip()
                if part:
                    title_id = self.add_academic_title_node(part, source_id)
                    self.add_academic_title_edge(politician_id, title_id)
    
    def build_from_file(self, input_file: str):
        with open(input_file, 'r', encoding='utf-8') as f:
            politicians_data = json.load(f)
        
        log.info(f"Number of politicians: {len(politicians_data)}")
        
        for i, politician_data in enumerate(politicians_data, 1):
            title = politician_data.get('title', 'Unknown')
            log.info(f"[{i}/{len(politicians_data)}] Processing: {title}")
            self.process_politician(politician_data)
        
        self.resolve_politician_edges()
    
    def export_to_json(self, output_file: str):

        log.info(f"\nExporting data to: {output_file}")
        
        graph_data = {
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'total_nodes': sum(len(nodes) for nodes in self.nodes.values()),
                'total_edges': sum(len(edges) for edges in self.edges.values()),
                'node_types': list(self.nodes.keys()),
                'edge_types': list(self.edges.keys())
            },
            'nodes': self.nodes,
            'edges': self.edges
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        
        log.info(f"Completed!")
    
    def export_to_neo4j_cypher(self, output_file: str):
        log.info(f"\nCreating Cypher script: {output_file}")
        
        cypher_statements = []
        
        cypher_statements.append("// Neo4j Cypher Script - Knowledge Graph Import")
        cypher_statements.append(f"// Generated at: {datetime.now().isoformat()}")
        cypher_statements.append("// Clear existing data (optional)")
        cypher_statements.append("// MATCH (n) DETACH DELETE n;\n")
        
        cypher_statements.append("// Create constraints")
        cypher_statements.append("CREATE CONSTRAINT politician_id IF NOT EXISTS FOR (p:Politician) REQUIRE p.id IS UNIQUE;")
        cypher_statements.append("CREATE CONSTRAINT position_id IF NOT EXISTS FOR (p:Position) REQUIRE p.id IS UNIQUE;")
        cypher_statements.append("CREATE CONSTRAINT location_id IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE;")
        cypher_statements.append("CREATE CONSTRAINT award_id IF NOT EXISTS FOR (a:Award) REQUIRE a.id IS UNIQUE;")
        cypher_statements.append("CREATE CONSTRAINT military_id IF NOT EXISTS FOR (m:MilitaryCareer) REQUIRE m.id IS UNIQUE;")
        cypher_statements.append("CREATE CONSTRAINT military_rank_id IF NOT EXISTS FOR (mr:MilitaryRank) REQUIRE mr.id IS UNIQUE;")
        cypher_statements.append("CREATE CONSTRAINT campaigns_id IF NOT EXISTS FOR (c:Campaigns) REQUIRE c.id IS UNIQUE;")
        cypher_statements.append("CREATE CONSTRAINT alma_mater_id IF NOT EXISTS FOR (a:AlmaMater) REQUIRE a.id IS UNIQUE;")
        cypher_statements.append("CREATE CONSTRAINT academic_title_id IF NOT EXISTS FOR (a:AcademicTitle) REQUIRE a.id IS UNIQUE;")
        
        # Create nodes for each type
        node_types_mapping = {
            'Politician': 'Politician',
            'Position': 'Position',
            'Location': 'Location',
            'Award': 'Award',
            'MilitaryCareer': 'MilitaryCareer',
            'MilitaryRank': 'MilitaryRank',
            'Campaigns': 'Campaigns',
            'AlmaMater': 'AlmaMater',
            'AcademicTitle': 'AcademicTitle',
        }
        
        for node_type, label in node_types_mapping.items():
            cypher_statements.append(f"\n// Create {node_type} nodes")
            for node in self.nodes[node_type]:
                props = ', '.join([f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in node.items()])
                cypher_statements.append(f"MERGE (n:{label} {{{props}}});")
        
        relationship_configs = [
            ('SERVED_AS', 'Politician', 'Position', True),
            ('SUCCEEDED', 'Politician', 'Politician', True),  
            ('PRECEDED', 'Politician', 'Politician', True),  
            ('BORN_AT', 'Politician', 'Location', False),
            ('DIED_AT', 'Politician', 'Location', False),
            ('AWARDED', 'Politician', 'Award', False),
            ('SERVED_IN', 'Politician', 'MilitaryCareer', True),
            ('HAS_RANK', 'Politician', 'MilitaryRank', False),
            ('FOUGHT_IN', 'Politician', 'Campaigns', False),
            ('ALUMNUS_OF', 'Politician', 'AlmaMater', False),
            ('HAS_ACADEMIC_TITLE', 'Politician', 'AcademicTitle', False)
        ]
        
        for rel_type, from_label, to_label, has_props in relationship_configs:
            cypher_statements.append(f"\n// Create {rel_type} relationships")
            for edge in self.edges[rel_type]:
                from_id = json.dumps(edge['from'], ensure_ascii=False)
                to_id = json.dumps(edge['to'], ensure_ascii=False)
                
                if has_props and edge.get('properties'):
                    props = ', '.join([f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in edge['properties'].items() if v])
                    props_str = f" {{{props}}}" if props else ""
                else:
                    props_str = ""
                
                cypher_statements.append(
                    f"MATCH (a:{from_label} {{id: {from_id}}}), (b:{to_label} {{id: {to_id}}}) "
                    f"MERGE (a)-[:{rel_type}{props_str}]->(b);"
                )
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cypher_statements))
        
        log.info(f"Completed!")

if __name__ == "__main__":
    builder = KnowledgeGraphBuilder()
    builder.build_from_file(settings.INPUT_GRAPH_POLITICIAN_FILE)
    builder.export_to_json(settings.OUTPUT_GRAPH_FILE)
    builder.export_to_neo4j_cypher(settings.OUTPUT_CYPHER_FILE)
