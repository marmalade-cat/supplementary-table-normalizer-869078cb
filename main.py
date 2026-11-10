#!/usr/bin/env python3
"""
Minimal supplementary-table-normalizer prototype.
Scans a local folder for .csv/.tsv/.json files, parses them, applies simple heuristics
to map columns to a small module schema (poses, edges, sequences), validates basic fields,
and prints a JSON report.

This is intentionally small and dependency-free.
"""
import sys, os, csv, json
from typing import List, Dict, Any

def find_files(folder: str) -> List[str]:
    exts = ('.csv', '.tsv', '.json')
    files = []
    for entry in os.listdir(folder):
        low = entry.lower()
        if low.endswith(exts):
            files.append(os.path.join(folder, entry))
    return files

def load_file(path: str) -> Any:
    if path.lower().endswith('.json'):
        with open(path, 'r', encoding='utf8') as f:
            try:
                return json.load(f)
            except Exception as e:
                return {'_error': f'json parse error: {e}'}
    else:
        delim = '\t' if path.lower().endswith('.tsv') else ','
        rows = []
        with open(path, 'r', encoding='utf8', errors='replace') as f:
            reader = csv.DictReader(f, delimiter=delim)
            for r in reader:
                rows.append(r)
        return rows

# Heuristics
POSE_KEYS = {'x','y','z','yaw','pitch','roll','id','name'}
EDGE_KEYS = {'source','target','from','to','weight','type'}
SEQ_KEYS = {'time','t','step','module','action'}

def guess_table_type(rows_or_obj) -> str:
    # JSON objects containing top-level keys may already be structured
    if isinstance(rows_or_obj, dict):
        keys = set(rows_or_obj.keys())
        if {'poses','edges','sequences'} & keys:
            return 'structured'
        # fallback to content inspection
        # If values look like lists of dicts, decide by contained keys
        list_vals = [v for v in rows_or_obj.values() if isinstance(v, list) and v]
        if list_vals:
            sample = list_vals[0]
            if isinstance(sample, dict):
                k = set(sample.keys())
                if k & POSE_KEYS:
                    return 'poses'
    if isinstance(rows_or_obj, list):
        if not rows_or_obj:
            return 'unknown'
        sample_keys = set(k.lower() for k in rows_or_obj[0].keys())
        if sample_keys & POSE_KEYS:
            return 'poses'
        if sample_keys & EDGE_KEYS:
            return 'edges'
        if sample_keys & SEQ_KEYS:
            return 'sequences'
    return 'unknown'

def normalize_poses(rows: List[Dict[str,str]]) -> List[Dict[str,Any]]:
    out = []
    for r in rows:
        low = {k.lower(): v for k,v in r.items()}
        idv = low.get('id') or low.get('name') or low.get('module')
        try:
            x = float(low.get('x')) if 'x' in low and low.get('x')!='' else None
            y = float(low.get('y')) if 'y' in low and low.get('y')!='' else None
            z = float(low.get('z')) if 'z' in low and low.get('z')!='' else None
        except ValueError:
            x=y=z=None
        pose = {'id': idv, 'x': x, 'y': y}
        if z is not None:
            pose['z']=z
        for ang in ('yaw','pitch','roll'):
            if ang in low and low[ang] != '':
                try:
                    pose[ang]=float(low[ang])
                except ValueError:
                    pass
        out.append(pose)
    return out

def normalize_edges(rows: List[Dict[str,str]]) -> List[Dict[str,Any]]:
    out=[]
    for r in rows:
        low={k.lower():v for k,v in r.items()}
        s = low.get('source') or low.get('from') or low.get('a')
        t = low.get('target') or low.get('to') or low.get('b')
        if not (s and t):
            continue
        e={'source':s,'target':t}
        if 'type' in low and low['type']!='':
            e['type']=low['type']
        out.append(e)
    return out

def normalize_sequences(rows: List[Dict[str,str]]) -> List[Dict[str,Any]]:
    # group by sequence id if present, else create a single sequence
    grouped = {}
    for r in rows:
        low={k.lower():v for k,v in r.items()}
        seqid = low.get('sequence') or low.get('id') or 'default'
        step = {}
        if 'time' in low:
            try:
                step['time']=float(low['time'])
            except Exception:
                pass
        if 'module' in low:
            step['module']=low['module']
        elif 'step' in low:
            step['module']=low['step']
        grouped.setdefault(seqid,[]).append(step)
    out=[]
    for k,v in grouped.items():
        out.append({'id':k,'steps':v})
    return out

def process_file(path: str) -> Dict[str,Any]:
    loaded = load_file(path)
    kind = guess_table_type(loaded)
    normalized = {}
    problems = []
    if kind=='structured' and isinstance(loaded, dict):
        # trust simple structure but validate lists
        for key in ('poses','edges','sequences'):
            if key in loaded and isinstance(loaded[key], list):
                normalized[key]=loaded[key]
    elif kind=='poses' and isinstance(loaded, list):
        normalized['poses']=normalize_poses(loaded)
    elif kind=='edges' and isinstance(loaded, list):
        normalized['edges']=normalize_edges(loaded)
    elif kind=='sequences' and isinstance(loaded, list):
        normalized['sequences']=normalize_sequences(loaded)
    else:
        problems.append('could not classify file content')
    # simple validation
    for p in normalized.get('poses',[]):
        if not p.get('id'):
            problems.append('pose missing id')
    for e in normalized.get('edges',[]):
        if not (e.get('source') and e.get('target')):
            problems.append('edge missing endpoints')
    return {'path': path, 'kind': kind, 'normalized': normalized, 'problems': list(set(problems))}

def summarize(results: List[Dict[str,Any]]) -> Dict[str,Any]:
    s={'files': len(results), 'poses':0,'edges':0,'sequences':0,'files_with_problems':0}
    for r in results:
        s['poses'] += len(r['normalized'].get('poses',[]))
        s['edges'] += len(r['normalized'].get('edges',[]))
        s['sequences'] += len(r['normalized'].get('sequences',[]))
        if r['problems']:
            s['files_with_problems'] += 1
    return s

def main(argv):
    if len(argv)<2:
        print('Usage: python main.py /path/to/folder')
        return 1
    folder = argv[1]
    if not os.path.isdir(folder):
        print('Not a folder:', folder)
        return 2
    files = find_files(folder)
    print(f'Found {len(files)} candidate files in', folder)
    results=[]
    for f in files:
        r = process_file(f)
        results.append(r)
    report = {'summary': summarize(results), 'files': results}
    print(json.dumps(report, indent=2))
    return 0

if __name__=='__main__':
    sys.exit(main(sys.argv))
