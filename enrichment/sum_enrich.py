# enrichment/sum_enrich.py

import json
from collections import defaultdict
from tqdm import tqdm

from utils.config import settings
from graph.load_graph import load_graph_from_json

graph, node_info = load_graph_from_json(settings.INPUT_SUM_ENRICH_FILE)

with open(settings.INPUT_SUM_ENRICH_FILE, "r", encoding="utf-8") as f:
    kg = json.load(f)
metadata = kg.get("metadata", {})

node_lookup = node_info

nodes = []
for nid, info in node_info.items():
    if info.get("type") == "Politician":
        nodes.append({
            "id": nid,
            "name": info.get("name", ""),
            "type": info.get("type"),
            "properties": info.get("properties", {})
        })

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
    summary = []
    summary.append(f"{name} là một chính trị gia Việt Nam.")
    # Positions
    positions = []
    for edge in edge_lookup.get(pol["id"], []):
        if edge["type"] == "SERVED_AS":
            pos_id = edge.get("to")
            pos = node_lookup.get(pos_id, {})
            pos_name = pos.get("name", "")
            term_start = edge.get("properties", {}).get("term_start", "")
            term_end = edge.get("properties", {}).get("term_end", "")
            if pos_name:
                positions.append(f"{pos_name} ({term_start} - {term_end})" if term_start or term_end else pos_name)
    if positions:
        summary.append(f"Các chức vụ từng đảm nhiệm: {', '.join(positions)}.")
    # Locations
    born_at = None
    died_at = None
    for edge in edge_lookup.get(pol["id"], []):
        if edge["type"] == "BORN_AT":
            loc_id = edge.get("to")
            loc = node_lookup.get(loc_id, {})
            born_at = loc.get("name", "")
        if edge["type"] == "DIED_AT":
            loc_id = edge.get("to")
            loc = node_lookup.get(loc_id, {})
            died_at = loc.get("name", "")
    if born_at:
        summary.append(f"Sinh tại {born_at}.")
    if died_at:
        summary.append(f"Mất tại {died_at}.")
    # AlmaMater
    schools = []
    for edge in edge_lookup.get(pol["id"], []):
        if edge["type"] == "ALUMNUS_OF":
            school_id = edge.get("to")
            school = node_lookup.get(school_id, {})
            school_name = school.get("name", "")
            if school_name:
                schools.append(school_name)
    if schools:
        summary.append(f"Tốt nghiệp tại: {', '.join(schools)}.")
    # MilitaryCareer
    military_units = []
    for edge in edge_lookup.get(pol["id"], []):
        if edge["type"] == "SERVED_IN":
            unit_id = edge.get("to")
            unit = node_lookup.get(unit_id, {})
            unit_name = unit.get("name", "")
            if unit_name:
                military_units.append(unit_name)
    if military_units:
        summary.append(f"Từng phục vụ tại: {', '.join(military_units)}.")
    # MilitaryRank
    ranks = []
    for edge in edge_lookup.get(pol["id"], []):
        if edge["type"] == "HAS_RANK":
            rank_id = edge.get("to")
            rank = node_lookup.get(rank_id, {})
            rank_name = rank.get("name", "")
            if rank_name:
                ranks.append(rank_name)
    if ranks:
        summary.append(f"Cấp bậc: {', '.join(ranks)}.")
    # Awards
    awards = []
    for edge in edge_lookup.get(pol["id"], []):
        if edge["type"] == "AWARDED":
            award_id = edge.get("to")
            award = node_lookup.get(award_id, {})
            award_name = award.get("name", "")
            if award_name:
                awards.append(award_name)
    if awards:
        summary.append(f"Giải thưởng/Huân chương: {', '.join(awards)}.")
    # AcademicTitles
    titles = []
    for edge in edge_lookup.get(pol["id"], []):
        if edge["type"] == "HAS_ACADEMIC_TITLE":
            title_id = edge.get("to")
            title = node_lookup.get(title_id, {})
            title_name = title.get("name", "")
            if title_name:
                titles.append(title_name)
    if titles:
        summary.append(f"Học hàm/học vị: {', '.join(titles)}.")
    # Campaigns
    campaigns = []
    for edge in edge_lookup.get(pol["id"], []):
        if edge["type"] == "FOUGHT_IN":
            camp_id = edge.get("to")
            camp = node_lookup.get(camp_id, {})
            camp_name = camp.get("name", "")
            if camp_name:
                campaigns.append(camp_name)
    if campaigns:
        summary.append(f"Tham gia chiến dịch: {', '.join(campaigns)}.")
    # Succession relations
    succeeded = []
    preceded = []
    for edge in edge_lookup.get(pol["id"], []):
        if edge["type"] == "SUCCEEDED":
            target_id = edge.get("to")
            target = node_lookup.get(target_id, {})
            target_name = target.get("name", "")
            if target_name:
                succeeded.append(target_name)
        if edge["type"] == "PRECEDED":
            target_id = edge.get("to")
            target = node_lookup.get(target_id, {})
            target_name = target.get("name", "")
            if target_name:
                preceded.append(target_name)
    if succeeded:
        summary.append(f"Kế nhiệm: {', '.join(succeeded)}.")
    if preceded:
        summary.append(f"Tiền nhiệm: {', '.join(preceded)}.")
    return " ".join(summary)

# Process all politicians
output_nodes = []
for pol in tqdm(nodes, desc="Processing Politicians"):
    if "id" not in pol:
        continue
    pol_out = dict(pol)
    pol_out["full_text_summary"] = build_summary(pol)
    output_nodes.append(pol_out)

nodes_by_type = defaultdict(list)

politician_summaries = {n["id"]: n["full_text_summary"] for n in output_nodes}

for nid, info in node_info.items():
    node_entry = {
        "id": nid,
        "name": info.get("name", ""),
        "type": info.get("type", ""),
        "properties": info.get("properties", {})
    }
    if info.get("type") == "Politician" and nid in politician_summaries:
        node_entry["full_text_summary"] = politician_summaries[nid]

    nodes_by_type[info.get("type", "Unknown")].append(node_entry)

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

print(f"Done! Saved to {settings.OUTPUT_SUM_ENRICH_FILE}")

