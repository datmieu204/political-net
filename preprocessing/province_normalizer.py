# ./preprocessing/province_normalizer.py

import argparse
import json
import re
from collections import defaultdict
from typing import Dict, Any, List

from utils.config import settings
from utils.external import PROVINCES
from utils.queue_based_async_logger import get_async_logger

log = get_async_logger("province_normalizer", log_file="logs/preprocessing/province_normalizer.log")

FIELDS = ["birth_place", "hometown", "residence"]

_PROVINCE_KEYS_LOWER: List[str] = list(PROVINCES.keys())
_PROVINCE_KEYS_LOWER = [k.lower() for k in _PROVINCE_KEYS_LOWER]

def clean_wiki_markup(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    t = text
    t = re.sub(r'\{\{[^}]+\}\}', '', t)
    t = re.sub(r'<ref[^>]*>.*?</ref>', '', t, flags=re.DOTALL)
    t = re.sub(r'<ref[^>]*/?>', '', t)
    t = re.sub(r'\[\[(?:Tập[_ ]?tin|File|Image|Hình):[^\]]+\]\]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'https?://[^\s\]]+', '', t, flags=re.IGNORECASE)

    def _replace_wikilink(m):
        s = m.group(1)
        if '|' in s:
            return s.split('|')[-1].strip()
        return s.strip()

    t = re.sub(r'\[\[([^\]]+)\]\]', _replace_wikilink, t)
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'<br\s*/?>', ' ', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+', ' ', t).strip()
    t = t.replace("''", '').replace('||', '')
    return t


def extract_province_from_location(location: str) -> str:
    if not location or not isinstance(location, str):
        return ""

    loc = clean_wiki_markup(location)
    if not loc:
        return ""

    for key, canonical in PROVINCES.items():
        pattern = r'\b' + re.escape(key) + r'\b'
        if re.search(pattern, loc, flags=re.IGNORECASE):
            return canonical

    m = re.search(r'tỉnh\s+([^,;\n]+)', loc, flags=re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        for key, canonical in PROVINCES.items():
            if key.lower() in candidate.lower() or candidate.lower() in key.lower():
                return canonical

    m = re.search(r'thành\s+phố\s+([^,;\n]+)', loc, flags=re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        for key, canonical in PROVINCES.items():
            if key.lower() in candidate.lower() or candidate.lower() in key.lower():
                return canonical

    m = re.search(r'\bTP\.?\s+([^,;\n]+)', loc, flags=re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        for key, canonical in PROVINCES.items():
            if key.lower() in candidate.lower() or candidate.lower() in key.lower():
                return canonical

    for key in PROVINCES.keys():
        if key.lower() in loc.lower():
            return PROVINCES[key]

    return ""

def normalize_record(record: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    rec = dict(record)
    infobox = rec.get('infobox')
    if not isinstance(infobox, dict):
        return rec

    infobox_copy = dict(infobox)
    stats = defaultdict(int)

    for field in fields:
        if field in infobox_copy and isinstance(infobox_copy[field], str):
            orig = infobox_copy[field]
            prov = extract_province_from_location(orig)
            if prov:
                infobox_copy[field] = prov
                stats['normalized'] += 1
            else:
                stats['not_found'] += 1

    rec['infobox'] = infobox_copy
    return rec, stats

def process_file(input_path: str, output_path: str, fields: List[str]):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total = len(data)
    norm_count = 0
    not_found = 0

    out = []
    for rec in data:
        new_rec, stats = normalize_record(rec, fields)
        out.append(new_rec)
        norm_count += stats.get('normalized', 0)
        not_found += stats.get('not_found', 0)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    log.info(f"Processed {total} records")
    log.info(f"Fields normalized (successful): {norm_count}")
    log.info(f"Fields not found/unmatched: {not_found}")

if __name__ == '__main__':
    process_file(settings.INPUT_PROVINCE_NORMALIZED_FILE, settings.OUTPUT_PROVINCE_NORMALIZED_FILE, FIELDS)