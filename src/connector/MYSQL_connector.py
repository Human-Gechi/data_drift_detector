from dataclasses import dataclass
import MySQLdb
import pandas as pd
from log import get_ingest_logger

data_logger = get_ingest_logger()

class DatabaseConnectionError(Exception):
    pass

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
        data = {}

        for (schema, table), group_cols in groups.items():
            table_ref = f'"{schema}"."{table}"'
            data[(schema, table)] = {}

            for group, columns in group_cols.items():
                if not columns:
                    data[(schema, table)][group] = None
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

                if combined_df.empty:
                    data[(schema, table)][group] = pd.DataFrame(columns=columns)
                else:
                    data[(schema, table)][group] = combined_df

        return data
