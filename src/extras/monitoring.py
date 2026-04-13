import numpy as np
from typing import Literal
import json

import json

def compute_and_save_hashes(conn_params, conn_type: Literal['postgres','snowflake','file', 'mysql','bigquery'], output_file="hashes.json", table_names=None, schemas=None, datsets=None, client=None):
    from src.connector.bigquery_connector import BigQueryConn
    from src.connector.file_connector import DataFileLoader
    from src.connector.mysql_connector import MySQLConnector
    from src.connector.snowflake_connector import SnowflakeConn
    from src.connector.postgres_connector import PostgresConn

    hashes = {}

    if conn_type == 'postgres':
        pg = PostgresConn(**conn_params)
        with pg as conn:
            hashes = pg.get_table_hashes(conn, table_names=table_names, schemas=schemas)

    elif conn_type == 'snowflake':
        snow = SnowflakeConn(**conn_params)
        with snow as conn:
            hashes = snow.get_table_hashes(conn, table_names=table_names, schemas=schemas)

    elif conn_type == 'file':
        loader = DataFileLoader(**conn_params)
        hashes = loader.get_file_hashes(path=conn_params.get("file_path"))

    elif conn_type == 'mysql':
        mysql = MySQLConnector(**conn_params)
        with mysql as conn:
            hashes = mysql.get_table_hashes(conn, table_names=table_names, schemas=schemas)
    elif conn_type == "bigquery":
        bigquery = BigQueryConn(**conn_params)
        with bigquery as conn:
            hashes = bigquery.get_table_hashes(conn, client, datasets=datsets,table_names=table_names)
    else:
        raise ConnectionError
    if hashes:
        hashes_str_keys = {
            f"{k[0]}.{k[1]}" if isinstance(k, tuple) else str(k): v
            for k, v in hashes.items()
        }

        with open(output_file, "w") as f:
            json.dump(hashes_str_keys, f, indent=4)
        print(f"✅ Hashes saved to {output_file}")
    else:
        print("⚠️ No hashes were computed. Check your connection type.")