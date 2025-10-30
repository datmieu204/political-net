# ./graph/build_edges_.py

import json
import re

from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime

import sys
sys.path.append(str(Path(__file__).parent.parent))
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("build_succession_edges", log_file="logs/graph/build_succession_edges.log")

class SuccessionEdgeBuilder:
    def __init__(self):
        self.politician_name_to_id: Dict[str, str] = {}
        self.position_ids: Set[str] = set()
        self.succeeded_edges: List[Dict] = []
        self.preceded_edges: List[Dict] = []
        
        self.ignore_values = [
            'chức vụ kết thúc', 
            'đương nhiệm', 
            'incumbent', 
            'none', 
            'n/a', 
            '-',
            ''
        ]
    
    def _normalize_name(self, name: str) -> str:
        if not name:
            return ""
        return name.lower().strip()
    
    def extract_text_from_wikilink(self, text: str) -> str:
        if not text:
            return ""
        
        text = re.sub(r'<[^>]+>', '', text)
        
        match = re.search(r'\[\[([^|\]]+)\|([^\]]+)\]\]', text)
        if match:
            return match.group(2).strip()
        
        match = re.search(r'\[\[([^\]]+)\]\]', text)
        if match:
            return match.group(1).strip()
        
        return text.strip()
    
    def extract_names_from_wikilink(self, text: str) -> List[str]:
        if not text:
            return []
        
        main_text = self.extract_text_from_wikilink(text)
        
        names = []
        for delimiter in [',', ';', '<br>', '<br/>', '\n']:
            if delimiter in main_text:
                parts = main_text.split(delimiter)
                for part in parts:
                    clean_name = self.extract_text_from_wikilink(part.strip())
                    if clean_name:
                        names.append(clean_name)
                return names
        
        if main_text:
            names.append(main_text)
        
        return names
    
    def load_knowledge_graph(self, kg_file: str):
        log.info(f"Loading knowledge graph from: {kg_file}")
        
        with open(kg_file, 'r', encoding='utf-8') as f:
            kg_data = json.load(f)
        
        politicians = kg_data.get('nodes', {}).get('Politician', [])
        for politician in politicians:
            name = politician.get('name', '')
            pol_id = politician.get('id', '')
            if name and pol_id:
                normalized = self._normalize_name(name)
                self.politician_name_to_id[normalized] = pol_id
        
        positions = kg_data.get('nodes', {}).get('Position', [])
        for position in positions:
            pos_id = position.get('id', '')
            if pos_id:
                self.position_ids.add(pos_id)
        
        return kg_data
    
    def should_ignore(self, value: str) -> bool:
        if not value:
            return True
        normalized = value.lower().strip()
        return normalized in self.ignore_values
    
    def get_politician_id(self, name: str) -> Optional[str]:
        if not name or self.should_ignore(name):
            return None
        
        normalized = self._normalize_name(name)
        return self.politician_name_to_id.get(normalized)
    
    def build_succession_edges_for_politician(self, politician_data: Dict) -> int:
        title = politician_data.get('title', '')
        if not title:
            return 0
        
        source_id = str(politician_data.get('id', '')).strip()
        politician_id = self.get_politician_id(title)
        
        if not politician_id:
            return 0
        
        infobox = politician_data.get('infobox_normalized', politician_data.get('infobox', {}))
        edges_created = 0
        
        for i in range(1, 15):
            office_key = 'office' if i == 1 else f'office{i}'
            office = infobox.get(office_key, '')
            
            if not office:
                continue

            predecessor_key = 'predecessor' if i == 1 else f'predecessor{i}'
            successor_key = 'successor' if i == 1 else f'successor{i}'
            
            predecessor = infobox.get(predecessor_key, '')
            successor = infobox.get(successor_key, '')

            position_id = f"pos{source_id}_{str(i).zfill(3)}"
            
            if predecessor and not self.should_ignore(predecessor):
                predecessor_names = self.extract_names_from_wikilink(predecessor)
                for pred_name in predecessor_names:
                    pred_id = self.get_politician_id(pred_name)
                    if pred_id:
                        edge = {
                            'from': politician_id,
                            'to': pred_id,
                            'type': 'SUCCEEDED',
                            'properties': {
                                'position_id': position_id
                            }
                        }
                        self.succeeded_edges.append(edge)
                        edges_created += 1
            
            if successor and not self.should_ignore(successor):
                successor_names = self.extract_names_from_wikilink(successor)
                for succ_name in successor_names:
                    succ_id = self.get_politician_id(succ_name)
                    if succ_id:
                        edge = {
                            'from': politician_id,
                            'to': succ_id,
                            'type': 'PRECEDED',
                            'properties': {
                                'position_id': position_id
                            }
                        }
                        self.preceded_edges.append(edge)
                        edges_created += 1
        
        return edges_created
    
    def build_from_file(self, politicians_file: str, kg_file: str):
        log.info(f"Politicians file: {politicians_file}")
        
        kg_data = self.load_knowledge_graph(kg_file)
        
        with open(politicians_file, 'r', encoding='utf-8') as f:
            politicians_data = json.load(f)
        
        total_politicians = len(politicians_data)
        log.info(f"Processing {total_politicians} politicians...")
        
        total_edges = 0
        for idx, politician_data in enumerate(politicians_data, 1):
            edges_count = self.build_succession_edges_for_politician(politician_data)
            total_edges += edges_count
            
            if idx % 100 == 0:
                log.info(f"Processed {idx}/{total_politicians} politicians, created {total_edges} edges")
        
        log.info(f"\nCompleted processing all politicians")
        return kg_data
    
    def update_knowledge_graph(self, kg_data: Dict, output_file: str):
        log.info(f"\nUpdating knowledge graph...")
        
        if 'edges' not in kg_data:
            kg_data['edges'] = {}
        
        kg_data['edges']['SUCCEEDED'] = self.succeeded_edges
        kg_data['edges']['PRECEDED'] = self.preceded_edges
        
        if 'metadata' in kg_data:
            kg_data['metadata']['updated_at'] = datetime.now().isoformat()
            kg_data['metadata']['total_edges'] = sum(len(edges) for edges in kg_data['edges'].values())
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(kg_data, f, ensure_ascii=False, indent=2)
        
        log.info(f"Updated knowledge graph: {output_file}")

    
    def export_succession_to_cypher(self, output_file: str):
        log.info(f"\nExporting succession edges to Cypher: {output_file}")
        
        cypher_statements = []
        cypher_statements.append("// Neo4j Cypher Script - Succession Edges")
        cypher_statements.append(f"// Generated at: {datetime.now().isoformat()}")
        cypher_statements.append(f"// Total SUCCEEDED edges: {len(self.succeeded_edges)}")
        cypher_statements.append(f"// Total PRECEDED edges: {len(self.preceded_edges)}")
        cypher_statements.append("")
        
        if self.succeeded_edges:
            cypher_statements.append("// Create SUCCEEDED relationships")
            for edge in self.succeeded_edges:
                from_id = json.dumps(edge['from'])
                to_id = json.dumps(edge['to'])
                
                props = edge.get('properties', {})
                if props:
                    props_str = ', '.join([f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in props.items() if v])
                    props_formatted = f" {{{props_str}}}" if props_str else ""
                else:
                    props_formatted = ""
                
                cypher_statements.append(
                    f"MATCH (a:Politician {{id: {from_id}}}), (b:Politician {{id: {to_id}}}) "
                    f"MERGE (a)-[:SUCCEEDED{props_formatted}]->(b);"
                )
        
        if self.preceded_edges:
            cypher_statements.append("")
            cypher_statements.append("// Create PRECEDED relationships")
            for edge in self.preceded_edges:
                from_id = json.dumps(edge['from'])
                to_id = json.dumps(edge['to'])
                
                props = edge.get('properties', {})
                if props:
                    props_str = ', '.join([f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in props.items() if v])
                    props_formatted = f" {{{props_str}}}" if props_str else ""
                else:
                    props_formatted = ""
                
                cypher_statements.append(
                    f"MATCH (a:Politician {{id: {from_id}}}), (b:Politician {{id: {to_id}}}) "
                    f"MERGE (a)-[:PRECEDED{props_formatted}]->(b);"
                )
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cypher_statements))

if __name__ == '__main__':
    base_dir = Path(__file__).parent.parent
    politicians_file = base_dir / 'data' / 'processed' / 'infobox' / 'politicians_data_normalized.json'
    kg_file = base_dir / 'data' / 'processed' / 'graph' / 'knowledge_graph.json'
    output_json_file = kg_file
    output_cypher_file = base_dir / 'data' / 'processed' / 'graph' / 'succession_edges.cypher'
    
    builder = SuccessionEdgeBuilder()
    kg_data = builder.build_from_file(str(politicians_file), str(kg_file))
    builder.update_knowledge_graph(kg_data, str(output_json_file))
    builder.export_succession_to_cypher(str(output_cypher_file))
