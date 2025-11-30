"""
python merge_extractions.py -t output/tf_entity_extraction.json -m output/mcq_entity_extraction.json -o output/merged_tf_mcq.json
"""
from __future__ import annotations
import argparse
import json
import os
import re
from typing import List, Dict, Any, Optional


def robust_load_json(path: str) -> List[Dict[str, Any]]:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    try:
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError('Expected JSON array')
        return data
    except Exception:
        # Attempt to fix common trailing comma issues
        cleaned = re.sub(r',\s*([\]\}])', r'\1', text)
        cleaned = cleaned.strip()
        try:
            data = json.loads(cleaned)
            if not isinstance(data, list):
                raise ValueError('Expected JSON array after cleanup')
            return data
        except Exception as e:
            raise RuntimeError(f"Failed to parse JSON file {path}: {e}")


def write_json(path: str, arr: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(arr, f, ensure_ascii=False, indent=2)


def find_file_in_dir(directory: str, base_names: List[str], prefer_clean: bool = True) -> Optional[str]:
    """Find a file in directory by base names. Prefer *_cleaned.json if available."""
    candidates = os.listdir(directory)
    for base in base_names:
        cleaned_name = f"{base}_cleaned.json"
        normal_name = f"{base}.json"
        if prefer_clean and cleaned_name in candidates:
            return os.path.join(directory, cleaned_name)
        if normal_name in candidates:
            return os.path.join(directory, normal_name)
    return None


def remove_id_field(arr: List[Dict[str, Any]]) -> int:
    removed = 0
    for rec in arr:
        if isinstance(rec, dict) and 'id' in rec:
            try:
                del rec['id']
                removed += 1
            except Exception:
                pass
    return removed


def main(argv=None):
    parser = argparse.ArgumentParser(description='Merge TF and MCQ extraction JSON files (TF first)')
    parser.add_argument('-t', '--tf', help='TF JSON file path (optional)')
    parser.add_argument('-m', '--mcq', help='MCQ JSON file path (optional)')
    parser.add_argument('-d', '--dir', help='Directory containing tf/mcq files; used when -t/-m not provided')
    parser.add_argument('-o', '--out', default='output/merged_extraction.json', help='Output merged JSON file')
    parser.add_argument('--prefer-clean', action='store_true', help='Prefer *_cleaned.json files when finding inputs')
    parser.add_argument('--remove-id', action='store_true', help='Remove `id` fields from records in the merged file')
    args = parser.parse_args(argv)

    tf_path = args.tf
    mcq_path = args.mcq

    if args.dir:
        # If explicit paths are not provided, try to find files in directory
        if not tf_path:
            tf_path = find_file_in_dir(args.dir, ['tf_entity_extraction', 'tf_entity_extraction'], prefer_clean=args.prefer_clean)
        if not mcq_path:
            mcq_path = find_file_in_dir(args.dir, ['mcq_entity_extraction', 'mcq_entity_extraction'], prefer_clean=args.prefer_clean)

    if not tf_path or not mcq_path:
        parser.error('TF and MCQ file paths must be provided either via -t/-m or with -d directory containing them')

    print(f"Loading TF file: {tf_path}")
    tf_arr = robust_load_json(tf_path)
    print(f"  TF records: {len(tf_arr)}")

    print(f"Loading MCQ file: {mcq_path}")
    mcq_arr = robust_load_json(mcq_path)
    print(f"  MCQ records: {len(mcq_arr)}")

    merged = tf_arr + mcq_arr

    removed_ids = 0
    if args.remove_id:
        removed_ids = remove_id_field(merged)
        print(f"Removed `id` from {removed_ids} records")

    print(f"Writing merged file: {args.out} (total {len(merged)} records)")
    write_json(args.out, merged)
    print("Done")


if __name__ == '__main__':
    main()
