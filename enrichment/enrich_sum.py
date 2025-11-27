# enrichment/enrich_sum.py

import json
from tqdm import tqdm
from collections import defaultdict

from utils.config import settings
from graph.load_graph import load_graph_from_json

graph, node_info = load_graph_from_json(settings.INPUT_SUM_ENRICH_FILE)

with open(settings.INPUT_SUM_ENRICH_FILE, "r", encoding="utf-8") as f:
    kg = json.load(f)
metadata = kg.get("metadata", {})

node_lookup = node_info

edge_lookup = defaultdict(list)
for u, v, k, data in graph.edges(keys=True, data=True):
    rel_type = data.get("rel_type") or data.get("type") or "UNKNOWN"
    props = data.get("properties", {})
    edge_lookup[u].append({
        "type": rel_type,
        "from": u,
        "to": v,
        "properties": props
    })

def build_summary(pol):
    name = pol.get("name", "")
    props = pol.get("properties", {})
    
    birth_date = props.get("birth_date", "")
    death_date = props.get("death_date", "")
    party = props.get("party", "")
    
    intro_parts = [f"{name} là một chính trị gia Việt Nam"]
    if birth_date:
        intro_parts.append(f"sinh ngày {birth_date}")
    if death_date:
        intro_parts.append(f"mất ngày {death_date}")
    if party:
        intro_parts.append(f"thuộc {party}")
    
    summary = [", ".join(intro_parts) + "."]
    
    my_edges = edge_lookup.get(pol["id"], [])

    # CẠNH
    # SERVED_AS
    positions = []
    for edge in my_edges:
        if edge["type"] == "SERVED_AS":
            pos_id = edge.get("to")
            pos = node_lookup.get(pos_id, {})
            pos_name = pos.get("name", "")
            
            eprops = edge.get("properties", {})
            t_start = eprops.get("term_start", "")
            t_end = eprops.get("term_end", "")
            status = eprops.get("status", "")
            reason = eprops.get("reason", "")
            
            detail_parts = []
            if t_start or t_end:
                detail_parts.append(f"{t_start} - {t_end}")
            
            if status:
                detail_parts.append(f"trạng thái: {status}")
            
            if reason:
                detail_parts.append(f"lý do: {reason}")
            
            pos_str = pos_name
            if detail_parts:
                pos_str += f" ({', '.join(detail_parts)})"
            
            if pos_name:
                positions.append(pos_str)
                
    if positions:
        summary.append(f"Các chức vụ từng đảm nhiệm: {'; '.join(positions)}.")

    # BORN_AT, DIED_AT
    born_at = []
    died_at = []
    for edge in my_edges:
        target = node_lookup.get(edge["to"], {}).get("name", "")
        if not target: continue
        
        if edge["type"] == "BORN_AT":
            born_at.append(target)
        elif edge["type"] == "DIED_AT":
            died_at.append(target)
            
    if born_at: summary.append(f"Sinh tại {', '.join(born_at)}.")
    if died_at: summary.append(f"Mất tại {', '.join(died_at)}.")

    # ALUMNUS_OF, HAS_ACADEMIC_TITLE
    schools = []
    titles = []
    for edge in my_edges:
        target = node_lookup.get(edge["to"], {}).get("name", "")
        if not target: continue

        if edge["type"] == "ALUMNUS_OF":
            schools.append(target)
        elif edge["type"] == "HAS_ACADEMIC_TITLE":
            titles.append(target)
            
    if schools: summary.append(f"Tốt nghiệp tại: {', '.join(schools)}.")
    if titles: summary.append(f"Học hàm/học vị: {', '.join(titles)}.")

    # SERVED_IN, HAS_RANK
    mil_units = []
    ranks = []
    for edge in my_edges:
        target = node_lookup.get(edge["to"], {}).get("name", "")
        if not target: continue
        eprops = edge.get("properties", {})

        if edge["type"] == "SERVED_IN":
            y_start = eprops.get("year_start")
            y_end = eprops.get("year_end")
            time_str = f" ({y_start}-{y_end})" if y_start or y_end else ""
            mil_units.append(f"{target}{time_str}")
            
        elif edge["type"] == "HAS_RANK":
            ranks.append(target)

    if mil_units: summary.append(f"Từng phục vụ tại: {', '.join(mil_units)}.")
    if ranks: summary.append(f"Cấp bậc: {', '.join(ranks)}.")

    # AWARDED
    awards = []
    for edge in my_edges:
        if edge["type"] == "AWARDED":
            target = node_lookup.get(edge["to"], {}).get("name", "")
            year = edge.get("properties", {}).get("year")
            if target:
                if year: awards.append(f"{target} ({year})")
                else: awards.append(target)
    if awards: summary.append(f"Giải thưởng/Huân chương: {', '.join(awards)}.")

    # FOUGHT_IN
    campaigns = []
    for edge in my_edges:
        if edge["type"] == "FOUGHT_IN":
            target = node_lookup.get(edge["to"], {}).get("name", "")
            if target: campaigns.append(target)
    if campaigns: summary.append(f"Tham gia chiến dịch: {', '.join(campaigns)}.")

    # SUCCEEDED, PRECEDED
    succeeded = []
    preceded = []
    for edge in my_edges:
        target = node_lookup.get(edge["to"], {}).get("name", "")
        if not target: continue
        
        if edge["type"] == "SUCCEEDED":
            succeeded.append(target)
        elif edge["type"] == "PRECEDED":
            preceded.append(target)
            
    if succeeded: summary.append(f"Kế nhiệm: {', '.join(succeeded)}.")
    if preceded: summary.append(f"Tiền nhiệm: {', '.join(preceded)}.")

    return " ".join(summary)


nodes_by_type = defaultdict(list)
processed_ids = set()

raw_nodes_list = []
for nid, info in node_info.items():
    raw_nodes_list.append({
        "id": nid,
        "name": info.get("name", ""),
        "type": info.get("type", "UNKNOWN"),
        "properties": info.get("properties", {})
    })

for node in tqdm(raw_nodes_list, desc="Processing Nodes"):
    node_out = node.copy()
    
    if node["type"] == "Politician":
        node_out["full_text_summary"] = build_summary(node)
    
    nodes_by_type[node["type"]].append(node_out)
    processed_ids.add(node["id"])

edges_by_type = defaultdict(list)
for u, v, k, data in graph.edges(keys=True, data=True):
    rel_type = data.get("rel_type") or data.get("type") or "UNKNOWN"
    props = data.get("properties", {})
    edge_entry = {
        "from": u,
        "to": v,
        "type": rel_type,
        "properties": props
    }
    edges_by_type[rel_type].append(edge_entry)

output = {
    "metadata": metadata,
    "nodes": nodes_by_type,
    "edges": edges_by_type
}

with open(settings.OUTPUT_SUM_ENRICH_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Saved enriched graph to {settings.OUTPUT_SUM_ENRICH_FILE}")