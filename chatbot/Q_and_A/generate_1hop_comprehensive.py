"""
Generate comprehensive 1-hop questions using ALL graph edges.

Features:
- 28 question patterns (14 forward + 14 backward)
- 11 edge types + 3 special virtual relations (birth_year, death_year, term_duration)
- Both TRUE_FALSE and MCQ formats
- Position name MUST be included for succession-related questions

Edge types:
1. BORN_AT: Politician -> Province (quê)
2. SERVED_AS: Politician -> Position (chức vụ)  
3. AWARDED: Politician -> Award (giải thưởng)
4. ALUMNUS_OF: Politician -> School (trường)
5. HAS_ACADEMIC_TITLE: Politician -> AcademicTitle (học vị)
6. FOUGHT_IN: Politician -> Battle (trận đánh)
7. MEMBER_OF: Politician -> Party (đảng)
8. SUCCEEDED: Politician -> Politician (kế nhiệm - requires position)
9. PRECEDED: Politician -> Politician (tiền nhiệm - requires position)
10. CONTRIBUTED_TO: Politician -> Event (đóng góp)
11. PARTICIPATED_IN: Politician -> Event (tham gia)

Virtual relations:
12. BORN_YEAR: Politician -> Year (sinh năm)
13. DIED_YEAR: Politician -> Year (mất năm)
14. TERM_DURATION: Politician -> Duration (nhiệm kỳ - requires position)
"""

import json
import os
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
import pandas as pd
from tqdm import tqdm

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from chatbot.Q_and_A.kg_utils import KnowledgeGraph


# ========== QUESTION PATTERNS ==========

# Diverse question endings for TRUE_FALSE
# Positive endings (normal answer: Đúng/Sai)
TF_ENDINGS_POSITIVE = [
    'Đúng hay sai?',
    'Đúng không?',
    'Đúng chưa?',
    'Phải không?',
    'Có đúng không?',
    'Có phải không?',
    'Có chính xác không?',
    'Có đúng vậy không?',
    'Có phải vậy không?',
    'Có chính xác vậy không?',
    'Đúng vậy không?',
    'Sai hay đúng?'
]

# Negative endings (inverted answer: Đúng->Sai, Sai->Đúng)
TF_ENDINGS_NEGATIVE = [
    'Không đúng sao?',
    'Không phải sao?',
    'Không đúng à?',
    'Không phải à?',
    'Chẳng phải sao?',
    'Chẳng đúng sao?'
    'Chẳng phải à?',
    'Chẳng đúng à?',
    'Chẳng phải vậy sao?',
    'Chẳng đúng vậy sao?',
    'Không chính xác à?',
    'Không chính xác sao?',
    'Chẳng chính xác à?',
    'Chẳng chính xác sao?'
]

def get_random_tf_ending():
    """
    Get a random TRUE_FALSE question ending for diversity.
    Returns (ending, is_negative) where is_negative=True means answer should be inverted.
    """
    # 70% positive, 30% negative for variety
    if random.random() < 0.7:
        return random.choice(TF_ENDINGS_POSITIVE), False
    else:
        return random.choice(TF_ENDINGS_NEGATIVE), True


# Pattern templates for each edge type
EDGE_PATTERNS = {
    # Physical edges
    'BORN_AT': {
        'forward_tf': '{subject} sinh ra ở {object}',
        'backward_tf': '{object} là quê của {subject}',
        'forward_mcq': '{subject} sinh ra ở đâu?',
        'backward_mcq': '{object} là quê của ai?',
        'relation_name': 'quê'
    },
    'DIED_AT': {
        'forward_tf': '{subject} mất tại {object}',
        'backward_tf': '{object} là nơi mất của {subject}',
        'forward_mcq': '{subject} mất tại đâu?',
        'backward_mcq': 'Ai mất tại {object}?',
        'relation_name': 'nơi mất'
    },
    'SERVED_AS': {
        'forward_tf': '{subject} từng giữ chức vụ {object}',
        'backward_tf': '{object} là chức vụ mà {subject} từng giữ',
        'forward_mcq': '{subject} từng giữ chức vụ gì?',
        'backward_mcq': 'Ai từng giữ chức vụ {object}?',
        'relation_name': 'chức vụ'
    },
    'AWARDED': {
        'forward_tf': '{subject} được trao tặng {object}',
        'backward_tf': '{object} được trao tặng cho {subject}',
        'forward_mcq': '{subject} được trao tặng giải thưởng gì?',
        'backward_mcq': 'Ai được trao tặng {object}?',
        'relation_name': 'giải thưởng'
    },
    'ALUMNUS_OF': {
        'forward_tf': '{subject} tốt nghiệp tại {object}',
        'backward_tf': '{object} là trường mà {subject} từng học',
        'forward_mcq': '{subject} tốt nghiệp tại trường nào?',
        'backward_mcq': 'Ai tốt nghiệp tại {object}?',
        'relation_name': 'trường học'
    },
    'HAS_ACADEMIC_TITLE': {
        'forward_tf': '{subject} có học vị {object}',
        'backward_tf': '{object} là học vị của {subject}',
        'forward_mcq': '{subject} có học vị gì?',
        'backward_mcq': 'Ai có học vị {object}?',
        'relation_name': 'học vị'
    },
    'FOUGHT_IN': {
        'forward_tf': '{subject} tham gia trận {object}',
        'backward_tf': 'Trận {object} có sự tham gia của {subject}',
        'forward_mcq': '{subject} tham gia trận nào?',
        'backward_mcq': 'Ai tham gia trận {object}?',
        'relation_name': 'trận đánh'
    },
    'SERVED_IN': {
        'forward_tf': '{subject} phục vụ trong {object}',
        'backward_tf': '{object} có sự phục vụ của {subject}',
        'forward_mcq': '{subject} phục vụ trong đơn vị quân sự nào?',
        'backward_mcq': 'Ai phục vụ trong {object}?',
        'relation_name': 'quân ngũ'
    },
    'HAS_RANK': {
        'forward_tf': '{subject} có cấp bậc quân sự {object}',
        'backward_tf': '{object} là cấp bậc quân sự của {subject}',
        'forward_mcq': '{subject} có cấp bậc quân sự gì?',
        'backward_mcq': 'Ai có cấp bậc quân sự {object}?',
        'relation_name': 'cấp bậc'
    },
    'SUCCEEDED': {
        'forward_tf': '{subject} kế nhiệm {object} trong chức vụ {position}',
        'backward_tf': '{object} là tiền nhiệm của {subject} trong chức vụ {position}',
        'forward_mcq': '{subject} kế nhiệm ai trong chức vụ {position}?',
        'backward_mcq': 'Ai kế nhiệm {object} trong chức vụ {position}?',
        'relation_name': 'kế nhiệm',
        'requires_position': True
    },
    'PRECEDED': {
        'forward_tf': '{subject} là tiền nhiệm của {object} trong chức vụ {position}',
        'backward_tf': '{object} kế nhiệm {subject} trong chức vụ {position}',
        'forward_mcq': '{subject} là tiền nhiệm của ai trong chức vụ {position}?',
        'backward_mcq': 'Ai là tiền nhiệm của {object} trong chức vụ {position}?',
        'relation_name': 'tiền nhiệm',
        'requires_position': True
    },
    
    # Virtual relations (keep questions but skip Year/Duration in entity extraction)
    'BORN_YEAR': {
        'forward_tf': '{subject} sinh năm {object}',
        'backward_tf': 'Năm {object} là năm sinh của {subject}',
        'forward_mcq': '{subject} sinh năm nào?',
        'backward_mcq': 'Ai sinh năm {object}?',
        'relation_name': 'năm sinh'
    },
    'DIED_YEAR': {
        'forward_tf': '{subject} mất năm {object}',
        'backward_tf': 'Năm {object} là năm mất của {subject}',
        'forward_mcq': '{subject} mất năm nào?',
        'backward_mcq': 'Ai mất năm {object}?',
        'relation_name': 'năm mất'
    },
    'TERM_DURATION': {
        'forward_tf': '{subject} giữ chức vụ {position} {object}',
        'backward_tf': 'Giai đoạn {object} là thời gian {subject} giữ chức vụ {position}',
        'forward_mcq': '{subject} giữ chức vụ {position} trong giai đoạn nào?',
        'backward_mcq': 'Ai giữ chức vụ {position} trong giai đoạn {object}?',
        'relation_name': 'nhiệm kỳ',
        'requires_position': True
    }
}


class Comprehensive1HopGenerator:
    """Generate comprehensive 1-hop questions from ALL graph edges."""
    
    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg
        self.questions = []
        self.stats = defaultdict(int)
        
        # Direct type mapping from KG type to ALLOWED_ENTITY_TYPES
        self.kg_type_to_entity = {
            'Politician': 'Politician',
            'Position': 'Position',
            'Province': 'Location',  # Province -> Location
            'Award': 'Award',
            'School': 'AlmaMater',  # School -> AlmaMater
            'AcademicTitle': 'AcademicTitle',
            'Battle': 'Campaigns',  # Battle -> Campaigns
        }
        
        # Edge type to entity type (for objects)
        self.edge_to_entity_type = {
            'BORN_AT': 'Location',
            'DIED_AT': 'Location',
            'SERVED_AS': 'Position',
            'AWARDED': 'Award',
            'ALUMNUS_OF': 'AlmaMater',
            'HAS_ACADEMIC_TITLE': 'AcademicTitle',
            'FOUGHT_IN': 'Campaigns',
            'SERVED_IN': 'MilitaryCareer',
            'HAS_RANK': 'MilitaryRank',
            'SUCCEEDED': 'Politician',
            'PRECEDED': 'Politician',
            'TERM_DURATION': 'TermPeriod',
            'BORN_YEAR': 'Year',
            'DIED_YEAR': 'Year',
        }
        

    def extract_virtual_relations(self) -> List[Dict]:
        """Extract virtual relations (birth_year, death_year, term_duration)."""
        virtual_edges = []
        
        for node_id, node in self.kg.nodes_by_id.items():
            if node['type'] != 'Politician':
                continue
            
            name = node.get('name', '')
            if not name:
                continue
            
            props = node.get('properties', {})
            
            # BORN_YEAR
            birth_date = props.get('birth_date')
            if birth_date:
                year_match = re.search(r'\d{4}', str(birth_date))
                if year_match:
                    year = year_match.group(0)
                    virtual_edges.append({
                        'from_id': node_id,
                        'from_name': name,
                        'to_id': f'YEAR_{year}',
                        'to_name': year,
                        'edge_type': 'BORN_YEAR',
                        'properties': {}
                    })
            
            # DIED_YEAR
            death_date = props.get('death_date')
            if death_date:
                year_match = re.search(r'\d{4}', str(death_date))
                if year_match:
                    year = year_match.group(0)
                    virtual_edges.append({
                        'from_id': node_id,
                        'from_name': name,
                        'to_id': f'YEAR_{year}',
                        'to_name': year,
                        'edge_type': 'DIED_YEAR',
                        'properties': {}
                    })
            
            # TERM_DURATION (from SERVED_AS edges with term_start/term_end)
            for edge in self.kg.get_outgoing_edges(node_id):
                if edge['type'] == 'SERVED_AS':
                    # MultiDiGraph.get_edge_data returns dict of {key: edge_data}
                    edge_data_dict = self.kg.graph.get_edge_data(node_id, edge['to'])
                    if edge_data_dict:
                        # Iterate through all parallel edges
                        for key, edge_data in edge_data_dict.items():
                            if edge_data.get('type') != 'SERVED_AS':
                                continue
                            
                            props = edge_data.get('properties', {})
                            term_start = props.get('term_start')
                            term_end = props.get('term_end')
                            
                            if term_start or term_end:
                                # Format duration string
                                if term_start and term_end:
                                    duration = f'từ {term_start} đến {term_end}'
                                elif term_start:
                                    duration = f'từ {term_start} đến nay'
                                else:
                                    duration = f'đến {term_end}'
                                
                                # Get position name
                                pos_node = self.kg.get_node(edge['to'])
                                position_name = pos_node.get('name', '') if pos_node else ''
                                
                                if position_name:
                                    virtual_edges.append({
                                        'from_id': node_id,
                                        'from_name': name,
                                        'to_id': f'DURATION_{node_id}_{edge["to"]}_{key}',
                                        'to_name': duration,
                                        'edge_type': 'TERM_DURATION',
                                        'properties': {'position_name': position_name}
                                    })
        
        return virtual_edges

    def collect_all_edges(self) -> List[Dict]:
        """Collect all edges from graph (physical + virtual)."""
        all_edges = []
        
        # Physical edges
        for u, v, data in self.kg.graph.edges(data=True):
            edge_type = data.get('type')
            if not edge_type or edge_type not in EDGE_PATTERNS:
                continue
            
            from_node = self.kg.get_node(u)
            to_node = self.kg.get_node(v)
            
            if not from_node or not to_node:
                continue
            if not from_node.get('name') or not to_node.get('name'):
                continue
            
            edge_info = {
                'from_id': u,
                'from_name': from_node['name'],
                'to_id': v,
                'to_name': to_node['name'],
                'edge_type': edge_type,
                'properties': data.get('properties', {})
            }
            
            # For succession edges, find position
            if edge_type in ['SUCCEEDED', 'PRECEDED']:
                # Find common position
                from_positions = set()
                to_positions = set()
                
                for edge in self.kg.get_outgoing_edges(u):
                    if edge['type'] == 'SERVED_AS':
                        from_positions.add(edge['to'])
                
                for edge in self.kg.get_outgoing_edges(v):
                    if edge['type'] == 'SERVED_AS':
                        to_positions.add(edge['to'])
                
                common_positions = from_positions & to_positions
                
                if common_positions:
                    # Use first common position
                    pos_id = list(common_positions)[0]
                    pos_node = self.kg.get_node(pos_id)
                    if pos_node and pos_node.get('name'):
                        edge_info['properties']['position_id'] = pos_id
                        edge_info['properties']['position_name'] = pos_node['name']
                        all_edges.append(edge_info)
                # Skip if no common position found
            else:
                all_edges.append(edge_info)
        
        # Virtual edges
        virtual_edges = self.extract_virtual_relations()
        all_edges.extend(virtual_edges)
        
        return all_edges
    
    def generate_mcq_choices(self, correct_answer: str, answer_type: str, 
                            edge_type: str, num_choices: int = 4) -> Tuple[List[str], int]:
        """Generate MCQ choices with one correct answer."""
        choices = [correct_answer]
        
        # Get similar entities for distractors
        if answer_type == 'Year':
            # For years, generate nearby years
            try:
                year = int(correct_answer)
                for _ in range(num_choices - 1):
                    offset = random.choice([-5, -4, -3, -2, -1, 1, 2, 3, 4, 5])
                    fake_year = str(year + offset)
                    if fake_year not in choices:
                        choices.append(fake_year)
            except:
                pass
        
        elif answer_type == 'Politician':
            # For backward MCQ: get other politicians (regardless of edge_type)
            similar_nodes = []
            for node_id, node in self.kg.nodes_by_id.items():
                if node.get('type') == 'Politician' and node.get('name') and node.get('name') != correct_answer:
                    similar_nodes.append(node['name'])
            
            # Sample distractors
            if similar_nodes:
                random.shuffle(similar_nodes)
                for name in similar_nodes[:num_choices - 1]:
                    if name not in choices:
                        choices.append(name)
        
        else:
            # For forward MCQ: get from same type based on edge_type
            similar_nodes = []
            for node_id, node in self.kg.nodes_by_id.items():
                if node.get('name') and node.get('name') != correct_answer:
                    # Match by type or relation
                    if edge_type in ['BORN_AT', 'DIED_AT'] and node.get('type') == 'Province':
                        similar_nodes.append(node['name'])
                    elif edge_type == 'SERVED_AS' and node.get('type') == 'Position':
                        similar_nodes.append(node['name'])
                    elif edge_type == 'AWARDED' and node.get('type') == 'Award':
                        similar_nodes.append(node['name'])
                    elif edge_type == 'ALUMNUS_OF' and node.get('type') == 'School':
                        similar_nodes.append(node['name'])
                    elif edge_type == 'HAS_ACADEMIC_TITLE' and node.get('type') == 'AcademicTitle':
                        similar_nodes.append(node['name'])
                    elif edge_type == 'FOUGHT_IN' and node.get('type') == 'Battle':
                        similar_nodes.append(node['name'])
                    elif edge_type == 'SERVED_IN' and node.get('type') == 'MilitaryCareer':
                        similar_nodes.append(node['name'])
                    elif edge_type == 'HAS_RANK' and node.get('type') == 'MilitaryRank':
                        similar_nodes.append(node['name'])
                    elif edge_type in ['SUCCEEDED', 'PRECEDED'] and node.get('type') == 'Politician':
                        similar_nodes.append(node['name'])
            
            # Sample distractors
            if similar_nodes:
                random.shuffle(similar_nodes)
                for name in similar_nodes[:num_choices - 1]:
                    if name not in choices:
                        choices.append(name)
        
        # If still not enough choices, return None to skip this question
        if len(choices) < num_choices:
            return None, -1
        
        # Shuffle
        choices = choices[:num_choices]
        random.shuffle(choices)
        correct_idx = choices.index(correct_answer)
        
        # Format with A), B), C), D)
        formatted = [f"{chr(65+i)}) {c}" for i, c in enumerate(choices)]
        
        return formatted, correct_idx
    
    def generate_false_question(self, edge: Dict, pattern_type: str, direction: str) -> Optional[Dict]:
        """Generate a FALSE question by swapping one entity."""
        edge_type = edge['edge_type']
        pattern = EDGE_PATTERNS[edge_type]
        
        # Decide what to swap
        swap_subject = random.random() < 0.5
        
        if swap_subject:
            # Swap subject (from)
            # Get candidates of same type
            from_node = self.kg.get_node(edge['from_id'])
            if not from_node:
                return None
            
            candidates = [nid for nid, n in self.kg.nodes_by_id.items() 
                         if n.get('type') == from_node['type'] and n.get('name') 
                         and nid != edge['from_id']]
            
            if not candidates:
                return None
            
            fake_from_id = random.choice(candidates)
            fake_from_node = self.kg.get_node(fake_from_id)
            fake_from_name = fake_from_node['name']
            
            # Build false question
            template = pattern[f'{direction}_tf']
            question_text = template.format(
                subject=fake_from_name,
                object=edge['to_name'],
                position=edge['properties'].get('position_name', '')
            )
            # Add random ending and check if inverted
            ending, is_negative = get_random_tf_ending()
            question_text = question_text + '. ' + ending
            
            # Invert answer if negative ending
            answer = 'Đúng' if is_negative else 'Sai'
            
            return {
                'question_text': question_text,
                'answer': answer,
                'q_type': 'TRUE_FALSE',
                'hop_count': 1,
                'edge_type': edge_type,
                'direction': direction,
                'reasoning_path': [fake_from_id, edge_type, edge['to_id']]
            }
        
        else:
            # Swap object (to)
            # For succession edges, must keep position consistent
            if edge_type in ['SUCCEEDED', 'PRECEDED']:
                # Swap the other politician
                candidates = []
                for nid, n in self.kg.nodes_by_id.items():
                    if n.get('type') == 'Politician' and n.get('name') and nid != edge['to_id']:
                        candidates.append((nid, n['name']))
                
                if not candidates:
                    return None
                
                fake_to_id, fake_to_name = random.choice(candidates)
            
            else:
                # Get from same type
                    to_node = self.kg.get_node(edge['to_id'])
                    if not to_node:
                        return None
                    
                    candidates = [nid for nid, n in self.kg.nodes_by_id.items()
                                 if n.get('type') == to_node['type'] and n.get('name')
                                 and nid != edge['to_id']]
                    
                    if not candidates:
                        return None
                    
                    fake_to_id = random.choice(candidates)
                    fake_to_node = self.kg.get_node(fake_to_id)
                    fake_to_name = fake_to_node['name']
            
            # Build false question
            template = pattern[f'{direction}_tf']
            question_text = template.format(
                subject=edge['from_name'],
                object=fake_to_name,
                position=edge['properties'].get('position_name', '')
            )
            # Add random ending and check if inverted
            ending, is_negative = get_random_tf_ending()
            question_text = question_text + '. ' + ending
            
            # Invert answer if negative ending
            answer = 'Đúng' if is_negative else 'Sai'
            
            return {
                'question_text': question_text,
                'answer': answer,
                'q_type': 'TRUE_FALSE',
                'hop_count': 1,
                'edge_type': edge_type,
                'direction': direction,
                'reasoning_path': [edge['from_id'], edge_type, fake_to_id]
            }
    
    def generate_questions_from_edge(self, edge: Dict) -> List[Dict]:
        """Generate 4 questions from one edge: forward TF/MCQ + backward TF/MCQ."""
        questions = []
        edge_type = edge['edge_type']
        pattern = EDGE_PATTERNS[edge_type]
        
        # Prepare substitution dict
        subs = {
            'subject': edge['from_name'],
            'object': edge['to_name'],
            'position': edge['properties'].get('position_name', '')
        }
        
        # Determine answer type for MCQ
        to_node = self.kg.get_node(edge['to_id'])
        answer_type = to_node.get('type', 'Unknown') if to_node else 'Unknown'
        
        # Prepare entities for forward direction (subject=Politician, object=based on edge_type)
        forward_entities = [
            {'text': edge['from_name'], 'type': 'Politician'}
        ]
        
        # Add object entity
        entity_type = self.edge_to_entity_type.get(edge_type)
        if entity_type:
            forward_entities.append({'text': edge['to_name'], 'type': entity_type})
        
        # Add position entity if needed
        position_name = edge['properties'].get('position_name', '')
        if position_name and edge_type in ['SUCCEEDED', 'PRECEDED', 'TERM_DURATION']:
            forward_entities.append({'text': position_name, 'type': 'Position'})
        
        # Prepare entities for backward direction (object first, then subject)
        backward_entities = []
        entity_type = self.edge_to_entity_type.get(edge_type)
        if entity_type:
            backward_entities.append({'text': edge['to_name'], 'type': entity_type})
        
        backward_entities.append({'text': edge['from_name'], 'type': 'Politician'})
        
        if position_name and edge_type in ['SUCCEEDED', 'PRECEDED', 'TERM_DURATION']:
            backward_entities.append({'text': position_name, 'type': 'Position'})
        
        # 1. Forward TRUE_FALSE (TRUE)
        ending, is_negative = get_random_tf_ending()
        q_text = pattern['forward_tf'].format(**subs) + '. ' + ending
        answer = 'Sai' if is_negative else 'Đúng'
        questions.append({
            'question_text': q_text,
            'answer': answer,
            'q_type': 'TRUE_FALSE',
            'hop_count': 1,
            'edge_type': edge_type,
            'direction': 'forward',
            'reasoning_path': [edge['from_id'], edge_type, edge['to_id']],
            'entities': forward_entities.copy()  # Store entities directly
        })
        
        # 2. Forward TRUE_FALSE (FALSE)
        false_q = self.generate_false_question(edge, pattern, 'forward')
        if false_q:
            false_q['entities'] = forward_entities.copy()  # Same entities as forward TRUE
            questions.append(false_q)
        
        # 3. Backward TRUE_FALSE (TRUE)
        ending, is_negative = get_random_tf_ending()
        q_text = pattern['backward_tf'].format(**subs) + '. ' + ending
        answer = 'Sai' if is_negative else 'Đúng'
        questions.append({
            'question_text': q_text,
            'answer': answer,
            'q_type': 'TRUE_FALSE',
            'hop_count': 1,
            'edge_type': edge_type,
            'direction': 'backward',
            'reasoning_path': [edge['to_id'], edge_type + '_INV', edge['from_id']],
            'entities': backward_entities.copy()  # Store entities directly
        })
        
        # 4. Backward TRUE_FALSE (FALSE)
        false_q = self.generate_false_question(edge, pattern, 'backward')
        if false_q:
            false_q['entities'] = backward_entities.copy()  # Same entities as backward TRUE
            questions.append(false_q)
        
        # 5. Forward MCQ
        q_text = pattern['forward_mcq'].format(**subs)
        choices, correct_idx = self.generate_mcq_choices(
            edge['to_name'], answer_type, edge_type
        )
        # Skip if not enough choices
        if choices is not None:
            # Build entities: subject + position (if needed) + all choices
            mcq_fwd_entities = [{'text': edge['from_name'], 'type': 'Politician'}]
            if position_name and edge_type in ['SUCCEEDED', 'PRECEDED', 'TERM_DURATION']:
                mcq_fwd_entities.append({'text': position_name, 'type': 'Position'})
            
            # Add all choices with appropriate type (remove "A) ", "B) " prefix)
            for choice in choices:
                choice_text = choice.split(') ', 1)[-1] if ') ' in choice else choice
                entity_type = self.edge_to_entity_type.get(edge_type)
                if entity_type:
                    mcq_fwd_entities.append({'text': choice_text, 'type': entity_type})
            
            questions.append({
                'question_text': q_text,
                'answer': chr(65 + correct_idx),
                'choices': choices,
                'q_type': 'MCQ',
                'hop_count': 1,
                'edge_type': edge_type,
                'direction': 'forward',
                'reasoning_path': [edge['from_id'], edge_type, edge['to_id']],
                'entities': mcq_fwd_entities
            })
        
        # 6. Backward MCQ
        q_text = pattern['backward_mcq'].format(**subs)
        choices, correct_idx = self.generate_mcq_choices(
            edge['from_name'], 'Politician', edge_type
        )
        # Skip if not enough choices
        if choices is not None:
            # Build entities: object first + position (if needed) + all politician choices
            mcq_back_entities = []
            entity_type = self.edge_to_entity_type.get(edge_type)
            if entity_type:
                mcq_back_entities.append({'text': edge['to_name'], 'type': entity_type})
            
            if position_name and edge_type in ['SUCCEEDED', 'PRECEDED', 'TERM_DURATION']:
                mcq_back_entities.append({'text': position_name, 'type': 'Position'})
            
            # Add all politician choices (remove "A) ", "B) " prefix)
            for choice in choices:
                choice_text = choice.split(') ', 1)[-1] if ') ' in choice else choice
                mcq_back_entities.append({'text': choice_text, 'type': 'Politician'})
            
            questions.append({
                'question_text': q_text,
                'answer': chr(65 + correct_idx),
                'choices': choices,
                'q_type': 'MCQ',
                'hop_count': 1,
                'edge_type': edge_type,
                'direction': 'backward',
                'reasoning_path': [edge['to_id'], edge_type + '_INV', edge['from_id']],
                'entities': mcq_back_entities
            })
        
        return questions
    
    def generate_all_questions(self) -> List[Dict]:
        """Generate questions from ALL edges in graph."""
        print("Collecting all edges from graph...")
        all_edges = self.collect_all_edges()
        print(f"Found {len(all_edges)} edges")
        
        # Count by edge type
        edge_type_counts = defaultdict(int)
        for edge in all_edges:
            edge_type_counts[edge['edge_type']] += 1
        
        print("\nEdge distribution:")
        for edge_type in sorted(edge_type_counts.keys()):
            count = edge_type_counts[edge_type]
            print(f"  {edge_type}: {count} edges")
        
        print(f"\nGenerating questions from {len(all_edges)} edges...")
        
        for edge in tqdm(all_edges, desc="Generating questions"):
            questions = self.generate_questions_from_edge(edge)
            self.questions.extend(questions)
            
            # Update stats
            for q in questions:
                self.stats[f"{q['q_type']}_{q['edge_type']}_{q['direction']}"] += 1
        
        print(f"\nGenerated {len(self.questions)} questions total")
        return self.questions
    
    def print_stats(self):
        """Print generation statistics."""
        print("\n" + "="*60)
        print("GENERATION STATISTICS")
        print("="*60)
        
        total = len(self.questions)
        mcq_count = sum(1 for q in self.questions if q['q_type'] == 'MCQ')
        tf_count = sum(1 for q in self.questions if q['q_type'] == 'TRUE_FALSE')
        
        print(f"Total questions: {total}")
        print(f"  MCQ: {mcq_count} ({mcq_count/total*100:.1f}%)")
        print(f"  TRUE_FALSE: {tf_count} ({tf_count/total*100:.1f}%)")
        
        # Count TRUE/FALSE balance
        true_count = sum(1 for q in self.questions if q['q_type'] == 'TRUE_FALSE' and q['answer'] == 'Đúng')
        false_count = sum(1 for q in self.questions if q['q_type'] == 'TRUE_FALSE' and q['answer'] == 'Sai')
        print(f"\nTRUE_FALSE balance:")
        print(f"  Đúng: {true_count}")
        print(f"  Sai: {false_count}")
        
        # Count by edge type
        print("\nBy edge type:")
        edge_counts = defaultdict(int)
        for q in self.questions:
            edge_counts[q['edge_type']] += 1
        
        for edge_type in sorted(edge_counts.keys()):
            count = edge_counts[edge_type]
            print(f"  {edge_type}: {count} questions")
    
    def extract_entities_from_question(self, question_data: Dict) -> List[Dict]:
        """Extract entities from question based on reasoning path and type."""
        entities = []
        seen_texts: Set[str] = set()
        
        edge_type = question_data['edge_type']
        reasoning_path = question_data['reasoning_path']
        q_type = question_data['q_type']
        direction = question_data.get('direction', 'forward')
        
        # Determine if this is a backward question
        is_backward = '_INV' in str(reasoning_path[1]) if len(reasoning_path) > 1 else False
        
        # Get subject (always first ID in path)
        from_id = reasoning_path[0]
        from_node = self.kg.get_node(from_id)
        
        # For backward questions, from_id is actually the object, need to assign type correctly
        if from_node:
            from_name = from_node.get('name', '')
            
            # Determine type based on direction and edge_type
            if is_backward:
                # Backward: from_id is object, assign type based on edge_type
                if edge_type == 'BORN_AT':
                    from_type = 'Location'
                elif edge_type == 'SERVED_AS':
                    from_type = 'Position'
                elif edge_type == 'AWARDED':
                    from_type = 'Award'
                elif edge_type == 'ALUMNUS_OF':
                    from_type = 'AlmaMater'
                elif edge_type == 'HAS_ACADEMIC_TITLE':
                    from_type = 'AcademicTitle'
                elif edge_type == 'FOUGHT_IN':
                    from_type = 'Campaigns'
                elif edge_type in ['SUCCEEDED', 'PRECEDED']:
                    from_type = 'Politician'
                else:
                    from_type = self.type_mapping.get(from_node.get('type', ''), 'Unknown')
            else:
                # Forward: from_id is subject (always Politician)
                from_type = 'Politician'
            
            if from_name and from_name not in seen_texts:
                entities.append({'text': from_name, 'type': from_type})
                seen_texts.add(from_name)
        
        # Add position if required (before choices)
        if edge_type in ['SUCCEEDED', 'PRECEDED', 'TERM_DURATION']:
            # Get edge properties using kg.get_edge_between
            to_id = reasoning_path[-1]
            edges = self.kg.get_edge_between(from_id, to_id)
            for edge in edges:
                if edge['type'] == edge_type:
                    position_name = edge.get('properties', {}).get('position_name', '')
                    if position_name and position_name not in seen_texts:
                        entities.append({'text': position_name, 'type': 'Position'})
                        seen_texts.add(position_name)
                    break
        
        # For MCQ: extract ALL entities from choices
        if q_type == 'MCQ' and 'choices' in question_data:
            for choice in question_data['choices']:
                # Remove "A) ", "B) ", etc. prefix
                choice_text = choice.split(') ', 1)[-1] if ') ' in choice else choice
                
                # Determine entity type based on edge_type
                if edge_type == 'BORN_AT':
                    entity_type = 'Location'  # Map Province to Location
                elif edge_type == 'SERVED_AS':
                    entity_type = 'Position'
                elif edge_type == 'AWARDED':
                    entity_type = 'Award'
                elif edge_type == 'ALUMNUS_OF':
                    entity_type = 'AlmaMater'  # Map School to AlmaMater
                elif edge_type == 'HAS_ACADEMIC_TITLE':
                    entity_type = 'AcademicTitle'
                elif edge_type == 'FOUGHT_IN':
                    entity_type = 'Campaigns'
                elif edge_type in ['SUCCEEDED', 'PRECEDED']:
                    entity_type = 'Politician'
                else:
                    entity_type = 'Unknown'
                
                if choice_text and choice_text not in seen_texts:
                    entities.append({'text': choice_text, 'type': entity_type})
                    seen_texts.add(choice_text)
        
        # For TRUE_FALSE: only get the correct object (skip Year/Duration)
        else:
            to_id = reasoning_path[-1]
            
            # Skip Year and Duration entities for BORN_YEAR, DIED_YEAR, TERM_DURATION
            if edge_type in ['BORN_YEAR', 'DIED_YEAR', 'TERM_DURATION']:
                pass  # Don't add Year or Duration to entities
            else:
                to_node = self.kg.get_node(to_id)
                if to_node:
                    to_name = to_node.get('name', '')
                    
                    # Determine entity type based on direction and edge_type
                    if is_backward:
                        # Backward: to_id is subject (always Politician)
                        entity_type = 'Politician'
                    else:
                        # Forward: to_id is object, assign type based on edge_type
                        if edge_type == 'BORN_AT':
                            entity_type = 'Location'
                        elif edge_type == 'SERVED_AS':
                            entity_type = 'Position'
                        elif edge_type == 'AWARDED':
                            entity_type = 'Award'
                        elif edge_type == 'ALUMNUS_OF':
                            entity_type = 'AlmaMater'
                        elif edge_type == 'HAS_ACADEMIC_TITLE':
                            entity_type = 'AcademicTitle'
                        elif edge_type == 'FOUGHT_IN':
                            entity_type = 'Campaigns'
                        elif edge_type in ['SUCCEEDED', 'PRECEDED']:
                            entity_type = 'Politician'
                        else:
                            entity_type = 'Unknown'
                    
                    if to_name and to_name not in seen_texts:
                        entities.append({'text': to_name, 'type': entity_type})
                        seen_texts.add(to_name)
        
        return entities
    
    def get_intent_relations(self, question_data: Dict) -> List[str]:
        """Get intent relations from reasoning path."""
        reasoning_path = question_data['reasoning_path']
        relations = []
        
        # Extract edge types from reasoning path
        for i, item in enumerate(reasoning_path):
            if isinstance(item, str) and i % 2 == 1:  # Edge types are at odd indices
                # Remove _INV suffix for backward relations
                edge_type = item.replace('_INV', '')
                relations.append(edge_type)
        
        return relations
    
    def convert_to_json_format(self, question_data: Dict) -> Dict:
        """Convert question to JSON format with entities and intent_relation."""
        # Use pre-stored entities if available, otherwise extract
        entities = question_data.get('entities', [])
        intent_relations = self.get_intent_relations(question_data)
        
        return {
            'question': question_data['question_text'],
            'answer_json': {
                'entities': entities,
                'intent_relation': intent_relations
            }
        }
    
    def print_direction_stats(self):
        """Print direction statistics."""
        # Count by direction
        forward_count = sum(1 for q in self.questions if q['direction'] == 'forward')
        backward_count = sum(1 for q in self.questions if q['direction'] == 'backward')
        print(f"\nBy direction:")
        print(f"  Forward: {forward_count}")
        print(f"  Backward: {backward_count}")
    
    def save_outputs(self, output_dir: str):
        """Save questions to CSV files."""
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\nSaving outputs to {output_dir}...")
        
        # Separate by type
        mcq_questions = []
        mcq_answers = []
        tf_questions = []
        tf_answers = []
        
        mcq_id = 1
        tf_id = 1
        
        for q in self.questions:
            # Format reasoning path
            path_str = '|'.join(q['reasoning_path'])
            
            if q['q_type'] == 'MCQ':
                # Format question with choices
                question_text = q['question_text']
                if 'choices' in q:
                    question_text += '\n' + '\n'.join(q['choices'])
                
                mcq_questions.append({
                    'id': mcq_id,
                    'question': question_text,
                    'hop_count': q['hop_count'],
                    'reasoning_path': path_str,
                    'variant_type': 'Normal'
                })
                
                mcq_answers.append({
                    'id': mcq_id,
                    'answer': q['answer']
                })
                
                mcq_id += 1
            
            else:  # TRUE_FALSE
                tf_questions.append({
                    'id': tf_id,
                    'question': q['question_text'],
                    'hop_count': q['hop_count'],
                    'reasoning_path': path_str,
                    'variant_type': 'Normal'
                })
                
                tf_answers.append({
                    'id': tf_id,
                    'answer': q['answer']
                })
                
                tf_id += 1
        
        # Save MCQ
        if mcq_questions:
            mcq_q_df = pd.DataFrame(mcq_questions)
            mcq_a_df = pd.DataFrame(mcq_answers)
            
            mcq_q_df.to_csv(os.path.join(output_dir, 'mcq_questions.csv'), 
                           index=False, encoding='utf-8')
            mcq_a_df.to_csv(os.path.join(output_dir, 'mcq_answers.csv'),
                           index=False, encoding='utf-8')
            
            print(f"Saved {len(mcq_questions)} MCQ questions")
        
        # Save TRUE_FALSE
        if tf_questions:
            tf_q_df = pd.DataFrame(tf_questions)
            tf_a_df = pd.DataFrame(tf_answers)
            
            tf_q_df.to_csv(os.path.join(output_dir, 'true_false_questions.csv'),
                          index=False, encoding='utf-8')
            tf_a_df.to_csv(os.path.join(output_dir, 'true_false_answers.csv'),
                          index=False, encoding='utf-8')
            
            print(f"Saved {len(tf_questions)} TRUE_FALSE questions")
        
        # Save JSON format with entities and relations (separate MCQ and TF)
        print("\nGenerating JSON format with entities and relations...")
        mcq_json = []
        tf_json = []
        
        for q in tqdm(self.questions, desc="Converting to JSON"):
            json_obj = self.convert_to_json_format(q)
            
            if q['q_type'] == 'MCQ':
                # For MCQ: merge choices into question text
                if 'choices' in q:
                    json_obj['question'] = json_obj['question'] + '\n' + '\n'.join(q['choices'])
                mcq_json.append(json_obj)
            else:
                # For TF: just question and answer_json
                tf_json.append(json_obj)
        
        # Save MCQ JSON
        if mcq_json:
            mcq_json_path = os.path.join(output_dir, 'mcq_entity_extraction.json')
            with open(mcq_json_path, 'w', encoding='utf-8') as f:
                json.dump(mcq_json, f, ensure_ascii=False, indent=2)
            print(f"Saved {len(mcq_json)} MCQ questions to mcq_entity_extraction.json")
        
        # Save TRUE_FALSE JSON
        if tf_json:
            tf_json_path = os.path.join(output_dir, 'tf_entity_extraction.json')
            with open(tf_json_path, 'w', encoding='utf-8') as f:
                json.dump(tf_json, f, ensure_ascii=False, indent=2)
            print(f"Saved {len(tf_json)} TRUE_FALSE questions to tf_entity_extraction.json")
        
        print("✓ All outputs saved")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate comprehensive 1-hop questions from ALL graph edges (28 patterns)')
    parser.add_argument('--kg', required=True,
                       help='Path to knowledge graph JSON file')
    parser.add_argument('--out_dir', required=True,
                       help='Output directory for generated questions')
    
    args = parser.parse_args()
    
    print("="*60)
    print("COMPREHENSIVE 1-HOP QUESTION GENERATION")
    print("="*60)
    print("Features:")
    print("- 28 question patterns (14 edge types × 2 directions)")
    print("- Both TRUE_FALSE and MCQ formats")
    print("- Position names included for succession questions")
    print("="*60)
    
    # Load KG
    print(f"\nLoading knowledge graph from {args.kg}...")
    kg = KnowledgeGraph(args.kg)
    
    # Generate
    generator = Comprehensive1HopGenerator(kg)
    questions = generator.generate_all_questions()
    
    # Print stats
    generator.print_stats()
    
    # Save
    generator.save_outputs(args.out_dir)
    
    print("\n✓ Generation complete!")


if __name__ == '__main__':
    main()
