import json
import mmap


def get_latest_two_hashes(file_path, target_table):
    results = []

    with open(file_path, "rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            position = mm.size()

            while position > 0 and len(results) < 2:
                new_position = mm.rfind(b"\n", 0, position)

                if new_position == -1:
                    line = mm[0:position].strip()
                    position = 0
                else:
                    line = mm[new_position:position].strip()
                    position = new_position

                if not line:
                    continue

                if bytes(target_table, "utf-8") in line:
                    entry = json.loads(line)
                    if entry.get("table_name") == target_table:
                        results.append(entry)

    return results


def apply_algo():
    pass


# Testing the microphone 😂
# history = get_latest_two_hashes('monitoring_history.jsonl', "MARTS_SUPPLYCHAIN.DIM_PRODUCTS")

# if len(history) == 2:
# curr, prev = history[0], history[1]
# if curr['hash'] != prev['hash']:
# print(f"🚨 Drift Detected: {prev['hash']} -> {curr['hash']}")
# else:
# print(f"No changes made 🤗")
