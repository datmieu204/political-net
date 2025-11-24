# ./graph/export_graph.py

import os
import json
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv
load_dotenv()

from utils.config import settings
from utils._logger import get_logger
logger = get_logger("graph.export_graph", log_file="logs/graph/export_graph.log")


class Neo4jGraphExporter:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    
    def close(self):
        if self.driver:
            self.driver.close()
    
    def export_graph(self, output_file: str = None):
        if output_file is None:
            output_file = f"data/processed/graph/knowledge_graph_enriched.json"
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        logger.info(f"Export to {output_file}")
        
        graph_data = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "export_mode": "full_database",
                "total_nodes": 0,
                "total_edges": 0,
                "node_types": [],
                "edge_types": []
            },
            "nodes": {},
            "edges": {}
        }
        
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            node_labels = ["Politician", "Position", "Location", "Award", "MilitaryCareer", 
                          "MilitaryRank", "Campaigns", "AlmaMater", "AcademicTitle"]
            
            for label in node_labels:
                print(f"Exporting {label} nodes...")
                query = f"""
                MATCH (n:{label})
                RETURN n.id AS id, n.name AS name, n.type AS type, properties(n) AS props
                """
                
                result = session.run(query)
                
                nodes_list = []
                for record in result:
                    node_data = {
                        "id": record["id"],
                        "type": record["type"] or label,
                        "name": record["name"]
                    }
                    
                    props = record["props"]
                    filtered_props = {
                        k: v for k, v in props.items() 
                        if k not in ["id", "name", "type", "source", "created_at", "last_updated", "enriched"]
                    }
                    
                    if filtered_props:
                        node_data["properties"] = filtered_props
                    
                    nodes_list.append(node_data)
                
                if nodes_list:
                    graph_data["nodes"][label] = nodes_list
                    graph_data["metadata"]["total_nodes"] += len(nodes_list)
                    print(f"  → Exported {len(nodes_list)} {label} nodes")
            
            edge_types = ["SERVED_AS", "SUCCEEDED", "PRECEDED", "BORN_AT", "DIED_AT", 
                         "AWARDED", "SERVED_IN", "HAS_RANK", "FOUGHT_IN", "ALUMNUS_OF", 
                         "HAS_ACADEMIC_TITLE"]
            
            for edge_type in edge_types:
                print(f"Exporting {edge_type} edges...")
                query = f"""
                MATCH (a)-[r:{edge_type}]->(b)
                RETURN a.id AS from, b.id AS to, type(r) AS type, properties(r) AS props
                """
                
                result = session.run(query)
                
                edges_list = []
                for record in result:
                    edge_data = {
                        "from": record["from"],
                        "to": record["to"],
                        "type": record["type"]
                    }
                    
                    props = record["props"]
                    filtered_props = {
                        k: v for k, v in props.items() 
                        if k not in ["source", "created_at", "type"]
                    }
                    
                    if filtered_props:
                        edge_data["properties"] = filtered_props
                    
                    edges_list.append(edge_data)
                
                if edges_list:
                    graph_data["edges"][edge_type] = edges_list
                    graph_data["metadata"]["total_edges"] += len(edges_list)
                    print(f"  → Exported {len(edges_list)} {edge_type} edges")
        
        graph_data["metadata"]["node_types"] = list(graph_data["nodes"].keys())
        graph_data["metadata"]["edge_types"] = list(graph_data["edges"].keys())
        graph_data["metadata"]["updated_at"] = datetime.now().isoformat()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Export completed: {output_file}")
        logger.info(f"Total nodes: {graph_data['metadata']['total_nodes']}, Total edges: {graph_data['metadata']['total_edges']}")
        
        return output_file


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Export full Neo4j database to JSON")
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file path (default: data/processed/graph/knowledge_graph_full_{timestamp}.json)"
    )
    
    args = parser.parse_args()
    
    exporter = Neo4jGraphExporter()
    
    try:
        output_file = exporter.export_graph(output_file=args.output)
        logger.info(f"Success Database exported to: {output_file}")
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise
    finally:
        exporter.close()
        logger.info("Neo4j connection closed")
