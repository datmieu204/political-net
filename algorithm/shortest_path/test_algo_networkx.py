# algorithm/shortest_path/test_algo_networkx.py

import json
from pathlib import Path
from typing import List

import networkx as nx


GRAPH_JSON_PATH = Path("data/processed/graph/knowledge_graph.json")


def load_graph_from_json(json_path: Path) -> nx.DiGraph:
    """
    Load graph from file knowledge_graph.json.
    """
    if not json_path.exists():
        raise FileNotFoundError(f"Not found: {json_path}")

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    G = nx.DiGraph()

    nodes_by_type = data.get("nodes", {})
    if isinstance(nodes_by_type, dict):
        for node_type, nodes in nodes_by_type.items():
            for node in nodes:
                node_id = node["id"]
                attrs = {
                    "type": node.get("type", node_type),
                    "name": node.get("name"),
                }
                props = node.get("properties") or {}
                attrs.update(props)
                G.add_node(node_id, **attrs)

    edges_by_type = data.get("edges", {})
    if isinstance(edges_by_type, dict):
        for rel_type, edges in edges_by_type.items():
            for edge in edges:
                src = edge["from"]
                dst = edge["to"]
                props = edge.get("properties") or {}
                G.add_edge(src, dst, type=rel_type, weight=1, **props)

    return G


def shortest_path_ids(G: nx.DiGraph, source_id: str, target_id: str) -> List[str]:
    """
    Shortest path by number of edges between two nodes by id.
    """
    if source_id not in G:
        raise ValueError(f"Source node does not exist: {source_id}")
    if target_id not in G:
        raise ValueError(f"Target node does not exist: {target_id}")

    return nx.shortest_path(G, source=source_id, target=target_id)


def pretty_print_path(G: nx.DiGraph, path: List[str]) -> None:
    """
    Print path information: id, type, name, and edge type between nodes.
    """
    print(f"Path length (number of edges): {len(path) - 1}")
    for i, node_id in enumerate(path):
        data = G.nodes[node_id]
        node_type = data.get("type", "")
        name = data.get("name", "")
        print(f"[{i}] {node_id} ({node_type}) - {name}")
        if i < len(path) - 1:
            next_id = path[i + 1]
            edge_data = G.get_edge_data(node_id, next_id) or {}
            rel_type = edge_data.get("type", "")
            print(f"   └──[{rel_type}]──>")


if __name__ == "__main__":
    print(f"Loading graph from {GRAPH_JSON_PATH} ...")
    G = load_graph_from_json(GRAPH_JSON_PATH)
    print(f"Loaded {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.\n")

    # Example
    source = "pol248258"
    target = "pol1463408"

    try:
        print(f"Finding shortest path from {source} to {target} (networkx)...\n")
        path = shortest_path_ids(G, source, target)
        pretty_print_path(G, path)
    except nx.NetworkXNoPath:
        print(f"No path exists from {source} to {target}.")
    except ValueError as e:
        print(f"Error: {e}")