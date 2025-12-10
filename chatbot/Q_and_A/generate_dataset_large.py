"""
Script for generating LARGE-SCALE multi-hop reasoning dataset (30,000+ questions)
with comprehensive hop pattern coverage (1, 2, 3, 4-hop) and infinite key rotation.

Usage:
    python chatbot/Q_and_A/generate_dataset_large.py --kg data/processed/graph/knowledge_graph_enriched.json --out_dir chatbot/Q_and_A/output_large

Features:
- 30,000 questions total: 29,000 template-based + 1,000 LLM variants
- Comprehensive hop patterns:
  * 1-hop: quê, năm sinh, chức vụ, giải thưởng, học vị, trường, etc.
  * 2-hop: quê+năm sinh, quê+chức vụ, chức vụ+giải thưởng, etc.
  * 3-hop and 4-hop: all valid combinations
- 80% multi-hop (2-4 hops), 20% single-hop (1 hop)
- Infinite key rotation: automatically loops back to key 0
- Rate limiting: 1 request/second, 5 seconds between key switches
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from collections import defaultdict, Counter
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from tqdm import tqdm
import pandas as pd
from dotenv import load_dotenv
from itertools import combinations, product

# Load environment variables
load_dotenv()

# Conditional import for LLM (only when needed)
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    genai = None

# Import existing modules
from kg_utils import KnowledgeGraph
from templates import (
    generate_single_hop_question,
    generate_multi_hop_question,
    generate_mcq_choices,
    generate_false_statement,
    get_relation_phrase,
    RELATION_TEMPLATES
)


def setup_logging(output_dir: str, verbose: bool = False):
    """Setup logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    log_file = os.path.join(output_dir, "process_large.log")
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


class InfiniteKeyRotator:
    """
    API Key Rotator with infinite loop support.
    - 1 request per second
    - 5 seconds delay between key switches
    - Loops back to key 0 when exhausted
    """
    
    def __init__(self):
        self.keys = self._load_api_keys()
        self.current_index = 0
        self.request_count = 0
        self.last_request_time = 0
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if not self.keys:
            raise ValueError("No API keys found in .env file")
        
        self.logger.info(f"Loaded {len(self.keys)} API keys for infinite rotation")
        self._activate_current_key()
    
    def _load_api_keys(self) -> List[Tuple[str, str]]:
        """Load all available API keys."""
        keys = []
        
        # Load GOOGLE_API_KEY
        main_key = os.getenv("GOOGLE_API_KEY")
        if main_key:
            keys.append(("GOOGLE_API_KEY", main_key))
        
        # Load GOOGLE_API_KEY_1, GOOGLE_API_KEY_2, ...
        index = 1
        while True:
            key_name = f"GOOGLE_API_KEY_{index}"
            key_value = os.getenv(key_name)
            if not key_value:
                break
            keys.append((key_name, key_value))
            index += 1
        
        # Load GEMINI_API_KEY_*
        for index in range(1, 200):
            key_name = f"GEMINI_API_KEY_{index}"
            key_value = os.getenv(key_name)
            if key_value:
                keys.append((key_name, key_value))
        
        return keys
    
    def _activate_current_key(self):
        """Activate the current key."""
        if not HAS_GENAI:
            return
        key_name, key_value = self.keys[self.current_index]
        genai.configure(api_key=key_value)
        self.logger.info(f"Activated key: {key_name} (index {self.current_index})")
    
    def get_current_key_name(self) -> str:
        """Get the current key name."""
        return self.keys[self.current_index][0]
    
    def rotate_key(self):
        """Rotate to next key with 5-second delay. Loops back to key 0 when exhausted."""
        old_key = self.get_current_key_name()
        
        # Wait 5 seconds before switching
        self.logger.info(f"Waiting 5 seconds before rotating key...")
        time.sleep(5)
        
        # Move to next key (loop back to 0 if at end)
        self.current_index = (self.current_index + 1) % len(self.keys)
        
        self._activate_current_key()
        self.logger.info(f"Rotated: {old_key} → {self.get_current_key_name()}")
        self.request_count = 0  # Reset counter for new key
    
    def wait_for_rate_limit(self):
        """Enforce 1 request per second rate limit."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < 1.0:
            sleep_time = 1.0 - elapsed
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.request_count += 1
    
    def handle_api_error(self, error: Exception) -> bool:
        """
        Handle API errors and rotate key if needed.
        Always returns True (infinite rotation).
        """
        error_str = str(error).lower()
        
        quota_errors = ["quota", "rate limit", "429", "resource_exhausted", "too many requests"]
        should_rotate = any(err in error_str for err in quota_errors)
        
        if should_rotate:
            self.logger.warning(f"Quota/rate limit error: {error}")
            self.rotate_key()
            return True
        else:
            self.logger.error(f"API error: {error}")
            return False


class LargeScaleDatasetGenerator:
    """Generator for large-scale dataset (30,000+ questions)."""
    
    def __init__(self, kg: KnowledgeGraph, config: Dict):
        self.kg = kg
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        random.seed(config['seed'])
        
        # Storage
        self.questions = []
        self.question_ids = set()
        self.reasoning_paths_seen = {}
        
        # Statistics
        self.stats = defaultdict(int)
        
        # LLM client with infinite key rotation (only if genai available)
        if HAS_GENAI:
            self.key_rotator = InfiniteKeyRotator()
            self.llm_model = genai.GenerativeModel(config.get('llm_model', 'gemini-2.5-flash-lite'))
        else:
            self.key_rotator = None
            self.llm_model = None
        
        # Build indices
        self.served_as_index = self._build_served_as_index()
        
        self.logger.info("LargeScaleDatasetGenerator initialized")
    
    def _build_served_as_index(self) -> Set[Tuple[str, str]]:
        """Build (politician_id, position_id) index."""
        index = set()
        for u, v, data in self.kg.graph.edges(data=True):
            if data.get('type') == 'SERVED_AS':
                index.add((u, v))
        return index
    
    def _has_duplicate_nodes(self, path: List[str]) -> bool:
        """
        Check if a path has duplicate node IDs (excluding relations).
        Returns True if duplicates found, False otherwise.
        
        Example: [pol1, SUCCEEDED, pol1, ...] -> True (duplicate pol1)
        """
        nodes = [path[i] for i in range(0, len(path), 2)]  # Extract nodes (even indices)
        return len(nodes) != len(set(nodes))
    
    # ========== COMPREHENSIVE HOP PATTERN GENERATION ==========
    
    def generate_all_1hop_patterns(self) -> List[Dict]:
        """
        Generate ALL possible 1-hop patterns:
        - Politician -> BORN_AT -> Province
        - Politician -> BORN_YEAR -> Year
        - Politician -> SERVED_AS -> Position
        - Politician -> AWARDED -> Award
        - Politician -> ALUMNUS_OF -> School
        - Politician -> HAS_ACADEMIC_TITLE -> Title
        - etc.
        """
        candidates = []
        self.logger.info("Generating comprehensive 1-hop patterns...")
        
        # Define edge types to cover (exclude succession edges for 1-hop)
        edge_types = [et for et in self.kg.edge_types if et not in ['SUCCEEDED', 'PRECEDED']]
        
        all_nodes = list(self.kg.graph.nodes())
        
        for edge_type in edge_types:
            for node_id in all_nodes:
                edges = self.kg.get_outgoing_edges(node_id)
                
                for edge in edges:
                    if edge['type'] != edge_type:
                        continue
                    
                    if edge['from'] == edge['to']:  # Skip self-loops
                        continue
                    
                    from_node = self.kg.get_node(edge['from'])
                    to_node = self.kg.get_node(edge['to'])
                    
                    if not from_node or not to_node:
                        continue
                    if not from_node.get('name') or not to_node.get('name'):
                        continue
                    
                    # Create path signature
                    path_sig = f"{edge['from']}|{edge['type']}|{edge['to']}"
                    
                    # Limit reuse
                    if self.reasoning_paths_seen.get(path_sig, 0) >= 2:
                        continue
                    
                    self.reasoning_paths_seen[path_sig] = self.reasoning_paths_seen.get(path_sig, 0) + 1
                    
                    candidates.append({
                        'path': [edge['from'], edge['type'], edge['to']],
                        'hop_count': 1,
                        'from_name': from_node['name'],
                        'to_name': to_node['name'],
                        'from_type': from_node['type'],
                        'to_type': to_node['type'],
                        'relation': edge['type'],
                        'edge_props': [edge.get('properties', {})]
                    })
        
        # Add virtual relations (BORN_YEAR, DIED_YEAR, TERM_DURATION)
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
                        'path': [node_id, 'BORN_YEAR', f'YEAR_{year}'],
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
                        'path': [node_id, 'DIED_YEAR', f'YEAR_{year}'],
                        'hop_count': 1,
                        'from_name': node['name'],
                        'to_name': year,
                        'from_type': 'Politician',
                        'to_type': 'Year',
                        'relation': 'DIED_YEAR',
                        'edge_props': []
                    })
            
            # TERM_DURATION
            edges = self.kg.get_outgoing_edges(node_id)
            for edge in edges:
                if edge['type'] == 'SERVED_AS':
                    props = edge.get('properties', {})
                    start = props.get('term_start')
                    end = props.get('term_end')
                    
                    if start and end:
                        duration_str = f"từ {start} đến {end}"
                        duration_id = f"DURATION_{duration_str}"
                        
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
        
        self.logger.info(f"Generated {len(candidates)} 1-hop patterns")
        return candidates
    
    def generate_all_2hop_patterns(self) -> List[Dict]:
        """
        Generate ALL possible 2-hop patterns:
        - Pol A -> BORN_AT -> Province, BORN_YEAR -> Year
        - Pol A -> BORN_AT -> Province, SERVED_AS -> Position
        - Pol A -> SERVED_AS -> Position1, AWARDED -> Award
        - Pol A -> SUCCEEDED -> Pol B -> BORN_AT -> Province
        - etc.
        """
        candidates = []
        self.logger.info("Generating comprehensive 2-hop patterns...")
        
        politicians = [nid for nid in self.kg.graph.nodes() 
                      if self.kg.get_node(nid) and self.kg.get_node(nid).get('type') == 'Politician']
        
        # Pattern 1: Pol -> Edge1 -> X -> Edge2 -> Y (chain through intermediate node)
        for pol_id in politicians:
            edges_1 = self.kg.get_outgoing_edges(pol_id)
            
            for edge1 in edges_1:
                intermediate_id = edge1['to']
                edges_2 = self.kg.get_outgoing_edges(intermediate_id)
                
                for edge2 in edges_2:
                    if edge2['to'] == pol_id:  # Avoid loops
                        continue
                    
                    # Build candidate
                    path = [pol_id, edge1['type'], intermediate_id, edge2['type'], edge2['to']]
                    
                    # Skip if path has duplicate nodes
                    if self._has_duplicate_nodes(path):
                        continue
                    
                    path_sig = "|".join(path)
                    
                    if self.reasoning_paths_seen.get(path_sig, 0) >= 1:
                        continue
                    
                    pol_node = self.kg.get_node(pol_id)
                    inter_node = self.kg.get_node(intermediate_id)
                    end_node = self.kg.get_node(edge2['to'])
                    
                    if not all([pol_node, inter_node, end_node]):
                        continue
                    if not all([pol_node.get('name'), inter_node.get('name'), end_node.get('name')]):
                        continue
                    
                    self.reasoning_paths_seen[path_sig] = 1
                    
                    candidates.append({
                        'path': path,
                        'hop_count': 2,
                        'from_name': pol_node['name'],
                        'to_name': end_node['name'],
                        'from_type': pol_node['type'],
                        'to_type': end_node['type'],
                        'edge_props': [edge1.get('properties', {}), edge2.get('properties', {})]
                    })
                    
                    if len(candidates) % 10000 == 0:
                        self.logger.info(f"  Generated {len(candidates)} 2-hop patterns so far...")
        
        # Skip Pattern 2 (virtual year relations after physical edges) 
        # because it creates confusing questions like "Position sinh năm X"
        
        self.logger.info(f"Generated {len(candidates)} 2-hop patterns")
        return candidates
    
    def generate_all_3hop_patterns(self, max_candidates: int = 100000) -> List[Dict]:
        """
        Generate 3-hop patterns with limit to avoid explosion.
        Now starts from ALL node types, not just Politicians.
        """
        candidates = []
        self.logger.info("Generating 3-hop patterns...")
        
        # Get ALL nodes (all types)
        all_nodes = [nid for nid in self.kg.graph.nodes() if self.kg.get_node(nid)]
        
        random.shuffle(all_nodes)
        
        for node_id in all_nodes:
            if len(candidates) >= max_candidates:
                break
            
            edges_1 = self.kg.get_outgoing_edges(node_id)
            
            for edge1 in edges_1[:15]:  # Limit branching
                inter1 = edge1['to']
                edges_2 = self.kg.get_outgoing_edges(inter1)
                
                for edge2 in edges_2[:15]:
                    inter2 = edge2['to']
                    edges_3 = self.kg.get_outgoing_edges(inter2)
                    
                    for edge3 in edges_3[:15]:
                        if edge3['to'] in [node_id, inter1]:  # Avoid cycles
                            continue
                        
                        path = [node_id, edge1['type'], inter1, edge2['type'], inter2, edge3['type'], edge3['to']]
                        
                        # Skip if path has duplicate nodes
                        if self._has_duplicate_nodes(path):
                            continue
                        
                        path_sig = "|".join(path)
                        
                        if self.reasoning_paths_seen.get(path_sig, 0) >= 1:
                            continue
                        
                        # Validate all nodes
                        nodes = [self.kg.get_node(path[i]) for i in range(0, len(path), 2)]
                        if not all(nodes):
                            continue
                        if not all(n.get('name') for n in nodes):
                            continue
                        
                        self.reasoning_paths_seen[path_sig] = 1
                        
                        candidates.append({
                            'path': path,
                            'hop_count': 3,
                            'from_name': nodes[0]['name'],
                            'to_name': nodes[-1]['name'],
                            'from_type': nodes[0]['type'],
                            'to_type': nodes[-1]['type'],
                            'edge_props': [edge1.get('properties', {}), edge2.get('properties', {}), edge3.get('properties', {})]
                        })
                        
                        if len(candidates) >= max_candidates:
                            break
                    if len(candidates) >= max_candidates:
                        break
                if len(candidates) >= max_candidates:
                    break
        
        self.logger.info(f"Generated {len(candidates)} 3-hop patterns")
        return candidates
    
    def generate_all_4hop_patterns(self, max_candidates: int = 50000) -> List[Dict]:
        """
        Generate 4-hop patterns with strict limit.
        Now starts from ALL node types, not just Politicians.
        """
        candidates = []
        self.logger.info("Generating 4-hop patterns...")
        
        # Get ALL nodes (all types)
        all_nodes = [nid for nid in self.kg.graph.nodes() if self.kg.get_node(nid)]
        
        random.shuffle(all_nodes)
        
        for node_id in all_nodes:
            if len(candidates) >= max_candidates:
                break
            
            edges_1 = self.kg.get_outgoing_edges(node_id)
            
            for edge1 in edges_1[:10]:
                inter1 = edge1['to']
                edges_2 = self.kg.get_outgoing_edges(inter1)
                
                for edge2 in edges_2[:10]:
                    inter2 = edge2['to']
                    edges_3 = self.kg.get_outgoing_edges(inter2)
                    
                    for edge3 in edges_3[:10]:
                        inter3 = edge3['to']
                        edges_4 = self.kg.get_outgoing_edges(inter3)
                        
                        for edge4 in edges_4[:10]:
                            if edge4['to'] in [node_id, inter1, inter2]:
                                continue
                            
                            path = [node_id, edge1['type'], inter1, edge2['type'], inter2, 
                                   edge3['type'], inter3, edge4['type'], edge4['to']]
                            
                            # Skip if path has duplicate nodes
                            if self._has_duplicate_nodes(path):
                                continue
                            
                            path_sig = "|".join(path)
                            
                            if self.reasoning_paths_seen.get(path_sig, 0) >= 1:
                                continue
                            
                            # Validate all nodes
                            nodes = [self.kg.get_node(path[i]) for i in range(0, len(path), 2)]
                            if not all(nodes):
                                continue
                            if not all(n.get('name') for n in nodes):
                                continue
                            
                            self.reasoning_paths_seen[path_sig] = 1
                            
                            candidates.append({
                                'path': path,
                                'hop_count': 4,
                                'from_name': nodes[0]['name'],
                                'to_name': nodes[-1]['name'],
                                'from_type': nodes[0]['type'],
                                'to_type': nodes[-1]['type'],
                                'edge_props': [edge1.get('properties', {}), edge2.get('properties', {}), 
                                             edge3.get('properties', {}), edge4.get('properties', {})]
                            })
                            
                            if len(candidates) >= max_candidates:
                                break
                        if len(candidates) >= max_candidates:
                            break
                    if len(candidates) >= max_candidates:
                        break
                if len(candidates) >= max_candidates:
                    break
            if len(candidates) >= max_candidates:
                break
        
        self.logger.info(f"Generated {len(candidates)} 4-hop patterns")
        return candidates
    
    # ========== QUESTION GENERATION ==========
    
    def generate_question_from_candidate(self, candidate: Dict, q_type: str) -> Optional[Dict]:
        """Generate a question from a candidate path with rich context."""
        try:
            path = candidate['path']
            hop_count = candidate['hop_count']
            edge_props = candidate.get('edge_props', [])
            
            # Build node names map
            node_names = {}
            for i in range(0, len(path), 2):
                node_id = path[i]
                node = self.kg.get_node(node_id)
                if node:
                    node_names[node_id] = node.get('name', node_id)
                else:
                    node_names[node_id] = node_id
            
            # Generate question text with rich context
            if hop_count == 1:
                question_text = generate_single_hop_question(
                    candidate['from_name'],
                    candidate['relation'],
                    candidate['to_name'],
                    q_type
                )
            else:
                question_text = self._generate_rich_multi_hop_question(
                    path, node_names, edge_props, q_type, hop_count
                )
            
            # Generate answer
            if q_type == 'TRUE_FALSE':
                # Check if this is a false candidate
                is_false = candidate.get('is_false', False)
                answer = 'False' if is_false else 'True'
            elif q_type == 'MCQ':
                # For multi-hop: build combined answer from ALL intermediate nodes
                if hop_count > 1:
                    answer_parts = []
                    # Extract all answer nodes (skip first node, include all others)
                    for i in range(2, len(path), 2):  # Skip source node (index 0)
                        node_id = path[i]
                        node = self.kg.get_node(node_id)
                        if node and node.get('name'):
                            answer_parts.append(node['name'])
                    
                    combined_answer = ' - '.join(answer_parts) if answer_parts else candidate['to_name']
                    
                    # Generate choices with combined format
                    choices, correct_idx = self._generate_combined_mcq_choices(
                        combined_answer,
                        answer_parts,
                        candidate['to_type'],
                        path
                    )
                else:
                    # Single hop: use standard choice generation
                    choices, correct_idx = generate_mcq_choices(
                        candidate['to_name'],
                        candidate['to_type'],
                        self.kg,
                        num_choices=4
                    )
                
                answer = chr(65 + correct_idx)  # A, B, C, D
            else:
                answer = candidate['to_name']
            
            # Create question dict
            question = {
                'question_id': f"Q{len(self.questions) + 1:06d}",
                'question_text': question_text,
                'answer': answer,
                'q_type': q_type,
                'hop_count': hop_count,
                'reasoning_path': path,
                'variant_type': 'ORIGINAL'
            }
            
            if q_type == 'MCQ':
                question['choices'] = choices
            
            return question
            
        except Exception as e:
            import traceback
            self.logger.error(f"Error generating question: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _create_false_candidate(self, candidate: Dict) -> Optional[Dict]:
        """
        Create FALSE candidate by swapping a node in the path.
        """
        import copy
        false_candidate = copy.deepcopy(candidate)
        path = false_candidate['path']
        
        # Node indices (0, 2, 4, ...)
        node_indices = list(range(0, len(path), 2))
        
        # Prefer swapping intermediate/target nodes (keep source stable)
        if len(node_indices) > 1:
            swap_indices = node_indices[1:]
        else:
            swap_indices = node_indices
        
        swap_idx = random.choice(swap_indices)
        original_node_id = path[swap_idx]
        original_node = self.kg.get_node(original_node_id)
        
        if not original_node:
            return None
        
        # Get replacement of same type
        node_type = original_node.get('type', 'Politician')
        candidates = self.kg.get_nodes_by_type(node_type)
        
        if len(candidates) < 2:
            return None
        
        # Pick random different node
        replacement_id = random.choice([c for c in candidates if c != original_node_id])
        replacement_node = self.kg.get_node(replacement_id)
        
        if not replacement_node:
            return None
        
        # Update path
        path[swap_idx] = replacement_id
        
        # Update names
        if swap_idx == 0:
            false_candidate['from_name'] = replacement_node['name']
        elif swap_idx == len(path) - 1:
            false_candidate['to_name'] = replacement_node['name']
        
        false_candidate['is_false'] = True
        return false_candidate
    
    def _generate_combined_mcq_choices(self, correct_answer: str, answer_parts: List[str],
                                       final_type: str, path: List[str]) -> Tuple[List[str], int]:
        """
        Generate MCQ choices for multi-hop with combined answer format.
        
        Args:
            correct_answer: Combined answer "Part1 - Part2 - ... - PartN"
            answer_parts: List of individual answer parts
            final_type: Type of final entity
            path: Full reasoning path
            
        Returns:
            Tuple of (formatted_choices, correct_index)
        """
        choices = [correct_answer]
        
        # Generate 3 distractors by varying parts
        for _ in range(3):
            fake_parts = []
            
            # For each answer part, occasionally replace with similar entity
            for i, part in enumerate(answer_parts):
                if random.random() < 0.6:  # 60% chance to vary this part
                    # Find the corresponding node in path
                    node_idx = 2 + (i * 2)  # Skip source, then every 2 indices
                    if node_idx < len(path):
                        node_id = path[node_idx]
                        node = self.kg.get_node(node_id)
                        if node:
                            # Get similar nodes of same type
                            similar_ids = self.kg.get_nodes_by_type(node['type'])
                            if len(similar_ids) > 1:
                                candidates = [self.kg.get_node(nid) for nid in similar_ids if nid != node_id]
                                candidates = [n for n in candidates if n and n.get('name')]
                                if candidates:
                                    fake_node = random.choice(candidates)
                                    fake_parts.append(fake_node['name'])
                                    continue
                
                # Keep original if couldn't vary
                fake_parts.append(part)
            
            fake_combined = ' - '.join(fake_parts)
            if fake_combined not in choices and fake_combined != correct_answer:
                choices.append(fake_combined)
        
        # Pad with more distractors if needed
        while len(choices) < 4:
            choices.append(f"[Lựa chọn {len(choices) + 1}]")
        
        # Shuffle
        random.shuffle(choices)
        correct_idx = choices.index(correct_answer)
        
        # Format with A), B), C), D)
        formatted = [f"{chr(65+i)}) {c}" for i, c in enumerate(choices)]
        
        return formatted, correct_idx
    
    def _generate_rich_multi_hop_question(self, path: List[str], node_names: Dict[str, str], 
                                          edge_props: List[Dict], q_type: str, hop_count: int) -> str:
        """
        Generate multi-hop question by directly calling proven templates from templates.py.
        Simple wrapper: use pattern-based generation (templates already clean and tested).
        """
        # Simply delegate to existing template function
        return generate_multi_hop_question(path, node_names, q_type, hop_count)
    
    def generate_template_questions(self, total: int, multi_ratio: float = 0.8) -> List[Dict]:
        """
        Generate template-based questions with hop distribution.
        Ensures exactly 'total' questions are generated with TRUE/FALSE balance.
        
        Args:
            total: Total number of questions to generate
            multi_ratio: Ratio of multi-hop questions (default 0.8 = 80%)
        """
        self.logger.info(f"Generating {total} template questions ({multi_ratio*100}% multi-hop)...")
        
        # Calculate distribution
        multi_total = int(total * multi_ratio)
        single_total = total - multi_total
        
        # Generate candidates for each hop
        candidates_1hop = self.generate_all_1hop_patterns()
        candidates_2hop = self.generate_all_2hop_patterns()
        candidates_3hop = self.generate_all_3hop_patterns()
        candidates_4hop = self.generate_all_4hop_patterns()
        
        # Distribute multi-hop across 2, 3, 4 hops
        multi_2hop = int(multi_total * 0.5)
        multi_3hop = int(multi_total * 0.3)
        multi_4hop = multi_total - multi_2hop - multi_3hop
        
        self.logger.info(f"Target distribution: {single_total} 1-hop, {multi_2hop} 2-hop, {multi_3hop} 3-hop, {multi_4hop} 4-hop")
        
        # Shuffle candidates
        random.shuffle(candidates_1hop)
        random.shuffle(candidates_2hop)
        random.shuffle(candidates_3hop)
        random.shuffle(candidates_4hop)
        
        # Create candidate pools with targets
        candidate_pools = [
            {'candidates': candidates_1hop, 'target': single_total, 'hop': 1, 'idx': 0},
            {'candidates': candidates_2hop, 'target': multi_2hop, 'hop': 2, 'idx': 0},
            {'candidates': candidates_3hop, 'target': multi_3hop, 'hop': 3, 'idx': 0},
            {'candidates': candidates_4hop, 'target': multi_4hop, 'hop': 4, 'idx': 0}
        ]
        
        questions = []
        tf_counts = {'True': 0, 'False': 0}
        used_question_texts = set()
        
        # Generate questions iterating through pools
        with tqdm(total=total, desc="Generating questions") as pbar:
            retry_count = 0
            max_retries = total * 3  # Allow some retries for quality
            
            while len(questions) < total and retry_count < max_retries:
                retry_count += 1
                
                # Find a pool that still needs questions
                available_pools = [p for p in candidate_pools 
                                  if len([q for q in questions if q['hop_count'] == p['hop']]) < p['target']
                                  and p['idx'] < len(p['candidates'])]
                
                if not available_pools:
                    # FALLBACK: If a pool is exhausted, redistribute to other available pools
                    remaining = total - len(questions)
                    if remaining > 0:
                        # Find pools with candidates remaining
                        fallback_pools = [p for p in candidate_pools if p['idx'] < len(p['candidates'])]
                        
                        if not fallback_pools:
                            self.logger.warning(f"Exhausted all candidates at {len(questions)}/{total}")
                            break
                        
                        # Redistribute remaining questions to fallback pools
                        # Priority: prefer longer hops if available
                        fallback_pools.sort(key=lambda p: p['hop'], reverse=True)
                        
                        self.logger.info(f"Redistributing {remaining} remaining questions to available pools")
                        for pool in fallback_pools:
                            available = len(pool['candidates']) - pool['idx']
                            pool['target'] += min(remaining, available)
                            remaining -= min(remaining, available)
                            if remaining == 0:
                                break
                        
                        # Continue with updated targets
                        continue
                    else:
                        break
                
                # Pick random pool
                pool = random.choice(available_pools)
                candidate = pool['candidates'][pool['idx']]
                pool['idx'] += 1
                
                # Alternate MCQ/TRUE_FALSE
                q_type = 'MCQ' if len(questions) % 2 == 0 else 'TRUE_FALSE'
                
                # For TRUE_FALSE: balance True/False (50/50)
                current_candidate = candidate
                if q_type == 'TRUE_FALSE':
                    total_tf = sum(tf_counts.values())
                    # Create false candidate if False is lagging
                    if total_tf == 0 or tf_counts['False'] < (total_tf + 1) * 0.5:
                        false_candidate = self._create_false_candidate(candidate)
                        if false_candidate:
                            current_candidate = false_candidate
                
                # Generate question
                question = self.generate_question_from_candidate(current_candidate, q_type)
                
                if question and question['question_text'] not in used_question_texts:
                    questions.append(question)
                    used_question_texts.add(question['question_text'])
                    self.stats[f"{q_type}_{pool['hop']}hop"] += 1
                    
                    # Track TRUE_FALSE balance
                    if q_type == 'TRUE_FALSE':
                        is_false = current_candidate.get('is_false', False)
                        tf_counts['False' if is_false else 'True'] += 1
                    
                    pbar.update(1)
        
        self.logger.info(f"Generated {len(questions)} template questions")
        self.logger.info(f"TRUE_FALSE balance: True={tf_counts['True']}, False={tf_counts['False']}")
        
        # Report actual distribution
        for hop in [1, 2, 3, 4]:
            count = len([q for q in questions if q['hop_count'] == hop])
            self.logger.info(f"  {hop}-hop: {count} questions")
        
        return questions
    
    # ========== LLM VARIANT GENERATION ==========
    
    def generate_llm_variants(self, seed_questions: List[Dict], variants_per_seed: int = 2, output_dir: str = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Generate LLM variants with infinite key rotation and rate limiting.
        Writes results in real-time to files.
        
        Args:
            seed_questions: List of seed questions
            variants_per_seed: Number of variants per seed (default 2: UNANSWERABLE, PARAPHRASE_HARD)
            output_dir: Directory to save real-time outputs
        
        Returns:
            Tuple of (raw_variants, filtered_variants)
        """
        if not HAS_GENAI or not self.llm_model:
            self.logger.warning("LLM generation skipped (google.generativeai not available)")
            return [], []
        
        self.logger.info(f"Generating LLM variants for {len(seed_questions)} seeds...")
        
        raw_variants = []
        filtered_variants = []
        
        # Get current max IDs from existing files to continue numbering
        next_id = 1
        if output_dir:
            mcq_file = os.path.join(output_dir, 'mcq_questions.csv')
            tf_file = os.path.join(output_dir, 'true_false_questions.csv')
            
            # Find the highest existing ID
            max_id = 0
            if os.path.exists(mcq_file):
                try:
                    df = pd.read_csv(mcq_file)
                    if len(df) > 0:
                        max_id = max(max_id, df['id'].max())
                except:
                    pass
            if os.path.exists(tf_file):
                try:
                    df = pd.read_csv(tf_file)
                    if len(df) > 0:
                        max_id = max(max_id, df['id'].max())
                except:
                    pass
            next_id = max_id + 1
            self.logger.info(f"Starting LLM variant IDs from {next_id}")
        
        for idx, seed in enumerate(tqdm(seed_questions, desc="LLM generation")):
            try:
                # Rate limiting: 1 request per second
                self.key_rotator.wait_for_rate_limit()
                
                # Format prompt
                prompt = self._format_llm_prompt(seed)
                
                # Generate with retry
                response = self._generate_with_retry(prompt)
                
                if response:
                    parsed = self._parse_llm_response(response)
                    
                    if parsed and 'variants' in parsed:
                        num_variants = len(parsed['variants'])
                        if num_variants < 2:
                            self.logger.warning(f"Seed {seed['question_id']}: Only got {num_variants} variant(s) instead of 2")
                        
                        for variant in parsed['variants']:
                            raw_variant = {
                                'seed_id': seed['question_id'],
                                'variant_type': variant.get('variant_type', 'UNKNOWN'),
                                'question_text': variant.get('question', ''),
                                'reasoning_hint': variant.get('reasoning_hint', ''),
                                'q_type': seed['q_type'],
                                'hop_count': seed['hop_count'],
                                'reasoning_path': seed['reasoning_path']
                            }
                            raw_variants.append(raw_variant)
                            
                            # Filter: must have valid question text
                            if len(raw_variant['question_text']) > 10:
                                # Assign answer based on variant type
                                if raw_variant['variant_type'] == 'UNANSWERABLE':
                                    if seed['q_type'] == 'TRUE_FALSE':
                                        raw_variant['answer'] = 'Not Given'
                                    else:  # MCQ
                                        # Randomize position of "Không có dữ kiện"
                                        choices = seed.get('choices', []).copy()
                                        if choices and len(choices) == 4:
                                            answer_pos = random.randint(0, 3)
                                            answer_label = chr(65 + answer_pos)  # A=0, B=1, C=2, D=3
                                            choices[answer_pos] = f"{answer_label}) Không có dữ kiện"
                                            raw_variant['answer'] = answer_label
                                            raw_variant['choices'] = choices
                                        else:
                                            raw_variant['answer'] = 'D'
                                            raw_variant['choices'] = choices
                                
                                elif raw_variant['variant_type'] == 'PARAPHRASE_HARD':
                                    raw_variant['answer'] = seed['answer']
                                    if seed['q_type'] == 'MCQ':
                                        raw_variant['choices'] = seed.get('choices', [])
                                
                                raw_variant['question_id'] = next_id
                                next_id += 1
                                filtered_variants.append(raw_variant)
                                
                                # Write to file immediately (append to existing files)
                                if output_dir:
                                    self._write_llm_variant_realtime(raw_variant, output_dir)
                            else:
                                self.logger.warning(f"Skipped variant from {seed['question_id']}: question too short ({len(raw_variant['question_text'])} chars)")
                    else:
                        self.logger.warning(f"Failed to parse LLM response for {seed['question_id']}")
                else:
                    self.logger.warning(f"Empty response for {seed['question_id']}")
                
            except Exception as e:
                self.logger.error(f"Error generating LLM variant for {seed['question_id']}: {e}")
                # Continue with next seed
        
        self.logger.info(f"Generated {len(raw_variants)} raw variants, {len(filtered_variants)} filtered")
        return raw_variants, filtered_variants
    
    def _write_llm_variant_realtime(self, variant: Dict, output_dir: str):
        """Write a single LLM variant to existing CSV and JSON files in real-time."""
        try:
            if variant['q_type'] == 'MCQ':
                mcq_file = os.path.join(output_dir, 'mcq_questions.csv')
                mcq_ans_file = os.path.join(output_dir, 'mcq_answers.csv')
                mcq_json_file = os.path.join(output_dir, 'mcq_with_entities.json')
                
                # Parse choices
                choices = variant.get('choices', [])
                choice_dict = {'A': '', 'B': '', 'C': '', 'D': ''}
                for choice in choices:
                    if choice.startswith('A)'):
                        choice_dict['A'] = choice[3:].strip()
                    elif choice.startswith('B)'):
                        choice_dict['B'] = choice[3:].strip()
                    elif choice.startswith('C)'):
                        choice_dict['C'] = choice[3:].strip()
                    elif choice.startswith('D)'):
                        choice_dict['D'] = choice[3:].strip()
                
                # Append question (same structure as template questions)
                q_row = pd.DataFrame([{
                    'id': variant['question_id'],
                    'question': variant['question_text'],
                    'A': choice_dict['A'],
                    'B': choice_dict['B'],
                    'C': choice_dict['C'],
                    'D': choice_dict['D'],
                    'hop_count': variant['hop_count'],
                    'reasoning_path': '|'.join(variant['reasoning_path'])
                }])
                q_row.to_csv(mcq_file, mode='a', header=False, index=False, encoding='utf-8')
                
                # Append answer
                a_row = pd.DataFrame([{
                    'id': variant['question_id'],
                    'answer': variant['answer']
                }])
                a_row.to_csv(mcq_ans_file, mode='a', header=False, index=False, encoding='utf-8')
                
                # Update JSON file
                self._append_to_json_file(mcq_json_file, variant, 'MCQ')
                
            else:  # TRUE_FALSE
                tf_file = os.path.join(output_dir, 'true_false_questions.csv')
                tf_ans_file = os.path.join(output_dir, 'true_false_answers.csv')
                tf_json_file = os.path.join(output_dir, 'true_false_with_entities.json')
                
                # Append question (same structure as template questions)
                q_row = pd.DataFrame([{
                    'id': variant['question_id'],
                    'question': variant['question_text'],
                    'hop_count': variant['hop_count'],
                    'reasoning_path': '|'.join(variant['reasoning_path'])
                }])
                q_row.to_csv(tf_file, mode='a', header=False, index=False, encoding='utf-8')
                
                # Append answer
                ans_text = variant['answer']
                if ans_text == 'Not Given':
                    ans_text = 'Không có dữ kiện'
                elif str(ans_text).lower() == 'true':
                    ans_text = 'Đúng'
                elif str(ans_text).lower() == 'false':
                    ans_text = 'Sai'
                
                a_row = pd.DataFrame([{
                    'id': variant['question_id'],
                    'answer': ans_text
                }])
                a_row.to_csv(tf_ans_file, mode='a', header=False, index=False, encoding='utf-8')
                
                # Update JSON file
                self._append_to_json_file(tf_json_file, variant, 'TRUE_FALSE')
                
        except Exception as e:
            self.logger.error(f"Failed to write LLM variant {variant['question_id']} in real-time: {e}")
    
    def _append_to_json_file(self, json_file: str, variant: Dict, q_type: str):
        """Append a single variant to JSON file with entities."""
        try:
            # Load existing JSON
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = []
            
            # Extract entities and relations from reasoning path
            entities = []
            relations = []
            
            for i, item in enumerate(variant['reasoning_path']):
                if i % 2 == 0:  # Node
                    node = self.kg.get_node(item)
                    if node:
                        entity = {
                            "text": node.get('name', item),
                            "type": node.get('type', 'Unknown')
                        }
                        entities.append(entity)
                else:  # Relation
                    relations.append(item)
            
            # Remove consecutive duplicates
            unique_relations = []
            for i, rel in enumerate(relations):
                if i == 0 or rel != relations[i-1]:
                    unique_relations.append(rel)
            
            # Create entry
            entry = {
                "question": variant['question_text'],
                "answer_json": {
                    "entities": entities,
                    "intent_relation": unique_relations
                }
            }
            
            data.append(entry)
            
            # Save back
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to append to JSON file {json_file}: {e}")
    
    def _format_llm_prompt(self, seed: Dict) -> str:
        """Format LLM prompt for variant generation."""
        
        # Special instructions for TRUE_FALSE questions
        if seed['q_type'] == 'TRUE_FALSE':
            format_note = """
**LƯU Ý QUAN TRỌNG CHO CÂU HỎI ĐÚNG/SAI:**
- Câu hỏi PHẢI kết thúc bằng "Đúng hay sai?"
- Khi đề cập kế nhiệm/tiền nhiệm, PHẢI ghi rõ chức vụ (ví dụ: "kế nhiệm vị trí Chủ tịch", "tiền nhiệm ở chức Bí thư")
- Ví dụ tốt: "Nguyễn Văn A kế nhiệm Trần Văn B ở vị trí Chủ tịch UBND tỉnh. Đúng hay sai?"
- Ví dụ xấu: "Nguyễn Văn A kế nhiệm Trần Văn B." (thiếu "Đúng hay sai?" và thiếu chức vụ)
"""
        else:
            format_note = ""
        
        prompt = f"""Bạn là trợ lý tạo dữ liệu cho benchmark suy luận multi-hop trên knowledge graph.

**NHIỆM VỤ:** Tạo 2 biến thể từ câu hỏi gốc:
1. **UNANSWERABLE**: Câu hỏi không thể trả lời từ KG (thiếu thông tin)
2. **PARAPHRASE_HARD**: Diễn đạt phức tạp hơn nhưng cùng đáp án

**SEED QUESTION:**
{seed['question_text']}

**THÔNG TIN:**
- Loại: {seed['q_type']}
- Số hop: {seed['hop_count']}
- Đáp án: {seed['answer']}
{format_note}
**OUTPUT (JSON only):**
```json
{{
  "variants": [
    {{
      "variant_type": "UNANSWERABLE",
      "question": "<câu hỏi không thể trả lời>",
      "reasoning_hint": "<giải thích>"
    }},
    {{
      "variant_type": "PARAPHRASE_HARD",
      "question": "<câu hỏi diễn đạt phức tạp>",
      "reasoning_hint": "<giải thích>"
    }}
  ]
}}
```
"""
        return prompt
    
    def _generate_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Generate with retry and key rotation."""
        for attempt in range(max_retries):
            try:
                generation_config = genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2000
                )
                
                response = self.llm_model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
                if response.text:
                    content = response.text.strip()
                    # Clean markdown
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    return content.strip()
                
            except Exception as e:
                self.logger.warning(f"Generation failed (attempt {attempt+1}): {e}")
                
                # Try to rotate key
                if self.key_rotator.handle_api_error(e):
                    # Re-initialize model with new key
                    self.llm_model = genai.GenerativeModel(self.config.get('llm_model', 'gemini-2.5-flash-lite'))
                    continue
                
                # Exponential backoff
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        return None
    
    def _parse_llm_response(self, response: str) -> Optional[Dict]:
        """Parse LLM JSON response."""
        try:
            data = json.loads(response)
            if "variants" in data:
                return data
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                if "variants" in data:
                    return data
        except (json.JSONDecodeError, ValueError):
            pass
        
        return None
    
    # ========== OUTPUT ==========
    
    def save_outputs(self, output_dir: str, llm_raw: List[Dict] = None, llm_filtered: List[Dict] = None):
        """Save all outputs to CSV and JSON files with format matching original generate_dataset.py"""
        os.makedirs(output_dir, exist_ok=True)
        
        self.logger.info(f"Saving {len(self.questions)} questions to {output_dir}...")
        
        # Separate by question type
        mcq_questions_data = []
        mcq_answers_data = []
        tf_questions_data = []
        tf_answers_data = []
        
        for q in self.questions:
            # Convert reasoning_path to JSON string format (matching original)
            reasoning_path_str = json.dumps(q['reasoning_path'], ensure_ascii=False)
            
            # Determine variant_type (matching original format)
            variant_type = q.get('variant_type', 'ORIGINAL')
            if variant_type == 'ORIGINAL':
                variant_type = 'Normal'  # Original uses "Normal" instead of "ORIGINAL"
            
            if q['q_type'] == 'MCQ':
                # For MCQ, include choices in question text (matching original format)
                question_text = q['question_text']
                if 'choices' in q and q['choices']:
                    # Choices are already formatted as "A) ...", "B) ...", etc.
                    question_text += '\n' + '\n'.join(q['choices'])
                
                question_data = {
                    'question': question_text,
                    'hop_count': q['hop_count'],
                    'reasoning_path': reasoning_path_str,
                    'variant_type': variant_type
                }
                mcq_questions_data.append(question_data)
                
                # Convert answer (matching original format)
                answer_str = q['answer']  # Already 'A', 'B', 'C', or 'D'
                mcq_answers_data.append({'answer': answer_str})
                
            else:  # TRUE_FALSE
                question_data = {
                    'question': q['question_text'],
                    'hop_count': q['hop_count'],
                    'reasoning_path': reasoning_path_str,
                    'variant_type': variant_type
                }
                tf_questions_data.append(question_data)
                
                # Convert answer to Vietnamese (matching original format)
                answer = q['answer']
                if answer == 'True':
                    answer_str = 'Đúng'
                elif answer == 'False':
                    answer_str = 'Sai'
                elif answer in ['Not Given', 'Không có dữ kiện']:
                    answer_str = 'Không có dữ kiện'
                else:
                    answer_str = 'Đúng'  # Default
                
                tf_answers_data.append({'answer': answer_str})
        
        # Reset IDs from 1 for each file (matching original format)
        for i, (q, a) in enumerate(zip(mcq_questions_data, mcq_answers_data), start=1):
            q['id'] = i
            a['id'] = i
        
        for i, (q, a) in enumerate(zip(tf_questions_data, tf_answers_data), start=1):
            q['id'] = i
            a['id'] = i
        
        # Save MCQ files
        if mcq_questions_data:
            mcq_questions_df = pd.DataFrame(mcq_questions_data)
            mcq_answers_df = pd.DataFrame(mcq_answers_data)
            
            # Reorder columns to match original: id, question, hop_count, reasoning_path, variant_type
            mcq_questions_df = mcq_questions_df[['id', 'question', 'hop_count', 'reasoning_path', 'variant_type']]
            mcq_answers_df = mcq_answers_df[['id', 'answer']]
            
            mcq_questions_df.to_csv(os.path.join(output_dir, 'mcq_questions.csv'), 
                                   index=False, encoding='utf-8')
            mcq_answers_df.to_csv(os.path.join(output_dir, 'mcq_answers.csv'), 
                                 index=False, encoding='utf-8')
            
            self.logger.info(f"Saved {len(mcq_questions_data)} MCQ questions and answers")
        
        # Save TRUE_FALSE files
        if tf_questions_data:
            tf_questions_df = pd.DataFrame(tf_questions_data)
            tf_answers_df = pd.DataFrame(tf_answers_data)
            
            # Reorder columns to match original: id, question, hop_count, reasoning_path, variant_type
            tf_questions_df = tf_questions_df[['id', 'question', 'hop_count', 'reasoning_path', 'variant_type']]
            tf_answers_df = tf_answers_df[['id', 'answer']]
            
            tf_questions_df.to_csv(os.path.join(output_dir, 'true_false_questions.csv'), 
                                  index=False, encoding='utf-8')
            tf_answers_df.to_csv(os.path.join(output_dir, 'true_false_answers.csv'), 
                                index=False, encoding='utf-8')
            
            self.logger.info(f"Saved {len(tf_questions_data)} TRUE_FALSE questions and answers")
        
        # Save LLM variants
        if llm_raw:
            with open(os.path.join(output_dir, 'llm_variants_raw.json'), 'w', encoding='utf-8') as f:
                json.dump(llm_raw, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved {len(llm_raw)} raw LLM variants")
        
        if llm_filtered:
            with open(os.path.join(output_dir, 'llm_variants_filtered.json'), 'w', encoding='utf-8') as f:
                json.dump(llm_filtered, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved {len(llm_filtered)} filtered LLM variants")
        
        # Save JSON files with entities and relations
        self._save_json_with_entities(output_dir, mcq_questions_data, 'MCQ')
        self._save_json_with_entities(output_dir, tf_questions_data, 'TRUE_FALSE')
        
        self.logger.info("✓ All outputs saved")
    
    def _save_json_with_entities(self, output_dir: str, questions_data: List[Dict], q_type: str):
        """
        Save JSON file with extracted entities and relations.
        
        Format:
        {
            "question": "...",
            "answer_json": {
                "entities": [{"text": "...", "type": "..."}],
                "intent_relation": ["SUCCEEDED", "FOUGHT_IN"]
            }
        }
        """
        if not questions_data:
            return
        
        output_data = []
        
        for q_data in questions_data:
            # Parse reasoning path
            reasoning_path = json.loads(q_data['reasoning_path'])
            
            # Extract entities and relations
            entities = []
            relations = []
            
            # Extract from path: [node1, rel1, node2, rel2, node3, ...]
            for i, item in enumerate(reasoning_path):
                if i % 2 == 0:  # Node
                    node = self.kg.get_node(item)
                    if node:
                        entity = {
                            "text": node.get('name', item),
                            "type": node.get('type', 'Unknown')
                        }
                        entities.append(entity)
                else:  # Relation
                    relations.append(item)
            
            # Remove consecutive duplicate relations while preserving order
            # Example: ["SUCCEEDED", "SUCCEEDED", "SERVED_AS"] -> ["SUCCEEDED", "SERVED_AS"]
            unique_relations = []
            for i, rel in enumerate(relations):
                if i == 0 or rel != relations[i-1]:
                    unique_relations.append(rel)
            relations = unique_relations
            
            # For MCQ, extract entities from choices as well
            if q_type == 'MCQ':
                # Parse choices from question text
                question_text = q_data['question']
                lines = question_text.split('\n')
                
                for line in lines[1:]:  # Skip first line (the question)
                    if line.strip() and line.strip()[0] in ['A', 'B', 'C', 'D']:
                        # Extract text after "A) ", "B) ", etc.
                        choice_text = line.strip()[3:].strip()
                        
                        # Split by " - " for multi-hop answers
                        parts = choice_text.split(' - ')
                        
                        for part in parts:
                            # Try to match with KG entities
                            # First check if it's in our entities list already
                            if not any(e['text'] == part for e in entities):
                                # Try to find in KG
                                found = False
                                for node_id, node in self.kg.nodes_by_id.items():
                                    if node.get('name') == part:
                                        entity = {
                                            "text": part,
                                            "type": node.get('type', 'Unknown')
                                        }
                                        entities.append(entity)
                                        found = True
                                        break
                                
                                # If not found in KG, try to infer type
                                if not found:
                                    # Check for year pattern
                                    if part.isdigit() and len(part) == 4:
                                        entity = {
                                            "text": part,
                                            "type": "Year"
                                        }
                                        entities.append(entity)
                                    elif 'từ' in part and 'đến' in part:
                                        entity = {
                                            "text": part,
                                            "type": "TermPeriod"
                                        }
                                        entities.append(entity)            # Remove duplicates while preserving order
            seen = set()
            unique_entities = []
            for e in entities:
                key = (e['text'], e['type'])
                if key not in seen:
                    seen.add(key)
                    unique_entities.append(e)
            
            # Create output entry
            entry = {
                "question": q_data['question'],
                "answer_json": {
                    "entities": unique_entities,
                    "intent_relation": relations
                }
            }
            output_data.append(entry)
        
        # Save to JSON file
        filename = 'mcq_with_entities.json' if q_type == 'MCQ' else 'true_false_with_entities.json'
        output_path = os.path.join(output_dir, filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Saved {len(output_data)} {q_type} questions with entities to {filename}")
    
    def print_stats(self):
        """Print generation statistics."""
        self.logger.info("=" * 60)
        self.logger.info("GENERATION STATISTICS")
        self.logger.info("=" * 60)
        self.logger.info(f"Total questions: {len(self.questions)}")
        
        # By type
        mcq_count = sum(1 for q in self.questions if q['q_type'] == 'MCQ')
        tf_count = sum(1 for q in self.questions if q['q_type'] == 'TRUE_FALSE')
        self.logger.info(f"  MCQ: {mcq_count}")
        self.logger.info(f"  TRUE_FALSE: {tf_count}")
        
        # By hop count
        hop_counts = Counter(q['hop_count'] for q in self.questions)
        for hop in sorted(hop_counts.keys()):
            self.logger.info(f"  {hop}-hop: {hop_counts[hop]}")
        
        # By variant type
        variant_counts = Counter(q.get('variant_type', 'ORIGINAL') for q in self.questions)
        for variant, count in variant_counts.items():
            self.logger.info(f"  {variant}: {count}")
        
        self.logger.info("=" * 60)


def parse_args():
    parser = argparse.ArgumentParser(description="Generate large-scale multi-hop dataset (30,000+ questions)")
    
    parser.add_argument('--kg', type=str, required=True,
                       help='Path to knowledge_graph_enriched.json')
    parser.add_argument('--out_dir', type=str, required=True,
                       help='Output directory for generated dataset')
    parser.add_argument('--total', type=int, default=30000,
                       help='Total number of questions (default: 30000)')
    parser.add_argument('--llm_count', type=int, default=1000,
                       help='Number of LLM-generated variants (default: 1000)')
    parser.add_argument('--multi_ratio', type=float, default=0.8,
                       help='Ratio of multi-hop questions (default: 0.8 = 80%%)')
    parser.add_argument('--llm_model', type=str, default='gemini-2.5-flash-lite',
                       help='Gemini model name')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Setup
    os.makedirs(args.out_dir, exist_ok=True)
    setup_logging(args.out_dir, args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("LARGE-SCALE DATASET GENERATION")
    logger.info("=" * 60)
    logger.info(f"Total questions: {args.total}")
    logger.info(f"  Template-based: {args.total - args.llm_count}")
    logger.info(f"  LLM variants: {args.llm_count}")
    logger.info(f"Multi-hop ratio: {args.multi_ratio * 100}%")
    logger.info("=" * 60)
    
    # Load KG
    logger.info(f"Loading knowledge graph from {args.kg}...")
    kg = KnowledgeGraph(args.kg)
    
    # Create generator
    config = {
        'seed': args.seed,
        'llm_model': args.llm_model
    }
    
    generator = LargeScaleDatasetGenerator(kg, config)
    
    # Generate template questions
    template_count = args.total - args.llm_count
    template_questions = generator.generate_template_questions(template_count, args.multi_ratio)
    generator.questions.extend(template_questions)
    
    # Generate LLM variants
    if args.llm_count > 0:
        # Select seed questions (half MCQ, half TRUE_FALSE)
        mcq_seeds = [q for q in template_questions if q['q_type'] == 'MCQ'][:args.llm_count // 4]
        tf_seeds = [q for q in template_questions if q['q_type'] == 'TRUE_FALSE'][:args.llm_count // 4]
        
        all_seeds = mcq_seeds + tf_seeds
        logger.info(f"Selected {len(all_seeds)} seed questions for LLM variant generation")
        
        llm_raw, llm_filtered = generator.generate_llm_variants(all_seeds, variants_per_seed=2, output_dir=args.out_dir)
        
        # Add filtered LLM variants to questions
        generator.questions.extend(llm_filtered[:args.llm_count])
        
        logger.info(f"Added {len(llm_filtered[:args.llm_count])} LLM variants")
    else:
        llm_raw, llm_filtered = [], []
    
    # Print stats
    generator.print_stats()
    
    # Save outputs
    generator.save_outputs(args.out_dir, llm_raw, llm_filtered)
    
    logger.info("✓ Large-scale dataset generation complete!")


if __name__ == '__main__':
    main()
