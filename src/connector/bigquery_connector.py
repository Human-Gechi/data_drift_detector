from typing import Optional, Dict, List
from dataclasses import dataclass
from google.cloud import bigquery
from google.oauth2 import service_account

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
            S

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'client'):
            self.client.close()

    def group_columns_by_type(self, client, dataset: str, table_name: str) -> Dict[str, List[str]]:
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
            if ftype in {"integer", "float", "numeric", "bignumeric"}:
                groups["numerical"].append(field.name)
            elif ftype in {"string", "bytes"}:
                groups["text"].append(field.name)
            elif ftype in {"date", "datetime", "timestamp", "time"}:
                groups["date"].append(field.name)
            elif ftype == "bool":
                groups["bool"].append(field.name)
        return groups

    def fetch_grouped_data(self, client, dataset: str, table_name: str, limit: int = 1000):
        groups = self.group_columns_by_type(client, dataset, table_name)
        data = {}
        table_ref = f"{client.project}.{dataset}.{table_name}"
        for group, columns in groups.items():
            if columns:
                col_str = ", ".join([f"`{col}`" for col in columns])
                query = f"SELECT {col_str} FROM `{table_ref}` LIMIT {limit}"
                query_job = client.query(query)
                data[group] = query_job.to_dataframe()
            else:
                data[group] = None
        return data

try:
    with BigQueryConn(project="project", credentials_path="path/to/creds.json") as client:
        data = client.fetch_grouped_data(client, "ataset", "table")
        print(data["numerical"])
        print(data["text"])
        print(data["date"])
        print(data["bool"])
except DatabaseConnectionError as e:
    print(f"{e}")
