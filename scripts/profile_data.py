#!/usr/bin/env python3
import json, sys
from collections import Counter

def find_records(data):
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data, None, {}
    if isinstance(data, dict):
        for key in ["features"] + [k for k in data if k != "features"]:
            val = data.get(key)
            if isinstance(val, list) and val and isinstance(val[0], dict):
                return val, key, {k: 1 for k in data if k != key}
        if all(isinstance(v, (list, dict)) for v in data.values()):
            return data, None, {}
    return [], None, {}

def get_paths(records, prefix="", depth=0):
    if depth > 10:
        return
    if isinstance(records, dict) and not any(isinstance(v, dict)
        for v in records.values()):
        for k, v in records.items():
            if not isinstance(v, dict):
                yield (k if not prefix else f"{prefix}.{k}", [v])
        return
    for record in (records.values() if isinstance(records, dict) else records):
        if not isinstance(record, dict):
            continue
        for k, v in record.items():
            path = k if not prefix else f"{prefix}.{k}"
            if isinstance(v, list):
                if v and isinstance(v[0], dict):
                    for item in v:
                        yield from get_paths([item], f"{path}[]")
                else:
                    for i, item in enumerate(v[:4]):
                        yield f"{path}[{i}]", [item]
            elif isinstance(v, dict):
                yield from get_paths([v], path)
            else:
                yield path, [v]

def analyze_path(values):
    valid = [v for v in values if v is not None]
    nulls, types = len(values) - len(valid), {}
    for v in valid:
        t = "int" if isinstance(v, bool) else type(v).__name__
        types[t] = types.get(t, 0) + 1
    types = ", ".join(sorted(types.keys())) or "null"
    example = next((str(v)[:40] if isinstance(v, str) else v
        for v in values if v is not None), "")
    nums = [v for v in valid if isinstance(v, (int, float))
        and not isinstance(v, bool)]
    mn, mx = (min(nums), max(nums)) if nums else (None, None)
    strs = [v for v in valid if isinstance(v, str)]
    dist = len(set(strs[:1000])) if strs else None
    return types, len(values), nulls, mn, mx, dist, example

def is_timestamp(v):
    if isinstance(v, str) and len(v) > 10 and v[:4].isdigit():
        return v[4] == "-" and v[5:7].isdigit()
    return isinstance(v, int) and v > 1e9

def profile_file(fpath):
    try:
        with open(fpath) as f:
            data = json.load(f, object_pairs_hook=dict)
    except (OSError, json.JSONDecodeError) as e:
        print(f"## {fpath}\n{type(e).__name__}: {e}\n")
        return

    records, key, other_keys = find_records(data)
    if not records:
        print(f"## {fpath}\nNo records found\n")
        return

    print(f"## {fpath}")
    if isinstance(records, dict):
        n_items = sum(len(v) if isinstance(v, list) else 1
            for v in records.values())
        rec_str = f"top-level map ({len(records)} keys, {n_items} items)"
    elif key:
        rec_str = f'"{key}" (list, {len(records)} items)'
    else:
        rec_str = f"top level: list; {len(records)} items"

    other_list = list(other_keys.keys())[:10]
    other_str = ", ".join(other_list)
    if len(other_keys) > 10:
        other_str += f", ({len(other_keys) - 10} more)"
    print(f"- top level: object; records: {rec_str}; other keys:" +
        (f" {other_str}" if other_str else " none"))

    paths = {}
    for path, vals in get_paths(records):
        if path not in paths:
            paths[path] = []
        paths[path].extend(vals)

    print("\n| path | types | n | nulls | min | max | distinct | example |")
    print("|------|-------|---|-------|-----|-----|----------|---------|")
    for path in sorted(paths.keys()):
        types, n, nulls, mn, mx, dist, ex = analyze_path(paths[path])
        m, x, d = ("" if mn is None else str(mn)), ("" if mx is None else
            str(mx)), ("" if dist is None else str(dist))
        print(f"| {path} | {types} | {n} | {nulls} | {m} | {x} | {d} | {ex} |")

    repeats = []
    for path in paths:
        if "." not in path and "[]" not in path:
            vals = [v for v in paths[path] if v is not None]
            if not vals:
                continue
            distinct = len(set(str(v) for v in vals))
            is_id_field = path == "id" or path.endswith("_id")
            high_distinct = distinct >= 0.9 * len(vals)
            if is_id_field or high_distinct:
                counter = Counter(str(v) for v in vals)
                repeats.extend(f"{path} {v} x{c}" for v, c in
                    counter.most_common() if c > 1)
    print(f"- repeated keys: {' '.join(repeats) if repeats else 'none'}")

    for path in sorted(paths.keys()):
        ts_vals = [v for v in paths[path] if is_timestamp(v)]
        if ts_vals:
            forms = Counter()
            for v in ts_vals:
                if isinstance(v, str):
                    if "Z" in v:
                        forms["Z"] += 1
                    elif "+" in v or v.count("-") > 2:
                        forms["±HH:MM"] += 1
                    else:
                        forms["no offset"] += 1
                elif v >= 2e10:
                    forms["epoch ms"] += 1
                else:
                    forms["epoch s"] += 1
            print(f"- timestamp forms: {path}: " +
                " ".join(f"{k} {forms[k]}" for k in sorted(forms)))
    print()

def main():
    for fpath in sys.argv[1:]:
        profile_file(fpath)

if __name__ == "__main__":
    main()
