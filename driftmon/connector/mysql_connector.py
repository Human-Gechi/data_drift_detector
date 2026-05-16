from collections import defaultdict
from dataclasses import dataclass

import MySQLdb
import pandas as pd

# Mapping datatypes
MYSQL_TO_PANDAS_MAP = {
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


class DatabaseConnectionError(Exception):
    pass


@dataclass
class MySQLConn:
    host: str
    port: int
    user: str
    password: str
    database: str

    """MYSQL connection handler with context manager support and profiling utilities.

    Manages MYSQL connections, authentication, and provides helper methods
    for table and schema operations, column profiling by data type, and hash-based
    table comparison.

    Features:
        - Context manager support (__enter__/__exit__) for automatic connection cleanup
        - group tables by data type
        - Fetch all the tables in a particular schema
        - Check table existence
        - Table hash calculation using CHECKSUM for table hashing
        - Automatic grouping of columns by data type (numerical, text, date, bool)
        - Batched data retrieval for tables

    Attributes:
            host: str -> MySQL host
            port: int -> MySQL port
            user: str -> MySQL username
            password: str -> MySQL password
            database: str -> MySQL database name
            conn (mysql.connector.MySQLConnection): MySQL connection instance (created in __enter__)
    Example:
        with MySQLConn(host='your-host', port=1000, user='your-username', password='your-paswword', 
            database='your-db-name') as conn:
            exists = MYSQLConn.table_exists(conn, 'my_schema', 'my_table')

    Raises:
        DatabaseConnectionError: If credentials file not found or connection fails
    """

    def connect(self):
        """Establish MySQL connection and return conn instance.
        Returns:
            MySQLdb.connect: Authenticated MySQL connection

        Raises:
            DatabaseConnectionError: If Programming, Interface, Database, Operational Error
        """
        try:
            self.conn = MySQLdb.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
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

    def close(self):
        """
        Close MySQL connection.

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
        Establish MySQL connection and return self.

        Returns:
            SnowflakeConn: Self instance with active connection.

        Raises:
            DatabaseConnectionError: If connection fails.
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Close MySQL connection on context manager exit.

        Ensures proper cleanup of connection resources when exiting the with block.
        """
        self.close()

    def _get_table_info(self, table_names=None, schema=None):
        """
        Email alert handler for sending data drift notifications.

        Sends an HTML-formatted email to a specified recipient when data drift is detected
        in monitored tables. Uses Jinja2 templates for formatting and supports retry logic.

        Args:
            sender_email (str): Sender's email address.
            receiver_email (str): Recipient's email address.
            sender_password (str): Sender's email password (for SMTP authentication).
            tables (List[str]): List of table names to monitor.
            file_path (str, optional): Path to the monitoring history file
            (default: "monitoring_history.jsonl").

        Methods:
            send_email(subject, html_body):
                Runs drift detection and sends an email with the drift report.
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
                    MySQLdb.OperationalError,
                    MySQLdb.ProgrammingError,
                    MySQLdb.InterfaceError,
                    MySQLdb.DatabaseError,
                ) as e:
                    raise DatabaseConnectionError(f"MySQL error in get_table_info: {e}") from e
                except Exception as e:
                    raise DatabaseConnectionError(f"Unexpected error in get_table_info: {e}") from e
            cursor.close()
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_table_info: {e}") from e
        return results

    def _group_tables_by_type(self, table_names=None, schema=None):
        """
        Group columns of tables by their MySQL data type categories.

        Args:
            conn: Active MySQL connection.
            table_names (list or str): Table names to group.
            schema (str): Schema name.

        Returns:
            dict: Mapping of (schema, table) to dict of grouped columns by type.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
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
            table_info = self._get_table_info(self.conn, table_names, schema)
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
            conn: Active MySQL connection.
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
            MySQLdb.OperationalError,
            MySQLdb.ProgrammingError,
            MySQLdb.InterfaceError,
            MySQLdb.DatabaseError,
        ) as e:
            raise DatabaseConnectionError(f"MySQL error in table_exists: {e}") from e
        except Exception as e:
            raise DatabaseConnectionError(f"Unexpected error in table_exists: {e}") from e

    def _get_tables_in_schema(self, schema):
        """
        Retrieve all table names in a given schema.

        Args:
            conn: Active MySQL connection.
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
                MySQLdb.OperationalError,
                MySQLdb.ProgrammingError,
                MySQLdb.InterfaceError,
                MySQLdb.DatabaseError,
            ) as e:
                raise DatabaseConnectionError(f"MySQL error in get_tables_in_schema: {e}") from e
            except Exception as e:
                raise DatabaseConnectionError(
                    f"Unexpected error in get_tables_in_schema: {e}"
                ) from e
            cursor.close()
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_tables_in_schema: {e}") from e
        return tables

    def _get_table_hashes(self, table_names=None, schema=None):
        """
        Calculate hash values for specified tables using MySQL's CHECKSUM TABLE.

        Args:
            conn: Active MySQL connection.
            table_names (list or str): Table names to hash.
            schema (str): Schema name.

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
                    if self._table_exists(self.conn, schema, table):
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
                    raise DatabaseConnectionError(f"MySQL error in get_table_hashes: {e}") from e
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
            conn: Active MySQL connection.
            schema (str): Schema name.
            table_names (list or str): Table names to process.
            batch_size (int): Number of rows per query batch, 50000 : default

        Yields:
            tuple: (key, DataFrame) where key is "schema.table.group"
            and DataFrame contains grouped columns' data.

        Raises:
            DatabaseConnectionError: On query or connection errors.
        """
        if schema is None:
            schema = "PUBLIC"
        if table_names and isinstance(table_names, str):
            table_names = [table_names]

        valid_tables = []
        try:
            if table_names:
                for table in table_names:
                    if self._table_exists(self.conn, schema, table):
                        valid_tables.append(table)
            else:
                valid_tables = self._get_tables_in_schema(self.conn, schema)

            table_info = self._get_table_info(self.conn, table_names=valid_tables, schema=schema)
            groups = self._group_tables_by_type(self.conn, table_names=valid_tables, schema=schema)

            for (sch, table), group_cols in groups.items():
                raw_cols = table_info.get((sch, table), [])
                table_dtype_map = {
                    col: MYSQL_TO_PANDAS_MAP.get(dtype.lower(), "object") for col, dtype in raw_cols
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
                        group_df = pd.concat(_fetch_batches(), ignore_index=True)
                        yield key, group_df
                    except Exception as e:
                        raise DatabaseConnectionError(
                            f"Error in get_group_data for {key}: {e}"
                        ) from e
        except Exception as e:
            raise DatabaseConnectionError(f"Error in get_group_data: {e}") from e
