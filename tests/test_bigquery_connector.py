from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from google.api_core.exceptions import NotFound

from driftmon.connector.bigquery_connector import BigQueryConn


@pytest.fixture
def bigquery_conn():
    conn = BigQueryConn(project="test-project", credentials_path="fake.json")
    return conn


@patch(
    "driftmon.connector.bigquery_connector.service_account.Credentials.from_service_account_file"
)
@patch("driftmon.connector.bigquery_connector.bigquery.Client")
def test_connect_and_close(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client.return_value = mock_client_instance

    result = bigquery_conn.connect()
    assert result == mock_client_instance
    assert bigquery_conn.conn == mock_client_instance

    bigquery_conn.close()
    mock_client_instance.close.assert_called_once()
    assert bigquery_conn.conn is None


@patch(
    "driftmon.connector.bigquery_connector.service_account.Credentials.from_service_account_file"
)
@patch("driftmon.connector.bigquery_connector.bigquery.Client")
def test_context_manager(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client.return_value = mock_client_instance

    with bigquery_conn as conn:
        assert conn.conn == mock_client_instance
    mock_client_instance.close.assert_called_once()
    assert bigquery_conn.conn is None


@patch(
    "driftmon.connector.bigquery_connector.service_account.Credentials.from_service_account_file"
)
@patch("driftmon.connector.bigquery_connector.bigquery.Client")
def test_get_dataset_location(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance

    mock_dataset = MagicMock()
    mock_dataset.location = "US"
    mock_client_instance.get_dataset.return_value = mock_dataset

    with bigquery_conn as client:
        location = client._get_dataset_location("my_dataset")
        assert location == "US"
        mock_client_instance.get_dataset.assert_called_once_with("test-project.my_dataset")


@patch(
    "driftmon.connector.bigquery_connector.service_account.Credentials.from_service_account_file"
)
@patch("driftmon.connector.bigquery_connector.bigquery.Client")
def test_dataset_exists(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance

    mock_client_instance.get_dataset.return_value = True

    with bigquery_conn as client:
        client._dataset_exists("my_dataset")
        mock_client_instance.get_dataset.assert_called_once_with("test-project.my_dataset")


@patch(
    "driftmon.connector.bigquery_connector.service_account.Credentials.from_service_account_file"
)
@patch("driftmon.connector.bigquery_connector.bigquery.Client")
def test_dataset_not_exists(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance
    mock_client_instance.get_dataset.side_effect = NotFound(False)

    with bigquery_conn as client:
        result = client._dataset_exists("my_dataset")
        assert result is False
        mock_client_instance.get_dataset.assert_called_once_with("test-project.my_dataset")


@patch(
    "driftmon.connector.bigquery_connector.service_account.Credentials.from_service_account_file"
)
@patch("driftmon.connector.bigquery_connector.bigquery.Client")
def test_table_exists(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance

    with bigquery_conn as client:
        result = client._table_exists("my_dataset", "my_table")
        assert result is True
        mock_client_instance.get_table.assert_called_once_with("test-project.my_dataset.my_table")


@patch(
    "driftmon.connector.bigquery_connector.service_account.Credentials.from_service_account_file"
)
@patch("driftmon.connector.bigquery_connector.bigquery.Client")
def test_table_not_exists(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance
    mock_client_instance.get_table.side_effect = NotFound(False)

    with bigquery_conn as client:
        result = client._table_exists("my_dataset", "my_table")
        assert result is False
        mock_client_instance.get_table.assert_called_once_with("test-project.my_dataset.my_table")


@patch(
    "driftmon.connector.bigquery_connector.service_account.Credentials.from_service_account_file"
)
@patch("driftmon.connector.bigquery_connector.bigquery.Client")
def test_get_table_hashes(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance

    bigquery_conn._table_exists = MagicMock(return_value=True)
    bigquery_conn._get_dataset_location = MagicMock(return_value="US")

    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [(-123456789,)]
    mock_client_instance.query.return_value = mock_query_job

    datasets = ["dataset1"]
    tables = ["table1"]

    with bigquery_conn as client:
        result = client._get_table_hashes(datasets, tables)
        assert result == {("dataset1", "table1"): -123456789}
        mock_client_instance.query.assert_called_once()


@patch(
    "driftmon.connector.bigquery_connector.service_account.Credentials.from_service_account_file"
)
@patch("driftmon.connector.bigquery_connector.bigquery.Client")
def test_group_columns_by_type(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance

    mock_field_numeric = MagicMock()
    mock_field_numeric.field_type = "INT64"
    mock_field_numeric.name = "col_numeric"

    mock_field_text = MagicMock()
    mock_field_text.field_type = "STRING"
    mock_field_text.name = "col_text"

    mock_field_date = MagicMock()
    mock_field_date.field_type = "DATE"
    mock_field_date.name = "col_date"

    mock_field_bool = MagicMock()
    mock_field_bool.field_type = "BOOLEAN"
    mock_field_bool.name = "col_bool"

    mock_table = MagicMock()
    mock_table.schema = [
        mock_field_numeric,
        mock_field_text,
        mock_field_date,
        mock_field_bool,
    ]
    mock_client_instance.get_table.return_value = mock_table

    groups = {
        "numerical": ["col_numeric"],
        "text": ["col_text"],
        "date": ["col_date"],
        "boolean": ["col_bool"],
    }
    dataset = "dataset1"
    table = "table1"

    with bigquery_conn as client:
        result = client._group_columns_by_type(dataset, table)
        assert result == groups
        mock_client_instance.get_table.assert_called_once_with("test-project.dataset1.table1")


@patch(
    "driftmon.connector.bigquery_connector.service_account.Credentials.from_service_account_file"
)
@patch("driftmon.connector.bigquery_connector.bigquery.Client")
def test_available_dtypes(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance

    bigquery_conn._table_exists = MagicMock(return_value=True)
    bigquery_conn._dataset_exists = MagicMock(return_value=True)

    mock_field1 = MagicMock()
    mock_field1.field_type = "STRING"
    mock_field2 = MagicMock()
    mock_field2.field_type = "DATE"

    mock_table = MagicMock()
    mock_table.schema = [mock_field1, mock_field2]
    mock_client_instance.get_table.return_value = mock_table

    dtypes = set({"STRING", "DATE"})
    dataset = "my_dataset"
    table = "my_table"

    with bigquery_conn as client:
        result = client._available_dtypes(dataset, table)
        assert result == dtypes
        mock_client_instance.get_table.assert_called_once_with("test-project.my_dataset.my_table")


@patch(
    "driftmon.connector.bigquery_connector.service_account.Credentials.from_service_account_file"
)
@patch("driftmon.connector.bigquery_connector.bigquery.Client")
def test_get_group_data(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance

    bigquery_conn._get_dataset_location = MagicMock(return_value="EU")
    bigquery_conn._table_exists = MagicMock(return_value=True)
    bigquery_conn._available_dtypes = MagicMock(return_value=set({"STRING", "DATE"}))
    bigquery_conn._group_columns_by_type = MagicMock(
        return_value={
            "numerical": [],
            "text": ["col_text"],
            "date": [],
            "boolean": [],
        }
    )

    mock_table = MagicMock()
    mock_table.num_rows = 2
    mock_client_instance.get_table.return_value = mock_table

    df = pd.DataFrame({"col_text": ["Alex", "Ogechi"]})
    mock_query_job = MagicMock()
    mock_client_instance.query.return_value = mock_query_job
    mock_query_job.to_dataframe.return_value = df

    datasets = ["my_dataset"]
    tables = ["my_table"]

    with bigquery_conn as client:
        results = list(client.get_group_data(datasets, tables, batch_size=2))
        assert results
        key, result_df = results[0]
        assert key == "test-project.my_dataset.my_table.text"
        assert result_df.equals(df)
