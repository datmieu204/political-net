"""Debug script to check TERM_DURATION edge generation."""
import sys
sys.path.insert(0, 'D:\\Github\\HungIsWorking\\political-net')

from chatbot.Q_and_A.generate_1hop_comprehensive import Comprehensive1HopGenerator
from chatbot.Q_and_A.kg_utils import KnowledgeGraph
from collections import Counter

kg = KnowledgeGraph('data/processed/graph/knowledge_graph_enriched.json')

gen = Comprehensive1HopGenerator(kg)
virtual_edges = gen.extract_virtual_relations()

# Count by type
edge_counts = Counter([e['edge_type'] for e in virtual_edges])
print('Virtual edges:')
for edge_type, count in sorted(edge_counts.items()):
    print(f'  {edge_type}: {count}')

# Show sample TERM_DURATION edges
term_edges = [e for e in virtual_edges if e['edge_type'] == 'TERM_DURATION']
print(f'\nSample TERM_DURATION edges (first 10):')
for edge in term_edges[:10]:
    pos_name = edge['properties'].get('position_name', 'N/A')
    print(f'  {edge["from_name"]} -> {edge["to_name"]} (pos: {pos_name})')

# Check SERVED_AS edges with term properties
print('\n\nChecking SERVED_AS edges for term_start/term_end:')
served_as_with_terms = 0
for u, v, data in kg.graph.edges(data=True):
    if data.get('type') == 'SERVED_AS':
        props = data.get('properties', {})
        if props.get('term_start') or props.get('term_end'):
            served_as_with_terms += 1
            if served_as_with_terms <= 5:
                from_node = kg.get_node(u)
                to_node = kg.get_node(v)
                print(f'  {from_node.get("name")} -> {to_node.get("name")}')
                print(f'    term_start: {props.get("term_start")}')
                print(f'    term_end: {props.get("term_end")}')

print(f'\nTotal SERVED_AS edges with terms: {served_as_with_terms}')
