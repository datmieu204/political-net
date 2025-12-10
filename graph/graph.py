# ./graph/graph.py

import json

from neo4j import GraphDatabase
from utils.config import settings
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("graph", log_file="logs/graph/graph.log")

"""
Connect to Neo4j and clear database
"""

def create_neo4j_driver():
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    return driver

def close_neo4j_driver(driver):
    driver.close()

def clear_neo4j_database(driver):
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    log.info("Cleared all nodes and relationships.")



"""
Import JSON graph data into Neo4j
"""
def import_graph_from_json(driver, json_file_path):
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        log.warning("JSON format is a list")
        data_dict = {"nodes": [], "edges": []}
        for item in data:
            if "nodes" in item:
                data_dict["nodes"].append(item["nodes"])
            if "edges" in item:
                data_dict["edges"].append(item["edges"])
        data = data_dict

    nodes = data.get("nodes", {})
    edges = data.get("edges", {})

    if (not edges or (isinstance(edges, dict) and all(len(v) == 0 for v in edges.values()))) and isinstance(data, dict) and "triplets" in data:
        triplets = data.get("triplets", [])
        converted_edges = {}
        for t in triplets:
            rel_type = t.get("predicate", "RELATED")
            subj = t.get("subject")
            obj = t.get("object")
            props = t.get("properties", {})
            if subj is None or obj is None:
                continue
            converted_edges.setdefault(rel_type, []).append({
                "from": subj,
                "to": obj,
                "properties": props,
            })
        edges = converted_edges

    total_nodes = 0
    total_edges = 0

    with driver.session(database=settings.NEO4J_DATABASE) as session:
        if isinstance(nodes, dict):
            for node_type, node_list in nodes.items():
                for node in node_list:
                    props = {}
                    for k, v in node.items():
                        if k == "type":
                            continue
                        elif k == "properties" and isinstance(v, dict):
                            for pk, pv in v.items():
                                props[pk] = pv
                        else:
                            props[k] = v
                    
                    cypher = f"MERGE (n:{node_type} {{id: $id}}) SET n += $props"
                    session.run(cypher, id=node["id"], props=props)
                    total_nodes += 1
        elif isinstance(nodes, list):
            for node in nodes:
                node_type = node.get("type", "Unknown")
                props = {}
                for k, v in node.items():
                    if k == "properties" and isinstance(v, dict):
                        for pk, pv in v.items():
                            props[pk] = pv
                    else:
                        props[k] = v
                
                cypher = f"MERGE (n:{node_type} {{id: $id}}) SET n += $props"
                session.run(cypher, id=node["id"], props=props)
                total_nodes += 1

        if isinstance(edges, dict):
            for rel_type, rel_list in edges.items():
                for rel in rel_list:
                    from_id = rel["from"]
                    to_id = rel["to"]
                    props = rel.get("properties", {})
                    cypher = (
                        f"MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) "
                        f"MERGE (a)-[r:{rel_type}]->(b) "
                        f"SET r += $props"
                    )
                    session.run(cypher, from_id=from_id, to_id=to_id, props=props)
                    total_edges += 1
        elif isinstance(edges, list):
            for rel in edges:
                rel_type = rel.get("type", "RELATED")
                from_id = rel.get("from")
                to_id = rel.get("to")
                props = rel.get("properties", {})
                cypher = (
                    f"MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) "
                    f"MERGE (a)-[r:{rel_type}]->(b) "
                    f"SET r += $props"
                )
                session.run(cypher, from_id=from_id, to_id=to_id, props=props)
                total_edges += 1

    log.info(f"Imported {total_nodes} nodes and {total_edges} edges into Neo4j.")

if __name__ == "__main__":
    driver = create_neo4j_driver()
    clear_neo4j_database(driver)
    import_graph_from_json(driver, settings.OUTPUT_SUM_ENRICH_FILE)
    close_neo4j_driver(driver)