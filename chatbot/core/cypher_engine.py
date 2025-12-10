# chatbot/core/cypher_engine.py

from typing import List, Dict, Any, Optional, Tuple
from utils._logger import get_logger

logger = get_logger("chatbot.core.cypher_engine", log_file="logs/chatbot/cypher_engine.log")

def _find_entity(
    entities: List[Dict[str, Any]], 
    target_type: str
) -> Optional[str]:
    for entity in entities:
        if entity.get("type") == target_type and entity.get("text"):
            print(f"Found entity for type '{target_type}': {entity['text']}")
            return entity["text"]
    return None

def _find_all_entities(
    entities: List[Dict[str, Any]], 
    target_type: str
) -> List[str]:
    results = []
    for entity in entities:
        if entity.get("type") == target_type and entity.get("text"):
            results.append(entity["text"])
    return results

def _escape_str(value: str) -> str:
    return value.replace('"', '\\"')

# ------------------------builder functions for specific intents ------------------------

def build_born_at_query(entities: List[Dict[str, Any]]) -> Optional[str]:
    politician = _find_entity(entities, "Politician")
    location   = _find_entity(entities, "Location")

    if politician:
        pol = _escape_str(politician)
        if location:
            loc = _escape_str(location)
            return f"""
MATCH (p:Politician)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
MATCH (p)-[:BORN_AT]->(loc:Location)
WHERE toLower(loc.name) CONTAINS toLower("{loc}")
RETURN p.name AS name, loc.name AS birth_place
LIMIT 5
""".strip()
        else:
            return f"""
MATCH (p:Politician)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
MATCH (p)-[:BORN_AT]->(loc:Location)
RETURN p.name AS name, loc.name AS birth_place
LIMIT 5
""".strip()
    
    if location:
        loc = _escape_str(location)
        return f"""
MATCH (p:Politician)-[:BORN_AT]->(loc:Location)
WHERE toLower(loc.name) CONTAINS toLower("{loc}")
RETURN p.name AS name, loc.name AS birth_place
LIMIT 20
""".strip()
    
    return None

def build_died_at_query(entities: List[Dict]) -> Optional[str]:
    politician = _find_entity(entities, "Politician")
    location   = _find_entity(entities, "Location")

    if politician:
        pol = _escape_str(politician)
        if location:
            loc = _escape_str(location)
            return f"""
MATCH (p:Politician)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
MATCH (p)-[:DIED_AT]->(loc:Location)
WHERE toLower(loc.name) CONTAINS toLower("{loc}")
RETURN p.name AS name, loc.name AS death_place
LIMIT 20
""".strip()
        else:
            return f"""
MATCH (p:Politician)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
MATCH (p)-[:DIED_AT]->(loc:Location)
RETURN p.name AS name, loc.name AS death_place
LIMIT 5
""".strip()
    
    if location:
        loc = _escape_str(location)
        return f"""
MATCH (p:Politician)-[:DIED_AT]->(loc:Location)
WHERE toLower(loc.name) CONTAINS toLower("{loc}")
RETURN p.name AS name, loc.name AS death_place
LIMIT 20
""".strip()
    
    return None

def build_preceded_query(entities: List[Dict]) -> Optional[str]:
    politician = _find_entity(entities, "Politician")
    position   = _find_entity(entities, "Position")

    if not politician:
        return None
    
    pol = _escape_str(politician)

    if position:
        pos = _escape_str(position)
        return f"""
MATCH (p:Politician)-[cur:SERVED_AS]->(pos:Position)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
  AND toLower(pos.name) CONTAINS toLower("{pos}")
MATCH (p)-[:PRECEDED {{position_id: pos.id}}]->(prev:Politician)
RETURN DISTINCT prev.name AS predecessor
LIMIT 20
""".strip()
    else:
        return f"""
MATCH (p:Politician)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
MATCH (p)-[:PRECEDED]->(prev:Politician)
RETURN DISTINCT prev.name AS predecessor
LIMIT 20
""".strip()
    
def build_succeeded_query(entities: List[Dict]) -> Optional[str]:
    politician = _find_entity(entities, "Politician")
    position   = _find_entity(entities, "Position")

    if not politician:
        return None

    pol = _escape_str(politician)

    if position:
        pos = _escape_str(position)
        return f"""
MATCH (p:Politician)-[cur:SERVED_AS]->(pos:Position)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
  AND toLower(pos.name) CONTAINS toLower("{pos}")
MATCH (succ:Politician)-[:SUCCEEDED {{position_id: pos.id}}]->(p)
RETURN DISTINCT succ.name AS successor
LIMIT 20
""".strip()
    else:
        return f"""
MATCH (p:Politician)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
MATCH (succ:Politician)-[:SUCCEEDED]->(p)
RETURN DISTINCT succ.name AS successor
LIMIT 20
""".strip()

def build_served_as_query(entities: List[Dict]) -> Optional[str]:
    politician = _find_entity(entities, "Politician")
    position   = _find_entity(entities, "Position")

    if politician and not position:
        pol = _escape_str(politician)
        return f"""
MATCH (p:Politician)-[r:SERVED_AS]->(pos:Position)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
RETURN 
  p.name AS name,
  pos.name AS position,
  r.term_start AS term_start,
  r.term_end AS term_end,
  r.status AS status,
  r.reason AS reason
ORDER BY r.term_start ASC
LIMIT 50
""".strip()
    
    if politician and position:
        pol = _escape_str(politician)
        pos = _escape_str(position)
        return f"""
MATCH (p:Politician)-[r:SERVED_AS]->(pos:Position)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
  AND toLower(pos.name) CONTAINS toLower("{pos}")
RETURN 
  p.name AS name,
  pos.name AS position,
  r.term_start AS term_start,
  r.term_end AS term_end,
  r.status AS status,
  r.reason AS reason
ORDER BY r.term_start ASC
LIMIT 20
""".strip()
    
    if position and not politician:
        pos = _escape_str(position)
        return f"""
MATCH (p:Politician)-[r:SERVED_AS]->(pos:Position)
WHERE toLower(pos.name) CONTAINS toLower("{pos}")
RETURN 
  p.name AS name,
  pos.name AS position,
  r.term_start AS term_start,
  r.term_end AS term_end,
  r.status AS status
ORDER BY r.term_start ASC
LIMIT 50
""".strip()
    
    return None

def build_has_rank_query(entities: List[Dict]) -> Optional[str]:
    politician = _find_entity(entities, "Politician")
    rank       = _find_entity(entities, "MilitaryRank")

    if politician and not rank:
        pol = _escape_str(politician)
        return f"""
MATCH (p:Politician)-[:HAS_RANK]->(r:MilitaryRank)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
RETURN p.name AS name, r.name AS rank
LIMIT 20
""".strip()
    
    if politician and rank:
        pol = _escape_str(politician)
        rk  = _escape_str(rank)
        return f"""
MATCH (p:Politician)-[:HAS_RANK]->(r:MilitaryRank)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
  AND toLower(r.name) CONTAINS toLower("{rk}")
RETURN p.name AS name, r.name AS rank
LIMIT 20
""".strip()
    
    if rank and not politician:
        rk  = _escape_str(rank)
        return f"""
MATCH (p:Politician)-[:HAS_RANK]->(r:MilitaryRank)
WHERE toLower(r.name) CONTAINS toLower("{rk}")
RETURN p.name AS name, r.name AS rank
LIMIT 50
""".strip()
    
    return None

def build_alumnus_of_query(entities: List[Dict]) -> Optional[str]:
    politician = _find_entity(entities, "Politician")
    alma_mater     = _find_entity(entities, "AlmaMater")

    if politician and not alma_mater:
        pol = _escape_str(politician)
        return f"""
MATCH (p:Politician)-[:ALUMNUS_OF]->(s:AlmaMater)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
RETURN p.name AS name, s.name AS school_name
LIMIT 20
""".strip()
    
    if politician and alma_mater:
        pol = _escape_str(politician)
        alma = _escape_str(alma_mater)
        return f"""
MATCH (p:Politician)-[:ALUMNUS_OF]->(s:AlmaMater)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
  AND toLower(s.name) CONTAINS toLower("{alma}")
RETURN p.name AS name, s.name AS school_name
LIMIT 20
""".strip()

    if alma_mater and not politician:
        alma = _escape_str(alma_mater)
        return f"""
MATCH (p:Politician)-[:ALUMNUS_OF]->(s:AlmaMater)
WHERE toLower(s.name) CONTAINS toLower("{alma}")
RETURN p.name AS name, s.name AS school_name
LIMIT 50
""".strip()

    return None

def build_awarded_query(entities: List[Dict]) -> Optional[str]:
    politician = _find_entity(entities, "Politician")
    award      = _find_entity(entities, "Award")

    if politician and not award:
        pol = _escape_str(politician)
        return f"""
MATCH (p:Politician)-[:AWARDED]->(a:Award)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
RETURN p.name AS name, a.name AS award_name
LIMIT 50
""".strip()
    
    if politician and award:
        pol = _escape_str(politician)
        aw  = _escape_str(award)
        return f"""
MATCH (p:Politician)-[:AWARDED]->(a:Award)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
  AND toLower(a.name) CONTAINS toLower("{aw}")
RETURN p.name AS name, a.name AS award_name
LIMIT 20
""".strip()

    if award and not politician:
        aw  = _escape_str(award)
        return f"""
MATCH (p:Politician)-[:AWARDED]->(a:Award)
WHERE toLower(a.name) CONTAINS toLower("{aw}")
RETURN p.name AS name, a.name AS award_name
LIMIT 50
""".strip()
    
    return None

def build_served_in_query(entities: List[Dict]) -> Optional[str]:
    politician = _find_entity(entities, "Politician")
    career     = _find_entity(entities, "MilitaryCareer")

    if politician and not career:
        pol = _escape_str(politician)
        return f"""
MATCH (p:Politician)-[r:SERVED_IN]->(m:MilitaryCareer)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
RETURN 
  p.name AS name,
  m.name AS military_career,
  r.year_start AS year_start,
  r.year_end AS year_end
LIMIT 20
""".strip()

    if politician and career:
        pol = _escape_str(politician)
        car = _escape_str(career)
        return f"""
MATCH (p:Politician)-[r:SERVED_IN]->(m:MilitaryCareer)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
  AND toLower(m.name) CONTAINS toLower("{car}")
RETURN 
  p.name AS name,
  m.name AS military_career,
  r.year_start AS year_start,
  r.year_end AS year_end
LIMIT 20
""".strip()
    
    if career and not politician:
        car = _escape_str(career)
        return f"""
MATCH (p:Politician)-[r:SERVED_IN]->(m:MilitaryCareer)
WHERE toLower(m.name) CONTAINS toLower("{car}")
RETURN 
  p.name AS name,
  m.name AS military_career,
  r.year_start AS year_start,
  r.year_end AS year_end
LIMIT 50
""".strip()

    return None

def build_fought_in_query(entities: List[Dict]) -> Optional[str]:
    politician = _find_entity(entities, "Politician")
    canpaign   = _find_entity(entities, "Campaigns")

    if politician and not canpaign:
        pol = _escape_str(politician)
        return f"""
MATCH (p:Politician)-[:FOUGHT_IN]->(c:Campaigns)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
RETURN p.name AS name, c.name AS campaign_name
LIMIT 20
""".strip()

    if politician and canpaign:
        pol = _escape_str(politician)
        camp = _escape_str(canpaign)
        return f"""
MATCH (p:Politician)-[:FOUGHT_IN]->(c:Campaigns)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
  AND toLower(c.name) CONTAINS toLower("{camp}")
RETURN p.name AS name, c.name AS campaign_name
LIMIT 20
""".strip()

    if canpaign and not politician:
        camp = _escape_str(canpaign)
        return f"""
MATCH (p:Politician)-[:FOUGHT_IN]->(c:Campaigns)
WHERE toLower(c.name) CONTAINS toLower("{camp}")
RETURN p.name AS name, c.name AS campaign_name
LIMIT 50
""".strip()
    
    return None

def build_academic_title_query(entities: List[Dict]) -> Optional[str]:
    politician = _find_entity(entities, "Politician")
    title      = _find_entity(entities, "AcademicTitle")

    if politician and not title:
        pol = _escape_str(politician)
        return f"""
MATCH (p:Politician)-[:HAS_ACADEMIC_TITLE]->(t:AcademicTitle)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
RETURN p.name AS name, t.name AS academic_title
LIMIT 20
""".strip()
    
    if politician and title:
        pol = _escape_str(politician)
        tit = _escape_str(title)
        return f"""
MATCH (p:Politician)-[:HAS_ACADEMIC_TITLE]->(t:AcademicTitle)
WHERE toLower(p.name) CONTAINS toLower("{pol}")
  AND toLower(t.name) CONTAINS toLower("{tit}")
RETURN p.name AS name, t.name AS academic_title
LIMIT 20
""".strip()
    
    if title and not politician:
        tit = _escape_str(title)
        return f"""
MATCH (p:Politician)-[:HAS_ACADEMIC_TITLE]->(t:AcademicTitle)
WHERE toLower(t.name) CONTAINS toLower("{tit}")
RETURN p.name AS name, t.name AS academic_title
LIMIT 50
""".strip()

    return None

# ------------------------ Main function to build Cypher query ------------------------

def build_cypher_from_intent(
    intent_relation: str,
    entities: List[Dict]
) -> Optional[str]:
    
    intent = (intent_relation or "UNKNOWN").upper()

    if intent == "BORN_AT":
        return build_born_at_query(entities)
    if intent == "DIED_AT":
        return build_died_at_query(entities)
    if intent == "PRECEDED":
        return build_preceded_query(entities)
    if intent == "SUCCEEDED":
        return build_succeeded_query(entities)
    if intent == "SERVED_IN":
        return build_served_in_query(entities)
    if intent == "FOUGHT_IN":
        return build_fought_in_query(entities)
    if intent == "HAS_ACADEMIC_TITLE":
        return build_academic_title_query(entities)
    if intent == "HAS_RANK":
        return build_has_rank_query(entities)
    if intent == "ALUMNUS_OF":
        return build_alumnus_of_query(entities)
    if intent == "AWARDED":
        return build_awarded_query(entities)
    if intent == "SERVED_AS":
        return build_served_as_query(entities)
    
    return None

INTENT_BUILDER_MAP = {
    "BORN_AT": build_born_at_query,
    "DIED_AT": build_died_at_query,
    "PRECEDED": build_preceded_query,
    "SUCCEEDED": build_succeeded_query,
    "SERVED_AS": build_served_as_query,
    "HAS_RANK": build_has_rank_query,
    "ALUMNUS_OF": build_alumnus_of_query,
    "AWARDED": build_awarded_query,
    "SERVED_IN": build_served_in_query,
    "FOUGHT_IN": build_fought_in_query,
    "HAS_ACADEMIC_TITLE": build_academic_title_query,
}

def build_query_from_entities_and_relation(
    relation: str,
    politician: str = None,
    location: str = None,
    position: str = None,
    alma_mater: str = None,
    award: str = None,
    military_rank: str = None,
    military_career: str = None,
    campaign: str = None,
    academic_title: str = None
) -> Optional[str]:
    entities = []
    if politician:
        entities.append({"type": "Politician", "text": politician})
    if location:
        entities.append({"type": "Location", "text": location})
    if position:
        entities.append({"type": "Position", "text": position})
    if alma_mater:
        entities.append({"type": "AlmaMater", "text": alma_mater})
    if award:
        entities.append({"type": "Award", "text": award})
    if military_rank:
        entities.append({"type": "MilitaryRank", "text": military_rank})
    if military_career:
        entities.append({"type": "MilitaryCareer", "text": military_career})
    if campaign:
        entities.append({"type": "Campaigns", "text": campaign})
    if academic_title:
        entities.append({"type": "AcademicTitle", "text": academic_title})
    
    builder = INTENT_BUILDER_MAP.get(relation.upper())
    if builder:
        return builder(entities)
    
    return None

GRAPH_SCHEMA = {
    "nodes": {
        "Politician": ["name", "birth_date", "death_date", "party"],
        "Position": ["name", "id"],
        "Location": ["name"],
        "AlmaMater": ["name"],
        "Award": ["name"],
        "MilitaryRank": ["name"],
        "MilitaryCareer": ["name"],
        "Campaigns": ["name"],
        "AcademicTitle": ["name"],
    },
    "relationships": {
        "BORN_AT": {"from": "Politician", "to": "Location"},
        "DIED_AT": {"from": "Politician", "to": "Location"},
        "SERVED_AS": {"from": "Politician", "to": "Position", "props": ["term_start", "term_end", "status"]},
        "PRECEDED": {"from": "Politician", "to": "Politician", "props": ["position_id"]},
        "SUCCEEDED": {"from": "Politician", "to": "Politician", "props": ["position_id"]},
        "ALUMNUS_OF": {"from": "Politician", "to": "AlmaMater"},
        "AWARDED": {"from": "Politician", "to": "Award"},
        "HAS_RANK": {"from": "Politician", "to": "MilitaryRank"},
        "SERVED_IN": {"from": "Politician", "to": "MilitaryCareer", "props": ["year_start", "year_end"]},
        "FOUGHT_IN": {"from": "Politician", "to": "Campaigns"},
        "HAS_ACADEMIC_TITLE": {"from": "Politician", "to": "AcademicTitle"},
    }
}


# ======================== MULTI-HOP REASONING ========================

def build_multihop_exploration_query(
    current_entities: List[str],
    explored_relations: List[str],
    hop_number: int,
    max_results: int = 20
) -> str:
    """
    Tạo query khám phá các quan hệ mới từ entities hiện tại.
    (Ở v1: explored_relations chưa filter mạnh trong Cypher để tránh query phức tạp)
    """
    if not current_entities:
        return ""

    entity_patterns = " OR ".join([
        f'toLower(p.name) CONTAINS toLower("{_escape_str(e)}")'
        for e in current_entities
    ])

    query = f"""
MATCH (p:Politician)
WHERE {entity_patterns}
MATCH path = (p)-[r*1..2]-(connected)
WHERE connected:Politician OR connected:Position OR connected:Location 
      OR connected:AlmaMater OR connected:Award
WITH p, path
LIMIT {max_results}
RETURN 
  p.name AS source_entity,
  [rel IN relationships(path) | type(rel)] AS relation_types,
  [node IN nodes(path) | 
    CASE 
      WHEN node:Politician THEN {{type: 'Politician', name: node.name}}
      WHEN node:Position THEN {{type: 'Position', name: node.name}}
      WHEN node:Location THEN {{type: 'Location', name: node.name}}
      WHEN node:AlmaMater THEN {{type: 'AlmaMater', name: node.name}}
      WHEN node:Award THEN {{type: 'Award', name: node.name}}
      ELSE {{type: labels(node)[0], name: coalesce(node.name, 'Unknown')}}
    END
  ] AS path_nodes
""".strip()

    logger.info(f"[HOP-{hop_number}] Generated exploration query")
    return query


def build_path_query(
    start_entity: str,
    end_entity: str,
    max_depth: int = 4
) -> str:
    """
    Tìm đường đi ngắn nhất giữa 2 entities (path reasoning).
    """
    start = _escape_str(start_entity)
    end = _escape_str(end_entity)

    query = f"""
MATCH (start:Politician)
WHERE toLower(start.name) CONTAINS toLower("{start}")
MATCH (end)
WHERE (end:Politician OR end:Position OR end:Location OR end:AlmaMater)
  AND toLower(coalesce(end.name, '')) CONTAINS toLower("{end}")
MATCH path = shortestPath((start)-[*1..{max_depth}]-(end))
RETURN 
  [node IN nodes(path) | 
    CASE 
      WHEN node:Politician THEN {{type: 'Politician', name: node.name, birth_date: node.birth_date}}
      WHEN node:Position THEN {{type: 'Position', name: node.name}}
      WHEN node:Location THEN {{type: 'Location', name: node.name}}
      WHEN node:AlmaMater THEN {{type: 'AlmaMater', name: node.name}}
      ELSE {{type: labels(node)[0], name: coalesce(node.name, 'Unknown')}}
    END
  ] AS path_nodes,
  [rel IN relationships(path) | 
    {{type: type(rel), properties: properties(rel)}}
  ] AS path_relations,
  length(path) AS path_length
LIMIT 5
""".strip()

    logger.info(f"Generated path query: {start} -> {end}")
    return query


def build_chain_query(
    start_entity: str,
    relation_chain: List[str],
    hop_number: int
) -> str:
    """
    Xây dựng query cho chuỗi quan hệ cụ thể (chain reasoning).
    VD: A -PRECEDED-> B -SERVED_AS-> Position
    """
    if not relation_chain:
        return ""

    start = _escape_str(start_entity)

    # MATCH (n0:Politician) ... MATCH (n0)-[r0:REL0]->(n1)-[r1:REL1]->(n2)...
    match_head = f"(n0:Politician)\nWHERE toLower(n0.name) CONTAINS toLower(\"{start}\")"
    rel_parts = []
    for i, rel in enumerate(relation_chain[:hop_number]):
        rel_parts.append(f"(n{i})-[r{i}:{rel}]->(n{i+1})")

    match_clause = "MATCH " + "-".join(rel_parts)

    return_nodes = ", ".join([
        f"n{i}.name AS node_{i}" for i in range(len(relation_chain) + 1)
    ])
    return_rels = ", ".join([
        f"type(r{i}) AS rel_{i}" for i in range(len(relation_chain))
    ])

    query = f"""
MATCH {match_head}
{match_clause}
RETURN {return_nodes}, {return_rels}
LIMIT 20
""".strip()

    logger.info(f"[HOP-{hop_number}] Chain query with relations: {relation_chain[:hop_number]}")
    return query


def build_aggregation_query(
    entity: str,
    relation_type: str,
    aggregation: str = "count"
) -> str:
    """
    Tạo query tổng hợp (đếm, liệt kê) - hữu ích cho câu hỏi so sánh/đếm.
    VD: "Ai có nhiều giải thưởng nhất?"
    """
    ent = _escape_str(entity)

    if aggregation == "count":
        query = f"""
MATCH (p:Politician)-[r:{relation_type}]->(target)
WHERE toLower(p.name) CONTAINS toLower("{ent}")
RETURN 
  p.name AS politician,
  count(target) AS total_{relation_type.lower()},
  collect(target.name) AS items
ORDER BY total_{relation_type.lower()} DESC
LIMIT 10
""".strip()
    else:
        query = f"""
MATCH (p:Politician)-[r:{relation_type}]->(target)
WHERE toLower(p.name) CONTAINS toLower("{ent}")
RETURN 
  p.name AS politician,
  collect({{name: target.name, properties: properties(r)}}) AS {relation_type.lower()}_list
LIMIT 10
""".strip()

    logger.info(f"Aggregation query: {entity} - {relation_type} - {aggregation}")
    return query


def build_comparative_query(
    entities: List[str],
    attribute: str,
    relation_type: str = None
) -> str:
    """
    So sánh nhiều entities theo một thuộc tính hoặc quan hệ.
    VD: "So sánh số giải thưởng của A và B"
    """
    if len(entities) < 2:
        return ""

    entity_patterns = " OR ".join([
        f'toLower(p.name) CONTAINS toLower("{_escape_str(e)}")'
        for e in entities
    ])

    if relation_type:
        query = f"""
MATCH (p:Politician)
WHERE {entity_patterns}
OPTIONAL MATCH (p)-[r:{relation_type}]->(target)
WITH p, count(target) AS total, collect(target.name) AS items
RETURN 
  p.name AS politician,
  p.{attribute} AS {attribute},
  total AS total_{relation_type.lower()},
  items AS {relation_type.lower()}_list
ORDER BY total DESC
""".strip()
    else:
        query = f"""
MATCH (p:Politician)
WHERE {entity_patterns}
RETURN 
  p.name AS politician,
  p.{attribute} AS {attribute}
ORDER BY p.{attribute}
""".strip()

    logger.info(f"Comparative query for: {entities}")
    return query


def build_context_aware_query(
    question: str,
    previous_results: List[Dict],
    hop_number: int,
    max_hops: int,
    explored_relations: List[str] = None
) -> Optional[str]:
    """
    Tạo query dựa trên context từ các hop trước.
    Dùng để 'explore' thông minh hơn thay vì random.
    """
    if hop_number > max_hops:
        return None

    discovered_entities: List[str] = []
    discovered_relation_types: List[str] = []

    for result in previous_results:
        for key, value in result.items():
            if isinstance(value, str) and key in [
                "name", "politician", "source_entity", "predecessor", "successor"
            ]:
                discovered_entities.append(value)

            if key == "relation_types" and isinstance(value, list):
                discovered_relation_types.extend(value)
            elif key.startswith("rel_") and isinstance(value, str):
                discovered_relation_types.append(value)

    discovered_entities = list(set(discovered_entities))[:5]

    if not discovered_entities:
        return None

    if explored_relations is None:
        explored_relations = []

    all_explored = list(set(explored_relations + discovered_relation_types))

    logger.info(
        f"[HOP-{hop_number}] Context-aware query: "
        f"{len(discovered_entities)} entities, "
        f"excluding {len(all_explored)} relation types (tracking only in Python)"
    )

    # v1: vẫn dùng exploration query, chưa filter all_explored trong Cypher
    return build_multihop_exploration_query(
        current_entities=discovered_entities,
        explored_relations=all_explored,
        hop_number=hop_number,
        max_results=15
    )
