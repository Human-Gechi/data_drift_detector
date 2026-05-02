from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Generator, List, Optional, Tuple

import pandas as pd
from google.api_core.exceptions import BadRequest, Forbidden, NotFound
from google.cloud import bigquery
from google.oauth2 import service_account


class DatabaseConnectionError(Exception):
    pass


@dataclass
class BigQueryConn:
    project: Optional[str] = None
    credentials_path: Optional[str] = None
    location: Optional[str] = None

    def __enter__(self):
        try:
            if self.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
                self.conn = bigquery.Client(
                    project=self.project,
                    credentials=credentials,
                    location=self.location,
                )
            else:
                self.conn = bigquery.Client(
                    project=self.project,
                    location=self.location,
                )
            return self.conn
        except FileNotFoundError as e:
            raise DatabaseConnectionError(f"File not found: {e}")
        except Exception as e:
            raise DatabaseConnectionError(f"BigQuery connection failed: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "conn"):
            self.conn.close()

    def get_dataset_location(self, conn, dataset: str) -> Optional[str]:
        try:
            dataset_ref = f"{conn.project}.{dataset}"
            dataset_obj = conn.get_dataset(dataset_ref)
            return dataset_obj.location
        except NotFound:
            return None
        except Exception:
            return None

    def dataset_exists(self, conn, dataset: str) -> bool:
        try:
            conn.get_dataset(f"{conn.project}.{dataset}")
            return True
        except NotFound:
            return False
        except Exception:
            return False

    def table_exists(self, conn, dataset: str, table_name: str) -> bool:
        try:
            table_ref = f"{conn.project}.{dataset}.{table_name}"
            conn.get_table(table_ref)
            return True
        except NotFound:
            return False
        except Exception:
            return False

    def get_table_hashes(
        self, conn, datasets: List[str], table_names: List[str], location: Optional[str] = None
    ) -> Dict[Tuple[str, str], Optional[int]]:
        results = {}

        datasets_by_location = defaultdict(list)
        for dataset in datasets:
            resolved_location = location or self.get_dataset_location(conn, dataset)
            if resolved_location:
                datasets_by_location[resolved_location].append(dataset)

        for loc, dataset_list in datasets_by_location.items():
            for dataset in dataset_list:
                for table_name in table_names:
                    if not self.table_exists(conn, dataset, table_name):
                        continue

                    table_ref = f"{conn.project}.{dataset}.{table_name}"
                    try:
                        query_job = conn.query(
                            f"""SELECT BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) 
                            FROM `{table_ref}` AS t""",
                            location=loc,
                        )
                        result = list(query_job.result())
                        hash_value = result[0][0] if result else None
                        results[(dataset, table_name)] = hash_value
                    except (NotFound, Forbidden, BadRequest) as e:
                        continue
                    except Exception:
                        continue

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

        try:
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
        except Exception:
            return {"numerical": [], "text": [], "date": [], "bool": []}

    def available_dtypes(self, conn, dataset: str, table_name: str) -> Optional[set]:
        if not (
            self.table_exists(conn, dataset, table_name) and self.dataset_exists(conn, dataset)
        ):
            return None

        try:
            table_ref = f"{conn.project}.{dataset}.{table_name}"
            table = conn.get_table(table_ref)
            return set(field.field_type for field in table.schema)
        except Exception:
            return None

    def get_group_data(
        self,
        conn,
        datasets: List[str],
        table_names: List[str],
        batch_size: int = 50000,
        location: Optional[str] = None,
    ) -> Generator[Tuple[str, pd.DataFrame], None, None]:
        datasets_by_location = defaultdict(list)
        for dataset in datasets:
            resolved_location = location or self.get_dataset_location(conn, dataset)
            if resolved_location:
                datasets_by_location[resolved_location].append(dataset)

        for loc, dataset_list in datasets_by_location.items():
            for dataset in dataset_list:
                for table_name in table_names:
                    if not self.table_exists(conn, dataset, table_name):
                        continue

                    dtypes = self.available_dtypes(conn, dataset, table_name)
                    if not dtypes:
                        continue

                    try:
                        table_ref = f"{conn.project}.{dataset}.{table_name}"
                        table = conn.get_table(table_ref)
                        total_rows = table.num_rows

                        groups = self.group_columns_by_type(conn, dataset, table_name)

                        for group, columns in groups.items():
                            if not columns:
                                continue

                            key = f"{table_ref}.{group}"
                            col_str = ", ".join([f"`{col}`" for col in columns])

                            def fetch_batches():
                                for offset in range(0, total_rows, batch_size):
                                    query = f"""SELECT {col_str} FROM `{table_ref}` 
                                    LIMIT {batch_size} OFFSET {offset}"""
                                    try:
                                        query_job = conn.query(query, location=loc)
                                        df = query_job.to_dataframe()
                                        if df.empty:
                                            break
                                        yield df
                                    except Exception:
                                        break

                            try:
                                batches = list(fetch_batches())
                                if batches:
                                    group_df = pd.concat(batches, ignore_index=True)
                                    yield key, group_df
                            except Exception:
                                continue
                    except Exception:
                        continue
