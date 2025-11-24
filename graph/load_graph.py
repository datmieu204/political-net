# graph/load_graph.py

import json
import networkx as nx
from neo4j import GraphDatabase

from utils.config import settings
from utils._logger import get_logger

logger = get_logger("graph.load_graph", log_file="logs/graph/load_graph.log")


class GraphLoader:

    def __init__(self, use_neo4j: bool = True):
        """
        Initialize GraphLoader
        
        Args:
            use_neo4j: True = Neo4j, False = JSON
        """
        self.use_neo4j = use_neo4j
        self.driver = None
        
        if use_neo4j:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
    
    def close(self):
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def load_from_neo4j(self, directed: bool = True) -> tuple:
        """
        Args:
            directed: True = MultiDiGraph, False = MultiGraph (undirected)
        
        Returns:
            tuple: (graph, node_info)
                - graph: NetworkX MultiDiGraph/MultiGraph
                - node_info: Dict containing detailed info of each node
        """
        if not self.use_neo4j or not self.driver:
            raise ValueError("Neo4j driver not initialized. Set use_neo4j=True in constructor.")
        
        logger.info("Loading graph from Neo4j...")
        
        graph = nx.MultiDiGraph() if directed else nx.MultiGraph()
        node_info = {}
        
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            # Load all nodes with valid IDs
            node_query = """
            MATCH (n)
            WHERE n.id IS NOT NULL
            RETURN n.id AS id, n.name AS name, labels(n)[0] AS type, properties(n) AS props
            """
            result = session.run(node_query)
            
            for record in result:
                node_id = record["id"]
                if not node_id:
                    continue
                    
                graph.add_node(node_id)
                node_info[node_id] = {
                    "name": record["name"] or "",
                    "type": record["type"] or "Unknown",
                    "properties": record["props"] or {}
                }
            
            # Load all edges between valid nodes
            edge_query = """
            MATCH (a)-[r]->(b)
            WHERE a.id IS NOT NULL AND b.id IS NOT NULL
            RETURN a.id AS from, b.id AS to, type(r) AS rel_type, properties(r) AS props
            """
            result = session.run(edge_query)
            
            for record in result:
                from_id = record["from"]
                to_id = record["to"]
                
                if from_id and to_id and from_id in graph and to_id in graph:
                    graph.add_edge(
                        from_id,
                        to_id,
                        rel_type=record["rel_type"] or "UNKNOWN",
                        properties=record["props"] or {}
                    )
        
        logger.info(f"Loaded graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
        return graph, node_info
    
    def load_from_json(self, json_file: str, directed: bool = True) -> tuple:
        """
        Args:
            json_file: Path to JSON file
            directed: True = MultiDiGraph, False = MultiGraph (undirected)
        
        Returns:
            tuple: (graph, node_info)
                - graph: NetworkX MultiDiGraph/MultiGraph
                - node_info: Dict containing detailed info of each node
        """
        logger.info(f"Loading graph from {json_file}")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        graph = nx.MultiDiGraph() if directed else nx.MultiGraph()
        node_info = {}
        
        # Load nodes
        if 'nodes' in data:
            for node_type, node_list in data['nodes'].items():
                for node in node_list:
                    node_id = node.get('id')
                    if node_id:
                        graph.add_node(node_id)
                        node_info[node_id] = {
                            "name": node.get('name', ''),
                            "type": node.get('type', node_type),
                            "properties": node.get('properties', {})
                        }
        
        # Load edges
        if 'edges' in data:
            for edge_type, edge_list in data['edges'].items():
                for edge in edge_list:
                    from_id = edge.get('from')
                    to_id = edge.get('to')
                    
                    if from_id and to_id and from_id in graph and to_id in graph:
                        graph.add_edge(
                            from_id,
                            to_id,
                            rel_type=edge_type,
                            properties=edge.get('properties', {})
                        )
        
        logger.info(f"Loaded graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
        return graph, node_info
    
    def load_subgraph_by_type(self, source: str, node_types: list = None, 
                              edge_types: list = None, **kwargs) -> tuple:
        """
        Load a subgraph by node types or edge types
        
        Args:
            source: "neo4j" or path to JSON file
            node_types: List of node types to include (None = include all)
            edge_types: List of edge types to include (None = include all)
            **kwargs: Additional args for load methods (directed, etc.)
        
        Returns:
            tuple: (graph, node_info) - Filtered subgraph
        """
        # Load full graph
        if source == "neo4j":
            graph, node_info = self.load_from_neo4j(**kwargs)
        else:
            graph, node_info = self.load_from_json(source, **kwargs)
        
        # Filter nodes by type
        if node_types:
            nodes_to_keep = [
                node_id for node_id, info in node_info.items()
                if info.get("type") in node_types
            ]
            graph = graph.subgraph(nodes_to_keep).copy()
            node_info = {k: v for k, v in node_info.items() if k in nodes_to_keep}
        
        # Filter edges by type
        if edge_types:
            edges_to_remove = [
                (u, v, k) for u, v, k, data in graph.edges(keys=True, data=True)
                if data.get("rel_type") not in edge_types
            ]
            graph.remove_edges_from(edges_to_remove)
        
        logger.info(f"Filtered graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
        return graph, node_info


# Global functions
def load_graph_from_neo4j(directed: bool = True) -> tuple:
    """
    Load graph from Neo4j
    
    Args:
        directed: True = MultiDiGraph, False = MultiGraph
    
    Returns:
        tuple: (graph, node_info)
    """
    loader = GraphLoader(use_neo4j=True)
    try:
        return loader.load_from_neo4j(directed=directed)
    finally:
        loader.close()


def load_graph_from_json(json_file: str, directed: bool = True) -> tuple:
    """
    Load graph from JSON
    
    Args:
        json_file: Path to JSON file
        directed: True = MultiDiGraph, False = MultiGraph
    
    Returns:
        tuple: (graph, node_info)
    """
    loader = GraphLoader(use_neo4j=False)
    return loader.load_from_json(json_file, directed=directed)


if __name__ == "__main__":
    try:
        graph, node_info = load_graph_from_neo4j()
    except Exception as e:
        print(f"Neo4j failed: {e}")
    
    try:
        graph, node_info = load_graph_from_json("data/processed/graph/knowledge_graph_enriched.json")
    except Exception as e:
        print(f"JSON failed: {e}")

