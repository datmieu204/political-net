# SERVED_AS

MATCH (p:Politician)-[r:SERVED_AS]->(pos:Position)
MERGE (e:RelationChunk {rel_id: elementId(r)})
SET e.relation_type = 'SERVED_AS',
    e.source_id = p.id,
    e.target_id = pos.id,
    e.source_label = head(labels(p)),
    e.target_label = head(labels(pos)),
    e.term_start = r.term_start,
    e.term_end   = r.term_end,
    e.status     = r.status,
    e.reason     = r.reason,
    e.text_for_embedding = 
        'Quan hệ SERVED_AS: ' + coalesce(p.name, '') + 
        ' giữ chức ' + coalesce(pos.name, '') + 
        CASE WHEN r.term_start IS NOT NULL AND r.term_start <> '' 
             THEN ' từ ' + r.term_start ELSE '' END +
        CASE WHEN r.term_end IS NOT NULL AND r.term_end <> '' 
             THEN ' đến ' + r.term_end ELSE '' END +
        CASE WHEN r.status IS NOT NULL AND r.status <> '' 
             THEN '. Trạng thái: ' + r.status ELSE '' END +
        CASE WHEN r.reason IS NOT NULL AND r.reason <> ''
             THEN '. Lý do: ' + r.reason ELSE '' END;

# PRECEDED, SUCCEEDED

MATCH (p1:Politician)-[r:PRECEDED]->(p2:Politician)
MERGE (e:RelationChunk {rel_id: elementId(r)})
SET e.relation_type = 'PRECEDED',
    e.source_id = p1.id,
    e.target_id = p2.id,
    e.position_id = r.position_id,
    e.text_for_embedding =
        'Quan hệ PRECEDED: ' + coalesce(p1.name, '') + 
        ' là người tiền nhiệm của ' + coalesce(p2.name, '') +
        CASE WHEN r.position_id IS NOT NULL THEN
          ' trong chức vụ có id ' + r.position_id
        ELSE '' END;

MATCH (p1:Politician)-[r:SUCCEEDED]->(p2:Politician)
MERGE (e:RelationChunk {rel_id: elementId(r)})
SET e.relation_type = 'SUCCEEDED',
    e.source_id = p1.id,
    e.target_id = p2.id,
    e.position_id = r.position_id,
    e.text_for_embedding =
        'Quan hệ SUCCEEDED: ' + coalesce(p1.name, '') + 
        ' là người kế nhiệm của ' + coalesce(p2.name, '') +
        CASE WHEN r.position_id IS NOT NULL THEN
          ' trong chức vụ có id ' + r.position_id
        ELSE '' END;

# BORN_AT, DIED_AT, AWARDED, SERVED_IN, ALUMNUS_OF, HAS_ACADEMIC_TITLE, HAS_RANK, FOUGHT_IN

// BORN_AT
MATCH (p:Politician)-[r:BORN_AT]->(loc:Location)
MERGE (e:RelationChunk {rel_id: elementId(r)})
SET e.relation_type = 'BORN_AT',
    e.source_id = p.id,
    e.target_id = loc.id,
    e.text_for_embedding =
        'Quan hệ BORN_AT: ' + coalesce(p.name, '') +
        ' sinh tại ' + coalesce(loc.name, '');

// DIED_AT
MATCH (p:Politician)-[r:DIED_AT]->(loc:Location)
MERGE (e:RelationChunk {rel_id: elementId(r)})
SET e.relation_type = 'DIED_AT',
    e.source_id = p.id,
    e.target_id = loc.id,
    e.text_for_embedding =
        'Quan hệ DIED_AT: ' + coalesce(p.name, '') +
        ' mất tại ' + coalesce(loc.name, '');

// AWARDED
MATCH (p:Politician)-[r:AWARDED]->(a:Award)
MERGE (e:RelationChunk {rel_id: elementId(r)})
SET e.relation_type = 'AWARDED',
    e.source_id = p.id,
    e.target_id = a.id,
    e.text_for_embedding =
        'Quan hệ AWARDED: ' + coalesce(p.name, '') +
        ' được trao tặng ' + coalesce(a.name, '');

// SERVED_IN
MATCH (p:Politician)-[r:SERVED_IN]->(m:MilitaryCareer)
MERGE (e:RelationChunk {rel_id: elementId(r)})
SET e.relation_type = 'SERVED_IN',
    e.source_id = p.id,
    e.target_id = m.id,
    e.text_for_embedding =
        'Quan hệ SERVED_IN: ' + coalesce(p.name, '') +
        ' phục vụ trong ' + coalesce(m.name, '');

// ALUMNUS_OF
MATCH (p:Politician)-[r:ALUMNUS_OF]->(alm:AlmaMater)
MERGE (e:RelationChunk {rel_id: elementId(r)})
SET e.relation_type = 'ALUMNUS_OF',
    e.source_id = p.id,
    e.target_id = alm.id,
    e.text_for_embedding =
        'Quan hệ ALUMNUS_OF: ' + coalesce(p.name, '') +
        ' từng học tại ' + coalesce(alm.name, '');

// HAS_ACADEMIC_TITLE
MATCH (p:Politician)-[r:HAS_ACADEMIC_TITLE]->(t:AcademicTitle)
MERGE (e:RelationChunk {rel_id: elementId(r)})
SET e.relation_type = 'HAS_ACADEMIC_TITLE',
    e.source_id = p.id,
    e.target_id = t.id,
    e.text_for_embedding =
        'Quan hệ HAS_ACADEMIC_TITLE: ' + coalesce(p.name, '') +
        ' có học hàm/học vị ' + coalesce(t.name, '');

// HAS_RANK
MATCH (p:Politician)-[r:HAS_RANK]->(mr:MilitaryRank)
MERGE (e:RelationChunk {rel_id: elementId(r)})
SET e.relation_type = 'HAS_RANK',
    e.source_id = p.id,
    e.target_id = mr.id,
    e.text_for_embedding =
        'Quan hệ HAS_RANK: ' + coalesce(p.name, '') +
        ' có quân hàm ' + coalesce(mr.name, '');

// FOUGHT_IN
MATCH (p:Politician)-[r:FOUGHT_IN]->(c:Campaigns)
MERGE (e:RelationChunk {rel_id: elementId(r)})
SET e.relation_type = 'FOUGHT_IN',
    e.source_id = p.id,
    e.target_id = c.id,
    e.text_for_embedding =
        'Quan hệ FOUGHT_IN: ' + coalesce(p.name, '') +
        ' tham gia chiến dịch ' + coalesce(c.name, '');
