from typing import Optional, List
from dataclasses import dataclass
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd

class DatabaseConnectionError(Exception):
    pass

@dataclass
class BigQueryConn:
    project: Optional[str] = None
    credentials_path: Optional[str] = None

    def __enter__(self):
        try:
            if self.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
                self.client = bigquery.Client(project=self.project, credentials=credentials)
            else:
                self.client = bigquery.Client(project=self.project)
            return self.client
        except FileNotFoundError as e:
            raise DatabaseConnectionError(f"File not found: {e}")
        except Exception as e:
            raise DatabaseConnectionError(f"BigQuery connection failed: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'client'):
            self.client.close()

    def group_columns_by_type(self, client, dataset: str, table_name: str):
        numerical_types = {
            "integer", "bigint", "smallint", "decimal", "numeric", "real", "double precision", "float","number"
        }
        text_types = {"character varying", "varchar", "character", "char", "text", "citext", "string"}
        date_types = {"date", "timestamp","timestamptz", "time", "timestamp_ntz"}
        bool_types = {"boolean", "bool"}
        table_ref = f"{client.project}.{dataset}.{table_name}"
        table = client.get_table(table_ref)
        groups = {
            "numerical": [],
            "text": [],
            "date": [],
            "bool": []
        }
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

    def iter_grouped_data(self, client, datasets: List[str], table_names: List[str], limit: int = 1000):
        for dataset in datasets:
            for table_name in table_names:
                groups = self.group_columns_by_type(client, dataset, table_name)
                table_ref = f"{client.project}.{dataset}.{table_name}"
                for group, columns in groups.items():
                    if columns:
                        col_str = ", ".join([f"`{col}`" for col in columns])
                        query = f"SELECT {col_str} FROM `{table_ref}` LIMIT {limit}"
                        query_job = client.query(query)
                        df = query_job.to_dataframe()
                        yield (dataset, table_name, group, df)
                    else:
                        yield (dataset, table_name, group, None)