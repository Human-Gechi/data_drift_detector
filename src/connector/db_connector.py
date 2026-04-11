import psycopg2
from dataclasses import dataclass
from typing import Optional
from google.cloud import bigquery
from google.oauth2 import service_account
import snowflake.connector
import MySQLdb

class DatabaseConnectionError(Exception):
    pass

@dataclass
class PostgresConn:
    host: str
    port: int
    user: str
    db: str
    password: str

    def __enter__(self):
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                dbname=self.db
            )
            return self.conn
        except (psycopg2.OperationalError, psycopg2.ProgrammingError, psycopg2.InterfaceError, psycopg2.DatabaseError) as e:
            raise DatabaseConnectionError(f"PostgreSQL connection failed: {e}")
        except Exception as e:
            raise DatabaseConnectionError(f"An unexpected error occurred: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'conn'):
            self.conn.close()

@dataclass
class MySQLConnector:
    host: str
    port: int
    user: str
    password: str
    db: str

    def __enter__(self):
        try:
            self.conn = MySQLdb.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.db
            )
            return self.conn
        except (MySQLdb.OperationalError, MySQLdb.ProgrammingError, MySQLdb.InterfaceError, MySQLdb.DatabaseError) as e:
            raise DatabaseConnectionError(f"MySQL connection failed: {e}")
        except Exception as e:
            raise DatabaseConnectionError(f"An unexpected error occurred: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'conn'):
            self.conn.close()

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
        except Exception as e:
            raise DatabaseConnectionError(f"BigQuery connection failed: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'client'):
            self.client.close()

@dataclass
class SnowflakeConn:
    user: str
    password: str
    account: str
    database: str
    schema: str
    warehouse: Optional[str] = None
    role: Optional[str] = None

    def __enter__(self):
        try:
            conn_params = {
                "user": self.user,
                "password": self.password,
                "account": self.account,
                "database": self.database,
                "schema": self.schema
            }
            if self.warehouse:
                conn_params["warehouse"] = self.warehouse
            if self.role:
                conn_params["role"] = self.role
            self.conn = snowflake.connector.connect(**conn_params)
            return self.conn
        except (snowflake.connector.errors.Error, Exception) as e:
            raise DatabaseConnectionError(f"Snowflake connection failed: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'conn'):
            self.conn.close()

if __name__ == "__main__":
    try:
        with PostgresConn(host="oko", port=190, user="hie", password="halo", db="flesh") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            print(cursor.fetchone())
    except DatabaseConnectionError as e:
        print(e)