from unittest.mock import MagicMock, patch

import pytest

from src.connector.postgres_connector import PostgresConn


@pytest.fixture
def postgres_conn():
    conn = PostgresConn(
        host="localhost", port=5432, user="test_user", password="test_password", database="test_db"
    )
    return conn


@patch("src.connector.postgres_connector.psycopg2.connect")
def test__enter_and__exit(mock_conn, postgres_conn):
    mock_conn.return_value = MagicMock()
    mock_conn_instance = MagicMock()
    mock_conn.return_value = mock_conn_instance

    with postgres_conn as conn:
        assert conn == mock_conn_instance
        assert hasattr(postgres_conn, "conn")
    mock_conn_instance.close.assert_called_once()
