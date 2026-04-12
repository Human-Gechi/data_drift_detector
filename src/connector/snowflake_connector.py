from typing import Optional
import snowflake.connector
from dataclasses import dataclass

class DatabaseConnectionError(Exception):
    pass

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

    def get_table_info(self, conn, table_names=None,schemas=None):
        if table_names is None:
            raise ValueError("table_names must be provided")
        if isinstance(table_names, str):
            table_names = [table_names]

        if schemas is None:
            schemas = ["public"]
        if isinstance(schemas, str):
            schemas = [schemas]

        results = {}
        cursor = conn.cursor()
        for schema in schemas:
            for table_name in table_names:
                cursor.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (schema, table_name)
                )
                columns = cursor.fetchall()
                results[(schema, table_name)] = columns
        cursor.close()
        return results

    def get_group_dtypes(self):
        pass