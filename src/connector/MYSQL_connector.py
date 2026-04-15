from collections import defaultdict
from dataclasses import dataclass

import MySQLdb
import pandas as pd

from log import get_ingest_logger

PG_TO_PANDAS_MAP = {
    "integer": "Int64",
    "bigint": "Int64",
    "smallint": "Int64",
    "decimal": "Float64",
    "numeric": "Float64",
    "real": "Float64",
    "double precision": "Float64",
    "boolean": "boolean",
    "char": "string",
    "varchar": "string",
    "text": "string",
    "date": "datetime64[ns]",
    "timestamp": "datetime64[ns]",
    "timestamptz": "datetime64[ns]",
}
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
                host=self.host, port=self.port, user=self.user, password=self.password, db=self.db
            )
            return self.conn
        except (
            MySQLdb.OperationalError,
            MySQLdb.ProgrammingError,
            MySQLdb.InterfaceError,
            MySQLdb.DatabaseError,
        ) as e:
            raise DatabaseConnectionError(f"MySQL connection failed: {e}") from e
        except Exception as e:
            raise DatabaseConnectionError(f"An unexpected error occurred: {e}") from e

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "conn"):
            try:
                self.conn.close()
            except Exception as e:
                pass

    def get_table_info(self, conn, table_names=None, schemas=None):
        if table_names is None:
            raise ValueError("table_names must be provided")
        if isinstance(table_names, str):
            table_names = [table_names]

        if schemas is None:
            schemas = ["public"]
        if isinstance(schemas, str):
            schemas = [schemas]

        results = {}
        try:
            cursor = conn.cursor()
            for schema in schemas:
                for table_name in table_names:
                    try:
                        cursor.execute(
                            """
                            SELECT column_name, data_type
                            FROM information_schema.columns
                            WHERE table_schema = %s AND table_name = %s
                            ORDER BY ordinal_position
                            """,
                            (schema, table_name),
                        )
                        columns = cursor.fetchall()
                        results[(schema, table_name)] = columns
                    except (
                        MySQLdb.OperationalError,
                        MySQLdb.ProgrammingError,
                        MySQLdb.InterfaceError,
                        MySQLdb.DatabaseError,
                    ) as e:
                        raise DatabaseConnectionError(f"MySQL error in get_table_info: {e}") from e
                    except Exception as e:
                        raise DatabaseConnectionError(
                            f"Unexpected error in get_table_info: {e}"
                        ) from e
            cursor.close()
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_table_info: {e}") from e
        return results

    def group_tables_by_type(self, conn, table_names=None, schemas=None):
        numerical_types = {
            "int",
            "integer",
            "bigint",
            "smallint",
            "tinyint",
            "mediumint",
            "decimal",
            "numeric",
            "float",
            "double",
            "double precision",
            "real",
        }

        text_types = {
            "char",
            "varchar",
            "text",
            "tinytext",
            "mediumtext",
            "longtext",
            "enum",
            "set",
        }

        date_types = {"date", "datetime", "timestamp", "time", "year"}

        bool_types = {"tinyint", "bool", "boolean"}

        try:
            table_info = self.get_table_info(conn, table_names, schemas)
            grouped = {}

            for (schema, table), columns in table_info.items():
                groups = {"numerical": [], "text": [], "date": [], "bool": []}
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
        except Exception as e:
            raise DatabaseConnectionError(f"Error in group_tables_by_type: {e}") from e

    def table_exists(self, conn, schema, table):
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """,
                (schema, table),
            )
            exists = cursor.fetchone() is not None
            cursor.close()
            return exists
        except (
            MySQLdb.OperationalError,
            MySQLdb.ProgrammingError,
            MySQLdb.InterfaceError,
            MySQLdb.DatabaseError,
        ) as e:
            raise DatabaseConnectionError(f"MySQL error in table_exists: {e}") from e
        except Exception as e:
            raise DatabaseConnectionError(f"Unexpected error in table_exists: {e}") from e

    def get_tables_in_schemas(self, conn, schemas):
        if isinstance(schemas, str):
            schemas = [schemas]
        tables = []
        try:
            cursor = conn.cursor()
            for schema in schemas:
                try:
                    cursor.execute(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_type = 'BASE TABLE'
                        """,
                        (schema,),
                    )
                    tables_in_schema = [row[0] for row in cursor.fetchall()]
                    tables.extend([(schema, t) for t in tables_in_schema])
                except (
                    MySQLdb.OperationalError,
                    MySQLdb.ProgrammingError,
                    MySQLdb.InterfaceError,
                    MySQLdb.DatabaseError,
                ) as e:
                    raise DatabaseConnectionError(
                        f"MySQL error in get_tables_in_schemas: {e}"
                    ) from e
                except Exception as e:
                    raise DatabaseConnectionError(
                        f"Unexpected error in get_tables_in_schemas: {e}"
                    ) from e
            cursor.close()
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_tables_in_schemas: {e}") from e
        return tables

    def get_table_hashes(self, conn, table_names=None, schemas=None):
        if table_names is None:
            raise ValueError("table_names must be provided")
        if schemas is None:
            schemas = ["public"]
        if isinstance(table_names, str):
            table_names = [table_names]
        if isinstance(schemas, str):
            schemas = [schemas]

        results = {}
        try:
            cursor = conn.cursor()
            for schema in schemas:
                for table in table_names:
                    try:
                        if self.table_exists(conn, schema, table):
                            query = f"CHECKSUM TABLE {schema}.{table};"
                            cursor.execute(query)
                            hash_value = cursor.fetchone()[1]
                            if hash_value is None:
                                break
                            results[(schema, table)] = hash_value
                        else:
                            results[(schema, table)] = None
                    except (
                        MySQLdb.OperationalError,
                        MySQLdb.ProgrammingError,
                        MySQLdb.InterfaceError,
                        MySQLdb.DatabaseError,
                    ) as e:
                        raise DatabaseConnectionError(
                            f"MySQL error in get_table_hashes: {e}"
                        ) from e
                    except Exception as e:
                        raise DatabaseConnectionError(
                            f"Unexpected error in get_table_hashes: {e}"
                        ) from e
            cursor.close()
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_table_hashes: {e}") from e
        return results

    def get_group_data(self, conn, schemas=None, table_names=None, batch_size=50000):
        if schemas is None:
            schemas = ["PUBLIC"]
        if isinstance(schemas, str):
            schemas = [schemas]
        if table_names and isinstance(table_names, str):
            table_names = [table_names]

        valid_tables = set()
        try:
            for schema in schemas:
                if table_names:
                    for table in table_names:
                        if self.table_exists(conn, schema, table):
                            valid_tables.add((schema, table))
                else:
                    tables = self.get_tables_in_schemas(conn, [schema])
                    for sch, tbl in tables:
                        valid_tables.add((sch, tbl))

            schema_table_map = defaultdict(list)
            for schema, table in valid_tables:
                schema_table_map[schema].append(table)

            for schema, tables in schema_table_map.items():
                table_info = self.get_table_info(conn, table_names=tables, schemas=[schema])
                groups = self.group_tables_by_type(conn, table_names=tables, schemas=[schema])

                for (sch, table), group_cols in groups.items():
                    raw_cols = table_info.get((sch, table), [])
                    table_dtype_map = {
                        col: PG_TO_PANDAS_MAP.get(dtype.lower(), "object")
                        for col, dtype in raw_cols
                    }

                    for group, columns in group_cols.items():
                        if not columns:
                            continue

                        key = f"{sch}.{table}.{group}"
                        col_str = ", ".join(f'"{col}"' for col in columns)

                        def fetch_batches():
                            offset = 0
                            while True:
                                batch_query = f"""SELECT {col_str} FROM "{sch}"."{table}" 
                                LIMIT {batch_size} OFFSET {offset}"""
                                cur = conn.cursor()
                                try:
                                    cur.execute(batch_query)
                                    rows = cur.fetchall()
                                except (
                                    MySQLdb.OperationalError,
                                    MySQLdb.ProgrammingError,
                                    MySQLdb.InterfaceError,
                                    MySQLdb.DatabaseError,
                                ) as e:
                                    raise DatabaseConnectionError(
                                        f"MySQL error in get_group_data: {e}"
                                    ) from e
                                except Exception as e:
                                    raise DatabaseConnectionError(
                                        f"Unexpected error in get_group_data: {e}"
                                    ) from e
                                finally:
                                    cur.close()

                                if not rows:
                                    break

                                batch_df = pd.DataFrame(rows, columns=columns)

                                current_group_map = {c: table_dtype_map[c] for c in columns}
                                yield batch_df.astype(current_group_map)

                                offset += batch_size

                        try:
                            group_df = pd.concat(fetch_batches(), ignore_index=True)
                            yield key, group_df
                        except Exception as e:
                            raise DatabaseConnectionError(
                                f"Error in get_group_data for {key}: {e}"
                            ) from e
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_group_data: {e}") from e
