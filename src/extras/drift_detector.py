import json
import mmap
from scipy import stats

def get_latest_two_hashes(file_path, table_names):
    from collections import defaultdict
    results = defaultdict(list)
    target_set = set(table_names)

    with open(file_path, "rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            position = mm.size()

            while position > 0 and any(len(v) < 2 for v in results.values()) or not results:
                new_position = mm.rfind(b"\n", 0, position)

                if new_position == -1:
                    line = mm[0:position].strip()
                    position = 0
                else:
                    line = mm[new_position:position].strip()
                    position = new_position

                if not line:
                    continue

                entry = json.loads(line)
                table_name = entry.get("table_name")
                if table_name in target_set and len(results[table_name]) < 2:
                    results[table_name].append(entry)

                if all(len(results[table]) == 2 for table in target_set):
                    break

    comparison = {}
    for table, entries in results.items():
        if len(entries) == 2:
            latest_hash = entries[0].get('hash')
            previous_hash = entries[1].get('hash')
            comparison[table] = (latest_hash, previous_hash)

    return comparison

def compare_algorithm():
    file_path = 'monitoring_history.jsonl'
    get_hash_changes = get_latest_two_hashes(file_path, table_names)
    for table in table_names:
        for table, (latest_hash, previous_hash) in get_hash_changes.items():
            if latest_hash != previous_hash:
                return f"🚨 Changes detected !!!"
            else:
                return f"No changes in table {table}"

    table_group = {}
    with open(file_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                table_names = record.get('table_name')
                for col_name, col_metrics in record["metrics"].items():
                    detected_type = col_metrics.get("detected_type")
                    table_group[(table_names, col_name)] = detected_type
            except json.JSONDecodeError as e:
                    print(f"JSON decode error on line {line_num}: {e}")
        return table_group
