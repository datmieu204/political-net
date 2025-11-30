"""
python chatbot/entity_identification/clean_extractions.py -d chatbot/entity_identification/output --inplace
"""
from __future__ import annotations
import argparse
import json
import os
from typing import List, Dict, Any, Tuple

ALLOWED_ENTITY_TYPES = {
    "Politician", "Position", "Location", "Award",
    "MilitaryCareer", "MilitaryRank", "AcademicTitle", "AlmaMater",
    "Campaigns", "TermPeriod"
}

ALLOWED_RELATION_TYPES = {
    "PRECEDED", "SUCCEEDED", "BORN_AT", "DIED_AT", "SERVED_AS",
    "ALUMNUS_OF", "HAS_RANK", "HAS_ACADEMIC_TITLE", "AWARDED",
    "SERVED_IN", "FOUGHT_IN"
}


def clean_records(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Return cleaned records and a simple stats dict."""
    stats = {
        "total_records": 0,
        "entities_total": 0,
        "entities_removed": 0,
        "ids_removed": 0,
        "relations_total": 0,
        "relations_removed": 0,
        "records_modified": 0,
    }

    cleaned = []
    for rec in records:
        stats["total_records"] += 1
        modified = False

        answer = rec.get("answer_json") if isinstance(rec, dict) else None
        if not isinstance(answer, dict):
            cleaned.append(rec)
            continue

        # Entities: expect a list of dicts with 'type'
        entities = answer.get("entities") if isinstance(answer.get("entities"), list) else []
        stats["entities_total"] += len(entities)
        kept_entities = []
        for ent in entities:
            # ent can be a dict or something else; be defensive
            if isinstance(ent, dict):
                ent_type = ent.get("type")
                if isinstance(ent_type, str) and ent_type in ALLOWED_ENTITY_TYPES:
                    kept_entities.append(ent)
                else:
                    stats["entities_removed"] += 1
                    modified = True
            else:
                # non-dict entity -> drop it
                stats["entities_removed"] += 1
                modified = True

        # Relations: many outputs store them under 'intent_relation' as list of strings
        relations = answer.get("intent_relation") if isinstance(answer.get("intent_relation"), list) else []
        stats["relations_total"] += len(relations)
        kept_relations = []
        for rel in relations:
            if isinstance(rel, str) and rel in ALLOWED_RELATION_TYPES:
                kept_relations.append(rel)
            else:
                stats["relations_removed"] += 1
                modified = True


        # Remove 'id' field if present (user requested)
        if isinstance(rec, dict) and 'id' in rec:
            try:
                del rec['id']
                stats['ids_removed'] += 1
                modified = True
            except Exception:
                pass

        # Update the record's answer_json with cleaned lists
        if modified:
            stats["records_modified"] += 1

        # Always set the cleaned lists (so structure stays consistent)
        answer["entities"] = kept_entities
        answer["intent_relation"] = kept_relations

        # Optionally remove other unexpected fields? We keep them.
        cleaned.append(rec)

    return cleaned, stats


def load_json_file(path: str) -> List[Dict[str, Any]]:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected JSON array in {path}")
        return data


def write_json_file(path: str, data: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_json_files_in_dir(directory: str) -> List[str]:
    files = []
    for entry in os.listdir(directory):
        if entry.lower().endswith('.json'):
            files.append(os.path.join(directory, entry))
    return files


def process_file(path: str, inplace: bool = False, report: Dict[str, Any] | None = None) -> Dict[str, Any]:
    print(f"Processing: {path}")
    records = load_json_file(path)
    cleaned, stats = clean_records(records)

    base, ext = os.path.splitext(path)
    out_path = path if inplace else f"{base}_cleaned{ext}"
    write_json_file(out_path, cleaned)

    print(f"  Wrote cleaned file: {out_path}")
    print(f"  Records: {stats['total_records']}, modified: {stats['records_modified']}")
    print(f"  Entities removed: {stats['entities_removed']}/{stats['entities_total']}")
    print(f"  Relations removed: {stats['relations_removed']}/{stats['relations_total']}")

    result = {
        "input": path,
        "output": out_path,
        "stats": stats
    }

    if report is not None:
        report[path] = result

    return result


def main(argv: List[str] | None = None):
    parser = argparse.ArgumentParser(description="Clean entity extraction JSON files")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--input', help='Input JSON file to clean')
    group.add_argument('-d', '--dir', help='Directory containing JSON files to clean')
    parser.add_argument('--inplace', action='store_true', help='Overwrite input files instead of writing _cleaned copies')
    parser.add_argument('--report', help='Write a JSON report of changes to this file')

    args = parser.parse_args(argv)

    targets = []
    if args.input:
        targets = [args.input]
    else:
        targets = find_json_files_in_dir(args.dir)
        if not targets:
            print(f"No JSON files found in directory: {args.dir}")
            return

    report_data: Dict[str, Any] = {}
    for p in targets:
        try:
            process_file(p, inplace=args.inplace, report=report_data)
        except Exception as e:
            print(f"Error processing {p}: {e}")

    if args.report:
        write_json_file(args.report, report_data)
        print(f"Report written to {args.report}")


if __name__ == '__main__':
    main()
