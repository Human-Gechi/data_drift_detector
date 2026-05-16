from dataclasses import dataclass

import pandas as pd
import psycopg2

PG_TO_PANDAS_MAP = {
    "integer": "Int64",
    "bigint": "Int64",
    "smallint": "Int64",
    "decimal": "Float64",
    "numeric": "Float64",
    "real": "Float64",
    "double precision": "Float64",
    "boolean": "boolean",
    "character varying": "string",
    "text": "string",
    "date": "datetime64[ns]",
    "timestamp": "datetime64[ns]",
    "timestamptz": "datetime64[ns]",
}


class DatabaseConnectionError(Exception):
    pass


@dataclass
class PostgresConn:
    host: str
    port: int
    user: str
    database: str
    password: str

    def connect(self):
        """
        Establish PostgreSQL connection and return connection instance.

        Returns:
            psycopg2.connect: Authenticated PostgreSQL connection.

        Raises:
            DatabaseConnectionError: If connection fails.
        """
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
            )
            return self.conn
        except (
            psycopg2.OperationalError,
            psycopg2.ProgrammingError,
            psycopg2.InterfaceError,
            psycopg2.DatabaseError,
        ) as e:
            raise DatabaseConnectionError(f"PostgreSQL connection failed: {e}") from e
        except Exception as e:
            raise DatabaseConnectionError(f"An unexpected error occurred: {e}") from e

    def close(self):
        """
        Close  PostgreSQL  connection.

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
        Establish PostgreSQL connection and return self.

        Returns:
            SnowflakeConn: Self instance with active connection.

        Raises:
            DatabaseConnectionError: If connection fails.
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Close PostgreSQL  connection on context manager exit.

        Ensures proper cleanup of connection resources when exiting the with block.
        """
        self.close()

    def _get_table_info(self, table_names=None, schema=None):
        """
        Retrieve column names and data types for specified tables in a schema.

        Args:
            conn: Active PostgreSQL connection.
            table_names (list or str): Table names to retrieve info for.
            schema (str): Schema name.

        Returns:
            dict: Mapping of (schema, table) to list of (column_name, data_type) tuples.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        if table_names is None:
            raise ValueError("table_names must be provided")
        if isinstance(table_names, str):
            table_names = [table_names]

        if schema is None:
            schema = "public"

        results = {}
        try:
            cursor = self.conn.cursor()
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
                    psycopg2.OperationalError,
                    psycopg2.ProgrammingError,
                    psycopg2.InterfaceError,
                    psycopg2.DatabaseError,
                ) as e:
                    raise DatabaseConnectionError(f"psycopg2 error in get_table_info: {e}") from e
                except Exception as e:
                    raise DatabaseConnectionError(
                        f"Unexpected error in get_table_info occurred: {e}"
                    ) from e
            cursor.close()
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_table_info: {e}") from e
        return results

    def _group_tables_by_type(self, table_names=None, schema=None):
        """
        Group columns of tables by their PostgreSQL data type categories.

        Args:
            conn: Active PostgreSQL connection.
            table_names (list or str): Table names to group.
            schema (str): Schema name.

        Returns:
            dict: Mapping of (schema, table) to dict of grouped columns by type.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        numerical_types = {
            "integer",
            "bigint",
            "smallint",
            "decimal",
            "numeric",
            "real",
            "double precision",
            "float",
        }
        text_types = {"character varying", "varchar", "character", "char", "text", "citext"}
        date_types = {"date", "timestamp", "timestamptz", "time"}
        bool_types = {"boolean", "bool"}

        try:
            table_info = self._get_table_info(table_names, schema)
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

    def _table_exists(self, schema, table):
        """
        Check if a table exists in the given schema.

        Args:
            conn: Active PostgreSQL connection.
            schema (str): Schema name.
            table (str): Table name.

        Returns:
            bool: True if table exists, False otherwise.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        try:
            cursor = self.conn.cursor()
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
            psycopg2.OperationalError,
            psycopg2.ProgrammingError,
            psycopg2.InterfaceError,
            psycopg2.DatabaseError,
        ) as e:
            raise DatabaseConnectionError(f"psycopg2 error in table_exists: {e}") from e
        except Exception as e:
            raise DatabaseConnectionError(f"Unexpected error in table_exists: {e}") from e

    def _get_tables_in_schema(self, schema):
        """
        Retrieve all table names in a given schema.

        Args:
            conn: Active PostgreSQL connection.
            schema (str): Schema name.

        Returns:
            list: List of table names.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        tables = []
        try:
            cursor = self.conn.cursor()
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
                tables.extend(tables_in_schema)
            except (
                psycopg2.OperationalError,
                psycopg2.ProgrammingError,
                psycopg2.InterfaceError,
                psycopg2.DatabaseError,
            ) as e:
                raise DatabaseConnectionError(f"psycopg2 error in get_tables_in_schema: {e}") from e
            except Exception as e:
                raise DatabaseConnectionError(
                    f"Unexpected error in get_tables_in_schema: {e}"
                ) from e
            cursor.close()
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_tables_in_schema:{e}") from e
        return tables

    def _get_table_hashes(self, table_names=None, schema=None, batch_size=50000):
        """
        Calculate hash values for specified tables using PostgreSQL's hashtext function.

        Args:
            conn: Active PostgreSQL connection.
            table_names (list or str): Table names to hash.
            schema (str): Schema name.
            batch_size (int): Number of rows per query batch.

        Returns:
            dict: Mapping of (schema, table) to hash value or None if table does not exist.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        if table_names is None:
            raise ValueError("table_names must be provided")
        if schema is None:
            schema = "public"
        if isinstance(table_names, str):
            table_names = [table_names]

        results = {}
        try:
            cursor = self.conn.cursor()
            for table in table_names:
                try:
                    if self._table_exists(schema, table):
                        offset, total_hash = 0, 0
                        while True:
                            query = f"""SELECT SUM(hashtext(t::text)) FROM 
                            (
                            SELECT * FROM "{schema}"."{table}" 
                            LIMIT {batch_size} OFFSET {offset}
                            ) AS t;"""
                            cursor.execute(query)
                            hash_value = cursor.fetchone()[0]
                            if hash_value is None:
                                break
                            total_hash += hash_value
                            offset += batch_size
                        results[(schema, table)] = total_hash
                    else:
                        results[(schema, table)] = None
                except (
                    psycopg2.OperationalError,
                    psycopg2.ProgrammingError,
                    psycopg2.InterfaceError,
                    psycopg2.DatabaseError,
                ) as e:
                    raise DatabaseConnectionError(f"psycopg2 error in get_table_hashes: {e}") from e
                except Exception as e:
                    raise DatabaseConnectionError(
                        f"Unexpected error in get_table_hashes: {e}"
                    ) from e
            cursor.close()
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_table_hashes: {e}") from e
        return results

    def get_group_data(self, schema=None, table_names=None, batch_size=50000):
        """
        Retrieve column data in batches grouped by type for profiling.

        Args:
            conn: Active PostgreSQL connection.
            schema (str): Schema name.
            table_names (list or str): Table names to process.
            batch_size (int): Number of rows per query batch.

        Yields:
            tuple: (key, DataFrame) where key is "schema.table.group"
            and DataFrame contains grouped columns' data.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        if schema is None:
            schema = "public"
        if table_names and isinstance(table_names, str):
            table_names = [table_names]

        valid_tables = []
        try:
            if table_names:
                for table in table_names:
                    if self._table_exists(schema, table):
                        valid_tables.append(table)
            else:
                valid_tables = self._get_tables_in_schema(schema)

            table_info = self._get_table_info(table_names=valid_tables, schema=schema)
            groups = self._group_tables_by_type(table_names=valid_tables, schema=schema)

            for (sch, table), group_cols in groups.items():
                raw_cols = table_info.get((sch, table), [])
                table_dtype_map = {
                    col: PG_TO_PANDAS_MAP.get(dtype.lower(), "object") for col, dtype in raw_cols
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
                            except (
                                psycopg2.OperationalError,
                                psycopg2.ProgrammingError,
                                psycopg2.InterfaceError,
                                psycopg2.DatabaseError,
                            ) as e:
                                raise DatabaseConnectionError(
                                    f"psycopg2 error in get_group_data: {e}"
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
                        group_df = pd.concat(_fetch_batches(), ignore_index=True)
                        yield key, group_df
                    except Exception as e:
                        raise DatabaseConnectionError(f"Error in get_group_data for {key}") from e
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_group_data: {e}") from e
