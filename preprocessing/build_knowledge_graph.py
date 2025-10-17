# -*- coding: utf-8 -*-

"""
Script to build Knowledge Graph from politician data
Define Nodes and Edges for Neo4j import
"""

import json
import re
from typing import List, Dict, Set, Tuple
from datetime import datetime

from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("build_knowledge_graph", log_file="logs/preprocessing/build_knowledge_graph.log")

class KnowledgeGraphBuilder:
    """Class to build Knowledge Graph from infobox data"""
    
    def __init__(self):
        # Store nodes and edges
        self.nodes = {
            'Politician': [],
            'Position': [],
            'Location': [],
            'Award': [],
            'MilitaryCareer': []
        }
        
        self.edges = {
            'SERVED_AS': [],
            'SUCCEEDED': [],
            'PRECEDED': [],
            'BORN_AT': [],
            'DIED_AT': [],
            'AWARDED': [],
            'SERVED_IN': []
        }
        
        self.unique_politicians = set()
        self.unique_positions = set()
        self.unique_locations = set()
        self.unique_awards = set()
        self.unique_military_careers = set()
    
    def extract_text_from_wikilink(self, text: str) -> str:
        """
        Extract plain text from wikilink [[Text]] or [[Link|Text]]
        """
        if not text or not isinstance(text, str):
            return ""
        
        text = re.sub(r'\{\{[^}]+\}\}', '', text)
        
        def replace_wikilink(match):
            content = match.group(1)
            if '|' in content:
                return content.split('|')[-1].strip()
            return content.strip()
        
        text = re.sub(r'\[\[([^\]]+)\]\]', replace_wikilink, text)
        
        text = re.sub(r'<[^>]+>', '', text)
        
        text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
        
        return text.strip()
    
    def extract_names_from_wikilink(self, text: str) -> List[str]:
        """
        Extract list of names from wikilink
        """
        if not text or not isinstance(text, str):
            return []
        
        names = []
        pattern = r'\[\[([^\]|:]+?)(?:\|[^\]]+?)?\]\]'
        matches = re.findall(pattern, text)
        
        for match in matches:
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
    
    def add_politician_node(self, politician_data: Dict):
        """
        Add Politician node
        """
        title = politician_data.get('title', '')
        if not title or title in self.unique_politicians:
            return
        
        infobox = politician_data.get('infobox_normalized', {})
        
        node = {
            'id': title,
            'type': 'Politician',
            'name': self.extract_text_from_wikilink(infobox.get('name', title)),
            'full_name': title,
            'birth_date': self.extract_text_from_wikilink(infobox.get('birth_date', '')),
            'death_date': self.extract_text_from_wikilink(infobox.get('death_date', infobox.get('ngày_chết', ''))),
            'party': self.extract_text_from_wikilink(infobox.get('party', '')),
            'ethnicity': self.extract_text_from_wikilink(infobox.get('ethnicity', infobox.get('dân_tộc', ''))),
            'religion': self.extract_text_from_wikilink(infobox.get('religion', infobox.get('tôn_giáo', ''))),
            'nationality': self.extract_text_from_wikilink(infobox.get('nationality', infobox.get('quốc_tịch', ''))),
            'image': infobox.get('image', ''),
            'military_rank': self.extract_text_from_wikilink(infobox.get('military_rank', infobox.get('cấp_bậc', ''))),
        }
        
        self.nodes['Politician'].append(node)
        self.unique_politicians.add(title)
    
    def add_position_node(self, position_text: str):
        """
        Add Position node
        """
        position = self.extract_text_from_wikilink(position_text)
        if not position or position in self.unique_positions:
            return
        
        node = {
            'id': position,
            'type': 'Position',
            'name': position
        }
        
        self.nodes['Position'].append(node)
        self.unique_positions.add(position)
    
    def add_location_node(self, location_text: str):
        """
        Add Location node
        """
        location = self.extract_text_from_wikilink(location_text)
        if not location or location in self.unique_locations:
            return
        
        node = {
            'id': location,
            'type': 'Location',
            'name': location
        }
        
        self.nodes['Location'].append(node)
        self.unique_locations.add(location)
    
    def add_award_node(self, award_text: str):
        """
        Add Award node
        """
        award = self.extract_text_from_wikilink(award_text)
        if not award or award in self.unique_awards:
            return
        
        node = {
            'id': award,
            'type': 'Award',
            'name': award
        }
        
        self.nodes['Award'].append(node)
        self.unique_awards.add(award)
    
    def add_military_career_node(self, military_text: str):
        """
        Add MilitaryCareer node
        """
        military = self.extract_text_from_wikilink(military_text)
        if not military or military in self.unique_military_careers:
            return
        
        node = {
            'id': military,
            'type': 'MilitaryCareer',
            'name': military
        }
        
        self.nodes['MilitaryCareer'].append(node)
        self.unique_military_careers.add(military)
    
    def add_served_as_edge(self, politician_id: str, position: str, properties: Dict = None):
        """
        Add SERVED_AS edge: Politician -> Position
        """
        position_clean = self.extract_text_from_wikilink(position)
        if not position_clean:
            return
        
        edge = {
            'from': politician_id,
            'to': position_clean,
            'type': 'SERVED_AS',
            'properties': properties or {}
        }
        
        self.edges['SERVED_AS'].append(edge)
    
    def add_succession_edges(self, politician_id: str, successor: str, predecessor: str):
        """
        Add SUCCEEDED and PRECEDED edges
        """
        # SUCCEEDED: politician_id -> predecessor (succeeded from)
        if predecessor:
            predecessor_names = self.extract_names_from_wikilink(predecessor)
            for pred_name in predecessor_names:
                edge = {
                    'from': politician_id,
                    'to': pred_name,
                    'type': 'SUCCEEDED',
                    'properties': {}
                }
                self.edges['SUCCEEDED'].append(edge)
        
        # PRECEDED: politician_id -> successor (predecessor of)
        if successor:
            successor_names = self.extract_names_from_wikilink(successor)
            for succ_name in successor_names:
                edge = {
                    'from': politician_id,
                    'to': succ_name,
                    'type': 'PRECEDED',
                    'properties': {}
                }
                self.edges['PRECEDED'].append(edge)
    
    def add_location_edges(self, politician_id: str, birth_place: str, death_place: str):
        """
        Add BORN_AT and DIED_AT edges
        """
        # BORN_AT
        if birth_place:
            birth_location = self.extract_text_from_wikilink(birth_place)
            if birth_location:
                edge = {
                    'from': politician_id,
                    'to': birth_location,
                    'type': 'BORN_AT',
                    'properties': {}
                }
                self.edges['BORN_AT'].append(edge)
        
        # DIED_AT
        if death_place:
            death_location = self.extract_text_from_wikilink(death_place)
            if death_location:
                edge = {
                    'from': politician_id,
                    'to': death_location,
                    'type': 'DIED_AT',
                    'properties': {}
                }
                self.edges['DIED_AT'].append(edge)
    
    def add_award_edge(self, politician_id: str, award_text: str):
        """
        Add AWARDED edge
        """
        if not award_text:
            return
        
        award = self.extract_text_from_wikilink(award_text)
        if award:
            edge = {
                'from': politician_id,
                'to': award,
                'type': 'AWARDED',
                'properties': {}
            }
            self.edges['AWARDED'].append(edge)
    
    def add_military_edge(self, politician_id: str, military_text: str):
        """
        Add SERVED_IN edge
        """
        if not military_text:
            return
        
        military = self.extract_text_from_wikilink(military_text)
        if military:
            edge = {
                'from': politician_id,
                'to': military,
                'type': 'SERVED_IN',
                'properties': {}
            }
            self.edges['SERVED_IN'].append(edge)
    
    def process_politician(self, politician_data: Dict):
        """
        Process a politician and create nodes/edges
        """
        title = politician_data.get('title', '')
        if not title:
            return
        
        infobox = politician_data.get('infobox_normalized', {})
        
        # 1. Add Politician node
        self.add_politician_node(politician_data)
        
        for i in range(1, 10):
            office_key = 'office' if i == 1 else f'office{i}'
            office = infobox.get(office_key, '')
            
            if office:
                self.add_position_node(office)
                
                properties = {
                    'term_start': self.extract_text_from_wikilink(
                        infobox.get(f'term_start{i}' if i > 1 else 'term_start', '')
                    ),
                    'term_end': self.extract_text_from_wikilink(
                        infobox.get(f'term_end{i}' if i > 1 else 'term_end', '')
                    )
                }
                self.add_served_as_edge(title, office, properties)
                
                predecessor_key = 'predecessor' if i == 1 else f'predecessor{i}'
                successor_key = 'successor' if i == 1 else f'successor{i}'
                
                predecessor = infobox.get(predecessor_key, '')
                successor = infobox.get(successor_key, '')
                
                self.add_succession_edges(title, successor, predecessor)
        
        birth_place = infobox.get('birth_place', infobox.get('nơi_sinh', ''))
        death_place = infobox.get('death_place', infobox.get('nơi_chết', ''))
        
        if birth_place:
            self.add_location_node(birth_place)
        if death_place:
            self.add_location_node(death_place)
        
        self.add_location_edges(title, birth_place, death_place)
        
        award_fields = ['awards', 'giải_thưởng', 'khen_thưởng']
        for field in award_fields:
            award = infobox.get(field, '')
            if award:
                self.add_award_node(award)
                self.add_award_edge(title, award)
        
        military_fields = ['branch', 'phục_vụ', 'service', 'allegiance', 'thuộc']
        for field in military_fields:
            military = infobox.get(field, '')
            if military:
                self.add_military_career_node(military)
                self.add_military_edge(title, military)
    
    def build_from_file(self, input_file: str):
        """
        Read JSON file and build knowledge graph
        """
        log.info(f"{'='*60}")
        log.info(f"BUILDING KNOWLEDGE GRAPH")
        log.info(f"{'='*60}")
        log.info(f"Reading data from: {input_file}")
        
        with open(input_file, 'r', encoding='utf-8') as f:
            politicians_data = json.load(f)
        
        log.info(f"Number of politicians: {len(politicians_data)}")
        log.info(f"{'='*60}\n")
        
        for i, politician_data in enumerate(politicians_data, 1):
            title = politician_data.get('title', 'Unknown')
            log.info(f"[{i}/{len(politicians_data)}] Processing: {title}")
            self.process_politician(politician_data)
        
        log.info(f"\n{'='*60}")
        log.info(f"GRAPH CONSTRUCTION COMPLETED")
        log.info(f"{'='*60}")
        self.print_statistics()
    
    def print_statistics(self):
        """
        Print graph statistics
        """
        log.info(f"\nNode Statistics:")
        for node_type, nodes in self.nodes.items():
            log.info(f"  • {node_type}: {len(nodes)}")
        
        log.info(f"\nEdge Statistics:")
        for edge_type, edges in self.edges.items():
            log.info(f"  • {edge_type}: {len(edges)}")
        
        total_nodes = sum(len(nodes) for nodes in self.nodes.values())
        total_edges = sum(len(edges) for edges in self.edges.values())
        
        log.info(f"\nTotal Nodes: {total_nodes}")
        log.info(f"Total Edges: {total_edges}")
        log.info(f"{'='*60}")
    
    def export_to_json(self, output_file: str):
        """
        Export to JSON file in triplet format for Neo4j
        """
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
            'edges': self.edges,
            'triplets': []
        }
        
        for edge_type, edges in self.edges.items():
            for edge in edges:
                triplet = {
                    'subject': edge['from'],
                    'predicate': edge_type,
                    'object': edge['to'],
                    'properties': edge.get('properties', {})
                }
                graph_data['triplets'].append(triplet)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        
        log.info(f"✓ Exported {len(graph_data['triplets'])} triplets")
        log.info(f"✓ Completed!")
    
    def export_to_neo4j_cypher(self, output_file: str):
        """
        Export to Cypher script file for Neo4j import
        """
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
        cypher_statements.append("CREATE CONSTRAINT military_id IF NOT EXISTS FOR (m:MilitaryCareer) REQUIRE m.id IS UNIQUE;\n")
        
        cypher_statements.append("// Create Politician nodes")
        for node in self.nodes['Politician']:
            props = ', '.join([f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in node.items()])
            cypher_statements.append(f"MERGE (p:Politician {{{props}}});")
        
        cypher_statements.append("\n// Create Position nodes")
        for node in self.nodes['Position']:
            props = ', '.join([f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in node.items()])
            cypher_statements.append(f"MERGE (p:Position {{{props}}});")
        
        cypher_statements.append("\n// Create Location nodes")
        for node in self.nodes['Location']:
            props = ', '.join([f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in node.items()])
            cypher_statements.append(f"MERGE (l:Location {{{props}}});")
        
        cypher_statements.append("\n// Create Award nodes")
        for node in self.nodes['Award']:
            props = ', '.join([f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in node.items()])
            cypher_statements.append(f"MERGE (a:Award {{{props}}});")
        
        cypher_statements.append("\n// Create MilitaryCareer nodes")
        for node in self.nodes['MilitaryCareer']:
            props = ', '.join([f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in node.items()])
            cypher_statements.append(f"MERGE (m:MilitaryCareer {{{props}}});")
        
        cypher_statements.append("\n// Create SERVED_AS relationships")
        for edge in self.edges['SERVED_AS']:
            from_id = json.dumps(edge['from'], ensure_ascii=False)
            to_id = json.dumps(edge['to'], ensure_ascii=False)
            props = ', '.join([f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in edge['properties'].items()])
            props_str = f" {{{props}}}" if props else ""
            cypher_statements.append(
                f"MATCH (p:Politician {{id: {from_id}}}), (pos:Position {{id: {to_id}}}) "
                f"MERGE (p)-[:SERVED_AS{props_str}]->(pos);"
            )
        
        cypher_statements.append("\n// Create SUCCEEDED relationships")
        for edge in self.edges['SUCCEEDED']:
            from_id = json.dumps(edge['from'], ensure_ascii=False)
            to_id = json.dumps(edge['to'], ensure_ascii=False)
            cypher_statements.append(
                f"MATCH (p1:Politician {{id: {from_id}}}), (p2:Politician {{id: {to_id}}}) "
                f"MERGE (p1)-[:SUCCEEDED]->(p2);"
            )
        
        cypher_statements.append("\n// Create PRECEDED relationships")
        for edge in self.edges['PRECEDED']:
            from_id = json.dumps(edge['from'], ensure_ascii=False)
            to_id = json.dumps(edge['to'], ensure_ascii=False)
            cypher_statements.append(
                f"MATCH (p1:Politician {{id: {from_id}}}), (p2:Politician {{id: {to_id}}}) "
                f"MERGE (p1)-[:PRECEDED]->(p2);"
            )
        
        cypher_statements.append("\n// Create BORN_AT relationships")
        for edge in self.edges['BORN_AT']:
            from_id = json.dumps(edge['from'], ensure_ascii=False)
            to_id = json.dumps(edge['to'], ensure_ascii=False)
            cypher_statements.append(
                f"MATCH (p:Politician {{id: {from_id}}}), (l:Location {{id: {to_id}}}) "
                f"MERGE (p)-[:BORN_AT]->(l);"
            )
        
        cypher_statements.append("\n// Create DIED_AT relationships")
        for edge in self.edges['DIED_AT']:
            from_id = json.dumps(edge['from'], ensure_ascii=False)
            to_id = json.dumps(edge['to'], ensure_ascii=False)
            cypher_statements.append(
                f"MATCH (p:Politician {{id: {from_id}}}), (l:Location {{id: {to_id}}}) "
                f"MERGE (p)-[:DIED_AT]->(l);"
            )
        
        cypher_statements.append("\n// Create AWARDED relationships")
        for edge in self.edges['AWARDED']:
            from_id = json.dumps(edge['from'], ensure_ascii=False)
            to_id = json.dumps(edge['to'], ensure_ascii=False)
            cypher_statements.append(
                f"MATCH (p:Politician {{id: {from_id}}}), (a:Award {{id: {to_id}}}) "
                f"MERGE (p)-[:AWARDED]->(a);"
            )
        
        cypher_statements.append("\n// Create SERVED_IN relationships")
        for edge in self.edges['SERVED_IN']:
            from_id = json.dumps(edge['from'], ensure_ascii=False)
            to_id = json.dumps(edge['to'], ensure_ascii=False)
            cypher_statements.append(
                f"MATCH (p:Politician {{id: {from_id}}}), (m:MilitaryCareer {{id: {to_id}}}) "
                f"MERGE (p)-[:SERVED_IN]->(m);"
            )
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cypher_statements))
        
        log.info(f"✓ Created Cypher script with {len(cypher_statements)} statements")
        log.info(f"✓ Completed!")


def main():
    """Main function"""
    
    input_file = 'data/processed/politicians_data.json'
    output_json_file = 'data/processed/knowledge_graph.json'
    output_cypher_file = 'data/processed/neo4j_import.cypher'
    
    builder = KnowledgeGraphBuilder()
    
    builder.build_from_file(input_file)
    
    builder.export_to_json(output_json_file)
    
    builder.export_to_neo4j_cypher(output_cypher_file)
    
    log.info(f"\n{'='*60}")
    log.info(f"ALL COMPLETED!")
    log.info(f"{'='*60}")
    log.info(f"JSON file: {output_json_file}")
    log.info(f"Cypher file: {output_cypher_file}")
    log.info(f"{'='*60}\n")


if __name__ == "__main__":
    main()
