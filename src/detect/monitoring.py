import datetime
import json
import os
from typing import List, Literal, Optional

from src.detect.profiler import SummaryStats


def save_profile(
    conn_type: Literal["postgres", "snowflake", "mysql", "bigquery"],
    connector,
    conn,
    output_file: str = "monitoring_history.jsonl",
    table_names: Optional[List[str]] = None,
    schema: Optional[str] = None,
    schemas: Optional[List[str]] = None,
    datasets: Optional[List[str]] = None,
):
    """
    Profiles tables from a database connection and saves the results to a monitoring history file.

    For each table, computes a hash and summary statistics for each column group (numerical, text, date, boolean).
    Supports BigQuery, Snowflake, Postgres, and MySQL. Appends results as JSON lines to 
    the specified output file.

    Args:
        conn_type (Literal): Type of database connection ("postgres", "snowflake", "mysql", "bigquery").
        connector: Database connector object with required methods.
        conn: Active database connection/client.
        output_file (str): Path to the output monitoring history file (default: "monitoring_history.jsonl").
        table_names (Optional[List[str]]): List of table names to profile.
        schema (Optional[str]): Schema name (for Postgres/MySQL).
        schemas (Optional[List[str]]): List of schemas (for Snowflake).
        datasets (Optional[List[str]]): List of datasets (for BigQuery).

    Returns:
        str: Status message indicating success or failure.
    """
    reports = []

    if table_names:
        table_names = [t for t in table_names if t]
    if datasets:
        datasets = [d for d in datasets if d]
    if schemas:
        schemas = [s for s in schemas if s]

    if not table_names:
        return "⚠️ No table names provided."

    if conn_type == "bigquery":
        if not datasets:
            return "⚠️ No datasets provided for BigQuery."

        dataset_location_cache = {}
        for dataset in datasets:
            if dataset not in dataset_location_cache:
                location = connector.get_dataset_location(conn, dataset)
                dataset_location_cache[dataset] = location or "US"

            resolved_location = dataset_location_cache[dataset]
            hashes = connector.get_table_hashes(
                conn, datasets=[dataset], table_names=table_names, location=resolved_location
            )

            for table in table_names:
                h_key = (dataset, table)

                if h_key not in hashes:
                    continue

                table_id = f"{conn.project}.{dataset}.{table}"
                metrics = {}

                for key, group_df in connector.get_group_data(
                    conn, datasets=[dataset], table_names=[table], location=resolved_location
                ):
                    if group_df is None or (hasattr(group_df, "empty") and group_df.empty):
                        continue

                    parts = key.split(".")
                    group_type = parts[-1]

                    if group_type == "numerical":
                        stats_json = SummaryStats.profile_numeric(group_df)
                    elif group_type == "text":
                        stats_json = SummaryStats.profile_text(group_df)
                    elif group_type == "date":
                        stats_json = SummaryStats.profile_date(group_df)
                    elif group_type == "boolean":
                        stats_json = SummaryStats.profile_bool(group_df)
                    else:
                        continue

                    if stats_json:
                        try:
                            metrics.update(json.loads(stats_json))
                        except (json.JSONDecodeError, TypeError):
                            continue

                if metrics:
                    report = {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "table_name": table_id,
                        "hash": hashes[h_key],
                        "metrics": metrics,
                    }
                    reports.append(report)

    elif conn_type == "snowflake":
        hashes = connector.get_table_hashes(conn, table_names=table_names, schemas=schemas or [])

        for s in schemas or []:
            for table in table_names:
                h_key = (s, table)

                if h_key not in hashes:
                    continue

                table_id = f"{s}.{table}"
                metrics = {}

                for key, group_df in connector.get_group_data(
                    conn, schemas=[s], table_names=[table]
                ):
                    if group_df is None or (hasattr(group_df, "empty") and group_df.empty):
                        continue

                    parts = key.split(".")
                    group_type = parts[-1]

                    if group_type == "numerical":
                        stats_json = SummaryStats.profile_numeric(group_df)
                    elif group_type == "text":
                        stats_json = SummaryStats.profile_text(group_df)
                    elif group_type == "date":
                        stats_json = SummaryStats.profile_date(group_df)
                    elif group_type == "boolean":
                        stats_json = SummaryStats.profile_bool(group_df)
                    else:
                        continue

                    if stats_json:
                        try:
                            metrics.update(json.loads(stats_json))
                        except (json.JSONDecodeError, TypeError):
                            continue

                if metrics:
                    report = {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "table_name": table_id,
                        "hash": hashes[h_key],
                        "metrics": metrics,
                    }
                    reports.append(report)

    else:
        hashes = connector.get_table_hashes(conn, table_names=table_names, schema=schema)

        for table in table_names:
            h_key = (schema, table)

            if h_key not in hashes:
                continue

            table_id = f"{schema}.{table}" if schema else table
            metrics = {}

            for key, group_df in connector.get_group_data(conn, schema=schema, table_names=[table]):
                if group_df is None or (hasattr(group_df, "empty") and group_df.empty):
                    continue

                parts = key.split(".")
                group_type = parts[-1]

                if group_type == "numerical":
                    stats_json = SummaryStats.profile_numeric(group_df)
                elif group_type == "text":
                    stats_json = SummaryStats.profile_text(group_df)
                elif group_type == "date":
                    stats_json = SummaryStats.profile_date(group_df)
                elif group_type == "boolean":
                    stats_json = SummaryStats.profile_bool(group_df)
                else:
                    continue

                if stats_json:
                    try:
                        metrics.update(json.loads(stats_json))
                    except (json.JSONDecodeError, TypeError):
                        continue

            if metrics:
                report = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "table_name": table_id,
                    "hash": hashes[h_key],
                    "metrics": metrics,
                }
                reports.append(report)

    if reports:
        try:
            with open(output_file, "a") as f:
                for report in reports:
                    f.write(json.dumps(report) + "\n")
                    f.flush()
                    os.fsync(f.fileno())

            return (
                f"✅ Successfully appended profiles and hashes for {len(reports)} "
                f"{'table' if len(reports) == 1 else 'tables'} to {output_file}"
            )
        except Exception as e:
            return f"⚠️ Error writing to output file: {str(e)}"
    else:
        return "⚠️ No data was processed. Check your input parameters."
