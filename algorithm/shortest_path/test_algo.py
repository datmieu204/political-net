from neo4j import GraphDatabase

from utils.config import settings


class ShortestPathNeo4j:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database

    def close(self):
        if self._driver:
            self._driver.close()

    def shortest_path_ids(self, start_id: str, end_id: str):
        """
        Find the shortest path (by number of edges) between two nodes by id.
        The path is computed on the entire graph imported into Neo4j.
        """

        cypher = """
        MATCH (start {id: $start_id}), (end {id: $end_id})
        MATCH p = shortestPath( (start)-[*..10]-(end) )
        RETURN [n IN nodes(p) | n.id] AS node_ids
        """

        with self._driver.session(database=self._database) as session:
            result = session.run(cypher, start_id=start_id, end_id=end_id)
            record = result.single()
            if not record:
                return None
            return record["node_ids"]

    def shortest_path_with_details(self, start_id: str, end_id: str):
        """
        Return the path along with detailed information about the nodes and relationships between them.
        """

        cypher = """
        MATCH (start {id: $start_id}), (end {id: $end_id})
        MATCH p = shortestPath( (start)-[*..10]-(end) )
        RETURN nodes(p) AS ns, relationships(p) AS rs
        """

        with self._driver.session(database=self._database) as session:
            record = session.run(cypher, start_id=start_id, end_id=end_id).single()
            if not record:
                return None

            nodes = record["ns"]
            rels = record["rs"]

            path_nodes = [
                {
                    "id": n["id"],
                    "labels": list(n.labels),
                    "name": n.get("name"),
                    "props": {k: v for k, v in n.items() if k not in ["id", "name"]},
                }
                for n in nodes
            ]

            path_rels = [
                {
                    "type": r.type,
                    "start_id": r.start_node["id"],
                    "end_id": r.end_node["id"],
                    "props": dict(r.items()),
                }
                for r in rels
            ]

            return {
                "nodes": path_nodes,
                "relationships": path_rels,
            }


def pretty_print_path(path_data):
    if not path_data:
        print("No path found between the two nodes.")
        return

    nodes = path_data["nodes"]
    rels = path_data["relationships"]

    print(f"Path length (number of edges): {len(rels)}")
    for i, node in enumerate(nodes):
        labels = ":".join(node["labels"]) if node["labels"] else ""
        print(f"[{i}] {node['id']} ({labels}) - {node.get('name')}")
        if i < len(rels):
            rel = rels[i]
            print(f"   └──[{rel['type']}]──>")


if __name__ == "__main__":
    client = ShortestPathNeo4j(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD,
        database=settings.NEO4J_DATABASE,
    )

    # example
    start_id = "pol3309882"
    end_id = "pol19508009"

    try:
        print(f"Finding shortest path from {start_id} to {end_id}...\n")
        path_data = client.shortest_path_with_details(start_id, end_id)
        pretty_print_path(path_data)
    finally:
        client.close()
