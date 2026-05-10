from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Generator, List, Optional, Tuple

import pandas as pd
from google.api_core.exceptions import BadRequest, Forbidden, NotFound
from google.cloud import bigquery
from google.oauth2 import service_account


class DatabaseConnectionError(Exception):
    pass


@dataclass
class BigQueryConn:
    """BigQuery connection handler with context manager support and profiling utilities.

    Manages Google BigQuery connections, authentication, and provides helper methods
    for table/dataset operations, column profiling by data type, and hash-based
    table comparison.

    Features:
        - Context manager support (__enter__/__exit__) for automatic connection cleanup
        - Authentication via service account JSON or Application Default Credentials
        - Dataset/table existence checks
        - Table hash calculation using BIT_XOR and FARM_FINGERPRINT
        - Automatic grouping of columns by data type (numerical, text, date, bool)
        - Batched data retrieval for large tables
        - Location-aware operations (US, EU, etc.)

    Attributes:
        project (Optional[str]): GCP project ID
        credentials_path (Optional[str]): Path to service account JSON key file
        location (Optional[str]): Default BigQuery location (e.g., 'US', 'EU')
        conn (bigquery.Client): BigQuery client instance (created in __enter__)

    Example:
        with BigQueryConn(project='my-project', credentials_path='key.json') as conn:
            exists = BigQueryConn.table_exists(conn, 'my_dataset', 'my_table')
            hashes = BigQueryConn.get_table_hashes(conn, ['dataset1'], ['table1'])

    Raises:
        DatabaseConnectionError: If credentials file not found or connection fails
    """

    project: Optional[str] = None
    credentials_path: Optional[str] = None
    location: Optional[str] = None

    def __enter__(self):
        """Establish BigQuery connection and return client instance.
        Initializes BigQuery client using either service account credentials
        (if credentials_path provided) or Application Default Credentials.

        Returns:
            bigquery.Client: Authenticated BigQuery client instance

        Raises:
            DatabaseConnectionError: If credentials file not found or connection fails
        """
        try:
            if self.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
                self.conn = bigquery.Client(
                    project=self.project,
                    credentials=credentials,
                    location=self.location,
                )
            else:
                self.conn = bigquery.Client(
                    project=self.project,
                    location=self.location,
                )
            return self.conn
        except FileNotFoundError as e:
            raise DatabaseConnectionError(f"File not found: {e}")
        except Exception as e:
            raise DatabaseConnectionError(f"BigQuery connection failed: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close BigQuery connection on context manager exit.
        Ensures proper cleanup of connection resources when exiting the with block.
        """
        if hasattr(self, "conn"):
            self.conn.close()

    def get_dataset_location(self, conn, dataset: str) -> Optional[str]:
        """Retrieve the location (region) of a BigQuery dataset.

        Args:
            conn (bigquery.Client): Active BigQuery connection
            dataset (str): Dataset name

        Returns:
            Optional[str]: Dataset location (e.g., 'US', 'EU') or None if not found
        """
        try:
            dataset_ref = f"{conn.project}.{dataset}"
            dataset_obj = conn.get_dataset(dataset_ref)
            return dataset_obj.location
        except NotFound:
            raise DatabaseConnectionError(f"Dataset not found: {dataset}")
        except Exception as e:
            raise DatabaseConnectionError(f"Error retrieving dataset location: {e}")

    def dataset_exists(self, conn, dataset: str) -> bool:
        """Check if a dataset exists in the connected project.
        Args:
            conn (bigquery.Client): Active BigQuery connection
            dataset (str): Dataset name

        Returns:
            bool: True if dataset exists, False otherwise
        """
        try:
            conn.get_dataset(f"{conn.project}.{dataset}")
            return True
        except NotFound:
            return False
        except Exception as e:
            raise DatabaseConnectionError(f"Error checking dataset existence: {e}")

    def table_exists(self, conn, dataset: str, table_name: str) -> bool:
        """Check if a table exists in the connected project.
        Args:
            conn (bigquery.Client): Active BigQuery connection
            dataset (str): Dataset name
            table (str): Table name

        Returns:
            bool: True if table exists, False otherwise
        """
        try:
            table_ref = f"{conn.project}.{dataset}.{table_name}"
            conn.get_table(table_ref)
            return True
        except NotFound:
            return False
        except Exception as e:
            raise DatabaseConnectionError(f"Error checking table existence: {e}")

    def get_table_hashes(
        self, conn, datasets: List[str], table_names: List[str], location: Optional[str] = None
    ) -> Dict[Tuple[str, str], Optional[int]]:
        """Calculate hash values for specified tables across datasets using fingerprinting.

        Computes a deterministic hash for each table by applying BIT_XOR of
        FARM_FINGERPRINT on the TO_JSON_STRING representation of all rows.

        Args:
            conn (bigquery.Client): Active BigQuery connection
            datasets (List[str]): List of dataset names to query
            table_names (List[str]): List of table names to hash within each dataset
            location (Optional[str]): Override dataset location (uses dataset location if None)

        Returns:
            Dict[Tuple[str, str], Optional[int]]: Dictionary mapping (dataset, table_name)
                to hash value. Missing or inaccessible tables return None.
        """
        results = {}

        datasets_by_location = defaultdict(list)
        for dataset in datasets:
            try:
                resolved_location = location or self.get_dataset_location(conn, dataset)
                if resolved_location:
                    datasets_by_location[resolved_location].append(dataset)
            except DatabaseConnectionError:
                continue

        for loc, dataset_list in datasets_by_location.items():
            for dataset in dataset_list:
                for table_name in table_names:
                    try:
                        if not self.table_exists(conn, dataset, table_name):
                            continue

                        table_ref = f"{conn.project}.{dataset}.{table_name}"
                        query_job = conn.query(
                            f"""SELECT BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) 
                            FROM `{table_ref}` AS t""",
                            location=loc,
                        )
                        result = list(query_job.result())
                        hash_value = result[0][0] if result else None
                        results[(dataset, table_name)] = hash_value
                    except (NotFound, Forbidden, BadRequest) as e:
                        continue
                    except Exception as e:
                        raise DatabaseConnectionError(
                            f"Error hashing table {dataset}.{table_name}: {e}"
                        )

        return results

    def group_columns_by_type(self, conn, dataset: str, table_name: str) -> Dict[str, List[str]]:
        """Group table columns by their BigQuery data type categories.

        Categorizes columns into four profiling groups:
            - numerical: int64, numeric, decimal, float64, etc.
            - text: string
            - date: date, timestamp, datetime, time
            - bool: boolean, bool

        Args:
            conn (bigquery.Client): Active BigQuery connection
            dataset (str): Dataset name
            table_name (str): Table name

        Returns:
            Dict[str, List[str]]: Dictionary with keys 'numerical', 'text', 'date', 'bool'
            each containing list of column names. Returns empty lists on error.
        """
        numerical_types = {
            "int64",
            "int",
            "smallint",
            "integer",
            "bigint",
            "tinyint",
            "byteint",
            "numeric",
            "decimal",
            "bignumeric",
            "bigdecimal",
            "float64",
            "float",
        }
        text_types = {"string"}
        date_types = {"date", "timestamp", "datetime", "time"}
        bool_types = {"boolean", "bool"}

        try:
            table_ref = f"{conn.project}.{dataset}.{table_name}"
            table = conn.get_table(table_ref)
            groups = {"numerical": [], "text": [], "date": [], "boolean": []}
            for field in table.schema:
                ftype = field.field_type.lower()
                if ftype in numerical_types:
                    groups["numerical"].append(field.name)
                elif ftype in text_types:
                    groups["text"].append(field.name)
                elif ftype in date_types:
                    groups["date"].append(field.name)
                elif ftype in bool_types:
                    groups["boolean"].append(field.name)
            return groups
        except Exception as e:
            raise DatabaseConnectionError(f"Error grouping columns by type: {e}")

    def available_dtypes(self, conn, dataset: str, table_name: str) -> Optional[set]:
        """Get unique set of BigQuery data types present in a table's schema.

        Args:
            conn (bigquery.Client): Active BigQuery connection
            dataset (str): Dataset name
            table_name (str): Table name

        Returns:
            Optional[set]: Set of field_type strings (e.g., {'STRING', 'INT64', 'DATE'})
                Returns None if table/dataset doesn't exist or schema inaccessible
        """
        try:
            if not (
                self.table_exists(conn, dataset, table_name) and self.dataset_exists(conn, dataset)
            ):
                return None

            table_ref = f"{conn.project}.{dataset}.{table_name}"
            table = conn.get_table(table_ref)
            return set(field.field_type for field in table.schema)
        except Exception as e:
            raise DatabaseConnectionError(f"Error getting available dtypes: {e}")

    def get_group_data(
        self,
        conn,
        datasets: List[str],
        table_names: List[str],
        batch_size: int = 50000,
        location: Optional[str] = None,
    ) -> Generator[Tuple[str, pd.DataFrame], None, None]:
        """Retrieve column data in batches grouped by type for profiling.

        Fetches data from specified tables, grouping columns by their data type category
        (numerical, text, date, boolean). Yields each group as a DataFrame using batched
        queries to handle large tables efficiently.
        Skips tables that don't exist or have no data for a column group.

        Args:
            conn (bigquery.Client): Active BigQuery connection
            datasets (List[str]): List of dataset names
            table_names (List[str]): List of table names to process
            batch_size (int): Number of rows per query batch (default: 50000)
            location (Optional[str]): Override dataset location (uses dataset location if None)

        Yields:
            Generator[Tuple[str, pd.DataFrame], None, None]: Tuple of (key, DataFrame)
                where key format is "project.dataset.table.group" and DataFrame contains
                the grouped columns' data.
        """
        datasets_by_location = defaultdict(list)
        for dataset in datasets:
            try:
                resolved_location = location or self.get_dataset_location(conn, dataset)
                if resolved_location:
                    datasets_by_location[resolved_location].append(dataset)
            except DatabaseConnectionError:
                continue

        for loc, dataset_list in datasets_by_location.items():
            for dataset in dataset_list:
                for table_name in table_names:
                    try:
                        if not self.table_exists(conn, dataset, table_name):
                            continue

                        dtypes = self.available_dtypes(conn, dataset, table_name)
                        if not dtypes:
                            continue

                        table_ref = f"{conn.project}.{dataset}.{table_name}"
                        table = conn.get_table(table_ref)
                        total_rows = table.num_rows

                        groups = self.group_columns_by_type(conn, dataset, table_name)

                        for group, columns in groups.items():
                            if not columns:
                                continue

                            key = f"{table_ref}.{group}"
                            col_str = ", ".join([f"`{col}`" for col in columns])

                            def fetch_batches():
                                for offset in range(0, total_rows, batch_size):
                                    query = f"""SELECT {col_str} FROM `{table_ref}` 
                                    LIMIT {batch_size} OFFSET {offset}"""
                                    try:
                                        query_job = conn.query(query, location=loc)
                                        df = query_job.to_dataframe()
                                        if df.empty:
                                            break
                                        yield df
                                    except Exception as e:
                                        raise DatabaseConnectionError(
                                            f"Error fetching batch data: {e}"
                                        )

                            batches = list(fetch_batches())
                            if batches:
                                group_df = pd.concat(batches, ignore_index=True)
                                yield key, group_df
                    except Exception as e:
                        raise DatabaseConnectionError(
                            f"Error getting group data for {dataset}.{table_name}: {e}"
                        )
