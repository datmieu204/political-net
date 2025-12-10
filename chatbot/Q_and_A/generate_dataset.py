"""
Main script for generating multi-hop reasoning dataset from knowledge graph.

Usage:
    python chatbot/generate_dataset.py \
    --kg                # Đường dẫn file knowledge graph JSON
    --total             # Tổng số câu hỏi cần sinh
    --multi_ratio       # Tỉ lệ multi-hop (default: 0.65)
    --single_ratio      # Tỉ lệ single-hop (default: 0.2)
    --llm_model         # Model Gemini (default: gemini-2.5-flash-lite)
    --seed              # Random seed cho reproducibility

    python chatbot/Q_and_A/generate_dataset.py --kg data/processed/graph/knowledge_graph_enriched.json --total 3000 --out_dir chatbot/Q_and_A/output
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from tqdm import tqdm
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from kg_utils import KnowledgeGraph
from llm_client import create_llm_client, format_variant_prompt, parse_llm_response
from templates import (
    generate_single_hop_question,
    generate_multi_hop_question,
    generate_mcq_choices,
    generate_false_statement
)


def setup_logging(output_dir: str, verbose: bool = False):
    """Setup logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    log_file = os.path.join(output_dir, "process.log")
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


class DatasetGenerator:
    """Main dataset generator class."""
    
    def __init__(self, kg: KnowledgeGraph, config: Dict):
        """
        Initialize dataset generator.
        
        Args:
            kg: KnowledgeGraph instance
            config: Configuration dictionary
        """
        self.kg = kg
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Random seed for reproducibility
        random.seed(config['seed'])
        
        # Storage for generated questions
        self.questions = []
        self.answers = []
        self.question_ids = set()
        self.reasoning_paths_seen = {}  # Changed to dict to track usage count
        
        # Statistics
        self.stats = defaultdict(int)
        
        # Build index of (politician_id, position_id) for validation
        self.served_as_index = self._build_served_as_index()
        
    def _build_served_as_index(self) -> Set[Tuple[str, str]]:
        """Build a set of (politician_id, position_id) for fast validation."""
        index = set()
        for u, v, data in self.kg.graph.edges(data=True):
            if data.get('type') == 'SERVED_AS':
                # u is politician, v is position
                index.add((u, v))
        self.logger.info(f"Built SERVED_AS index with {len(index)} entries")
        return index

    def _validate_succession_edge(self, from_id: str, to_id: str, edge_props: Dict) -> bool:
        """
        Validate a PRECEDED/SUCCEEDED edge by checking if both parties served in the position.
        
        Args:
            from_id: Source politician ID
            to_id: Target politician ID
            edge_props: Edge properties containing position_id
            
        Returns:
            True if valid (or if not a succession edge), False otherwise
        """
        position_id = edge_props.get('position_id')
        if not position_id:
            return False
            
        # Check if both politicians have a SERVED_AS relation to this position
        has_from = (from_id, position_id) in self.served_as_index
        has_to = (to_id, position_id) in self.served_as_index
        
        return has_from and has_to

    def generate_candidates(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Generate candidate single-hop and multi-hop questions.
        
        Returns:
            Tuple of (single_hop_candidates, multi_hop_candidates)
        """
        self.logger.info("Generating candidates...")
        
        single_hop = self._generate_single_hop_candidates()
        multi_hop = self._generate_multi_hop_candidates()
        
        # Add targeted multi-hop candidates for dead-end edges
        dead_end_multi_hop = self._generate_dead_end_multi_hop_candidates()
        multi_hop.extend(dead_end_multi_hop)
        
        # Shuffle combined multi-hop
        random.shuffle(multi_hop)
        
        self.logger.info(f"Generated {len(single_hop)} single-hop and {len(multi_hop)} multi-hop candidates")
        
        return single_hop, multi_hop
    
    def _generate_single_hop_candidates(self) -> List[Dict]:
        """Generate single-hop candidates from edges - FULL DATA SCAN."""
        candidates = []
        edge_types_to_use = [et for et in self.kg.edge_types if et not in ['SUCCEEDED', 'PRECEDED']]
        
        all_nodes = list(self.kg.graph.nodes())
        self.logger.info(f"Scanning ALL {len(all_nodes)} nodes for single-hop candidates...")
        
        for edge_type in edge_types_to_use:
            # Scan ALL edges for each type
            edges_found = 0
            for node_id in all_nodes:  # FULL SCAN - no limit
                edges = self.kg.get_outgoing_edges(node_id)
                
                for edge in edges:
                    if edge['type'] != edge_type:
                        continue
                    
                    # Skip self-loops
                    if edge['from'] == edge['to']:
                        continue
                    
                    edges_found += 1
                    
                    from_node = self.kg.get_node(edge['from'])
                    to_node = self.kg.get_node(edge['to'])
                    
                    if not from_node or not to_node or not from_node['name'] or not to_node['name']:
                        continue
                    
                    # Create path signature
                    path = [edge['from'], edge['type'], edge['to']]
                    path_sig = "|".join(path)
                    
                    # Check if path already used (dict tracks usage count)
                    path_count = self.reasoning_paths_seen.get(path_sig, 0)
                    if path_count >= 2:
                        continue
                    
                    self.reasoning_paths_seen[path_sig] = path_count + 1
                    
                    # Extract edge properties
                    edge_props = edge.get('properties', {})
                    
                    # For PRECEDED/SUCCEEDED, require position_id
                    if edge['type'] in ['PRECEDED', 'SUCCEEDED']:
                        if not edge_props.get('position_id'):
                            continue  # Skip candidates without position context
                    
                    candidates.append({
                        'path': path,
                        'hop_count': 1,
                        'from_name': from_node['name'],
                        'to_name': to_node['name'],
                        'from_type': from_node['type'],
                        'to_type': to_node['type'],
                        'relation': edge['type'],
                        'edge_props': [edge_props]  # Store as list for consistency with multi-hop
                    })
            
            self.logger.debug(f"  {edge_type}: {edges_found} candidates")
        
        # NEW: Generate candidates for virtual relations (BORN_YEAR, DIED_YEAR, TERM_DURATION)
        self.logger.info("Generating virtual relation candidates (BORN_YEAR, DIED_YEAR, TERM_DURATION)...")
        import re
        
        for node_id in all_nodes:
            node = self.kg.get_node(node_id)
            if not node or node['type'] != 'Politician':
                continue
                
            # BORN_YEAR
            birth_date = node.get('properties', {}).get('birth_date')
            if birth_date:
                year_match = re.search(r'\d{4}', str(birth_date))
                if year_match:
                    year = year_match.group(0)
                    candidates.append({
                        'path': [node_id, 'BORN_YEAR', 'YEAR_' + year],
                        'hop_count': 1,
                        'from_name': node['name'],
                        'to_name': year,
                        'from_type': 'Politician',
                        'to_type': 'Year',
                        'relation': 'BORN_YEAR',
                        'edge_props': []
                    })

            # DIED_YEAR
            death_date = node.get('properties', {}).get('death_date')
            if death_date:
                year_match = re.search(r'\d{4}', str(death_date))
                if year_match:
                    year = year_match.group(0)
                    candidates.append({
                        'path': [node_id, 'DIED_YEAR', 'YEAR_' + year],
                        'hop_count': 1,
                        'from_name': node['name'],
                        'to_name': year,
                        'from_type': 'Politician',
                        'to_type': 'Year',
                        'relation': 'DIED_YEAR',
                        'edge_props': []
                    })
            
            # TERM_DURATION (from SERVED_AS edges)
            edges = self.kg.get_outgoing_edges(node_id)
            for edge in edges:
                if edge['type'] == 'SERVED_AS':
                    props = edge.get('properties', {})
                    start = props.get('term_start')
                    end = props.get('term_end')
                    
                    if start and end:
                        duration_str = f"từ {start} đến {end}"
                        duration_id = f"DURATION_{duration_str}"
                        
                        # Inject position_id
                        props_with_pos = props.copy()
                        props_with_pos['position_id'] = edge['to']
                        
                        candidates.append({
                            'path': [edge['from'], 'TERM_DURATION', duration_id], 
                            'hop_count': 1,
                            'from_name': node['name'],
                            'to_name': duration_str,
                            'from_type': 'Politician',
                            'to_type': 'Duration',
                            'relation': 'TERM_DURATION',
                            'edge_props': [props_with_pos]
                        })

        # Shuffle for randomness
        random.shuffle(candidates)
        return candidates
    
    def _generate_dead_end_multi_hop_candidates(self) -> List[Dict]:
        """
        Generate multi-hop candidates that end with dead-end edges (2, 3, 4 hops).
        
        Patterns:
        - 2-hop: Pol A -> CHAIN -> Pol B -> DEAD_END -> Target
        - 3-hop: Pol A -> CHAIN -> Pol B -> CHAIN -> Pol C -> DEAD_END -> Target
        - 4-hop: Pol A -> CHAIN -> Pol B -> CHAIN -> Pol C -> CHAIN -> Pol D -> DEAD_END -> Target
        
        This ensures coverage of edges like BORN_AT, DIED_AT, AWARDED, etc.
        """
        candidates = []
        
        # Dead-end edges that need special handling
        dead_end_edges = ['BORN_AT', 'DIED_AT', 'AWARDED', 'SERVED_IN', 'HAS_RANK', 
                         'FOUGHT_IN', 'ALUMNUS_OF', 'HAS_ACADEMIC_TITLE']
        chain_edges = ['PRECEDED', 'SUCCEEDED']
        
        # Get ALL politicians - FULL DATA SCAN
        politicians = [node_id for node_id in self.kg.graph.nodes() 
                      if self.kg.get_node(node_id) and self.kg.get_node(node_id).get('type') == 'Politician']
        
        random.shuffle(politicians)
        
        self.logger.info(f"Generating dead-end multi-hop candidates (2, 3, 4 hops) from ALL {len(politicians)} politicians...")
        
        # Track candidates per (hop_count, dead_end_edge_type)
        # Increase target to get more coverage
        target_per_combo = 300  # Increased from 100 to get more diverse paths
        combo_counts = {}  # (hop_count, edge_type) -> count
        
        max_hop = self.config.get('max_hop', 4)
        
        def get_chain_paths(start_pol, depth, current_path, current_props):
            """Recursively find chain paths of given depth."""
            if depth == 0:
                yield current_path, current_props
                return
            
            edges = self.kg.get_outgoing_edges(start_pol)
            for edge in edges:
                if edge['type'] not in chain_edges:
                    continue
                
                next_pol = edge['to']
                
                # Prevent cycles and self-loops
                if next_pol in current_path:
                    continue
                
                next_node = self.kg.get_node(next_pol)
                if not next_node or next_node.get('type') != 'Politician':
                    continue
                
                edge_props = edge.get('properties', {})
                
                # Validate succession edge
                if not self._validate_succession_edge(start_pol, next_pol, edge_props):
                    continue
                
                new_path = current_path + [edge['type'], next_pol]
                new_props = current_props + [edge_props]
                
                yield from get_chain_paths(next_pol, depth - 1, new_path, new_props)
        
        # Generate for each hop count (2, 3, 4)
        for chain_depth in range(1, max_hop):  # chain_depth 1-3 for 2-4 hop total
            hop_count = chain_depth + 1
            
            for pol_a in politicians:  # FULL SCAN - ALL politicians
                pol_a_node = self.kg.get_node(pol_a)
                if not pol_a_node or not pol_a_node.get('name'):
                    continue
                
                # Get all chain paths of this depth
                for chain_path, chain_props in get_chain_paths(pol_a, chain_depth, [pol_a], []):
                    if len(chain_path) < 3:  # Need at least [pol_a, edge, pol_b]
                        continue
                    
                    last_pol = chain_path[-1]
                    
                    # Get dead-end edges from last politician
                    edges_from_last = self.kg.get_outgoing_edges(last_pol)
                    
                    for final_edge in edges_from_last:
                        if final_edge['type'] not in dead_end_edges:
                            continue
                        
                        edge_type = final_edge['type']
                        combo_key = (hop_count, edge_type)
                        
                        if combo_counts.get(combo_key, 0) >= target_per_combo:
                            continue
                        
                        target = final_edge['to']
                        target_node = self.kg.get_node(target)
                        
                        if not target_node or not target_node.get('name'):
                            continue
                        
                        # Build full path
                        path = chain_path + [final_edge['type'], target]
                        
                        # Create path signature
                        path_sig = "|".join(path)
                        path_count = self.reasoning_paths_seen.get(path_sig, 0)
                        if path_count >= 2:
                            continue
                        
                        self.reasoning_paths_seen[path_sig] = path_count + 1
                        
                        # Store all edge properties
                        final_edge_props = final_edge.get('properties', {})
                        all_props = chain_props + [final_edge_props]
                        
                        candidates.append({
                            'path': path,
                            'hop_count': hop_count,
                            'from_name': pol_a_node['name'],
                            'to_name': target_node['name'],
                            'from_type': 'Politician',
                            'to_type': target_node.get('type', 'Unknown'),
                            'edge_props': all_props,
                            'is_dead_end_path': True
                        })
                        
                        combo_counts[combo_key] = combo_counts.get(combo_key, 0) + 1
                    
                    # NEW: Check for virtual dead-end relations (BORN_YEAR, DIED_YEAR, TERM_DURATION)
                    import re
                    last_pol_node = self.kg.get_node(last_pol)
                    
                    # BORN_YEAR
                    birth_date = last_pol_node.get('properties', {}).get('birth_date')
                    if birth_date:
                        combo_key = (hop_count, 'BORN_YEAR')
                        if combo_counts.get(combo_key, 0) < target_per_combo:
                            year_match = re.search(r'\d{4}', str(birth_date))
                            if year_match:
                                year = year_match.group(0)
                                path = chain_path + ['BORN_YEAR', 'YEAR_' + year]
                                path_sig = "|".join(path)
                                if self.reasoning_paths_seen.get(path_sig, 0) < 2:
                                    self.reasoning_paths_seen[path_sig] = self.reasoning_paths_seen.get(path_sig, 0) + 1
                                    candidates.append({
                                        'path': path,
                                        'hop_count': hop_count,
                                        'from_name': pol_a_node['name'],
                                        'to_name': year,
                                        'from_type': 'Politician',
                                        'to_type': 'Year',
                                        'edge_props': chain_props + [],
                                        'is_dead_end_path': True
                                    })
                                    combo_counts[combo_key] = combo_counts.get(combo_key, 0) + 1

                    # DIED_YEAR
                    death_date = last_pol_node.get('properties', {}).get('death_date')
                    if death_date:
                        combo_key = (hop_count, 'DIED_YEAR')
                        if combo_counts.get(combo_key, 0) < target_per_combo:
                            year_match = re.search(r'\d{4}', str(death_date))
                            if year_match:
                                year = year_match.group(0)
                                path = chain_path + ['DIED_YEAR', 'YEAR_' + year]
                                path_sig = "|".join(path)
                                if self.reasoning_paths_seen.get(path_sig, 0) < 2:
                                    self.reasoning_paths_seen[path_sig] = self.reasoning_paths_seen.get(path_sig, 0) + 1
                                    candidates.append({
                                        'path': path,
                                        'hop_count': hop_count,
                                        'from_name': pol_a_node['name'],
                                        'to_name': year,
                                        'from_type': 'Politician',
                                        'to_type': 'Year',
                                        'edge_props': chain_props + [],
                                        'is_dead_end_path': True
                                    })
                                    combo_counts[combo_key] = combo_counts.get(combo_key, 0) + 1

                    # TERM_DURATION
                    for final_edge in edges_from_last:
                        if final_edge['type'] == 'SERVED_AS':
                            combo_key = (hop_count, 'TERM_DURATION')
                            if combo_counts.get(combo_key, 0) >= target_per_combo:
                                continue
                                
                            props = final_edge.get('properties', {})
                            start = props.get('term_start')
                            end = props.get('term_end')
                            
                            if start and end:
                                duration_str = f"từ {start} đến {end}"
                                # Use a virtual node ID for the duration to ensure the answer is the duration string
                                # Prefix with DURATION_ to identify it, but keep the content readable
                                duration_id = f"DURATION_{duration_str}"
                                
                                # Inject position_id into props so we can retrieve position name later
                                props_with_pos = props.copy()
                                props_with_pos['position_id'] = final_edge['to']
                                
                                path = chain_path + ['TERM_DURATION', duration_id]
                                path_sig = "|".join(path)
                                if self.reasoning_paths_seen.get(path_sig, 0) < 2:
                                    self.reasoning_paths_seen[path_sig] = self.reasoning_paths_seen.get(path_sig, 0) + 1
                                    candidates.append({
                                        'path': path,
                                        'hop_count': hop_count,
                                        'from_name': pol_a_node['name'],
                                        'to_name': duration_str,
                                        'from_type': 'Politician',
                                        'to_type': 'Duration',
                                        'edge_props': chain_props + [props_with_pos],
                                        'is_dead_end_path': True
                                    })
                                    combo_counts[combo_key] = combo_counts.get(combo_key, 0) + 1
        
        self.logger.info(f"Generated {len(candidates)} dead-end multi-hop candidates:")
        # Group by hop count
        by_hop = {}
        for (hop, edge_type), count in sorted(combo_counts.items()):
            if hop not in by_hop:
                by_hop[hop] = {}
            by_hop[hop][edge_type] = count
        
        for hop in sorted(by_hop.keys()):
            self.logger.info(f"  {hop}-hop:")
            for et, count in by_hop[hop].items():
                self.logger.info(f"    {et}: {count}")
        
        return candidates
    
    def _generate_multi_hop_candidates(self) -> List[Dict]:
        """Generate multi-hop candidates using shortest paths - FULL COVERAGE."""
        candidates = []
        max_hop = self.config['max_hop']
        
        # FULL DATA SCAN - ensure every node is visited as source
        all_nodes = list(self.kg.graph.nodes())
        random.shuffle(all_nodes)
        
        # Target: check enough pairs per node to ensure coverage
        # With 6223 nodes, checking 100 targets per node = 622,300 pairs (reasonable)
        targets_per_source = 100  # Check 100 random targets per source node
        
        self.logger.info(f"Searching multi-hop paths: ALL {len(all_nodes)} nodes x {targets_per_source} targets each (max {max_hop} hops)...")
        
        # Scan ALL source nodes - no early break!
        for i, source in enumerate(tqdm(all_nodes, desc="Finding paths")):
            # Sample random targets for this source
            other_nodes = [n for n in all_nodes if n != source]
            sample_targets = random.sample(other_nodes, min(targets_per_source, len(other_nodes)))
            
            for target in sample_targets:
                # Get shortest path WITH edge properties
                result = self.kg.get_shortest_path(source, target, max_length=max_hop, include_edge_props=True)
                
                if not result:
                    continue
                
                path, edge_props_list = result
                
                if not path or len(path) < 5:  # Need at least 2 hops (5 elements: n-e-n-e-n)
                    continue
                
                # Check if all PRECEDED/SUCCEEDED edges have position_id AND are valid
                edge_types = [path[i] for i in range(1, len(path), 2)]
                valid_path = True
                for i, edge_type in enumerate(edge_types):
                    if edge_type in ['PRECEDED', 'SUCCEEDED']:
                        edge_props = edge_props_list[i] if i < len(edge_props_list) else {}
                        
                        # Get source and target for this specific edge
                        # path is [n0, e0, n1, e1, n2...]
                        # edge i corresponds to path[2*i] -> path[2*i+2]
                        u = path[2*i]
                        v = path[2*i+2]
                        
                        if not self._validate_succession_edge(u, v, edge_props):
                            valid_path = False
                            break
                
                if not valid_path:
                    continue  # Skip paths with invalid succession edges
                
                hop_count = (len(path) - 1) // 2
                
                if hop_count < 2 or hop_count > max_hop:
                    continue
                
                # Create path signature - allow reuse for different question types
                path_sig = "|".join(path)
                path_count = self.reasoning_paths_seen.get(path_sig, 0)
                
                # Allow each path to be used up to 2 times (for MCQ and TRUE_FALSE)
                if path_count >= 2:
                    continue
                
                self.reasoning_paths_seen[path_sig] = path_count + 1
                
                # Get node names
                source_node = self.kg.get_node(source)
                target_node = self.kg.get_node(target)
                
                if not source_node or not target_node:
                    continue
                
                candidates.append({
                    'path': path,
                    'hop_count': hop_count,
                    'from_name': source_node['name'],
                    'to_name': target_node['name'],
                    'from_type': source_node['type'],
                    'to_type': target_node['type'],
                    'edge_props': edge_props_list  # NEW: Store edge properties
                })
        
        self.logger.info(f"Found {len(candidates)} multi-hop candidates")
        
        # Shuffle for randomness
        random.shuffle(candidates)
        return candidates
    
    def generate_questions(self, candidates: List[Dict], target_count: int,
                          is_multi_hop: bool) -> List[Dict]:
        """
        Generate questions from candidates.
        
        Args:
            candidates: List of candidate dictionaries
            target_count: Number of questions to generate
            is_multi_hop: Whether candidates are multi-hop
        
        Returns:
            List of generated question dictionaries
        """
        questions = []
        # Equal distribution: 50% TRUE_FALSE, 50% MCQ (remove YES_NO)
        q_types = ['TRUE_FALSE', 'MCQ']
        
        for i, candidate in enumerate(candidates):
            if len(questions) >= target_count:
                break
            
            # Đảm bảo tạo đủ MCQ multi-hop bằng cách ưu tiên MCQ cho multi-hop
            if is_multi_hop and len([q for q in questions if q['q_type'] == 'MCQ']) < target_count // 2:
                q_type = 'MCQ'  # Force MCQ cho multi-hop
            else:
                # Select question type (rotate through types for equal distribution)
                q_type = q_types[i % len(q_types)]
            
            # Generate question text
            try:
                if is_multi_hop:
                    question_text, actual_reasoning_path, actual_hop_count = self._generate_multi_hop_text(candidate, q_type)
                else:
                    question_text, actual_reasoning_path, actual_hop_count = self._generate_single_hop_text(candidate, q_type)
                
                # Skip if question generation failed (e.g., missing position context)
                if not question_text:
                    continue
                    
                # Generate answer
                answer_data, choices = self._generate_answer(candidate, q_type)
                
                if not question_text or not answer_data:
                    continue
                
                # For MCQ, append choices to question
                if q_type == 'MCQ' and choices:
                    question_text = f"{question_text}\n" + "\n".join(choices)
                
                # Ensure minimum length
                if len(question_text) < 10:
                    continue
                
                # Check for duplicates
                if question_text in [q['question'] for q in questions]:
                    continue
                
                question_id = len(self.questions) + len(questions) + 1
                
                questions.append({
                    'id': question_id,
                    'question': question_text,
                    'q_type': q_type,
                    'hop_count': actual_hop_count,  # Use actual hop count from question
                    'reasoning_path': actual_reasoning_path,  # Use actual reasoning path
                    'answer': answer_data,
                    'variant_type': 'Normal'  # Regular question
                })
                
                self.stats[f"{q_type}_{actual_hop_count}hop"] += 1
                
            except Exception as e:
                self.logger.debug(f"Failed to generate question from candidate: {e}")
                continue
        
        return questions
    
    def generate_questions_by_type(self, multi_hop_candidates: List[Dict], 
                                    single_hop_candidates: List[Dict],
                                    multi_count: int, single_count: int,
                                    q_type: str,
                                    initial_mcq_counts: List[int] = None,
                                    initial_tf_counts: Dict[str, int] = None) -> List[Dict]:
        """
        Generate questions of a specific type (MCQ or TRUE_FALSE).
        
        Args:
            multi_hop_candidates: Multi-hop candidates
            single_hop_candidates: Single-hop candidates
            multi_count: Number of multi-hop questions
            single_count: Number of single-hop questions
            q_type: Question type ('MCQ' or 'TRUE_FALSE')
            initial_mcq_counts: Initial counts for A, B, C, D (for balancing)
            initial_tf_counts: Initial counts for True, False (for balancing)
        
        Returns:
            List of generated question dictionaries
        """
        questions = []
        used_candidates = set()
        
        # Balancing counters
        mcq_counts = list(initial_mcq_counts) if initial_mcq_counts else [0, 0, 0, 0]  # A, B, C, D
        tf_counts = dict(initial_tf_counts) if initial_tf_counts else {'True': 0, 'False': 0}
        
        # Helper to process candidate
        def process_candidate(candidate, is_multi_hop):
            nonlocal mcq_counts, tf_counts
            
            # Determine if we need to modify candidate for balancing
            current_candidate = candidate
            target_mcq_index = None
            
            if q_type == 'MCQ':
                # Find index with minimum count to balance
                min_count = min(mcq_counts)
                candidates_indices = [i for i, c in enumerate(mcq_counts) if c == min_count]
                target_mcq_index = random.choice(candidates_indices)
                
            elif q_type == 'TRUE_FALSE':
                # Check if we need more False answers
                # Aim for 50/50 balance based on TOTAL counts (including initial offset)
                total_tf = sum(tf_counts.values())
                
                # If False is lagging behind 50%, try to generate False
                if total_tf == 0 or tf_counts['False'] < (total_tf + 1) * 0.5:
                    # Try to create false candidate
                    false_candidate = self._create_false_candidate(candidate)
                    if false_candidate:
                        current_candidate = false_candidate
            
            try:
                if is_multi_hop:
                    question_text, actual_reasoning_path, actual_hop_count = self._generate_multi_hop_text(current_candidate, q_type)
                else:
                    question_text, actual_reasoning_path, actual_hop_count = self._generate_single_hop_text(current_candidate, q_type)
                
                if not question_text:
                    return None
                
                answer_data, choices = self._generate_answer(current_candidate, q_type, target_correct_index=target_mcq_index)
                
                if not answer_data:
                    return None
                
                # Update counters
                if q_type == 'MCQ':
                    idx = answer_data.get('answer_index', 0)
                    if 0 <= idx < 4:
                        mcq_counts[idx] += 1
                elif q_type == 'TRUE_FALSE':
                    ans = answer_data.get('answer', 'True')
                    if ans in tf_counts:
                        tf_counts[ans] += 1
                
                if q_type == 'MCQ' and choices:
                    question_text = f"{question_text}\n" + "\n".join(choices)
                
                if len(question_text) < 10:
                    return None
                
                return {
                    'id': 0, # Set later
                    'question': question_text,
                    'q_type': q_type,
                    'hop_count': actual_hop_count,
                    'reasoning_path': actual_reasoning_path,
                    'answer': answer_data,
                    'variant_type': 'Normal'
                }
                
            except Exception as e:
                self.logger.debug(f"Failed to generate {q_type}: {e}")
                return None

        # Generate multi-hop questions
        for candidate in multi_hop_candidates:
            if len([q for q in questions if q['hop_count'] >= 2]) >= multi_count:
                break
            
            candidate_id = id(candidate)
            if candidate_id in used_candidates:
                continue
            
            result = process_candidate(candidate, is_multi_hop=True)
            if result:
                if result['question'] in [q['question'] for q in questions]:
                    continue
                    
                used_candidates.add(candidate_id)
                result['id'] = len(self.questions) + len(questions) + 1
                questions.append(result)
                self.stats[f"{q_type}_{result['hop_count']}hop"] += 1
        
        # Generate single-hop questions
        for candidate in single_hop_candidates:
            if len([q for q in questions if q['hop_count'] == 1]) >= single_count:
                break
            
            candidate_id = id(candidate)
            if candidate_id in used_candidates:
                continue
            
            result = process_candidate(candidate, is_multi_hop=False)
            if result:
                if result['question'] in [q['question'] for q in questions]:
                    continue
                    
                used_candidates.add(candidate_id)
                result['id'] = len(self.questions) + len(questions) + 1
                questions.append(result)
                self.stats[f"{q_type}_{result['hop_count']}hop"] += 1
        
        self.logger.info(f"Generated {len(questions)} {q_type} questions "
                        f"({len([q for q in questions if q['hop_count'] >= 2])} multi-hop, "
                        f"{len([q for q in questions if q['hop_count'] == 1])} single-hop)")
        
        if q_type == 'MCQ':
            self.logger.info(f"MCQ Distribution (including expected LLM): A={mcq_counts[0]}, B={mcq_counts[1]}, C={mcq_counts[2]}, D={mcq_counts[3]}")
        elif q_type == 'TRUE_FALSE':
            self.logger.info(f"TF Distribution (including expected LLM): True={tf_counts['True']}, False={tf_counts['False']}")
        
        return questions

    def _generate_single_hop_text(self, candidate: Dict, q_type: str) -> tuple:
        """Generate single-hop question text with position context.
        
        Returns:
            Tuple of (question_text, reasoning_path, hop_count)
        """
        from templates import RELATION_TEMPLATES, SINGLE_HOP_TEMPLATES
        import random
        
        relation = candidate['relation']
        subject_name = candidate['from_name']
        object_name = candidate['to_name']
        edge_props_list = candidate.get('edge_props', [])
        
        # Build actual reasoning path for this question (already stored in candidate)
        actual_path = candidate['path']  # Format: [from_id, relation, to_id]
        actual_hop_count = 1
        
        # Get base relation phrases
        relation_phrase = RELATION_TEMPLATES.get(relation, {}).get('forward', relation)
        relation_question = RELATION_TEMPLATES.get(relation, {}).get('question', relation)
        
        # Enrich with position context for PRECEDED/SUCCEEDED - REQUIRED
        if edge_props_list and len(edge_props_list) > 0:
            edge_props = edge_props_list[0]
            
            if relation in ['PRECEDED', 'SUCCEEDED']:
                position_name = ''
                if edge_props.get('position_id'):
                    position_id = edge_props['position_id']
                    position_node = self.kg.get_node(position_id)
                    position_name = position_node.get('name', '') if position_node else ''
                
                # REQUIRE position context for PRECEDED/SUCCEEDED
                if position_name:
                    if relation == 'PRECEDED':
                        relation_phrase = f"là tiền nhiệm trong chức vụ {position_name} của"
                        relation_question = f"là tiền nhiệm của ai trong chức vụ {position_name}"
                    elif relation == 'SUCCEEDED':
                        relation_phrase = f"kế nhiệm trong chức vụ {position_name}"
                        relation_question = f"kế nhiệm ai trong chức vụ {position_name}"
                else:
                    # Skip this candidate if no position context for PRECEDED/SUCCEEDED
                    return None, None, None
            
            elif relation == 'SERVED_AS':
                # Check term_end to determine "đang giữ" vs "đã từng giữ"
                term_end = edge_props.get('term_end', '')
                if term_end == 'nay':
                    relation_phrase = "đang giữ chức vụ"
                    relation_question = "đang giữ chức vụ gì"
                else:
                    relation_phrase = "đã từng giữ chức vụ"
                    relation_question = "đã từng giữ chức vụ gì"
            
            elif relation == 'TERM_DURATION':
                # Get position name from edge_props
                position_name = ""
                if edge_props.get('position_id'):
                    pos_node = self.kg.get_node(edge_props['position_id'])
                    if pos_node:
                        position_name = pos_node.get('name', '')
                
                if position_name:
                    relation_question = f"giữ chức vụ {position_name} trong giai đoạn nào"
                    relation_phrase = f"giữ chức vụ {position_name} trong giai đoạn"
        
        # Build custom question with enriched context
        seed = self.config['seed'] + hash(subject_name) % 1000
        random.seed(seed)
        
        templates = SINGLE_HOP_TEMPLATES.get(q_type, SINGLE_HOP_TEMPLATES.get("YES_NO", []))
        template = random.choice(templates) if templates else "{subject} {relation_question}?"
        
        question = template.format(
            subject=subject_name,
            relation=relation_phrase,
            object=object_name,
            relation_question=relation_question
        )
        
        return question, actual_path, actual_hop_count
    
    def _generate_multi_hop_text(self, candidate: Dict, q_type: str) -> tuple:
        """Generate multi-hop question text with position context.
        
        Returns:
            Tuple of (question_text, reasoning_path, hop_count)
        """
        path = candidate['path']
        edge_props_list = candidate.get('edge_props', [])
        
        # Build node_names mapping
        node_names = {}
        for i, item in enumerate(path):
            if i % 2 == 0:  # Node ID
                if str(item).startswith('YEAR_'):
                    node_names[item] = item.replace('YEAR_', '')
                elif str(item).startswith('DURATION_'):
                    node_names[item] = item.replace('DURATION_', '')
                else:
                    node = self.kg.get_node(item)
                    if node:
                        node_names[item] = node['name']
        
        # Build relation statements with position context for TRUE_FALSE
        # Build relation questions for MCQ
        from templates import RELATION_TEMPLATES
        
        entities = [node_names.get(path[i], path[i]) for i in range(0, len(path), 2)]
        edge_types = [path[i] for i in range(1, len(path), 2)]
        
        # Build statements/questions for each hop
        statements = []  # For TRUE_FALSE: "A kế nhiệm B trong chức vụ X"
        relation_questions = []  # For MCQ: "kế nhiệm ai trong chức vụ X"
        
        for i, edge_type in enumerate(edge_types):
            edge_props = edge_props_list[i] if i < len(edge_props_list) else {}
            
            # Get entity names
            from_entity = entities[i]
            to_entity = entities[i + 1] if i + 1 < len(entities) else "?"
            
            # Build with position context for PRECEDED/SUCCEEDED - ALWAYS include position
            if edge_type in ['PRECEDED', 'SUCCEEDED']:
                position_name = ''
                if edge_props.get('position_id'):
                    position_id = edge_props['position_id']
                    position_node = self.kg.get_node(position_id)
                    position_name = position_node.get('name', '') if position_node else ''
                
                # ALWAYS require position for PRECEDED/SUCCEEDED, skip if missing
                if position_name:
                    if edge_type == 'PRECEDED':
                        statements.append(f"{from_entity} là tiền nhiệm của {to_entity} trong chức vụ {position_name}")
                        relation_questions.append(f"là tiền nhiệm của ai trong chức vụ {position_name}")
                    else:  # SUCCEEDED
                        statements.append(f"{from_entity} kế nhiệm {to_entity} trong chức vụ {position_name}")
                        relation_questions.append(f"kế nhiệm ai trong chức vụ {position_name}")
                else:
                    # Skip this edge if no position context available for PRECEDED/SUCCEEDED
                    return None, None, None
            elif edge_type == 'SERVED_AS':
                # Add term context for SERVED_AS
                term_start = edge_props.get('term_start', '')
                term_end = edge_props.get('term_end', '')
                
                if term_end == 'nay':
                    time_phrase = f"đang giữ chức vụ"
                    if term_start:
                        time_phrase += f" (từ {term_start} đến nay)"
                elif term_start and term_end:
                    time_phrase = f"đã từng giữ chức vụ (từ {term_start} đến {term_end})"
                elif term_start:
                    time_phrase = f"đã từng giữ chức vụ (từ {term_start})"
                else:
                    time_phrase = "đã từng giữ chức vụ"
                    
                statements.append(f"{from_entity} {time_phrase} {to_entity}")
                if term_end == 'nay':
                    relation_questions.append("đang giữ chức vụ gì")
                else:
                    relation_questions.append("đã từng giữ chức vụ gì")
            
            elif edge_type == 'BORN_YEAR':
                statements.append(f"{from_entity} sinh năm {to_entity}")
                relation_questions.append("sinh năm bao nhiêu")
            
            elif edge_type == 'DIED_YEAR':
                statements.append(f"{from_entity} mất năm {to_entity}")
                relation_questions.append("mất năm bao nhiêu")
            
            elif edge_type == 'TERM_DURATION':
                # to_entity is the duration string
                duration_str = to_entity
                
                # Get position name from edge_props['position_id']
                position_name = ""
                if edge_props.get('position_id'):
                    pos_node = self.kg.get_node(edge_props['position_id'])
                    if pos_node:
                        position_name = pos_node.get('name', '')
                
                statements.append(f"{from_entity} giữ chức vụ {position_name} {duration_str}")
                relation_questions.append(f"giữ chức vụ {position_name} trong giai đoạn nào")

            elif edge_type == 'BORN_AT':
                # Add birth year question if we have birth_date
                from_node = self.kg.get_node(path[i*2])  # Get politician node
                birth_date = ''
                if from_node and 'properties' in from_node:
                    birth_date = from_node['properties'].get('birth_date', '')
                
                if birth_date and len(birth_date) >= 4:
                    birth_year = birth_date[:4]
                    statements.append(f"{from_entity} sinh năm {birth_year} tại {to_entity}")
                    relation_questions.append(f"sinh năm bao nhiêu")
                else:
                    statements.append(f"{from_entity} sinh tại {to_entity}")
                    relation_questions.append("sinh ở đâu")
            else:
                # Other relation types
                rel_phrase = RELATION_TEMPLATES.get(edge_type, {}).get('forward', edge_type)
                rel_question = RELATION_TEMPLATES.get(edge_type, {}).get('question', edge_type)
                statements.append(f"{from_entity} {rel_phrase} {to_entity}")
                relation_questions.append(rel_question)
        
        # Generate question based on type
        if q_type in ['TRUE_FALSE', 'YES_NO']:
            # TRUE_FALSE: Statement format "A kế nhiệm B..., C là tiền nhiệm của D.... Đúng hay sai?"
            combined_statement = ", ".join(statements)
            question = f"{combined_statement}. Đúng hay sai?"
            # For TRUE_FALSE, keep the full multi-hop path
            actual_path = path
            actual_hop_count = len([x for x in path[1::2]])  # Count relations
        else:
            # MCQ: Create specific multi-hop questions based on the actual path
            first_entity = entities[0]
            final_entity = entities[-1] if entities else first_entity
            actual_hop_count = len(edge_types)  # Count actual hops
            actual_path = path
            
            # Build MCQ question from the chain of relations
            compound_targets = []
            compound_types = []
            question_parts = []
            
            # Collect all targets along the path for compound answer
            for i, edge_type in enumerate(edge_types):
                edge_props = edge_props_list[i] if i < len(edge_props_list) else {}
                target_entity = entities[i + 1] if i + 1 < len(entities) else "Unknown"
                
                if edge_type == 'PRECEDED':
                    position_name = ''
                    if edge_props.get('position_id'):
                        position_node = self.kg.get_node(edge_props['position_id'])
                        position_name = position_node.get('name', '') if position_node else ''
                    if position_name:
                        question_parts.append(f"là tiền nhiệm của ai trong chức vụ {position_name}")
                    else:
                        question_parts.append("là tiền nhiệm của ai")
                    compound_targets.append(target_entity)
                    compound_types.append("person")
                    
                elif edge_type == 'SUCCEEDED':
                    position_name = ''
                    if edge_props.get('position_id'):
                        position_node = self.kg.get_node(edge_props['position_id'])
                        position_name = position_node.get('name', '') if position_node else ''
                    if position_name:
                        question_parts.append(f"kế nhiệm ai trong chức vụ {position_name}")
                    else:
                        question_parts.append("kế nhiệm ai")
                    compound_targets.append(target_entity)
                    compound_types.append("person")
                    
                elif edge_type == 'SERVED_AS':
                    question_parts.append("đã từng giữ chức vụ gì")
                    compound_targets.append(target_entity)
                    compound_types.append("position")
                    
                elif edge_type == 'BORN_AT':
                    question_parts.append("sinh ở đâu")
                    compound_targets.append(target_entity)
                    compound_types.append("place")
                    
                elif edge_type == 'ALUMNUS_OF':
                    question_parts.append("tốt nghiệp trường nào")
                    compound_targets.append(target_entity)
                    compound_types.append("school")
                    
                elif edge_type == 'HAS_ACADEMIC_TITLE':
                    question_parts.append("có học vị gì")
                    compound_targets.append(target_entity)
                    compound_types.append("degree")
                
                elif edge_type == 'BORN_YEAR':
                    question_parts.append("sinh năm bao nhiêu")
                    compound_targets.append(target_entity)
                    compound_types.append("Year")

                elif edge_type == 'DIED_YEAR':
                    question_parts.append("mất năm bao nhiêu")
                    compound_targets.append(target_entity)
                    compound_types.append("Year")

                elif 'TERM_DURATION' in edge_type:
                    # target_entity is the duration string (from node_names)
                    duration_str = target_entity
                    
                    # Get position name from edge_props['position_id']
                    position_name = ""
                    if edge_props.get('position_id'):
                        pos_node = self.kg.get_node(edge_props['position_id'])
                        if pos_node:
                            position_name = pos_node.get('name', '')
                    
                    question_parts.append(f"giữ chức vụ {position_name} trong giai đoạn nào")
                    compound_targets.append(duration_str)
                    compound_types.append("Duration")
                
                elif 'AWARDED' in edge_type:
                    question_parts.append("nhận giải thưởng gì")
                    compound_targets.append(target_entity)
                    compound_types.append("award")

                elif edge_type == 'SERVED_IN':
                    question_parts.append("phục vụ trong đơn vị nào")
                    compound_targets.append(target_entity)
                    compound_types.append("military_career")

                elif edge_type == 'HAS_RANK':
                    question_parts.append("có cấp bậc gì")
                    compound_targets.append(target_entity)
                    compound_types.append("rank")

                elif edge_type == 'FOUGHT_IN':
                    question_parts.append("tham gia chiến dịch nào")
                    compound_targets.append(target_entity)
                    compound_types.append("campaign")
                    
                else:
                    # Other relations
                    rel_question = RELATION_TEMPLATES.get(edge_type, {}).get('question', edge_type)
                    question_parts.append(rel_question)
                    compound_targets.append(target_entity)
                    compound_types.append("other")
            
            # Build question: use last 2-3 parts for multi-hop, or all for short paths
            if len(question_parts) >= 2:
                # Multi-hop: Ask about the final target through the chain
                # Example: "Người kế nhiệm X trong chức vụ Y tốt nghiệp trường nào?"
                if len(question_parts) == 2:
                    question = f"{first_entity} {question_parts[0]}, và người đó {question_parts[1]}?"
                else:
                    # For 3+ hops, focus on the chain ending
                    chain_desc = f"{first_entity} {question_parts[0]}"
                    for i in range(1, len(question_parts) - 1):
                        chain_desc += f", người đó {question_parts[i]}"
                    question = f"{chain_desc}, và người cuối cùng {question_parts[-1]}?"
            elif len(question_parts) == 1:
                question = f"{first_entity} {question_parts[0]}?"
            else:
                question = f"{first_entity} có liên quan gì?"
                compound_targets = [final_entity]
                compound_types = ["other"]
            
            # Store compound info with actual types
            candidate['compound_info'] = {
                'targets': compound_targets,
                'types': compound_types,
                'is_compound': len(compound_targets) > 1
            }
        
        return question, actual_path, actual_hop_count
    
    def _create_false_candidate(self, candidate: Dict) -> Dict:
        """
        Create a false candidate by swapping a node in the path.
        
        Args:
            candidate: Original valid candidate
            
        Returns:
            Modified candidate with swapped node and is_false=True
        """
        import copy
        false_candidate = copy.deepcopy(candidate)
        path = false_candidate['path']
        
        # Identify nodes in path (indices 0, 2, 4...)
        node_indices = list(range(0, len(path), 2))
        
        # Prefer swapping intermediate or target nodes (avoid start node to keep subject stable)
        if len(node_indices) > 1:
            swap_indices = node_indices[1:]
        else:
            swap_indices = node_indices
            
        swap_idx = random.choice(swap_indices)
        original_node_id = path[swap_idx]
        original_node = self.kg.get_node(original_node_id)
        
        if not original_node:
            return None
            
        # Get replacement node of same type
        node_type = original_node.get('type', 'Politician')
        original_name = original_node.get('name', '')
        
        replacement_name = self._get_random_entity_by_type(node_type, exclude=original_name)
        
        # Find ID for replacement name (best effort)
        replacement_ids = self.kg.get_node_by_name(replacement_name)
        replacement_id = replacement_ids[0] if replacement_ids else f"fake_{int(time.time())}_{random.randint(0,1000)}"
        
        # Update path
        path[swap_idx] = replacement_id
        
        # Update names if start/end swapped
        if swap_idx == 0:
            false_candidate['from_name'] = replacement_name
        elif swap_idx == len(path) - 1:
            false_candidate['to_name'] = replacement_name
            
        # Mark as false
        false_candidate['is_false'] = True
        false_candidate['original_path'] = candidate['path']
        
        return false_candidate

    def _generate_answer(self, candidate: Dict, q_type: str, target_correct_index: int = None) -> tuple:
        """
        Generate answer for a candidate.
        
        Args:
            candidate: Candidate dictionary
            q_type: Question type
            target_correct_index: Optional index (0-3) to force correct answer position for MCQ
        
        Returns:
            Tuple of (answer_data, choices_for_question)
        """
        if q_type in ['TRUE_FALSE', 'YES_NO']:
            # Check if it's a false candidate
            if candidate.get('is_false'):
                return {'answer': 'False', 'type': q_type}, None
            else:
                return {'answer': 'True', 'type': q_type}, None
        
        elif q_type == 'MCQ':
            # Generate multiple choices for compound questions
            compound_info = candidate.get('compound_info', {})
            
            if compound_info.get('is_compound', False):
                # Compound question with multiple targets separated by " - "
                compound_targets = compound_info['targets']
                compound_types = compound_info['types']
                
                # Create correct compound answer: "Target1 - Target2 - Target3"
                correct_answer = ' - '.join(compound_targets)
                
                # Generate alternative compound answers
                choices = []
                choices.append(correct_answer)  # Correct answer first
                
                # Generate 3 incorrect compound answers by mixing different entities
                for i in range(3):
                    fake_parts = []
                    for j, comp_type in enumerate(compound_types):
                        exclude_name = compound_targets[j] if j < len(compound_targets) else None
                        
                        if comp_type == "place":
                            fake_entity = self._get_random_entity_by_type("Location", exclude=exclude_name)
                        elif comp_type == "position":
                            fake_entity = self._get_random_entity_by_type("Position", exclude=exclude_name)
                        elif comp_type == "person":
                            fake_entity = self._get_random_entity_by_type("Politician", exclude=exclude_name)
                        elif comp_type == "school":
                            fake_entity = self._get_random_entity_by_type("AlmaMater", exclude=exclude_name)
                        elif comp_type == "degree":
                            fake_entity = self._get_random_entity_by_type("AcademicTitle", exclude=exclude_name)
                        elif comp_type == "award":
                            fake_entity = self._get_random_entity_by_type("Award", exclude=exclude_name)
                        elif comp_type == "rank":
                            fake_entity = self._get_random_entity_by_type("MilitaryRank", exclude=exclude_name)
                        elif comp_type == "campaign":
                            fake_entity = self._get_random_entity_by_type("Campaigns", exclude=exclude_name)
                        elif comp_type == "military_career":
                            fake_entity = self._get_random_entity_by_type("MilitaryCareer", exclude=exclude_name)
                        elif comp_type == "Year":
                            try:
                                correct_year = int(exclude_name) if exclude_name and exclude_name.isdigit() else 1970
                                fake_year = correct_year + random.randint(-10, 10)
                                while str(fake_year) == exclude_name:
                                     fake_year = correct_year + random.randint(-10, 10)
                                fake_entity = str(fake_year)
                            except:
                                fake_entity = str(random.randint(1950, 2020))
                        elif comp_type == "Duration":
                            years = re.findall(r'\d{4}', exclude_name) if exclude_name else []
                            if years:
                                base_start = int(years[0])
                                base_end = int(years[1]) if len(years) > 1 else None
                                offset = random.randint(-10, 10)
                                while offset == 0: offset = random.randint(-10, 10)
                                fake_start = base_start + offset
                                if base_end:
                                    fake_end = base_end + offset
                                    fake_entity = f"từ {fake_start} đến {fake_end}"
                                else:
                                    fake_entity = f"từ {fake_start}"
                            else:
                                s = random.randint(1990, 2020)
                                e = s + random.randint(1, 5)
                                fake_entity = f"từ {s} đến {e}"
                        else:
                            fake_entity = self._get_random_entity_by_type("Politician", exclude=exclude_name)
                        
                        fake_parts.append(fake_entity)
                    
                    fake_compound = ' - '.join(fake_parts)
                    if fake_compound != correct_answer and fake_compound not in choices:
                        choices.append(fake_compound)
                
                # If we don't have enough choices, generate more varied alternatives
                while len(choices) < 4:
                    fake_parts = []
                    for j, comp_type in enumerate(compound_types):
                        if comp_type == "person":
                            fake_entity = self._get_random_entity_by_type("Politician")
                        elif comp_type == "position":
                            fake_entity = self._get_random_entity_by_type("Position")
                        elif comp_type == "place":
                            fake_entity = self._get_random_entity_by_type("Location")
                        elif comp_type == "school":
                            fake_entity = self._get_random_entity_by_type("AlmaMater")
                        elif comp_type == "degree":
                            fake_entity = self._get_random_entity_by_type("AcademicTitle")
                        elif comp_type == "award":
                            fake_entity = self._get_random_entity_by_type("Award")
                        elif comp_type == "rank":
                            fake_entity = self._get_random_entity_by_type("MilitaryRank")
                        elif comp_type == "campaign":
                            fake_entity = self._get_random_entity_by_type("Campaigns")
                        elif comp_type == "military_career":
                            fake_entity = self._get_random_entity_by_type("MilitaryCareer")
                        elif comp_type == "Year":
                            fake_entity = str(random.randint(1950, 2020))
                        elif comp_type == "Duration":
                            s = random.randint(1990, 2020)
                            e = s + random.randint(1, 5)
                            fake_entity = f"từ {s} đến {e}"
                        else:
                            fake_entity = self._get_random_entity_by_type("Politician")
                        fake_parts.append(fake_entity)
                    fake_compound = ' - '.join(fake_parts)
                    if fake_compound not in choices:
                        choices.append(fake_compound)
                
                # Shuffle choices and find correct index
                random.shuffle(choices)
                
                # If target index provided, swap correct answer to that position
                if target_correct_index is not None and 0 <= target_correct_index < len(choices):
                    current_idx = choices.index(correct_answer)
                    if current_idx != target_correct_index:
                        choices[current_idx], choices[target_correct_index] = choices[target_correct_index], choices[current_idx]
                
                correct_idx = choices.index(correct_answer)
                
                # Format as A), B), C), D)
                formatted_choices = [f"{chr(65+i)}) {choice}" for i, choice in enumerate(choices[:4])]
                
                answer_data = {
                    'choices': formatted_choices,
                    'answer_index': correct_idx,
                    'correct_answer': formatted_choices[correct_idx],
                    'type': 'MCQ'
                }
                
                return answer_data, formatted_choices
                
            else:
                # Single answer question
                correct_answer = candidate['to_name']
                path = candidate['path']
                
                if len(path) >= 3:  # Multi-hop
                    final_entity_id = path[-1]
                    final_entity_node = self.kg.get_node(final_entity_id)
                    entity_type = final_entity_node['type'] if final_entity_node else candidate.get('to_type', 'Politician')
                else:  # Single-hop
                    entity_type = candidate['to_type']
                
                # Check if multi-hop (hop > 1) to include "Không có dữ kiện"
                include_no_data = candidate.get('hop_count', 1) > 1
                
                try:
                    formatted_choices, correct_idx = generate_mcq_choices(
                        correct_answer=correct_answer,
                        entity_type=entity_type,
                        kg=self.kg,
                        num_choices=4,
                        seed=self.config['seed'] + hash(correct_answer) % 1000,
                        target_index=target_correct_index,
                        include_no_data=include_no_data
                    )
                    
                    answer_data = {
                        'choices': formatted_choices,
                        'answer_index': correct_idx,
                        'correct_answer': formatted_choices[correct_idx],
                        'type': 'MCQ'
                    }
                    
                    return answer_data, formatted_choices
                    
                except Exception as e:
                    self.logger.warning(f"Failed to generate MCQ choices for {correct_answer}: {e}")
                    return None, None
        
        return None, None
    
    def _get_random_entity_by_type(self, entity_type: str, exclude: str = None) -> str:
        """Get a random entity name by type, excluding specified entity."""
        import random
        
        # Map entity types to possible alternatives
        type_alternatives = {
            'AcademicTitle': ['Position', 'Politician'],
            'AlmaMater': ['Position', 'Location'],
            'Location': ['Position', 'Politician'],
            'Position': ['Politician', 'Location'],
            'Politician': ['Position', 'Location'],
            'Award': ['Position', 'Politician'],
            'MilitaryRank': ['Position', 'Politician'],
            'Campaigns': ['Location', 'Politician'],
            'MilitaryCareer': ['Position', 'Politician']
        }
        
        # Try primary type first
        types_to_try = [entity_type] + type_alternatives.get(entity_type, [])
        
        for try_type in types_to_try:
            matching_nodes = []
            for node_id, node_data in self.kg.graph.nodes(data=True):
                if node_data.get('type') == try_type and node_data.get('name') != exclude:
                    name = node_data.get('name', '')
                    if name and len(name) > 2:  # Filter out short/empty names
                        matching_nodes.append(name)
            
            if matching_nodes:
                return random.choice(matching_nodes)
        
        # Final fallback - return a generic Vietnamese name
        fallback_names = [
            'Nguyễn Văn An', 'Trần Thị Bình', 'Lê Văn Cường', 'Phạm Thị Dung',
            'Hoàng Văn Em', 'Đỗ Thị Phương', 'Vũ Văn Giang', 'Bùi Thị Hà'
        ]
        return random.choice(fallback_names)
    
    def _enrich_question_with_context(self, question_text: str, candidate: Dict) -> str:
        """
        Enrich question with position and date context from edge properties.
        
        Args:
            question_text: Base question text
            candidate: Candidate dict with 'edge_props' list
        
        Returns:
            Enriched question text
        """
        if 'edge_props' not in candidate or not candidate['edge_props']:
            return question_text
        
        path = candidate['path']
        edge_props_list = candidate['edge_props']
        
        # Extract position context for PRECEDED/SUCCEEDED relations
        position_contexts = []
        for i, edge_type in enumerate(path[1::2]):  # Get all edge types from path
            if i >= len(edge_props_list):
                break
                
            edge_props = edge_props_list[i]
            
            if edge_type in ['PRECEDED', 'SUCCEEDED'] and edge_props.get('position_id'):
                position_id = edge_props['position_id']
                position_node = self.kg.get_node(position_id)
                if position_node:
                    position_name = position_node.get('name', '')
                    if position_name:
                        position_contexts.append(position_name)
            
            elif edge_type == 'SERVED_AS':
                # For SERVED_AS, we already have the position name in the path
                # Just check if we can add date info
                term_start = edge_props.get('term_start', '')
                term_end = edge_props.get('term_end', '')
                if term_start:
                    # Could add date context but keep it simple for now
                    pass
        
        # If we have position contexts, try to inject them into the question
        if position_contexts and ('kế nhiệm' in question_text or 'tiền nhiệm' in question_text):
            # Add position context to make question more specific
            # For now, append it as clarification
            enriched = question_text.rstrip('?.')
            # Only add if question doesn't already mention specific positions
            if not any(pos_ctx in question_text for pos_ctx in position_contexts):
                # Append position context as clarification
                enriched += f" (trong chức vụ {position_contexts[0]})" if len(position_contexts) == 1 else ""
            return enriched + "?"
        
        return question_text
    
    def generate_llm_variants(self, seed_questions: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Generate variants using LLM.
        
        Args:
            seed_questions: List of seed question dictionaries
        
        Returns:
            Tuple of (raw_variants, filtered_variants)
        """
        if not seed_questions:
            return [], []
        
        self.logger.info(f"Generating LLM variants for {len(seed_questions)} seeds...")
        
        llm_client = create_llm_client(model=self.config['llm_model'])
        
        raw_variants = []
        filtered_variants = []
        
        for idx, seed in enumerate(tqdm(seed_questions, desc="LLM generation")):
            try:
                # Format prompt
                answer_str = seed['answer'].get('answer', 'N/A') if isinstance(seed['answer'], dict) else str(seed['answer'])
                
                prompt = format_variant_prompt(
                    seed_question=seed['question'],
                    q_type=seed['q_type'],
                    hop_count=seed['hop_count'],
                    reasoning_path=seed['reasoning_path'],
                    answer=answer_str
                )
                
                # Call LLM
                response = llm_client.generate(prompt, temperature=0.7, max_tokens=1500)
                
                # Add delay between calls to avoid rate limit
                if idx < len(seed_questions) - 1:  # Don't delay after last call
                    time.sleep(1)  # 1 second delay between calls
                
                # Parse response
                parsed = parse_llm_response(response)
                
                if not parsed or 'variants' not in parsed:
                    self.logger.warning(f"Failed to parse LLM response for seed {seed['id']}")
                    continue
                
                # Store raw variants
                raw_variants.append({
                    'seed_id': seed['id'],
                    'variants': parsed['variants']
                })
                
                # Verify and filter variants
                for variant in parsed['variants']:
                    variant_type = variant.get('variant_type')
                    question_text = variant.get('question')
                    reasoning_hint = variant.get('reasoning_hint', '')
                    
                    if not question_text or len(question_text) < 10:
                        continue
                    
                    # Verify variant based on type
                    is_valid = self._verify_variant(variant_type, question_text, reasoning_hint, seed)
                    
                    if is_valid:
                        question_id = len(self.questions) + len(filtered_variants) + 1
                        
                        # For MCQ variants, we need to generate choices and append to question
                        final_question_text = question_text
                        answer_data = seed['answer']  # Start with seed answer
                        
                        if seed['q_type'] == 'MCQ':
                            if variant_type == 'UNANSWERABLE':
                                # UNANSWERABLE MCQ: Add "Không có dữ kiện" option as correct answer
                                seed_choices = []
                                if isinstance(seed['answer'], dict) and seed['answer'].get('type') == 'MCQ':
                                    # Extract raw choices without A), B) prefix
                                    raw_choices = [c.split(') ', 1)[1] for c in seed['answer'].get('choices', [])]
                                    seed_choices = raw_choices[:3]  # Take first 3 choices
                                
                                # Add "Không có dữ kiện" and shuffle
                                all_choices = seed_choices + ["Không có dữ kiện"]
                                import random
                                random.shuffle(all_choices)
                                
                                # Find index of "Không có dữ kiện"
                                correct_idx = all_choices.index("Không có dữ kiện")
                                
                                # Format choices
                                formatted_choices = [f"{chr(65+i)}) {choice}" for i, choice in enumerate(all_choices)]
                                final_question_text = f"{question_text}\n" + "\n".join(formatted_choices)
                                
                                # Set correct answer
                                answer_data = {
                                    'type': 'MCQ',
                                    'answer': formatted_choices[correct_idx],
                                    'choices': formatted_choices,
                                    'correct_idx': correct_idx
                                }
                            else:
                                # Other variants: reuse seed choices
                                if isinstance(seed['answer'], dict) and seed['answer'].get('type') == 'MCQ':
                                    seed_choices = seed['answer'].get('choices', [])
                                    if seed_choices:
                                        final_question_text = f"{question_text}\n" + "\n".join(seed_choices)
                                        answer_data = seed['answer']  # Keep original MCQ answer structure
                        
                        elif seed['q_type'] in ['TRUE_FALSE', 'YES_NO']:
                            if variant_type == 'UNANSWERABLE':
                                # UNANSWERABLE TRUE_FALSE: Answer is "Not Given"
                                answer_data = {
                                    'answer': 'Not Given',
                                    'type': seed['q_type']
                                }
                            # PARAPHRASE_HARD: Keep original answer (True) - only paraphrased, not changed
                        
                        filtered_variants.append({
                            'id': question_id,
                            'question': final_question_text,
                            'q_type': seed['q_type'],  # Keep original q_type (MCQ/TRUE_FALSE)
                            'hop_count': seed['hop_count'],
                            'reasoning_path': seed['reasoning_path'],
                            'answer': answer_data,
                            'seed_id': seed['id'],
                            'reasoning_hint': reasoning_hint,
                            'variant_type': variant_type  # UNANSWERABLE, PARAPHRASE_HARD
                        })
                        
                        self.stats[f"llm_{variant_type}"] += 1
                
            except Exception as e:
                self.logger.warning(f"Error generating variants for seed {seed['id']}: {e}")
                continue
        
        self.logger.info(f"Generated {len(filtered_variants)} valid LLM variants from {len(raw_variants)} raw outputs")
        
        return raw_variants, filtered_variants
    
    def _verify_variant(self, variant_type: str, question: str, 
                       reasoning_hint: str, seed: Dict) -> bool:
        """
        Verify that LLM-generated variant matches intended type.
        
        Args:
            variant_type: UNANSWERABLE or PARAPHRASE_HARD
            question: Generated question text
            reasoning_hint: Hint about reasoning
            seed: Original seed question
        
        Returns:
            True if variant is valid for its type
        """
        # For UNANSWERABLE: should mention entities not in KG or impossible relations
        if variant_type == 'UNANSWERABLE':
            # Basic heuristic: if it's too similar to seed, it might be answerable
            if question.lower() == seed['question'].lower():
                return False
            # Accept if reasoning_hint mentions missing info
            if any(keyword in reasoning_hint.lower() for keyword in 
                   ['không có', 'thiếu', 'không tồn tại', 'không tìm thấy']):
                return True
            return True  # Accept by default (LLM should know)
        
        # For PARAPHRASE_HARD: should be different but have same answer
        elif variant_type == 'PARAPHRASE_HARD':
            # Should be different from original
            if question.lower() == seed['question'].lower():
                return False
            return True
        
        return False
    
    def save_outputs(self, output_dir: str, llm_raw: List[Dict] = None, 
                    llm_filtered: List[Dict] = None):
        """
        Save generated questions and answers to SEPARATE CSV files (MCQ and TRUE_FALSE).
        
        Args:
            output_dir: Output directory path
            llm_raw: Raw LLM variants (optional)
            llm_filtered: Filtered LLM variants (optional)
        """
        self.logger.info(f"Saving outputs to {output_dir}...")
        
        # Separate questions by type
        mcq_questions = []
        mcq_answers = []
        true_false_questions = []
        true_false_answers = []
        
        for q in self.questions:
            q_type = q['q_type']
            
            # Determine variant type (Normal, Negative, Hard-paraphrase)
            variant_type = q.get('variant_type', 'Normal')
            
            # Check if it's MCQ or TRUE_FALSE
            is_mcq = (q_type == 'MCQ' or 
                     (isinstance(q.get('answer'), dict) and q['answer'].get('type') == 'MCQ'))
            
            # Prepare question data (with variant_type column)
            question_data = {
                'question': q['question'],
                'hop_count': q['hop_count'],
                'reasoning_path': json.dumps(q['reasoning_path'], ensure_ascii=False),
                'variant_type': variant_type
            }
            
            # Prepare answer
            if isinstance(q['answer'], dict):
                if q['answer']['type'] == 'MCQ':
                    # For MCQ, answer is just the letter (A, B, C, D)
                    if 'answer_index' in q['answer']:
                        answer_letter = chr(65 + q['answer']['answer_index'])  # 0->A, 1->B, etc.
                        answer_str = answer_letter
                    elif q['answer'].get('answer') == 'D) Không có dữ kiện':
                        answer_str = 'D'  # UNANSWERABLE
                    else:
                        # Extract letter from full answer like "A) Nguyễn Văn A"
                        full_answer = q['answer'].get('correct_answer', q['answer'].get('answer', ''))
                        if full_answer and len(full_answer) >= 1 and full_answer[0] in 'ABCD':
                            answer_str = full_answer[0]
                        else:
                            answer_str = 'A'  # Default fallback
                else:
                    # TRUE_FALSE: Convert to Vietnamese (Đúng, Sai, Không có dữ kiện)
                    raw_answer = q['answer'].get('answer', 'True')
                    if raw_answer == 'True':
                        answer_str = 'Đúng'
                    elif raw_answer == 'False':
                        answer_str = 'Sai'
                    elif raw_answer in ['Not Given', 'Không có dữ kiện']:
                        answer_str = 'Không có dữ kiện'
                    else:
                        answer_str = 'Đúng'  # Default
            else:
                answer_str = str(q['answer'])
            
            answer_data = {
                'answer': answer_str
            }
            
            # Separate by type
            if is_mcq:
                mcq_questions.append(question_data)
                mcq_answers.append(answer_data)
            else:
                true_false_questions.append(question_data)
                true_false_answers.append(answer_data)
        
        # Reset IDs from 1 for each file
        for i, (q, a) in enumerate(zip(mcq_questions, mcq_answers), start=1):
            q['id'] = i
            a['id'] = i
        
        for i, (q, a) in enumerate(zip(true_false_questions, true_false_answers), start=1):
            q['id'] = i
            a['id'] = i
        
        # Save MCQ files
        if mcq_questions:
            mcq_questions_df = pd.DataFrame(mcq_questions)
            mcq_answers_df = pd.DataFrame(mcq_answers)
            
            # Reorder columns: id first
            mcq_questions_df = mcq_questions_df[['id', 'question', 'hop_count', 'reasoning_path', 'variant_type']]
            mcq_answers_df = mcq_answers_df[['id', 'answer']]
            
            mcq_questions_df.to_csv(os.path.join(output_dir, 'mcq_questions.csv'), 
                                   index=False, encoding='utf-8')
            mcq_answers_df.to_csv(os.path.join(output_dir, 'mcq_answers.csv'), 
                                 index=False, encoding='utf-8')
            
            self.logger.info(f"Saved {len(mcq_questions)} MCQ questions and answers")
        else:
            self.logger.warning("No MCQ questions to save")
        
        # Save TRUE_FALSE files
        if true_false_questions:
            tf_questions_df = pd.DataFrame(true_false_questions)
            tf_answers_df = pd.DataFrame(true_false_answers)
            
            # Reorder columns: id first
            tf_questions_df = tf_questions_df[['id', 'question', 'hop_count', 'reasoning_path', 'variant_type']]
            tf_answers_df = tf_answers_df[['id', 'answer']]
            
            tf_questions_df.to_csv(os.path.join(output_dir, 'true_false_questions.csv'), 
                                  index=False, encoding='utf-8')
            tf_answers_df.to_csv(os.path.join(output_dir, 'true_false_answers.csv'), 
                                index=False, encoding='utf-8')
            
            self.logger.info(f"Saved {len(true_false_questions)} TRUE_FALSE questions and answers")
        else:
            self.logger.warning("No TRUE_FALSE questions to save")
        
        # Save LLM variants if provided
        if llm_raw:
            with open(os.path.join(output_dir, 'llm_variants_raw.json'), 'w', encoding='utf-8') as f:
                json.dump(llm_raw, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved {len(llm_raw)} raw LLM variants")
        
        if llm_filtered:
            with open(os.path.join(output_dir, 'llm_variants_filtered.json'), 'w', encoding='utf-8') as f:
                json.dump(llm_filtered, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved {len(llm_filtered)} filtered LLM variants")
    
    def print_stats(self):
        """Print generation statistics."""
        self.logger.info("=" * 60)
        self.logger.info("GENERATION STATISTICS")
        self.logger.info("=" * 60)
        self.logger.info(f"Total questions generated: {len(self.questions)}")
        
        # By question type
        by_type = defaultdict(int)
        by_hop = defaultdict(int)
        
        for q in self.questions:
            by_type[q['q_type']] += 1
            by_hop[q['hop_count']] += 1
        
        self.logger.info("\nBy question type:")
        for q_type, count in sorted(by_type.items()):
            self.logger.info(f"  {q_type}: {count}")
        
        self.logger.info("\nBy hop count:")
        for hop, count in sorted(by_hop.items()):
            self.logger.info(f"  {hop}-hop: {count}")
        
        self.logger.info("\nDetailed breakdown:")
        for key, count in sorted(self.stats.items()):
            self.logger.info(f"  {key}: {count}")
        
        self.logger.info("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate multi-hop reasoning dataset from knowledge graph"
    )
    
    parser.add_argument('--kg', type=str, default='knowledge_graph_enriched.json',
                       help='Path to knowledge graph JSON file')
    parser.add_argument('--total', type=int, default=1000,
                       help='Total number of questions to generate')
    parser.add_argument('--out_dir', type=str, default='./output',
                       help='Output directory')
    parser.add_argument('--multi_ratio', type=float, default=0.50,
                       help='Ratio of multi-hop questions')
    parser.add_argument('--single_ratio', type=float, default=0.15,
                       help='Ratio of single-hop questions')
    parser.add_argument('--max_hop', type=int, default=4,
                       help='Maximum number of hops for multi-hop questions')
    parser.add_argument('--llm_model', type=str, default='gemini-2.5-flash-lite',
                       help='Gemini model name (gemini-2.5-flash-lite, gemini-1.5-pro, etc.)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for reproducibility')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--dry_run', action='store_true',
                       help='Dry run: only print stats without writing files')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.out_dir, exist_ok=True)
    
    # Setup logging
    setup_logging(args.out_dir, args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting dataset generation...")
    logger.info(f"Configuration: {vars(args)}")
    
    # Load knowledge graph
    logger.info(f"Loading knowledge graph from {args.kg}...")
    kg = KnowledgeGraph(args.kg)
    
    # Create generator
    config = {
        'seed': args.seed,
        'max_hop': args.max_hop,
        'llm_model': args.llm_model
    }
    
    generator = DatasetGenerator(kg, config)
    
    # Generate candidates
    single_hop_candidates, multi_hop_candidates = generator.generate_candidates()
    
    # ===== NEW DISTRIBUTION LOGIC =====
    # MCQ = TRUE_FALSE (50% - 50%)
    # Each type: LLM = 1/3, Normal = 2/3
    # Multi-hop = 80%, Single-hop = 20%
    # MCQ: UNANSWERABLE + PARAPHRASE_HARD
    # TRUE_FALSE: UNANSWERABLE + PARAPHRASE_HARD
    
    total = args.total
    mcq_total = total // 2
    tf_total = total - mcq_total
    
    # For each type: Normal = 2/3, LLM = 1/3
    mcq_normal = int(mcq_total * 2 / 3)
    mcq_llm = mcq_total - mcq_normal
    
    tf_normal = int(tf_total * 2 / 3)
    tf_llm = tf_total - tf_normal
    
    # Multi-hop = 80%, Single-hop = 20% (for Normal questions)
    mcq_multi = int(mcq_normal * 0.8)
    mcq_single = mcq_normal - mcq_multi
    
    tf_multi = int(tf_normal * 0.8)
    tf_single = tf_normal - tf_multi
    
    logger.info(f"=== Distribution Plan ===")
    logger.info(f"MCQ: {mcq_total} total = {mcq_normal} normal ({mcq_multi} multi + {mcq_single} single) + {mcq_llm} LLM")
    logger.info(f"TRUE_FALSE: {tf_total} total = {tf_normal} normal ({tf_multi} multi + {tf_single} single) + {tf_llm} LLM")
    
    # Calculate expected LLM bias for balancing
    # MCQ LLM: ~50% UNANSWERABLE (Random A-D), ~50% PARAPHRASE (Random A-D)
    # Since UNANSWERABLE now has randomized answer position (not just D),
    # we don't need to bias D.
    expected_mcq_d = 0
    initial_mcq_counts = [0, 0, 0, 0]
    
    # TF LLM: ~50% UNANSWERABLE (Not Given), ~50% PARAPHRASE (True/False)
    # UNANSWERABLE is "Not Given" (not counted as True/False for balancing purposes, or neutral)
    # PARAPHRASE preserves seed (50/50).
    # So no bias needed for True/False from LLM.
    expected_tf_false_bias = 0
    initial_tf_counts = {'True': 0, 'False': 0}
    
    logger.info(f"Balancing Strategy:")
    logger.info(f"  MCQ: No pre-filling (UNANSWERABLE variants are randomized)")
    logger.info(f"  TF: No pre-filling")
    
    # Separate candidates by question type
    # First, generate all normal questions with forced types
    logger.info("Generating MCQ questions...")
    mcq_questions = generator.generate_questions_by_type(
        multi_hop_candidates, single_hop_candidates,
        multi_count=mcq_multi, single_count=mcq_single,
        q_type='MCQ',
        initial_mcq_counts=initial_mcq_counts
    )
    
    logger.info("Generating TRUE_FALSE questions...")
    tf_questions = generator.generate_questions_by_type(
        multi_hop_candidates, single_hop_candidates,
        multi_count=tf_multi, single_count=tf_single,
        q_type='TRUE_FALSE',
        initial_tf_counts=initial_tf_counts
    )
    
    # Store normal questions
    generator.questions.extend(mcq_questions)
    generator.questions.extend(tf_questions)
    
    logger.info(f"Generated {len(mcq_questions)} MCQ + {len(tf_questions)} TRUE_FALSE normal questions")
    
    # Generate LLM variants
    llm_raw = []
    llm_filtered = []
    
    # MCQ LLM: 2 variant types (UNANSWERABLE, PARAPHRASE_HARD)
    # => Need mcq_llm / 2 seeds (each seed produces 2 variants)
    mcq_seed_count = (mcq_llm // 2) + 1  # +1 buffer for failed variants
    mcq_seeds = [q for q in mcq_questions][:mcq_seed_count]
    
    # TRUE_FALSE LLM: 2 variant types (UNANSWERABLE, PARAPHRASE_HARD)
    # => Need tf_llm / 2 seeds (each seed produces 2 variants)
    tf_seed_count = (tf_llm // 2) + 1
    tf_seeds = [q for q in tf_questions][:tf_seed_count]
    
    logger.info(f"LLM seeds: {len(mcq_seeds)} MCQ + {len(tf_seeds)} TF = {len(mcq_seeds) + len(tf_seeds)} API calls")
    
    if mcq_seeds or tf_seeds:
        all_seeds = mcq_seeds + tf_seeds
        llm_raw, llm_filtered = generator.generate_llm_variants(all_seeds)
        
        # Separate by question type and variant type
        mcq_unanswerable = [v for v in llm_filtered if v['q_type'] == 'MCQ' and v.get('variant_type') == 'UNANSWERABLE']
        mcq_paraphrase = [v for v in llm_filtered if v['q_type'] == 'MCQ' and v.get('variant_type') == 'PARAPHRASE_HARD']
        
        tf_unanswerable = [v for v in llm_filtered if v['q_type'] == 'TRUE_FALSE' and v.get('variant_type') == 'UNANSWERABLE']
        tf_paraphrase = [v for v in llm_filtered if v['q_type'] == 'TRUE_FALSE' and v.get('variant_type') == 'PARAPHRASE_HARD']
        
        logger.info(f"MCQ LLM: {len(mcq_unanswerable)} UNANSWERABLE, {len(mcq_paraphrase)} PARAPHRASE_HARD")
        logger.info(f"TRUE_FALSE LLM: {len(tf_unanswerable)} UNANSWERABLE, {len(tf_paraphrase)} PARAPHRASE_HARD")
        
        # Select MCQ LLM variants
        mcq_llm_selected = []
        mcq_llm_half = mcq_llm // 2
        mcq_llm_selected.extend(mcq_unanswerable[:mcq_llm_half])
        mcq_llm_selected.extend(mcq_paraphrase[:mcq_llm - len(mcq_llm_selected)])
        
        # Select TRUE_FALSE LLM variants
        tf_llm_selected = []
        # Split between UNANSWERABLE and PARAPHRASE_HARD
        tf_llm_half = tf_llm // 2
        tf_llm_selected.extend(tf_unanswerable[:tf_llm_half])
        tf_llm_selected.extend(tf_paraphrase[:tf_llm - len(tf_llm_selected)])
        
        # Add to questions
        generator.questions.extend(mcq_llm_selected)
        generator.questions.extend(tf_llm_selected)
        
        logger.info(f"Added {len(mcq_llm_selected)} MCQ LLM + {len(tf_llm_selected)} TRUE_FALSE LLM variants")
    
    # Print statistics
    generator.print_stats()
    
    # Save outputs
    if not args.dry_run:
        generator.save_outputs(args.out_dir, llm_raw, llm_filtered)
        logger.info(f"✓ Dataset generation complete! Output saved to {args.out_dir}")
    else:
        logger.info("Dry run complete (no files written)")


if __name__ == '__main__':
    main()
