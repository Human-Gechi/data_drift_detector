from unittest.mock import MagicMock, patch

import pytest

from src.connector.bigquery_connector import BigQueryConn


@pytest.fixture
def bigquery_conn():
    conn = BigQueryConn(project="test-project", credentials_path="fake.json")
    return conn


@patch("src.connector.bigquery_connector.service_account.Credentials.from_service_account_file")
@patch("src.connector.bigquery_connector.bigquery.Client")
def test__enter_and__exit(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client.return_value = mock_client_instance

    with bigquery_conn as client:
        assert client == mock_client_instance
        assert hasattr(bigquery_conn, "conn")
    mock_client_instance.close.assert_called_once()


@patch("src.connector.bigquery_connector.service_account.Credentials.from_service_account_file")
@patch("src.connector.bigquery_connector.bigquery.Client")
def test_get_dataset_location(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance

    mock_dataset = MagicMock()
    mock_dataset.location = "US"
    mock_client_instance.get_dataset.return_value = mock_dataset

    with bigquery_conn as client:
        location = bigquery_conn.get_dataset_location(client, "my_dataset")
        assert location == "US"
        mock_client_instance.get_dataset.assert_called_once_with("test-project.my_dataset")


@patch("src.connector.bigquery_connector.service_account.Credentials.from_service_account_file")
@patch("src.connector.bigquery_connector.bigquery.Client")
def test_dataset_exists(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance

    mock_client_instance.get_dataset.return_value = True

    with bigquery_conn as client:
        bigquery_conn.dataset_exists(client, "my_dataset")
        mock_client_instance.get_dataset.assert_called_once_with("test-project.my_dataset")


@patch("src.connector.bigquery_connector.service_account.Credentials.from_service_account_file")
@patch("src.connector.bigquery_connector.bigquery.Client")
def test_dataset_not_exists(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance
    mock_client_instance.get_dataset.side_effect = Exception(False)

    with bigquery_conn as client:
        result = bigquery_conn.dataset_exists(client, "my_dataset")
        assert result is False
        mock_client_instance.get_dataset.assert_called_once_with("test-project.my_dataset")


@patch("src.connector.bigquery_connector.service_account.Credentials.from_service_account_file")
@patch("src.connector.bigquery_connector.bigquery.Client")
def test_table_exists(mock_client, mock_creds, bigquery_conn):
    mock_creds.return_value = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.project = "test-project"
    mock_client.return_value = mock_client_instance

    with bigquery_conn as client:
        result = bigquery_conn.table_exists(client, "my_dataset", "my_table")
        assert result is True
        mock_client_instance.get_table.assert_called_once_with("test-project.my_dataset.my_table")
