from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Union

import pandas as pd
import snowflake.connector


class DatabaseConnectionError(Exception):
    pass


PG_TO_PANDAS_MAP = {
    "integer": "Int64",
    "bigint": "Int64",
    "smallint": "Int64",
    "decimal": "Float64",
    "numeric": "Float64",
    "real": "Float64",
    "double precision": "Float64",
    "boolean": "boolean",
    "varchar": "string",
    "char": "string",
    "text": "string",
    "string": "string",
    "date": "datetime64[ns]",
    "timestamp": "datetime64[ns]",
    "timestamptz": "datetime64[ns]",
    "timestamp_ntz": "datetime64[ns]",
    "time": "datetime64[ns]",
    "number": "Float64",
}


@dataclass
class SnowflakeConn:
    user: str
    password: str
    account: str
    database: str
    warehouse: str
    schema: Optional[str] = None
    role: Optional[str] = None
    conn: Optional[snowflake.connector.SnowflakeConnection] = None

    def connect(self):
        """
        Establish Snowflake connection and store it in self.conn.

        Returns:
            snowflake.connector.SnowflakeConnection: Authenticated Snowflake connection.

        Raises:
            DatabaseConnectionError: If connection fails.
        """
        try:
            conn_params = {
                "user": self.user,
                "password": self.password,
                "account": self.account,
                "database": self.database,
                "warehouse": self.warehouse,
            }
            if self.schema:
                conn_params["schema"] = self.schema
            if self.role:
                conn_params["role"] = self.role
            self.conn = snowflake.connector.connect(**conn_params)
            return self.conn
        except (snowflake.connector.errors.Error, Exception) as e:
            raise DatabaseConnectionError(f"Snowflake connection failed: {e}") from e

    def close(self):
        """
        Close Snowflake connection.

        Ensures proper cleanup of connection resources.
        """
        if self.conn:
            try:
                self.conn.close()
                self.conn = None
            except Exception as e:
                pass

    def __enter__(self):
        """
        Establish Snowflake connection and return self.

        Returns:
            SnowflakeConn: Self instance with active connection.

        Raises:
            DatabaseConnectionError: If connection fails.
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Close Snowflake connection on context manager exit.

        Ensures proper cleanup of connection resources when exiting the with block.
        """
        self.close()

    def _get_table_info(self, table_names=None, schemas=None):
        """
        Retrieve column names and data types for specified tables in schemas.

        Args:
            table_names (list or str): Table names to retrieve info for.
            schemas (list or str): Schema names.

        Returns:
            dict: Mapping of (schema, table) to list of (column_name, data_type) tuples.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        if table_names is None:
            raise ValueError("table_names must be provided")
        if isinstance(table_names, str):
            table_names = [table_names]

        if schemas is None:
            schemas = ["public"]
        if isinstance(schemas, str):
            schemas = [schemas]

        if not self.conn:
            raise DatabaseConnectionError(
                "No active connection. Call connect() first or use context manager."
            )

        results = {}
        try:
            cursor = self.conn.cursor()
            for schema in schemas:
                for table_name in table_names:
                    try:
                        cursor.execute(
                            f"""
                            SELECT column_name, data_type
                            FROM information_schema.columns
                            WHERE table_schema = '{schema}' AND table_name = '{table_name}'
                            ORDER BY ordinal_position
                            """
                        )
                        columns = cursor.fetchall()
                        results[(schema, table_name)] = columns
                    except (snowflake.connector.errors.Error, Exception) as e:
                        raise DatabaseConnectionError(
                            f"Error in get_table_info for {schema}.{table_name}: {e}"
                        ) from e
            cursor.close()
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_table_info: {e}") from e
        return results

    def _group_tables_by_type(self, table_names=None, schemas=None):
        """
        Group columns of tables by their Snowflake data type categories.

        Args:
            table_names (list or str): Table names to group.
            schemas (list or str): Schema names.

        Returns:
            dict: Mapping of (schema, table) to dict of grouped columns by type.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        numerical_types = {
            "integer",
            "bigint",
            "smallint",
            "numeric",
            "real",
            "double precision",
            "float",
            "number",
        }
        text_types = {"string", "text", "varchar", "char"}
        date_types = {"date", "timestamp", "timestamptz", "time", "timestamp_ntz", "timestamp_ltz"}
        bool_types = {"boolean", "bool"}

        try:
            table_info = self._get_table_info(table_names, schemas)
            grouped = {}

            for (schema, table), columns in table_info.items():
                groups = {"numerical": [], "text": [], "date": [], "boolean": []}
                for col, dtype in columns:
                    dtype_l = dtype.lower()
                    if dtype_l in numerical_types:
                        groups["numerical"].append(col)
                    elif dtype_l in text_types:
                        groups["text"].append(col)
                    elif dtype_l in date_types:
                        groups["date"].append(col)
                    elif dtype_l in bool_types:
                        groups["boolean"].append(col)
                grouped[(schema, table)] = groups
            return grouped
        except Exception as e:
            raise DatabaseConnectionError(f"Error in group_tables_by_type: {e}") from e

    def _table_exists(self, schema: str, table: str):
        """
        Check if a table exists in the given schema.

        Args:
            schema (str): Schema name.
            table (str): Table name.

        Returns:
            bool: True if table exists, False otherwise.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        if not self.conn:
            raise DatabaseConnectionError(
                "No active connection. Call connect() first or use context manager."
            )

        try:
            print(f"Checking {schema}, table {table}")
            cursor = self.conn.cursor()
            cursor.execute(f"""
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = '{schema}' AND table_name = '{table}'
            """)
            print(f"Checking {schema}, table {table}")
            exists = cursor.fetchone() is not None
            cursor.close()
            return exists
        except (snowflake.connector.errors.Error, Exception) as e:
            raise DatabaseConnectionError(f"Error in table_exists: {e}") from e

    def _get_tables_in_schemas(
        self,
        schemas: Union[str, List[str]],
    ):
        """
        Retrieve all table names in given schemas.

        Args:
            schemas (list or str): Schema names.

        Returns:
            list: List of (schema, table) tuples.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        if not self.conn:
            raise DatabaseConnectionError(
                "No active connection. Call connect() first or use context manager."
            )

        if isinstance(schemas, str):
            schemas = [schemas]
        tables = []
        try:
            cursor = self.conn.cursor()
            for schema in schemas:
                try:
                    cursor.execute(
                        f"""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = '{schema}' AND table_type = 'BASE TABLE'
                        """
                    )
                    tables_in_schema = [row[0] for row in cursor.fetchall()]
                    tables.extend([(schema, t) for t in tables_in_schema])
                except (snowflake.connector.errors.Error, Exception) as e:
                    raise DatabaseConnectionError(
                        f"Error in get_tables_in_schemas for {schema}: {e}"
                    ) from e
            cursor.close()
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_tables_in_schemas: {e}") from e
        return tables

    def _get_table_hashes(self, table_names=None, schemas=None) -> dict:
        """
        Calculate hash values for specified tables using Snowflake's HASH_AGG.

        Args:
            table_names (list or str): Table names to hash.
            schemas (list or str): Schema names.

        Returns:
            dict: Mapping of (schema, table) to hash value or None if table does not exist.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        if not self.conn:
            raise DatabaseConnectionError(
                "No active connection. Call connect() first or use context manager."
            )

        if table_names is None:
            raise ValueError("table_names must be provided")
        if schemas is None:
            schemas = ["snowflake"]
        if isinstance(table_names, str):
            table_names = [table_names]
        if isinstance(schemas, str):
            schemas = [schemas]

        results = {}
        try:
            cursor = self.conn.cursor()
            for schema in schemas:
                for table in table_names:
                    try:
                        if self._table_exists(schema, table):
                            query = f'SELECT HASH_AGG(*) FROM "{schema}"."{table}"'
                            cursor.execute(query)
                            full_hash = cursor.fetchone()[0]
                            results[(schema, table)] = full_hash
                        else:
                            results[(schema, table)] = None
                    except (snowflake.connector.errors.Error, Exception) as e:
                        raise DatabaseConnectionError(
                            f"Error in get_table_hashes for {schema}.{table}: {e}"
                        ) from e
            cursor.close()
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_table_hashes: {e}") from e
        return results

    def get_group_data(self, schemas=None, table_names=None, batch_size=50000):
        """
        Retrieve column data in batches grouped by type for profiling.

        Args:
            schemas (list or str): Schema names.
            table_names (list or str): Table names to process.
            batch_size (int): Number of rows per query batch.

        Yields:
            tuple: (key, DataFrame) where key is "schema.table.group"
            and DataFrame contains grouped columns' data.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        if not self.conn:
            raise DatabaseConnectionError(
                "No active connection. Call connect() first or use context manager."
            )

        if schemas is None:
            schemas = ["snowflake"]
        if isinstance(schemas, str):
            schemas = [schemas]
        if table_names and isinstance(table_names, str):
            table_names = [table_names]

        valid_tables = set()
        try:
            for schema in schemas:
                if table_names:
                    for table in table_names:
                        if self._table_exists(schema, table):
                            valid_tables.add((schema, table))
                else:
                    tables = self._get_tables_in_schemas([schema])
                    for sch, tbl in tables:
                        valid_tables.add((sch, tbl))

            schema_table_map = defaultdict(list)
            for schema, table in valid_tables:
                schema_table_map[schema].append(table)

            for schema, tables in schema_table_map.items():
                table_info = self._get_table_info(table_names=tables, schemas=[schema])
                groups = self._group_tables_by_type(table_names=tables, schemas=[schema])

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

                        def _fetch_batches():
                            offset = 0
                            while True:
                                batch_query = f"""SELECT {col_str} FROM "{sch}"."{table}" 
                                LIMIT {batch_size} OFFSET {offset}"""
                                cur = self.conn.cursor()
                                try:
                                    cur.execute(batch_query)
                                    rows = cur.fetchall()
                                except (snowflake.connector.errors.Error, Exception) as e:
                                    raise DatabaseConnectionError(
                                        f"Error in get_group_data for {key}: {e}"
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
                            group_df = pd.concat(_fetch_batches(), ignore_index=True)
                            yield key, group_df
                        except Exception as e:
                            raise DatabaseConnectionError(
                                f"Error in get_group_data for {key}: {e}"
                            ) from e
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_group_data: {e}") from e
