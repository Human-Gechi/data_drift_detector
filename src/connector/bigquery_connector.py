from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
from google.api_core.exceptions import NotFound
from google.cloud import bigquery
from google.oauth2 import service_account


class DatabaseConnectionError(Exception):
    pass


@dataclass
class BigQueryConn:
    project: Optional[str] = None
    credentials_path: Optional[str] = None
    location: str = None

    def __enter__(self):
        try:
            if self.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
                self.conn = bigquery.Client(
                    project=self.project, credentials=credentials, location=self.location
                )
            else:
                self.conn = bigquery.Client(project=self.project, location=self.location)
            return self.conn
        except FileNotFoundError as e:
            raise DatabaseConnectionError(f"File not found: {e}")
        except Exception as e:
            raise DatabaseConnectionError(f"BigQuery connection failed: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "conn"):
            self.conn.close()

    def dataset_exists(self, conn, dataset: str) -> bool:
        try:
            conn.get_dataset(f"{conn.project}.{dataset}")
            return True
        except NotFound:
            return False

    def table_exists(self, conn, dataset: str, table_name: str) -> bool:
        try:
            conn.get_table(f"{conn.project}.{dataset}.{table_name}")
            return True
        except NotFound:
            return False

    def get_table_hashes(self, conn, datasets: List[str], table_names: List[str]) -> Dict[Any, Any]:
        results = {}
        for dataset in datasets:
            if self.dataset_exists(conn, dataset):
                for table_name in table_names:
                    if self.table_exists(conn, dataset, table_name):
                        table_ref = f"{conn.project}.{dataset}.{table_name}"
                        try:
                            query_job = conn.query(
                                f"""SELECT BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) 
                                FROM `{table_ref}` AS t"""
                            )
                            result = list(query_job.result())
                            hash_value = result[0][0] if result else None
                            results[(dataset, table_name)] = hash_value
                        except Exception as e:
                            print(f"Error fetching hash for {table_name}: {e}")
                            results[(dataset, table_name)] = None
                    else:
                        print(f"Table {table_name} does not exist in dataset {dataset}")
                        results[(dataset, table_name)] = None
            else:
                print(f"Dataset {dataset} does not exist")
                for table_name in table_names:
                    results[(dataset, table_name)] = None
        return results

    def group_columns_by_type(self, conn, dataset: str, table_name: str) -> Dict[str, List[str]]:
        numerical_types = {
            "int64",
            "int",
            "smallint",
            "integer",
            "bigint",
            "tinyint",
            "byteint",
            "numeric",
            "decimal",
            "bignumeric",
            "bigdecimal",
            "float64",
            "float",
        }
        text_types = {"string"}
        date_types = {"date", "timestamp", "datetime", "time"}
        bool_types = {"boolean", "bool"}
        table_ref = f"{conn.project}.{dataset}.{table_name}"
        table = conn.get_table(table_ref)
        groups = {"numerical": [], "text": [], "date": [], "bool": []}
        for field in table.schema:
            ftype = field.field_type.lower()
            if ftype in numerical_types:
                groups["numerical"].append(field.name)
            elif ftype in text_types:
                groups["text"].append(field.name)
            elif ftype in date_types:
                groups["date"].append(field.name)
            elif ftype in bool_types:
                groups["bool"].append(field.name)
        return groups

    def available_dtypes(self, conn, dataset: str, table_name: str):
        if not self.table_exists(conn, dataset, table_name) and not self.dataset_exists(
            conn, dataset
        ):
            print(f"Table {dataset}.{table_name} does not exist.")
            return None
        table_ref = f"{conn.project}.{dataset}.{table_name}"
        table = conn.get_table(table_ref)
        return set(field.field_type for field in table.schema)

    def get_group_data(self, conn, datasets: List[str], table_names: List[str], limit: int = 1000):
        for dataset in datasets:
            for table_name in table_names:
                dtypes = self.available_dtypes(conn, dataset, table_name)
                print(f"Available dtypes in {dataset}.{table_name}: {dtypes}")

                try:
                    if dtypes:
                        groups = self.group_columns_by_type(conn, dataset, table_name)
                except NotFound:
                    print(f"Table reference {dataset}.{table_name} does not exist. Skipping.....⏩")
                    continue

                table_ref = f"{conn.project}.{dataset}.{table_name}"
                for group, columns in groups.items():
                    key = f"{table_ref}.{group}"
                    if not columns:
                        continue
                    col_str = ", ".join([f"`{col}`" for col in columns])
                    query = f"SELECT {col_str} FROM `{table_ref}` LIMIT {limit}"
                    try:
                        query_job = conn.query(query)
                        df = query_job.to_dataframe()
                        yield key, df
                    except Exception as e:
                        print(f"Error querying {table_ref} for group {group}: {e}")
                        yield key, None
