import datetime
import json
from typing import Dict, List, Literal, Optional

from src.extras.profiler import SummaryStats


def append_profiles_hash(
    conn_params: Optional[Dict[str, str]] = None,
    conn_type: Literal["postgres", "snowflake", "file", "mysql", "bigquery"] = "file",
    output_file: str = "monitoring_history.jsonl",
    table_names: Optional[List[str]] = None,
    schemas: Optional[List[str]] = None,
    datasets: Optional[List[str]] = None,
    client=None,
    file_path: Optional[str] = None,
):
    from src.connector.bigquery_connector import BigQueryConn
    from src.connector.file_connector import DataFileLoader
    from src.connector.mysql_connector import MySQLConnector
    from src.connector.postgres_connector import PostgresConn
    from src.connector.snowflake_connector import SnowflakeConn

    if conn_type == "postgres":
        connector = PostgresConn(**conn_params)
    elif conn_type == "snowflake":
        connector = SnowflakeConn(**conn_params)
    elif conn_type == "mysql":
        connector = MySQLConnector(**conn_params)
    elif conn_type == "bigquery":
        connector = BigQueryConn(**conn_params)
    elif conn_type == "file":
        connector = DataFileLoader(**(conn_params or {}))
    else:
        raise ConnectionError(f"Unsupported connection type: {conn_type}")

    with connector as conn:
        if conn_type == "bigquery":
            hashes = connector.get_table_hashes(
                conn, client, datasets=datasets, table_names=table_names
            )
        elif conn_type == "file":
            hashes = connector.get_file_hashes(file_path=file_path)
        else:
            hashes = connector.get_table_hashes(conn, table_names=table_names, schemas=schemas)

        table_reports = {}

        for key, group_df in connector.get_group_data(
            conn, schemas=schemas, table_names=table_names
        ):
            parts = key.split(".")
            table_id = f"{parts[0]}.{parts[1]}"
            group_type = parts[2]

            if table_id not in table_reports:
                h_key = (parts[0], parts[1])
                table_reports[table_id] = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "table_name": table_id,
                    "hash": hashes.get(h_key) if isinstance(hashes, dict) else hashes,
                    "metrics": {},
                }

            stats_json = ""
            if group_type == "numerical":
                stats_json = SummaryStats.profile_numeric(group_df)
            elif group_type == "text":
                stats_json = SummaryStats.profile_text(group_df)
            elif group_type == "date":
                stats_json = SummaryStats.profile_date(group_df)
            elif group_type == "bool":
                stats_json = SummaryStats.profile_bool(group_df)

            if stats_json:
                table_reports[table_id]["metrics"].update(json.loads(stats_json))

        if table_reports:
            with open(output_file, "a") as f:
                for report in table_reports.values():
                    f.write(json.dumps(report) + "\n")
            return (
                "✅ Successfully appended profiles and hashes for "
                f"{len(table_reports)} tables to {output_file}"
            )
        else:
            return "⚠️ No data was processed. Check your table names and schemas."
