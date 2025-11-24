# analysis/node_ranking.py

import os
import json
import networkx as nx
from datetime import datetime

from graph.load_graph import GraphLoader
from utils._logger import get_logger
logger = get_logger("analysis.node_ranking", log_file="logs/analysis/node_ranking.log")


class GraphRankingAnalyzer:
    def __init__(self, graph: nx.DiGraph = None, node_info: dict = None):
        self.graph = graph
        self.node_info = node_info or {}
    
    def load_graph(self, source: str, **kwargs):
        loader = GraphLoader(use_neo4j=(source == "json"))
        
        try:
            if source == "neo4j":
                self.graph, self.node_info = loader.load_from_neo4j(**kwargs)
            else:
                self.graph, self.node_info = loader.load_from_json(source, **kwargs)
        finally:
            loader.close()
    
    def compute_pagerank(self, alpha: float = 0.85, max_iter: int = 100) -> dict:
        """
        PageRank for all nodes
        
        Args:
            alpha: Damping factor (0.85 default)
            max_iter: Maximum number of iterations
        
        Returns:
            Dict mapping node_id -> PageRank score
        """    
        pagerank_scores = nx.pagerank(self.graph, alpha=alpha, max_iter=max_iter)
        logger.info(f"PageRank computed for {len(pagerank_scores)} nodes")
        return pagerank_scores
    
    def compute_hits(self, max_iter: int = 100) -> tuple:
        """
        Compute HITS (Hubs and Authorities)
        
        Args:
            max_iter: Maximum number of iterations
        
        Returns:
            (hubs_dict, authorities_dict)
        """
        hubs, authorities = nx.hits(self.graph, max_iter=max_iter)
        logger.info(f"HITS computed for {len(hubs)} nodes")
        return hubs, authorities
    
    def compute_betweenness_centrality(self, normalized: bool = True) -> dict:
        """
        Compute Betweenness Centrality (intermediation level)
        
        Args:
            normalized: Normalize values to [0,1]
        
        Returns:
            Dict mapping node_id -> betweenness score
        """
        betweenness = nx.betweenness_centrality(self.graph, normalized=normalized)
        logger.info(f"Betweenness computed for {len(betweenness)} nodes")        
        return betweenness
    
    def compute_degree_centrality(self) -> dict:
        """
        Compute Degree Centrality (number of connections)
        
        Returns:
            Dict with in_degree, out_degree, total_degree
        """
        in_degree = dict(self.graph.in_degree())
        out_degree = dict(self.graph.out_degree())
        total_degree = {node: in_degree[node] + out_degree[node] for node in self.graph.nodes()}
        
        logger.info(f"Degree Centrality computed for {len(total_degree)} nodes")
        
        return {
            "in_degree": in_degree,
            "out_degree": out_degree,
            "total_degree": total_degree
        }
    
    def compute_closeness_centrality(self) -> dict:
        """
        Compute Closeness Centrality (average distance to other nodes)
        
        Returns:
            Dict mapping node_id -> closeness score
        """
        if nx.is_strongly_connected(self.graph):
            closeness = nx.closeness_centrality(self.graph)
        else:
            largest_scc = max(nx.strongly_connected_components(self.graph), key=len)
            subgraph = self.graph.subgraph(largest_scc)
            closeness = nx.closeness_centrality(subgraph)
        
        logger.info(f"Closeness computed for {len(closeness)} nodes")        
        return closeness
    
    def get_top_nodes(self, scores: dict, top_k: int = 20, node_type: str = None) -> list:
        """
        Get top K nodes with highest scores
        
        Args:
            scores: Dictionary of scores
            top_k: top nodes
            node_type: Filter by node type (Politician, Position, etc.)
        
        Returns:
            List of (node_id, score, name, type)
        """
        if node_type:
            filtered_scores = {
                node_id: score for node_id, score in scores.items()
                if self.node_info.get(node_id, {}).get("type") == node_type
            }
        else:
            filtered_scores = scores
        
        sorted_nodes = sorted(filtered_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        result = []
        for node_id, score in sorted_nodes:
            info = self.node_info.get(node_id, {})
            result.append({
                "node_id": node_id,
                "score": score,
                "name": info.get("name", "Unknown"),
                "type": info.get("type", "Unknown")
            })
        
        return result
    
    def analyze_all(self, output_dir: str = "analysis/results"):
        os.makedirs(output_dir, exist_ok=True)
        
        pagerank = self.compute_pagerank()
        hubs, authorities = self.compute_hits()
        betweenness = self.compute_betweenness_centrality()
        degree_stats = self.compute_degree_centrality()
        closeness = self.compute_closeness_centrality()
        
        results = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_nodes": self.graph.number_of_nodes(),
                "total_edges": self.graph.number_of_edges(),
                "algorithms": ["PageRank", "HITS", "Betweenness", "Degree", "Closeness"]
            },
            "rankings": {
                "pagerank": {
                    "description": "PageRank - Xếp hạng dựa trên cấu trúc liên kết",
                    "top_20_all": self.get_top_nodes(pagerank, 20),
                    "top_20_politicians": self.get_top_nodes(pagerank, 20, "Politician"),
                    "top_10_positions": self.get_top_nodes(pagerank, 10, "Position")
                },
                "hubs": {
                    "description": "HITS Hubs - Nodes có nhiều liên kết đi ra quan trọng",
                    "top_20_all": self.get_top_nodes(hubs, 20),
                    "top_20_politicians": self.get_top_nodes(hubs, 20, "Politician")
                },
                "authorities": {
                    "description": "HITS Authorities - Nodes được nhiều hubs quan trọng trỏ đến",
                    "top_20_all": self.get_top_nodes(authorities, 20),
                    "top_20_politicians": self.get_top_nodes(authorities, 20, "Politician")
                },
                "betweenness": {
                    "description": "Betweenness Centrality - Nodes nằm trên nhiều đường đi ngắn nhất",
                    "top_20_all": self.get_top_nodes(betweenness, 20),
                    "top_20_politicians": self.get_top_nodes(betweenness, 20, "Politician")
                },
                "degree": {
                    "description": "Degree Centrality - Số lượng kết nối",
                    "top_20_total": self.get_top_nodes(degree_stats["total_degree"], 20),
                    "top_20_in_degree": self.get_top_nodes(degree_stats["in_degree"], 20),
                    "top_20_out_degree": self.get_top_nodes(degree_stats["out_degree"], 20)
                },
                "closeness": {
                    "description": "Closeness Centrality - Khoảng cách trung bình đến các nodes khác",
                    "top_20_all": self.get_top_nodes(closeness, 20) if closeness else []
                }
            }
        }
        
        output_file = f"{output_dir}/graph_ranking.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"Results saved to: {output_file}")        
        return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", "-s",
        type=str,
        default="neo4j",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="analysis/results",
    )
    
    args = parser.parse_args()
    
    analyzer = GraphRankingAnalyzer()
    
    try:
        analyzer.load_graph(args.source)
        analyzer.analyze_all(output_dir=args.output)
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise

