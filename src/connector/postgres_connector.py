import psycopg2
from dataclasses import dataclass
import pandas as pd
from log import get_ingest_logger

data_logger = get_ingest_logger()
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

    def group_tables_by_type(self, conn, table_names=None, schemas=None):
        numerical_types = {
            "integer", "bigint", "smallint", "decimal", "numeric", "real", "double precision", "float"
        }
        text_types = {"character varying", "varchar", "character", "char", "text", "citext"}
        date_types = {"date", "timestamp","timestamptz", "time"}
        bool_types = {"boolean", "bool"}

        table_info = self.get_table_info(conn, table_names, schemas)
        grouped = {}

        for (schema, table), columns in table_info.items():
            groups = {
                "numerical": [],
                "text": [],
                "date": [],
                "bool": []
            }
            for col, dtype in columns:
                dtype_l = dtype.lower()
                if dtype_l in numerical_types:
                    groups["numerical"].append(col)
                elif dtype_l in text_types:
                    groups["text"].append(col)
                elif dtype_l in date_types:
                    groups["date"].append(col)
                elif dtype_l in bool_types:
                    groups["bool"].append(col)
            grouped[(schema, table)] = groups
        return grouped

    def get_group_data(self, conn, table_names=None, schemas=None, batch_size=50000):
        groups = self.group_tables_by_type(conn, table_names, schemas)
        flat_data = {}

        for (schema, table), group_cols in groups.items():
            table_ref = f'"{schema}"."{table}"'
            for group, columns in group_cols.items():
                if not columns:
                    flat_data[f"{schema}.{table}.{group}"] = pd.DataFrame()
                    continue

                col_str = ", ".join([f'"{col}"' for col in columns])
                query = f'SELECT {col_str} FROM {table_ref}'

                def fetch_batches():
                    offset = 0
                    while True:
                        batch_query = f'{query} LIMIT {batch_size} OFFSET {offset}'
                        cur = conn.cursor()
                        cur.execute(batch_query)
                        rows = cur.fetchall()
                        cur.close()
                        if not rows:
                            break
                        yield pd.DataFrame(rows, columns=columns)
                        offset += batch_size
                        data_logger.info(f"Fetched batch for {table_ref}, offset: {offset} for {group} columns")
                        
                combined_df = pd.concat(fetch_batches(), ignore_index=True)
                flat_data[f"{schema}.{table}.{group}"] = combined_df

        return flat_data

