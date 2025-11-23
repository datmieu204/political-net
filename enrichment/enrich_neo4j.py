# ./enrichment/enrich_neo4j.py

import os
import json
import time
import google.generativeai as genai

from tqdm import tqdm
from typing import Dict, List, Set
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv
load_dotenv()

from utils.config import settings
from utils._logger import get_logger
logger = get_logger("enrichment.enrich_neo4j", log_file="logs/enrichment/enrich_neo4j.log")

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# ENRICHMENT_SCHEMA = 
with open('enrichment/schema.json', 'r', encoding='utf-8') as f:
    ENRICHMENT_SCHEMA = json.load(f)


class Neo4jEnrichment:
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": ENRICHMENT_SCHEMA,
                "temperature": 0.1
            }
        )
        self.request_interval = 4.0
        self.last_request_time = 0
        self.enrichment_log = []
        self.stats = {
            "processed": 0,
            "positions_added": 0,
            "locations_added": 0,
            "alma_mater_added": 0,
            "military_careers_added": 0,
            "military_ranks_added": 0,
            "awards_added": 0,
            "campaigns_added": 0,
            "academic_titles_added": 0,
            "edges_added": 0,
            "errors": 0
        }
        # Detailed logs: track for each category
        self.detailed_logs = {
            "positions": [],
            "locations": [],
            "alma_mater": [],
            "military_careers": [],
            "military_ranks": [],
            "awards": [],
            "campaigns": [],
            "academic_titles": [],
            "edges": []
        }
        # ID counters for generating unique IDs
        self.id_counters = {
            "Position": {},
            "Location": {},
            "Award": {},
            "MilitaryCareer": {},
            "MilitaryRank": {},
            "Campaigns": {},
            "AlmaMater": {},
            "AcademicTitle": {}
        }
        # Prefix mapping for node types
        self.id_prefixes = {
            "Position": "pos",
            "Location": "loc",
            "Award": "awa",
            "MilitaryCareer": "mil",
            "MilitaryRank": "mil",
            "Campaigns": "cam",
            "AlmaMater": "alm",
            "AcademicTitle": "aca"
        }
    
    def close(self):
        if self.driver:
            self.driver.close()
    
    def generate_node_id(self, label: str, politician_id: str, index: int) -> str:
        """
        Generate node ID theo format: prefix + politician_base_id + _index
        VD: pos19498354_001, loc436788_001, awa436788_002
        """
        prefix = self.id_prefixes.get(label, "unk")
        # Extract số từ politician_id (pol19498354 -> 19498354)
        pol_base_id = politician_id.replace("pol", "")
        return f"{prefix}{pol_base_id}_{index:03d}"
    
    def extract_from_summary(self, summary: str, politician_name: str, politician_id: str) -> Dict:
        summary_escaped = summary.replace('"', '\\"').replace('\n', ' ')
        
        prompt = f"""
Bạn là chuyên gia phân tích tiểu sử chính trị gia. Hãy trích xuất CHÍNH XÁC thông tin từ văn bản sau:

**Chính trị gia**: {politician_name} (ID: {politician_id})

**Văn bản tiểu sử**:
{summary_escaped}

**YÊU CẦU**:
1. **Positions**: Trích xuất TẤT CẢ các chức vụ được nhắc đến. Ghép chức danh + tổ chức (VD: "Bí thư Tỉnh ủy Hà Nội").
   - Phát hiện status: "bị cách chức/miễn nhiệm" nếu có từ "bị cách chức"/"miễn nhiệm"/"bãi bỏ"/"thôi việc"/"từ chức"/"nghỉ việc".
   - Trích xuất lý do vào trường "reason" nếu nếu có kỷ luật, miễn nhiệm, bị cách chức, bãi bỏ, thôi việc, từ chức, nghỉ việc.
   
2. **Locations**: Chỉ trích xuất địa danh (tỉnh/thành phố) liên quan đến:
   - Nơi sinh (BORN_AT)
   - Nơi mất (DIED_AT)

3. **AlmaMater**: Trích xuất tên các trường học, học viện, đại học nơi chính trị gia theo học.

4. **MilitaryCareers**: Trích xuất đơn vị quân đội/công an phục vụ với khoảng thời gian (nếu có).

5. **MilitaryRanks**: Trích xuất cấp bậc quân đội/công an (VD: Đại tướng, Trung tướng, Thiếu tướng, Đại tá...).

6. **Awards**: Chỉ trích xuất các huân chương, huy chương, danh hiệu CHÍNH THỨC.

7. **Campaigns**: Các chiến dịch quân sự đã tham chiến.

8. **AcademicTitles**: Học hàm, học vị (VD: Tiến sĩ, Phó giáo sư, Giáo sư, Thạc sĩ...).

9. **SuccessionRelations**: Quan hệ kế nhiệm/tiền nhiệm với chính trị gia KHÁC (phải có tên người và chức vụ liên quan).

**LƯU Ý**: Chỉ trích xuất thông tin CÓ TRONG văn bản. KHÔNG bịa đặt.
"""
        
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            sleep_time = self.request_interval - time_since_last
            time.sleep(sleep_time)
        
        try:
            response = self.model.generate_content(prompt)
            self.last_request_time = time.time()
            
            # Parse JSON response
            try:
                result = json.loads(response.text)
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON decode error for {politician_name}: {json_err}")
                logger.debug(f"Response text: {response.text[:500]}...")  # Log first 500 chars
                
                # Try to fix common issues
                try:
                    # Remove potential BOM or invisible characters
                    cleaned_text = response.text.strip()
                    result = json.loads(cleaned_text)
                except:
                    logger.error(f"Failed to parse JSON even after cleaning for {politician_name}")
                    self.stats["errors"] += 1
                    return None
            
            logger.info(f"Successfully extracted data for {politician_name}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting summary for {politician_name}: {e}")
            print(f"Error extracting summary for {politician_name}: {e}")
            self.stats["errors"] += 1
            return None
    
    def check_node_exists(self, session, label: str, name: str = None, node_id: str = None) -> str:
        if node_id:
            query = f"""
            MATCH (n:{label} WHERE n.id = $node_id)
            RETURN n.id AS id
            """
            result = session.run(query, node_id=node_id)
        elif name:
            query = f"""
            MATCH (n:{label} WHERE toLower(n.name) = toLower($name))
            RETURN n.id AS id
            """
            result = session.run(query, name=name)
        else:
            return None
        
        record = result.single()
        return record["id"] if record else None
    
    def create_or_merge_node(self, session, label: str, node_id: str, name: str, properties: Dict = None):
        props = properties or {}
        props["source"] = "llm_enrichment"
        props["type"] = label
        props["name"] = name
        
        # MERGE by ID, set all properties
        query = f"""
        MERGE (n:{label} {{id: $node_id}})
        ON CREATE SET n += $props, n.created_at = datetime()
        ON MATCH SET n.enriched = true, n.last_updated = datetime()
        RETURN n.id AS id
        """
        result = session.run(query, node_id=node_id, props=props)
        record = result.single()
        return record["id"] if record else None
    
    def create_edge(self, session, from_id: str, to_node_id: str, to_node_label: str,
                    edge_type: str, properties: Dict = None):
        props = properties or {}
        props["source"] = "llm_enrichment"
        props["type"] = edge_type
        
        query = f"""
        MATCH (p:Politician WHERE p.id = $from_id)
        MATCH (t:{to_node_label} WHERE t.id = $to_id)
        MERGE (p)-[r:{edge_type}]->(t)
        ON CREATE SET r += $props, r.created_at = datetime()
        RETURN type(r) AS rel_type
        """
        try:
            result = session.run(query, from_id=from_id, to_id=to_node_id, props=props)
            record = result.single()
            return record is not None
        except Exception:
            return False
    
    def enrich_politician(self, session, politician: Dict):
        """
        Main function to enrich a single politician node in Neo4j
        """        
        summary = politician.get("summary", "")
        if not summary or len(summary) < 50:
            return  # Bỏ qua nếu summary quá ngắn
        
        pol_id = f"pol{politician['id']}"
        pol_name = politician["title"]
        
        # Trích xuất dữ liệu từ LLM
        extracted = self.extract_from_summary(summary, pol_name, pol_id)
        if not extracted:
            return
        
        for idx, pos in enumerate(extracted.get("positions", []), start=1):
            pos_name = pos.get("name")
            if not pos_name:
                continue
            
            existing_id = self.check_node_exists(session, "Position", name=pos_name)
            
            if not existing_id:
                pos_id = self.generate_node_id("Position", pol_id, idx)
                self.create_or_merge_node(session, "Position", pos_id, pos_name)
                self.stats["positions_added"] += 1
                self.detailed_logs["positions"].append({
                    "id": pos_id,
                    "name": pos_name,
                    "politician_id": pol_id,
                    "politician_name": pol_name,
                    "organization": pos.get("organization", "")
                })
            else:
                pos_id = existing_id
            
            edge_props = {
                "term_start": pos.get("term_start", ""),
                "term_end": pos.get("term_end", ""),
                "status": pos.get("status", ""),
                "reason": pos.get("reason", "")
            }
            edge_props = {k: v for k, v in edge_props.items() if v}
            
            if self.create_edge(session, pol_id, pos_id, "Position", "SERVED_AS", edge_props):
                self.stats["edges_added"] += 1
                self.detailed_logs["edges"].append({
                    "type": "SERVED_AS",
                    "from": pol_id,
                    "to": pos_id,
                    "properties": edge_props
                })
        
        for idx, loc in enumerate(extracted.get("locations", []), start=1):
            loc_name = loc.get("name")
            relation = loc.get("relation", "BORN_AT")
            
            if not loc_name:
                continue
            
            existing_id = self.check_node_exists(session, "Location", name=loc_name)
            
            if not existing_id:
                loc_id = self.generate_node_id("Location", pol_id, idx)
                self.create_or_merge_node(session, "Location", loc_id, loc_name)
                self.stats["locations_added"] += 1
                self.detailed_logs["locations"].append({
                    "id": loc_id,
                    "name": loc_name,
                    "politician_id": pol_id,
                    "politician_name": pol_name,
                    "relation": relation
                })
            else:
                loc_id = existing_id
            
            if self.create_edge(session, pol_id, loc_id, "Location", relation):
                self.stats["edges_added"] += 1
                self.detailed_logs["edges"].append({
                    "type": relation,
                    "from": pol_id,
                    "to": loc_id,
                    "properties": {}
                })
        
        for idx, school in enumerate(extracted.get("alma_mater", []), start=1):
            school_name = school.get("name")
            
            if not school_name:
                continue
            
            existing_id = self.check_node_exists(session, "AlmaMater", name=school_name)
            
            if not existing_id:
                alm_id = self.generate_node_id("AlmaMater", pol_id, idx)
                self.create_or_merge_node(session, "AlmaMater", alm_id, school_name)
                self.stats["alma_mater_added"] += 1
                self.detailed_logs["alma_mater"].append({
                    "id": alm_id,
                    "name": school_name,
                    "politician_id": pol_id,
                    "politician_name": pol_name
                })
            else:
                alm_id = existing_id
            
            if self.create_edge(session, pol_id, alm_id, "AlmaMater", "ALUMNUS_OF"):
                self.stats["edges_added"] += 1
                self.detailed_logs["edges"].append({
                    "type": "ALUMNUS_OF",
                    "from": pol_id,
                    "to": alm_id,
                    "properties": {}
                })
        
        for idx, military in enumerate(extracted.get("military_careers", []), start=1):
            unit_name = military.get("name")
            
            if not unit_name:
                continue
            
            existing_id = self.check_node_exists(session, "MilitaryCareer", name=unit_name)
            
            if not existing_id:
                mil_id = self.generate_node_id("MilitaryCareer", pol_id, idx)
                self.create_or_merge_node(session, "MilitaryCareer", mil_id, unit_name)
                self.stats["military_careers_added"] += 1
                self.detailed_logs["military_careers"].append({
                    "id": mil_id,
                    "name": unit_name,
                    "politician_id": pol_id,
                    "politician_name": pol_name,
                    "year_start": military.get("year_start", ""),
                    "year_end": military.get("year_end", "")
                })
            else:
                mil_id = existing_id
            
            edge_props = {}
            if military.get("year_start"):
                try:
                    edge_props["year_start"] = int(military.get("year_start"))
                except (ValueError, TypeError):
                    pass
            if military.get("year_end"):
                try:
                    edge_props["year_end"] = int(military.get("year_end"))
                except (ValueError, TypeError):
                    pass
            
            if self.create_edge(session, pol_id, mil_id, "MilitaryCareer", "SERVED_IN", edge_props):
                self.stats["edges_added"] += 1
                self.detailed_logs["edges"].append({
                    "type": "SERVED_IN",
                    "from": pol_id,
                    "to": mil_id,
                    "properties": edge_props
                })
        
        for idx, rank in enumerate(extracted.get("military_ranks", []), start=1):
            rank_name = rank.get("name")
            
            if not rank_name:
                continue
            
            existing_id = self.check_node_exists(session, "MilitaryRank", name=rank_name)
            
            if not existing_id:
                rank_id = self.generate_node_id("MilitaryRank", pol_id, idx)
                self.create_or_merge_node(session, "MilitaryRank", rank_id, rank_name)
                self.stats["military_ranks_added"] += 1
                self.detailed_logs["military_ranks"].append({
                    "id": rank_id,
                    "name": rank_name,
                    "politician_id": pol_id,
                    "politician_name": pol_name
                })
            else:
                rank_id = existing_id
            
            if self.create_edge(session, pol_id, rank_id, "MilitaryRank", "HAS_RANK"):
                self.stats["edges_added"] += 1
                self.detailed_logs["edges"].append({
                    "type": "HAS_RANK",
                    "from": pol_id,
                    "to": rank_id,
                    "properties": {}
                })
        
        for idx, award in enumerate(extracted.get("awards", []), start=1):
            award_name = award.get("name")
            if not award_name:
                continue
            
            existing_id = self.check_node_exists(session, "Award", name=award_name)
            
            if not existing_id:
                awa_id = self.generate_node_id("Award", pol_id, idx)
                props = {"year": award.get("year", "")} if award.get("year") else {}
                self.create_or_merge_node(session, "Award", awa_id, award_name, props)
                self.stats["awards_added"] += 1
                self.detailed_logs["awards"].append({
                    "id": awa_id,
                    "name": award_name,
                    "politician_id": pol_id,
                    "politician_name": pol_name,
                    "year": award.get("year", "")
                })
            else:
                awa_id = existing_id
            
            if self.create_edge(session, pol_id, awa_id, "Award", "AWARDED"):
                self.stats["edges_added"] += 1
                self.detailed_logs["edges"].append({
                    "type": "AWARDED",
                    "from": pol_id,
                    "to": awa_id,
                    "properties": {}
                })
        
        for idx, campaign in enumerate(extracted.get("campaigns", []), start=1):
            campaign_name = campaign.get("name")
            
            if not campaign_name:
                continue
            
            existing_id = self.check_node_exists(session, "Campaigns", name=campaign_name)
            
            if not existing_id:
                cam_id = self.generate_node_id("Campaigns", pol_id, idx)
                props = {"year": campaign.get("year", "")} if campaign.get("year") else {}
                self.create_or_merge_node(session, "Campaigns", cam_id, campaign_name, props)
                self.stats["campaigns_added"] += 1
                self.detailed_logs["campaigns"].append({
                    "id": cam_id,
                    "name": campaign_name,
                    "politician_id": pol_id,
                    "politician_name": pol_name,
                    "year": campaign.get("year", "")
                })
            else:
                cam_id = existing_id
            
            if self.create_edge(session, pol_id, cam_id, "Campaigns", "FOUGHT_IN"):
                self.stats["edges_added"] += 1
                self.detailed_logs["edges"].append({
                    "type": "FOUGHT_IN",
                    "from": pol_id,
                    "to": cam_id,
                    "properties": {}
                })
        
        for idx, title in enumerate(extracted.get("academic_titles", []), start=1):
            title_name = title.get("name")
            
            if not title_name:
                continue
            
            existing_id = self.check_node_exists(session, "AcademicTitle", name=title_name)
            
            if not existing_id:
                aca_id = self.generate_node_id("AcademicTitle", pol_id, idx)
                self.create_or_merge_node(session, "AcademicTitle", aca_id, title_name)
                self.stats["academic_titles_added"] += 1
                self.detailed_logs["academic_titles"].append({
                    "id": aca_id,
                    "name": title_name,
                    "politician_id": pol_id,
                    "politician_name": pol_name
                })
            else:
                aca_id = existing_id
            
            if self.create_edge(session, pol_id, aca_id, "AcademicTitle", "HAS_ACADEMIC_TITLE"):
                self.stats["edges_added"] += 1
                self.detailed_logs["edges"].append({
                    "type": "HAS_ACADEMIC_TITLE",
                    "from": pol_id,
                    "to": aca_id,
                    "properties": {}
                })
        
        for rel in extracted.get("succession_relations", []):
            person_name = rel.get("person_name")
            rel_type = rel.get("relation_type")  # SUCCEEDED hoặc PRECEDED
            position_name = rel.get("position", "")
            
            if not person_name or not rel_type:
                continue
            
            position_id = None
            if position_name:
                try:
                    pos_query = """
                    MATCH (pos:Position WHERE toLower(pos.name) = toLower($position_name))
                    RETURN pos.id AS position_id
                    LIMIT 1
                    """
                    pos_result = session.run(pos_query, position_name=position_name)
                    pos_record = pos_result.single()
                    if pos_record:
                        position_id = pos_record["position_id"]
                except Exception:
                    pass
            
            query = f"""
            MATCH (p:Politician WHERE p.id = $from_id)
            MATCH (target:Politician WHERE toLower(target.name) CONTAINS toLower($person_name))
            MERGE (p)-[r:{rel_type}]->(target)
            ON CREATE SET r.position_id = $position_id, r.context = $context, r.source = 'llm_enrichment', r.type = $rel_type
            RETURN count(r) AS created
            """
            try:
                result = session.run(
                    query,
                    from_id=pol_id,
                    person_name=person_name,
                    position_id=position_id,
                    context=rel.get("context", ""),
                    rel_type=rel_type
                )
                record = result.single()
                if record and record["created"] > 0:
                    self.stats["edges_added"] += 1
            except Exception:
                pass
        
        enrichment_summary = {
            "politician_id": pol_id,
            "politician_name": pol_name,
            "positions_extracted": len(extracted.get("positions", [])),
            "locations_extracted": len(extracted.get("locations", [])),
            "alma_mater_extracted": len(extracted.get("alma_mater", [])),
            "military_careers_extracted": len(extracted.get("military_careers", [])),
            "military_ranks_extracted": len(extracted.get("military_ranks", [])),
            "awards_extracted": len(extracted.get("awards", [])),
            "campaigns_extracted": len(extracted.get("campaigns", [])),
            "academic_titles_extracted": len(extracted.get("academic_titles", [])),
            "succession_relations_extracted": len(extracted.get("succession_relations", []))
        }
        self.enrichment_log.append(enrichment_summary)
        logger.info(f"Enriched {pol_name}: {enrichment_summary}")
        
        self.stats["processed"] += 1
    
    def save_detailed_logs(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"enrichment/result/detailed_enrichment_{timestamp}.json"
        
        os.makedirs("enrichment/result", exist_ok=True)
        
        output = {
            "timestamp": timestamp,
            "statistics": self.stats,
            "detailed_data": self.detailed_logs
        }
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Detailed logs saved to {log_file}")
        print(f"\nDetailed logs saved to: {log_file}")
    
    def run_enrichment(self, input_file: str, limit: int = None, skip: int = 0):        
        print(f"Reading politicians data from {input_file}...")
        with open(input_file, 'r', encoding='utf-8') as f:
            politicians = json.load(f)
        
        if limit:
            politicians = politicians[skip:skip+limit]
        else:
            politicians = politicians[skip:]
        
        print(f"Processing {len(politicians)} politicians (starting from #{skip})...")
        
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            for politician in tqdm(politicians, desc="Enriching"):
                try:
                    self.enrich_politician(session, politician)
                except Exception as e:
                    print(f"\nError processing {politician.get('title')}: {e}")
                    self.stats["errors"] += 1
                    continue
        
        print("\n" + "="*60)
        print("ENRICHMENT STATISTICS")
        print("="*60)
        for key, value in self.stats.items():
            print(f"{key:.<40} {value}")
            logger.info(f"{key}: {value}")
        print("="*60)
        
        self.save_detailed_logs()


if __name__ == "__main__":
    enricher = Neo4jEnrichment()
    
    try:
        input_file = "data/processed/expand/politicians_data_normalized.json"
        logger.info(f"Input file: {input_file}")
        
        enricher.run_enrichment(
            input_file=input_file,
            # limit=1,
            skip=0
        )
        logger.info("Enrichment completed successfully")
        
    except Exception as e:
        logger.error(f"Enrichment failed with error: {e}")
        raise
    finally:
        enricher.close()
        logger.info("Neo4j connection closed")
