#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
from collections import Counter, defaultdict

import networkx as nx
import community.community_louvain as community_louvain

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import settings


class PoliticalCommunityAnalyzer:
    def __init__(self, graph_file_path):
        self.graph_file_path = graph_file_path
        self.graph = nx.Graph()
        self.politicians_data = {}
        self.positions_data = {}
        self.communities = {}
        self.raw_data = None
        
    def load_graph(self):
        print("Loading graph data...")
        with open(self.graph_file_path, 'r', encoding='utf-8') as f:
            self.raw_data = json.load(f)
        
        # Load politicians
        for pol in self.raw_data['nodes']['Politician']:
            self.politicians_data[pol['id']] = {
                'name': pol['name'],
                'birth_date': pol['properties'].get('birth_date', ''),
                'death_date': pol['properties'].get('death_date', ''),
                'party': pol['properties'].get('party', 'Unknown'),
            }
            self.graph.add_node(pol['id'], node_type='Politician', **self.politicians_data[pol['id']])
        
        # Load positions
        for pos in self.raw_data['nodes']['Position']:
            self.positions_data[pos['id']] = {'name': pos['name']}
            self.graph.add_node(pos['id'], node_type='Position', **self.positions_data[pos['id']])
        
        # Build edges based on shared positions
        position_to_politicians = defaultdict(list)
        for edge in self.raw_data['edges'].get('SERVED_AS', []):
            if edge['from'] in self.politicians_data and edge['to'] in self.positions_data:
                position_to_politicians[edge['to']].append(edge['from'])
        
        edge_count = 0
        for politicians in position_to_politicians.values():
            for i in range(len(politicians)):
                for j in range(i + 1, len(politicians)):
                    if self.graph.has_edge(politicians[i], politicians[j]):
                        self.graph[politicians[i]][politicians[j]]['weight'] += 1
                    else:
                        self.graph.add_edge(politicians[i], politicians[j], weight=1)
                        edge_count += 1
        
        # Remove non-politician nodes
        self.graph.remove_nodes_from([n for n in self.graph.nodes() if n not in self.politicians_data])
        
        print(f"Graph loaded: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        
    def detect_communities(self, resolution=1.0):
        print(f"\nDetecting communities (resolution={resolution})...")
        partition = community_louvain.best_partition(self.graph, weight='weight', 
                                                     resolution=resolution, random_state=42)
        
        communities_dict = defaultdict(list)
        for node, comm_id in partition.items():
            communities_dict[comm_id].append(node)
        
        self.communities = dict(communities_dict)
        modularity = community_louvain.modularity(partition, self.graph, weight='weight')
        
        print(f"Found {len(self.communities)} communities (modularity={modularity:.4f})")
        self._merge_small_communities(min_size=10)
        print(f"After merging: {len(self.communities)} communities")
        
        return partition
    
    def _merge_small_communities(self, min_size=10):
        while True:
            small_comm = min((c for c, m in self.communities.items() if len(m) < min_size),
                           key=lambda c: len(self.communities[c]), default=None)
            if not small_comm:
                break
            
            connections = defaultdict(int)
            for node in self.communities[small_comm]:
                for neighbor in self.graph.neighbors(node):
                    for comm_id, members in self.communities.items():
                        if comm_id != small_comm and neighbor in members:
                            connections[comm_id] += 1
                            break
            
            target = max(connections.items(), key=lambda x: x[1])[0] if connections else \
                     max(self.communities.items(), key=lambda x: len(x[1]) if x[0] != small_comm else 0)[0]
            
            self.communities[target].extend(self.communities[small_comm])
            del self.communities[small_comm]
    
    def analyze_community(self, comm_id, members):
        subgraph = self.graph.subgraph(members)
        
        # Party distribution
        parties = [self.politicians_data[n]['party'] for n in members]
        party_dist = {p: {'count': c, 'percentage': c/len(parties)*100} 
                     for p, c in Counter(parties).items()}
        
        # Centrality metrics
        degree_cent = nx.degree_centrality(subgraph)
        central_node = max(degree_cent, key=degree_cent.get)
        
        try:
            eigen_cent = nx.eigenvector_centrality(subgraph, weight='weight', max_iter=1000) if subgraph.number_of_edges() > 0 else {}
            central_eigen = max(eigen_cent, key=eigen_cent.get) if eigen_cent else central_node
        except:
            eigen_cent = {}
            central_eigen = central_node
        
        # Birth year statistics
        birth_years = []
        for n in members:
            bd = self.politicians_data[n]['birth_date']
            dd = self.politicians_data[n]['death_date']
            if bd and bd.strip():
                try:
                    by = int(bd.split('-')[0])
                    if 1800 < by <= 2025:
                        if not dd or not dd.strip() or int(dd.split('-')[0]) > by:
                            birth_years.append(by)
                except:
                    pass
        
        birth_stats = {'min': min(birth_years), 'max': max(birth_years), 
                      'avg': sum(birth_years)/len(birth_years), 'count': len(birth_years)} if birth_years else {}
        
        # Term start statistics
        term_years = []
        for edge in self.raw_data['edges'].get('SERVED_AS', []):
            if edge['from'] in members:
                ts = edge.get('properties', {}).get('term_start', '')
                if ts and ts.strip():
                    try:
                        year = int(ts.split('-')[0].strip())
                        if 1900 <= year <= 2025:
                            term_years.append(year)
                    except:
                        pass
        
        term_stats = {'min': min(term_years), 'max': max(term_years),
                     'avg': sum(term_years)/len(term_years), 'count': len(term_years)} if term_years else {}
        
        return {
            'id': comm_id,
            'num_nodes': subgraph.number_of_nodes(),
            'num_edges': subgraph.number_of_edges(),
            'density': nx.density(subgraph),
            'party_distribution': party_dist,
            'node_type_stats': self._analyze_connected_nodes(members),
            'central_node': {
                'id': central_node,
                'name': self.politicians_data[central_node]['name'],
                'party': self.politicians_data[central_node]['party'],
                'birth_date': self.politicians_data[central_node]['birth_date'],
                'degree_centrality': degree_cent[central_node],
                'degree': subgraph.degree(central_node)
            },
            'central_node_eigenvector': {
                'id': central_eigen,
                'name': self.politicians_data[central_eigen]['name'],
                'party': self.politicians_data[central_eigen]['party'],
                'birth_date': self.politicians_data[central_eigen]['birth_date'],
                'eigenvector_centrality': eigen_cent.get(central_eigen, 0)
            },
            'birth_year_stats': birth_stats,
            'term_year_stats': term_stats,
            'members': members
        }
    
    def _analyze_connected_nodes(self, members):
        node_types = ['Location', 'Position', 'Award', 'AlmaMater', 'AcademicTitle', 
                     'MilitaryRank', 'MilitaryCareer', 'Campaigns']
        node_data = {nt: defaultdict(int) for nt in node_types}
        
        for edge_type, edges in self.raw_data['edges'].items():
            for edge in edges:
                if edge['from'] in members:
                    for nt in node_types:
                        if nt in self.raw_data['nodes']:
                            for node in self.raw_data['nodes'][nt]:
                                if node['id'] == edge['to']:
                                    node_data[nt][node['name']] += 1
                                    break
        
        return {nt: {'total': sum(counts.values()),
                     'items': {n: {'count': c, 'percentage': c/sum(counts.values())*100}
                              for n, c in sorted(counts.items(), key=lambda x: x[1], reverse=True)}}
                for nt, counts in node_data.items() if counts}
    
    def analyze_all_communities(self):
        print("\nAnalyzing communities...")
        results = {cid: self.analyze_community(cid, members) 
                  for cid, members in self.communities.items()}
        return dict(sorted(results.items(), key=lambda x: x[1]['num_nodes'], reverse=True))
    
    def export_member_lists(self, results):
        import csv
        os.makedirs(settings.OUTPUT_LIST_MEMBERS, exist_ok=True)
        
        for idx, (_, analysis) in enumerate(results.items(), 1):
            csv_file = os.path.join(settings.OUTPUT_LIST_MEMBERS, f'list_members_cluster_{idx}.csv')
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Name', 'ID', 'Birth Year'])
                
                members_info = sorted([{
                    'name': self.politicians_data[mid]['name'],
                    'id': mid,
                    'birth_year': self.politicians_data[mid]['birth_date'].split('-')[0] 
                                  if self.politicians_data[mid]['birth_date'] else ''
                } for mid in analysis['members']], key=lambda x: x['name'])
                
                for m in members_info:
                    writer.writerow([m['name'], m['id'], m['birth_year']])
    
    def export_results(self, results, output_file):
        print("\nExporting results...")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"{'='*100}\nPOLITICAL COMMUNITY ANALYSIS (Louvain)\n{'='*100}\n\n")
            f.write(f"OVERVIEW\n{'-'*100}\n")
            f.write(f"Communities: {len(results)}\n")
            f.write(f"Nodes: {self.graph.number_of_nodes()}\n")
            f.write(f"Edges: {self.graph.number_of_edges()}\n")
            f.write(f"Density: {nx.density(self.graph):.4f}\n\n")
            
            for idx, (cid, a) in enumerate(results.items(), 1):
                f.write(f"{'='*100}\nCOMMUNITY #{idx}\n{'='*100}\n\n")
                
                f.write(f"1. BASIC INFO\n{'-'*100}\n")
                f.write(f"Members: {a['num_nodes']}\nEdges: {a['num_edges']}\nDensity: {a['density']:.4f}\n\n")
                
                f.write(f"2. PARTY DISTRIBUTION\n{'-'*100}\n")
                for party, stats in sorted(a['party_distribution'].items(), key=lambda x: x[1]['count'], reverse=True):
                    f.write(f"  • {party}: {stats['count']} ({stats['percentage']:.2f}%)\n")
                f.write("\n")
                
                if a.get('node_type_stats'):
                    f.write(f"3. CONNECTED NODES\n{'-'*100}\n")
                    for nt, data in a['node_type_stats'].items():
                        f.write(f"\n3.{list(a['node_type_stats'].keys()).index(nt)+1}. {nt.upper()}\n")
                        f.write(f"Total: {data['total']}\nTop 10:\n")
                        for i, (name, stats) in enumerate(list(data['items'].items())[:10], 1):
                            f.write(f"  {i:2d}. {name:50s}: {stats['count']:3d} ({stats['percentage']:5.2f}%)\n")
                    f.write("\n")
                
                f.write(f"4. CENTRAL NODE (Degree)\n{'-'*100}\n")
                c = a['central_node']
                f.write(f"Name: {c['name']}\nParty: {c['party']}\nBirth: {c['birth_date']}\n")
                f.write(f"Degree Centrality: {c['degree_centrality']:.4f}\nConnections: {c['degree']}\n\n")
                
                f.write(f"5. CENTRAL NODE (Eigenvector)\n{'-'*100}\n")
                ce = a['central_node_eigenvector']
                f.write(f"Name: {ce['name']}\nParty: {ce['party']}\nBirth: {ce['birth_date']}\n")
                f.write(f"Eigenvector Centrality: {ce['eigenvector_centrality']:.4f}\n\n")
                
                f.write(f"6. BIRTH YEAR STATS\n{'-'*100}\n")
                if a['birth_year_stats']:
                    bs = a['birth_year_stats']
                    f.write(f"Range: {bs['min']}-{bs['max']} (span: {bs['max']-bs['min']} years)\n")
                    f.write(f"Average: {bs['avg']:.1f}\nCount: {bs['count']}/{a['num_nodes']}\n")
                else:
                    f.write("No data\n")
                f.write("\n")
                
                f.write(f"7. TERM START STATS\n{'-'*100}\n")
                if a['term_year_stats']:
                    ts = a['term_year_stats']
                    f.write(f"Range: {ts['min']}-{ts['max']} (span: {ts['max']-ts['min']} years)\n")
                    f.write(f"Average: {ts['avg']:.1f}\nCount: {ts['count']}\n")
                else:
                    f.write("No data\n")
                f.write("\n")
                
                f.write(f"8. TOP 10 CONNECTED MEMBERS\n{'-'*100}\n")
                subgraph = self.graph.subgraph(a['members'])
                for rank, (node, deg) in enumerate(sorted(subgraph.degree(), key=lambda x: x[1], reverse=True)[:10], 1):
                    pol = self.politicians_data[node]
                    f.write(f"{rank:2d}. {pol['name']:30s} - {deg:3d} connections - {pol['party']}\n")
                f.write("\n\n")
        
        print(f"Results exported to: {output_file}")
    
    def run_analysis(self, output_file=None, resolution=1.5):
        self.load_graph()
        self.detect_communities(resolution=resolution)
        results = self.analyze_all_communities()
        
        if output_file is None:
            os.makedirs(settings.OUTPUT_ANALYSIS_DIR, exist_ok=True)
            output_file = os.path.join(settings.OUTPUT_ANALYSIS_DIR, 'community_analysis_results.txt')
        
        self.export_results(results, output_file)
        self.export_member_lists(results)
        print("\nAnalysis complete!")
        return results


def main():
    graph_file = settings.OUTPUT_ENRICHED_GRAPH_FILE
    
    if not os.path.exists(graph_file):
        print(f"Error: File not found: {graph_file}")
        return
    
    print(f"\nPolitical Community Analyzer\nInput: {graph_file}\n")
    analyzer = PoliticalCommunityAnalyzer(graph_file)
    results = analyzer.run_analysis(resolution=1.5)
    
    print(f"\nDetected {len(results)} communities")

if __name__ == '__main__':
    main()