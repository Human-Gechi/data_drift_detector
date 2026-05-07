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
def test__enter_and__exit(mock_connect, postgres_conn):
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn

    with postgres_conn as conn:
        assert conn == mock_conn
        assert hasattr(postgres_conn, "conn")
    mock_conn.close.assert_called_once()


@patch("src.connector.postgres_connector.psycopg2.connect")
def test_get_table_info(mock_connect, postgres_conn):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mock_cursor.fetchall.return_value = [("col_numeric", "integer"), ("col_text", "text")]

    with postgres_conn as conn:
        result = postgres_conn.get_table_info(conn, table_names="my_table", schema="my_schema")
        assert result == {
            ("my_schema", "my_table"): [("col_numeric", "integer"), ("col_text", "text")]
        }
        mock_cursor.execute.assert_called_once()
        mock_cursor.close.assert_called_once()


@patch("src.connector.postgres_connector.psycopg2.connect")
def test_group_tables_by_type(mock_connect, postgres_conn):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    postgres_conn.get_table_info = MagicMock(
        return_value={("my_schema", "my_table"): [("col_numeric", "integer"), ("col_text", "text")]}
    )

    groups = {
        ("my_schema", "my_table"): {
            "numerical": ["col_numeric"],
            "text": ["col_text"],
            "date": [],
            "boolean": [],
        }
    }
    schema = "my_schema"
    table = "my_table"

    with postgres_conn as conn:
        result = postgres_conn.group_tables_by_type(conn, table, schema)
        assert result == groups


@patch("src.connector.postgres_connector.psycopg2.connect")
def test_table_exists(mock_connect, postgres_conn):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mock_cursor.fetchone.return_value = True

    with postgres_conn as conn:
        result = postgres_conn.table_exists(conn, schema="my_schema", table="my_table")
        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_cursor.close.assert_called_once()
