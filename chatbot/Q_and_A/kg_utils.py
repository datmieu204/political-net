"""
Knowledge Graph utilities for loading, querying, and verifying reasoning paths.
"""

import json
import logging
from typing import Dict, List, Tuple, Optional, Any, Set
import networkx as nx
from collections import defaultdict

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """Wrapper for Knowledge Graph with NetworkX backend."""
    
    def __init__(self, kg_path: str):
        """
        Load knowledge graph from JSON file.
        
        Args:
            kg_path: Path to knowledge_graph_enriched.json
        """
        self.kg_path = kg_path
        self.graph = nx.MultiDiGraph()
        self.nodes_by_id = {}
        self.name_to_ids = defaultdict(list)
        self.nodes_by_type = defaultdict(list)
        self.edge_types = set()
        
        self._load_graph()
        logger.info(f"Loaded KG: {self.graph.number_of_nodes()} nodes, "
                   f"{self.graph.number_of_edges()} edges")
    
    def _load_graph(self):
        """Load graph from JSON into NetworkX."""
        with open(self.kg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Load nodes
        if 'nodes' in data:
            nodes_dict = data['nodes']
            for node_type, nodes_list in nodes_dict.items():
                for node in nodes_list:
                    node_id = node['id']
                    node_name = node.get('name', '')
                    node_props = node.get('properties', {})
                    
                    self.graph.add_node(
                        node_id,
                        type=node_type,
                        name=node_name,
                        properties=node_props
                    )
                    
                    self.nodes_by_id[node_id] = {
                        'id': node_id,
                        'type': node_type,
                        'name': node_name,
                        'properties': node_props
                    }
                    
                    # Index by name (case-insensitive)
                    if node_name:
                        normalized_name = node_name.lower().strip()
                        self.name_to_ids[normalized_name].append(node_id)
                    
                    self.nodes_by_type[node_type].append(node_id)
        
        # Load edges
        if 'edges' in data:
            edges_dict = data['edges']
            for edge_type, edges_list in edges_dict.items():
                self.edge_types.add(edge_type)
                for edge in edges_list:
                    from_id = edge['from']
                    to_id = edge['to']
                    edge_props = edge.get('properties', {})
                    
                    self.graph.add_edge(
                        from_id,
                        to_id,
                        key=edge_type,
                        type=edge_type,
                        properties=edge_props
                    )
        
        logger.info(f"Node types: {list(self.nodes_by_type.keys())}")
        logger.info(f"Edge types: {list(self.edge_types)}")
    
    def get_node(self, node_id: str) -> Optional[Dict]:
        """Get node by ID."""
        return self.nodes_by_id.get(node_id)
    
    def get_node_by_name(self, name: str) -> List[str]:
        """Get node IDs by name (case-insensitive)."""
        normalized = name.lower().strip()
        return self.name_to_ids.get(normalized, [])
    
    def get_nodes_by_type(self, node_type: str) -> List[str]:
        """Get all node IDs of a given type."""
        return self.nodes_by_type.get(node_type, [])
    
    def get_edge_between(self, from_id: str, to_id: str) -> List[Dict]:
        """Get all edges between two nodes."""
        if not self.graph.has_edge(from_id, to_id):
            return []
        
        edges = []
        edge_data = self.graph.get_edge_data(from_id, to_id)
        for key, data in edge_data.items():
            edges.append({
                'from': from_id,
                'to': to_id,
                'type': data['type'],
                'properties': data.get('properties', {})
            })
        return edges
    
    def get_outgoing_edges(self, node_id: str) -> List[Dict]:
        """Get all outgoing edges from a node."""
        if node_id not in self.graph:
            return []
        
        edges = []
        for _, to_id, key, data in self.graph.out_edges(node_id, keys=True, data=True):
            edges.append({
                'from': node_id,
                'to': to_id,
                'type': data['type'],
                'properties': data.get('properties', {})
            })
        return edges
    
    def get_shortest_path(self, from_id: str, to_id: str, max_length: int = 4, 
                          include_edge_props: bool = False) -> Optional[any]:
        """
        Get shortest path between two nodes.
        
        Args:
            from_id: Source node ID
            to_id: Target node ID
            max_length: Maximum path length (number of edges)
            include_edge_props: If True, return (path, edge_props_list), else just path
        
        Returns:
            If include_edge_props=False:
                List alternating [node_id, edge_type, node_id, edge_type, ...]
            If include_edge_props=True:
                Tuple (path, edge_props_list) where edge_props_list contains properties for each edge
            Returns None if no path exists or path too long.
        """
        if from_id not in self.graph or to_id not in self.graph:
            return None
        
        try:
            # Get shortest path (list of node IDs)
            node_path = nx.shortest_path(self.graph, from_id, to_id)
            
            if len(node_path) - 1 > max_length:
                return None
            
            # Build alternating path with edge types
            full_path = [node_path[0]]
            edge_props_list = []
            
            for i in range(len(node_path) - 1):
                src = node_path[i]
                dst = node_path[i + 1]
                
                # Get edge type and properties (use first edge if multiple)
                edge_data = self.graph.get_edge_data(src, dst)
                if edge_data:
                    first_edge = list(edge_data.values())[0]
                    edge_type = first_edge['type']
                    edge_props = first_edge.get('properties', {})
                    
                    full_path.append(edge_type)
                    full_path.append(dst)
                    edge_props_list.append(edge_props)
            
            if include_edge_props:
                return (full_path, edge_props_list)
            else:
                return full_path
            
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def verify_path(self, path: List[str]) -> bool:
        """
        Verify that a reasoning path exists in the graph.
        
        Args:
            path: Alternating list [node_id, edge_type, node_id, edge_type, ...]
        
        Returns:
            True if path is valid, False otherwise.
        """
        if not path or len(path) < 3 or len(path) % 2 != 1:
            return False
        
        # Check all nodes exist
        for i in range(0, len(path), 2):
            if path[i] not in self.graph:
                return False
        
        # Check all edges exist
        for i in range(0, len(path) - 2, 2):
            src = path[i]
            edge_type = path[i + 1]
            dst = path[i + 2]
            
            # Check if edge exists
            if not self.graph.has_edge(src, dst):
                return False
            
            # Verify edge type matches
            edge_data = self.graph.get_edge_data(src, dst)
            found = False
            for key, data in edge_data.items():
                if data['type'] == edge_type:
                    found = True
                    break
            
            if not found:
                return False
        
        return True
    
    def get_answer_from_path(self, path: List[str]) -> Optional[str]:
        """
        Extract the final answer (target node) from a reasoning path.
        
        Args:
            path: Alternating list [node_id, edge_type, node_id, edge_type, ...]
        
        Returns:
            The name of the final node, or None if invalid path.
        """
        if not path or len(path) < 3 or len(path) % 2 != 1:
            return None
        
        final_node_id = path[-1]
        node = self.get_node(final_node_id)
        return node['name'] if node else None
    
    def find_all_paths_bounded(self, from_id: str, to_id: str, 
                               min_length: int = 2, max_length: int = 4) -> List[List]:
        """
        Find all simple paths between two nodes with length constraints.
        
        Args:
            from_id: Source node ID
            to_id: Target node ID
            min_length: Minimum path length (number of hops)
            max_length: Maximum path length (number of hops)
        
        Returns:
            List of paths in alternating format
        """
        if from_id not in self.graph or to_id not in self.graph:
            return []
        
        paths = []
        try:
            for node_path in nx.all_simple_paths(self.graph, from_id, to_id, 
                                                   cutoff=max_length):
                hop_count = len(node_path) - 1
                if hop_count < min_length:
                    continue
                
                # Convert to alternating format
                full_path = [node_path[0]]
                for i in range(len(node_path) - 1):
                    src = node_path[i]
                    dst = node_path[i + 1]
                    edge_data = self.graph.get_edge_data(src, dst)
                    if edge_data:
                        edge_type = list(edge_data.values())[0]['type']
                        full_path.append(edge_type)
                        full_path.append(dst)
                
                paths.append(full_path)
        except nx.NetworkXNoPath:
            pass
        
        return paths
    
    def verify_fact(self, subject: str, relation: str, obj: str, 
                    fuzzy_match: bool = True) -> bool:
        """
        Verify if a fact (subject, relation, object) exists in KG.
        
        Args:
            subject: Subject entity name
            relation: Relation type
            obj: Object entity name
            fuzzy_match: If True, use name matching; if False, expect IDs
        
        Returns:
            True if fact exists, False otherwise.
        """
        if fuzzy_match:
            # Find nodes by name
            subj_ids = self.get_node_by_name(subject)
            obj_ids = self.get_node_by_name(obj)
            
            if not subj_ids or not obj_ids:
                return False
            
            # Check if any combination has the relation
            for subj_id in subj_ids:
                for obj_id in obj_ids:
                    if self.graph.has_edge(subj_id, obj_id):
                        edge_data = self.graph.get_edge_data(subj_id, obj_id)
                        for key, data in edge_data.items():
                            if data['type'] == relation:
                                return True
            return False
        else:
            # Direct ID check
            if not self.graph.has_edge(subject, obj):
                return False
            
            edge_data = self.graph.get_edge_data(subject, obj)
            for key, data in edge_data.items():
                if data['type'] == relation:
                    return True
            return False
    
    def get_node_neighbors(self, node_id: str, edge_type: Optional[str] = None) -> List[str]:
        """Get neighbor node IDs, optionally filtered by edge type."""
        if node_id not in self.graph:
            return []
        
        neighbors = []
        for _, to_id, key, data in self.graph.out_edges(node_id, keys=True, data=True):
            if edge_type is None or data['type'] == edge_type:
                neighbors.append(to_id)
        
        return neighbors
    
    def get_random_nodes(self, node_type: str, count: int, seed: int = 42) -> List[str]:
        """Get random node IDs of a given type."""
        import random
        nodes = self.nodes_by_type.get(node_type, [])
        if not nodes:
            return []
        
        random.seed(seed)
        return random.sample(nodes, min(count, len(nodes)))


def fuzzy_match_name(name1: str, name2: str, threshold: float = 0.9) -> bool:
    """
    Fuzzy match two names using simple string similarity.
    
    Args:
        name1: First name
        name2: Second name
        threshold: Similarity threshold (0-1)
    
    Returns:
        True if names are similar enough
    """
    from difflib import SequenceMatcher
    
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()
    
    # Exact match
    if n1 == n2:
        return True
    
    # Substring match
    if n1 in n2 or n2 in n1:
        return True
    
    # Sequence similarity
    similarity = SequenceMatcher(None, n1, n2).ratio()
    return similarity >= threshold
