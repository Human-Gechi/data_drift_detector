import numpy as np
from typing import Literal, Optional, Dict, List
import json

def compute_and_save_hashes(
    conn_params: Optional[Dict[str, str]] = None,
    conn_type: Literal['postgres','snowflake','file','mysql','bigquery'] = 'file',output_file: str = "hashes.jsonl",
    table_names: Optional[List[str]] = None, schemas: Optional[List[str]] = None,datsets: Optional[List[str]] = None,client=None,file_path: Optional[str] = None):

    from src.connector.bigquery_connector import BigQueryConn
    from src.connector.file_connector import DataFileLoader
    from src.connector.mysql_connector import MySQLConnector
    from src.connector.snowflake_connector import SnowflakeConn
    from src.connector.postgres_connector import PostgresConn

    hashes = {}

    if conn_type == 'postgres':
        if conn_params is None:
            raise ValueError("conn_params required for postgres")
        pg = PostgresConn(**conn_params)
        with pg as conn:
            hashes = pg.get_table_hashes(conn, table_names=table_names, schemas=schemas)

    elif conn_type == 'snowflake':
        if conn_params is None:
            raise ValueError("conn_params required for snowflake")
        snow = SnowflakeConn(**conn_params)
        with snow as conn:
            hashes = snow.get_table_hashes(conn, table_names=table_names, schemas=schemas)

    elif conn_type == 'file':
        loader = DataFileLoader(**(conn_params or {}))
        hashes = loader.get_file_hashes(file_path=file_path)

    elif conn_type == 'mysql':
        if conn_params is None:
            raise ValueError("conn_params required for mysql")
        mysql = MySQLConnector(**conn_params)
        with mysql as conn:
            hashes = mysql.get_table_hashes(conn, table_names=table_names, schemas=schemas)
    elif conn_type == "bigquery":
        if conn_params is None:
            raise ValueError("conn_params required for Bigquery")
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

        with open(output_file, "a") as f:
            f.write(json.dumps(hashes_str_keys) + "\n")
            print(f"Adding hash {hashes_str_keys}")
        print(f"✅ Hashes saved to {output_file}")
    else:
        print("⚠️ No hashes were computed. Check your connection type.")
