import json
import mmap
from collections import defaultdict

import numpy as np
from scipy.stats import chi2_contingency, norm
from statsmodels.stats.proportion import proportions_ztest


def get_latest_two_hashes(file_path, table_names):
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
            latest_hash = entries[0].get("hash")
            previous_hash = entries[1].get("hash")
            comparison[table] = (latest_hash, previous_hash)

    return comparison


def detect_drift_in_history(file_path: str, alpha: float = 0.05, base_psi: float = 0.20):

    table_entries = defaultdict(list)

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            table_entries[record["table_name"]].append(record)

    drift_report = {}

    for table_name, entries in table_entries.items():
        if len(entries) < 2:
            drift_report[table_name] = {"error": "only_one_entry"}
            continue

        current = entries[-1]
        previous = entries[-2]

        if current.get("hash") == previous.get("hash"):
            drift_report[table_name] = {"hash_match": True, "drift": False}
            continue

        drift_report[table_name] = {"hash_match": False, "columns": {}}
        all_cols = set(previous["metrics"].keys()) | set(current["metrics"].keys())

        for col in all_cols:
            if col not in previous["metrics"]:
                drift_report[table_name]["columns"][col] = "new_column"
                continue
            if col not in current["metrics"]:
                drift_report[table_name]["columns"][col] = "disappeared_column"
                continue

            prev = previous["metrics"][col]
            cur = current["metrics"][col]
            dtype = prev.get("detected_type", "unknown")

            if dtype == "numerical":
                expected = prev.get("expected_percents", [])
                actual = cur.get("expected_percents", [])

                if not expected or not actual or len(expected) != len(actual):
                    drift_report[table_name]["columns"][col] = "bin_mismatch"
                    continue

                psi_val = sum(
                    (a - e) * np.log((a + 1e-4) / (e + 1e-4)) for e, a in zip(expected, actual)
                )
                drift_report[table_name]["columns"][col] = {
                    "drift": psi_val >= base_psi,
                    "score": round(psi_val, 4),
                    "method": "PSI",
                }

            elif dtype == "date":
                prev_max = prev.get("max", 0)
                cur_max = cur.get("max", 0)
                if prev_max == 0 or cur_max == 0:
                    drift_report[table_name]["columns"][col] = "insufficient_data/zero_epoch_time"
                    is_drift = True
                    continue

                NANO_PER_DAY = 864000
                day_diff = (cur_max - prev_max) / NANO_PER_DAY

                status = "consistent"
                is_drift = False
                if day_diff < 0:
                    status, is_drift = "backfilled_or_stale", True
                elif day_diff > 3:
                    status, is_drift = "large_data_gap", True

                drift_report[table_name]["columns"][col] = {
                    "drift": is_drift,
                    "status": status,
                    "days_diff": round(day_diff, 2),
                }

            elif dtype.startswith("categorical"):
                prev_counts = prev.get("full_counts", {})
                cur_counts = cur.get("full_counts", {})

                all_cats = list(set(prev_counts.keys()) | set(cur_counts.keys()))
                p_total, q_total = sum(prev_counts.values()), sum(cur_counts.values())

                if p_total == 0 or q_total == 0:
                    drift_report[table_name]["columns"][col] = "zero_count"
                    continue

                p_arr = np.array([prev_counts.get(c, 0) / p_total for c in all_cats])
                q_arr = np.array([cur_counts.get(c, 0) / q_total for c in all_cats])
                psi_score = np.sum((q_arr - p_arr) * np.log((q_arr + 1e-4) / (p_arr + 1e-4)))

                if dtype == "categorical":
                    raw_p = [prev_counts.get(c, 0) for c in all_cats]
                    raw_q = [cur_counts.get(c, 0) for c in all_cats]
                    _, p_val, _, _ = chi2_contingency([raw_p, raw_q])
                    is_drift = bool(p_val < alpha)
                    method = "Pearson Chi-Square"
                    score = float(p_val)
                else:
                    is_drift = bool(psi_score > base_psi)
                    method = "PSI"
                    score = round(float(psi_score), 4)

                drift_report[table_name]["columns"][col] = {
                    "drift": is_drift,
                    "score": score,
                    "method": method,
                }

            elif dtype == "unstructured_text":
                pre_mu = prev.get("avg_character_length", 0)
                pre_std = prev.get("std_character_length", 1)
                cur_mu = cur.get("avg_character_length", 0)
                n = cur.get("count", 1)

                if pre_std > 0:
                    z_score = (cur_mu - pre_mu) / (pre_std / np.sqrt(n))
                    p_val = 2 * (1 - norm.cdf(abs(z_score)))
                    len_drift = p_val < alpha
                else:
                    len_drift = abs(cur_mu - pre_mu) > (pre_mu * 0.2)
                    p_val = "N/A"

                pre_ur = prev.get("uniqueness_ratio", 0)
                cur_ur = cur.get("uniqueness_ratio", 0)
                ur_drift = abs(cur_ur - pre_ur) > 0.1

                drift_report[table_name]["columns"][col] = {
                    "drift": bool(len_drift or ur_drift),
                    "method": "Z-Test+Uniqueness",
                    "p_val": p_val,
                    "uniqueness_delta": round(cur_ur - pre_ur, 4),
                }

            elif dtype == "bool":
                pre_t, pre_n = prev.get("count_true", 0), prev.get("count", 0)
                cur_t, cur_n = cur.get("count_true", 0), cur.get("count", 0)

                if pre_n == 0 or cur_n == 0:
                    drift_report[table_name]["columns"][col] = "zero_total"
                    continue

                _, p_val = proportions_ztest([pre_t, cur_t], [pre_n, cur_n])
                drift_report[table_name]["columns"][col] = {
                    "drift": p_val < alpha,
                    "p_val": round(p_val, 4),
                    "method": "Prop-Z-Test",
                }

            else:
                drift_report[table_name]["columns"][col] = "unknown_type"

    return drift_report


def check_and_alert(file_path, table_names, alpha=0.05):
    hashes = get_latest_two_hashes(file_path, table_names)
    tables_with_change = [t for t, (latest, prev) in hashes.items() if latest != prev]

    if not tables_with_change:
        return "✅ No hash changes. No drift likely."

    print(
        f"🔍 Hash changes detected for {tables_with_change}.Running statistical drift detection...."
    )

    drift_report = detect_drift_in_history(file_path, alpha)
    messages = []

    for table, report in drift_report.items():
        if table not in tables_with_change:
            continue
        if report.get("hash_match"):
            continue

        columns = report.get("columns", {})
        drifted = [
            col
            for col, val in columns.items()
            if isinstance(val, dict) and val.get("drift") is True
        ]
        disappeared = [col for col, val in columns.items() if val == "disappeared_column"]
        new_cols = [col for col, val in columns.items() if val == "new_column"]
        bin_mismatch = [col for col, val in columns.items() if val == "bin_mismatch"]

        if drifted or disappeared or new_cols or bin_mismatch:
            msg = f"🚨 DRIFT in {table}:"
            if drifted:
                msg += f"\n  - Drifted columns: {drifted}"
            if disappeared:
                msg += f"\n  - Disappeared columns: {disappeared}"
            if new_cols:
                msg += f"\n  - New columns: {new_cols}"
            if bin_mismatch:
                msg += f"\n  - Bin mismatch columns: {bin_mismatch}"
            messages.append(msg)
        else:
            messages.append(
                f"✅Hash changed for {table} but no statistical drift detected(maybe minor changes)"
            )

    return "\n".join(messages) if messages else None


check = check_and_alert("monitoring_history.jsonl", ["public.drivers_raw"])
print(check)
