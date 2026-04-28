import datetime
import json
from typing import Dict, List, Literal, Optional

from src.detect.profiler import SummaryStats


def append_profiles_hash(
    conn_type: Literal["postgres", "snowflake", "mysql", "bigquery"],
    conn_params: Optional[Dict[str, str]] = None,
    output_file: str = "monitoring_history.jsonl",
    table_names: Optional[List[str]] = None,
    schemas: Optional[List[str]] = None,
    datasets: Optional[List[str]] = None,
):
    from src.connector.bigquery_connector import BigQueryConn
    from src.connector.mysql_connector import MySQLConnector
    from src.connector.postgres_connector import PostgresConn
    from src.connector.snowflake_connector import SnowflakeConn

    reports = []

    if conn_type == "postgres":
        connector = PostgresConn(**conn_params)
    elif conn_type == "snowflake":
        connector = SnowflakeConn(**conn_params)
    elif conn_type == "mysql":
        connector = MySQLConnector(**conn_params)
    elif conn_type == "bigquery":
        connector = BigQueryConn(**conn_params)
    else:
        raise ConnectionError(f"Unsupported connection type: {conn_type}")

    with connector as conn:
        if conn_type == "bigquery":
            hashes = connector.get_table_hashes(conn, datasets=datasets, table_names=table_names)
            for dataset in datasets:
                for table in table_names:
                    table_id = f"{conn.project}.{dataset}.{table}"
                    h_key = (dataset, table)
                    metrics = {}

                    for key, group_df in connector.get_group_data(
                        conn, datasets=[dataset], table_names=[table]
                    ):
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
                            stats_json = None

                        if stats_json:
                            metrics.update(json.loads(stats_json))

                    report = {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "table_name": table_id,
                        "hash": hashes.get(h_key) if isinstance(hashes, dict) else hashes,
                        "metrics": metrics,
                    }
                    reports.append(report)
        else:
            hashes = connector.get_table_hashes(conn, table_names=table_names, schemas=schemas)
            for schema in schemas or ["public"]:
                for table in table_names:
                    table_id = f"{schema}.{table}"
                    h_key = (schema, table)
                    metrics = {}

                    for key, group_df in connector.get_group_data(
                        conn, schemas=[schema], table_names=[table]
                    ):
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
                            stats_json = None

                        if stats_json:
                            metrics.update(json.loads(stats_json))

                    report = {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "table_name": table_id,
                        "hash": hashes.get(h_key) if isinstance(hashes, dict) else hashes,
                        "metrics": metrics,
                    }
                    reports.append(report)

    if reports:
        with open(output_file, "a") as f:
            for report in reports:
                f.write(json.dumps(report) + "\n")
        return (
            f"✅ Successfully appended profiles and hashes for {len(reports)} "
            f"{'table' if len(reports) == 1 else 'tables'} to {output_file}"
        )
    else:
        return "⚠️ No data was processed. Check your input parameters."
