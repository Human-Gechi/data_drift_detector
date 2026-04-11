import psycopg2
from dataclasses import dataclass
from typing import Optional
from google.cloud import bigquery

@dataclass
class PostgresConn:
    host: str
    port: int
    user: str
    db: str
    password: str
    warehouse: Optional[str] = None
    role: Optional[str] = None

    def connect(self):
        conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            dbname=self.db
        )
        return conn
    
@dataclass
class MySQL:
    pass

@dataclass
class BigQueryConn:
    project: Optional[str] = None
    credentials_path: Optional[str] = None

    def connect(self):
        if self.credentials_path:
            client = bigquery.Client(project=self.project, credentials=self.credentials_path)
        else:
            client = bigquery.Client(project=self.project)
        return client
