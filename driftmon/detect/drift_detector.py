import json
import mmap
from collections import defaultdict

import numpy as np
from scipy.stats import chi2_contingency, norm
from statsmodels.stats.proportion import proportions_ztest


def _get_latest_two_hashes(file_path, table_names):
    """
    Retrieve the latest two hash entries for each table in table_names
    from a newline-delimited JSON file.

    Args:
        file_path (str): Path to the hash history file.
        table_names (List[str]): List of table names to search for.

    Returns:
        dict: Mapping of table name to a tuple (latest_hash, previous_hash).
    """
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


def _detect_drift_in_history(file_path: str, alpha: float = 0.05, base_psi: float = 0.20):
    """
    Detects data drift in the monitoring history file for all tables.

    Args:
        file_path (str): Path to the monitoring history file.
        alpha (float): Significance level for statistical tests (default 0.05).
        base_psi (float): Threshold for Population Stability Index (default 0.20).

    Returns:
        dict: Drift report for each table, including column-level drift details.
    """
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


def _resolve_table_names(file_path, user_tables):
    """
    Resolves user-provided table names to their full names as found in the monitoring history file.

    Args:
        file_path (str): Path to the monitoring history file.
        user_tables (Union[str, List[str]]): Table names to resolve.

    Returns:
        list: List of resolved full table names.
    """
    if isinstance(user_tables, str):
        user_tables = [user_tables]

    mapping = {}
    with open(file_path, "r") as f:
        for line in f:
            records = json.loads(line)
            full_name = records.get("table_name")
            if not full_name:
                continue
            simple_name = full_name.split(".")[-1]
            mapping.setdefault(simple_name, set()).add(full_name)
            mapping.setdefault(full_name, set()).add(full_name)

    resolved = set()
    for name in user_tables:
        if name in mapping:
            resolved.update(mapping[name])
        else:
            print(f"Warning: Table '{name}' not found in monitoring history.")
    return list(resolved)


def detect_drift(
    table_names: str,
    alpha=0.05,
    base_psi: float = 0.20,
    file_path: str = "monitoring_history.jsonl",
):
    """
    Runs data drift detection for the specified tables using the monitoring history file.

    Args:
        file_path (str): Path to the monitoring history file.
        table_names (Union[str, List[str]]): Table names to check for drift.
        alpha (float): Significance level for statistical tests (default 0.05).
        base_psi (float): Threshold for Population Stability Index (default 0.20).

    Returns:
        str: Human-readable drift detection summary.
    """
    resolved_table_names = _resolve_table_names(file_path, table_names)
    if not resolved_table_names:
        return "No matching tables found in monitoring history."

    hashes = _get_latest_two_hashes(file_path, resolved_table_names)
    tables_with_change = {t for t, (latest, prev) in hashes.items() if latest != prev}
    tables_without_change = set(resolved_table_names) - tables_with_change

    print(f"🔍Running data drift detection............")
    print(f"   Tables with hash changes: {len(tables_with_change)}")
    print(f"   Tables without hash changes: {len(tables_without_change)}")

    drift_report = _detect_drift_in_history(file_path, alpha, base_psi)

    messages = []
    if tables_without_change:
        bullet = "\n   • ".join(sorted(tables_without_change))
        messages.append(f"✅ No hash changes detected in:\n   • {bullet}\n   ✨ No drift likely.\n")

    if tables_with_change:
        drift_summary = {}
        for table in tables_with_change:
            if table in drift_report:
                report = drift_report[table]
                columns = report.get("columns", {})
                drift_summary[table] = {
                    "drifted": [
                        col
                        for col, val in columns.items()
                        if isinstance(val, dict) and val.get("drift")
                    ],
                    "disappeared": [
                        col for col, val in columns.items() if val == "disappeared_column"
                    ],
                    "new_cols": [col for col, val in columns.items() if val == "new_column"],
                    "bin_mismatch": [col for col, val in columns.items() if val == "bin_mismatch"],
                }
            else:
                drift_summary[table] = {
                    "drifted": [],
                    "disappeared": [],
                    "new_cols": [],
                    "bin_mismatch": [],
                }

        tables_with_actual_drift = {
            t
            for t, info in drift_summary.items()
            if any([info["drifted"], info["disappeared"], info["new_cols"], info["bin_mismatch"]])
        }
        tables_without_drift = set(drift_summary.keys()) - tables_with_actual_drift

        if tables_without_drift:
            bullet = "\n   • ".join(sorted(tables_without_drift))
            messages.append(
                f"⚠️ Hash changed but no statistical drift detected for:\n   • {bullet} \n"
            )

        for table in tables_with_actual_drift:
            info = drift_summary[table]
            msg = f"🚨 DRIFT in {table}:"
            if info["drifted"]:
                msg += f"\n  - Drifted columns: {info['drifted']}"
            if info["disappeared"]:
                msg += f"\n  - Disappeared columns: {info['disappeared']}"
            if info["new_cols"]:
                msg += f"\n  - New columns: {info['new_cols']}"
            if info["bin_mismatch"]:
                msg += f"\n  - Bin mismatch columns: {info['bin_mismatch']}"
            messages.append(msg)

    return "\n".join(messages) if messages else "No tables to report."
