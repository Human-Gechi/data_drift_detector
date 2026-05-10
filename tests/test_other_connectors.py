from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from driftmon.connector.mysql_connector import MySQLConn
from driftmon.connector.postgres_connector import PostgresConn
from driftmon.connector.snowflake_connector import SnowflakeConn


@pytest.fixture
def postgres_conn():
    return PostgresConn(
        host="localhost", port=5432, user="test_user", password="test_password", database="test_db"
    )


@pytest.fixture
def mysql_conn():
    return MySQLConn(
        host="localhost", port=3306, user="test_user", password="test_password", database="test_db"
    )


@pytest.fixture
def snowflake_conn():
    return SnowflakeConn(
        user="test_user",
        password="test_password",
        account="test_account",
        database="test_db",
        warehouse="test_warehouse",
        schema="my_schema",
    )


@patch("src.connector.snowflake_connector.snowflake.connector.connect")
@patch("src.connector.postgres_connector.psycopg2.connect")
@patch("src.connector.mysql_connector.MySQLdb.connect")
def test__enter_and__exit(
    mock_mysql_connect,
    mock_postgres_connect,
    mock_snowflake_connect,
    postgres_conn,
    mysql_conn,
    snowflake_conn,
):
    mock_pg_conn = MagicMock()
    mock_postgres_connect.return_value = mock_pg_conn

    mock_mysql_conn = MagicMock()
    mock_mysql_connect.return_value = mock_mysql_conn

    mock_snow_conn = MagicMock()
    mock_snowflake_connect.return_value = mock_snow_conn

    with postgres_conn as conn:
        assert conn == mock_pg_conn
        assert hasattr(postgres_conn, "conn")
    mock_pg_conn.close.assert_called_once()

    with mysql_conn as conn:
        assert conn == mock_mysql_conn
        assert hasattr(mysql_conn, "conn")
    mock_mysql_conn.close.assert_called_once()

    with snowflake_conn as conn:
        assert conn == mock_snow_conn
        assert hasattr(snowflake_conn, "conn")
    mock_snow_conn.close.assert_called_once()


@patch("src.connector.snowflake_connector.snowflake.connector.connect")
@patch("src.connector.postgres_connector.psycopg2.connect")
@patch("src.connector.mysql_connector.MySQLdb.connect")
def test_get_table_info(
    mock_mysql_connect,
    mock_postgres_connect,
    mock_snowflake_connect,
    postgres_conn,
    mysql_conn,
    snowflake_conn,
):
    for conn, mock_connect in [
        (postgres_conn, mock_postgres_connect),
        (mysql_conn, mock_mysql_connect),
        (snowflake_conn, mock_snowflake_connect),
    ]:
        mock_db_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("col_numeric", "integer"),
            ("col_text", "text"),
            ("col_bool", "boolean"),
        ]

        with conn as db_conn:
            if conn is snowflake_conn:
                result = conn.get_table_info(db_conn, table_names="my_table", schemas="my_schema")
                expected = {
                    ("my_schema", "my_table"): [
                        ("col_numeric", "integer"),
                        ("col_text", "text"),
                        ("col_bool", "boolean"),
                    ]
                }
            else:
                result = conn.get_table_info(db_conn, table_names="my_table", schema="my_schema")
                expected = {
                    ("my_schema", "my_table"): [
                        ("col_numeric", "integer"),
                        ("col_text", "text"),
                        ("col_bool", "boolean"),
                    ]
                }
            assert result == expected
            mock_cursor.execute.assert_called_once()
            mock_cursor.close.assert_called_once()


@patch("src.connector.snowflake_connector.snowflake.connector.connect")
@patch("src.connector.postgres_connector.psycopg2.connect")
@patch("src.connector.mysql_connector.MySQLdb.connect")
def test_group_tables_by_type(
    mock_mysql_connect,
    mock_postgres_connect,
    mock_snowflake_connect,
    postgres_conn,
    mysql_conn,
    snowflake_conn,
):
    for conn, mock_connect in [
        (postgres_conn, mock_postgres_connect),
        (mysql_conn, mock_mysql_connect),
        (snowflake_conn, mock_snowflake_connect),
    ]:
        mock_db_conn = MagicMock()
        mock_connect.return_value = mock_db_conn

        conn.get_table_info = MagicMock(
            return_value={
                ("my_schema", "my_table"): [
                    ("col_numeric", "integer"),
                    ("col_text", "text"),
                    ("col_boolean", "boolean"),
                ]
            }
        )
        groups = {
            ("my_schema", "my_table"): {
                "numerical": ["col_numeric"],
                "text": ["col_text"],
                "date": [],
                "boolean": ["col_boolean"],
            }
        }
        schema = "my_schema"
        table_names = "my_table"
        with conn as db_conn:
            if conn is snowflake_conn:
                result = conn.group_tables_by_type(db_conn, table_names, schemas=schema)
            else:
                result = conn.group_tables_by_type(db_conn, table_names, schema)
            assert result == groups


@patch("src.connector.snowflake_connector.snowflake.connector.connect")
@patch("src.connector.postgres_connector.psycopg2.connect")
@patch("src.connector.mysql_connector.MySQLdb.connect")
def test_table_exists(
    mock_mysql_connect,
    mock_postgres_connect,
    mock_snowflake_connect,
    postgres_conn,
    mysql_conn,
    snowflake_conn,
):
    for conn, mock_connect in [
        (postgres_conn, mock_postgres_connect),
        (mysql_conn, mock_mysql_connect),
        (snowflake_conn, mock_snowflake_connect),
    ]:
        mock_db_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (1,)

        with conn as db_conn:
            if conn is snowflake_conn:
                result = conn.table_exists(db_conn, schema="my_schema", table="my_table")
            else:
                result = conn.table_exists(db_conn, schema="my_schema", table="my_table")
            assert result is True
            mock_cursor.execute.assert_called_once()
            mock_cursor.close.assert_called_once()


@patch("src.connector.snowflake_connector.snowflake.connector.connect")
@patch("src.connector.postgres_connector.psycopg2.connect")
@patch("src.connector.mysql_connector.MySQLdb.connect")
def test_get_table_in_schema(
    mock_mysql_connect,
    mock_postgres_connect,
    mock_snowflake_connect,
    postgres_conn,
    mysql_conn,
    snowflake_conn,
):
    for conn, mock_connect in [
        (postgres_conn, mock_postgres_connect),
        (mysql_conn, mock_mysql_connect),
        (snowflake_conn, mock_snowflake_connect),
    ]:
        mock_db_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_db_conn
        mock_db_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [("my_table1",), ("my_table2",)]

        with conn as db_conn:
            if conn is snowflake_conn:
                result = [t[1] for t in conn.get_tables_in_schemas(db_conn, schemas="my_schema")]
                assert result == ["my_table1", "my_table2"]
            else:
                result = conn.get_tables_in_schema(db_conn, schema="my_schema")
                assert result == ["my_table1", "my_table2"]
            mock_cursor.execute.assert_called_once()
            mock_cursor.close.assert_called_once()


@patch("src.connector.snowflake_connector.snowflake.connector.connect")
def test_get_table_hashes_snowflake(mock_connect, snowflake_conn):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    snowflake_conn.table_exists = MagicMock(return_value=True)
    mock_cursor.fetchone.side_effect = [
        (1234567891011121389,),
        (1234567891011121314,),
    ]

    schema = "my_schema"
    table_names = ["my_table1", "my_table2"]

    with snowflake_conn as conn:
        results = snowflake_conn.get_table_hashes(conn, table_names, schemas=schema)
        assert results == {
            ("my_schema", "my_table1"): 1234567891011121389,
            ("my_schema", "my_table2"): 1234567891011121314,
        }
        assert mock_cursor.close.call_count == 1


@patch("src.connector.postgres_connector.psycopg2.connect")
def test_get_table_hashes_postgres(mock_connect, postgres_conn):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    postgres_conn.table_exists = MagicMock(return_value=True)
    mock_cursor.fetchone.side_effect = [
        (1234567891011121389,),
        (None,),
        (1234567891011121314,),
        (None,),
    ]

    batch_size = 2
    schema = "my_schema"
    table_names = ["my_table1", "my_table2"]

    with postgres_conn as conn:
        results = postgres_conn.get_table_hashes(conn, table_names, schema, batch_size)
        assert results == {
            ("my_schema", "my_table1"): 1234567891011121389,
            ("my_schema", "my_table2"): 1234567891011121314,
        }
        assert mock_cursor.close.call_count == 1


@patch("src.connector.mysql_connector.MySQLdb.connect")
def test_get_table_hashes_mysql(mock_connect, mysql_conn):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mysql_conn.table_exists = MagicMock(return_value=True)
    mock_cursor.fetchone.return_value = ("my_schema.my_table", 1234567891011121389)

    schema = "my_schema"
    table_names = "my_table1"

    with mysql_conn as conn:
        results = mysql_conn.get_table_hashes(conn, table_names, schema)
        assert results == {("my_schema", "my_table1"): 1234567891011121389}
        assert mock_cursor.close.call_count == 1


@patch("src.connector.snowflake_connector.snowflake.connector.connect")
@patch("src.connector.postgres_connector.psycopg2.connect")
@patch("src.connector.mysql_connector.MySQLdb.connect")
def test_get_group_data(
    mock_mysql_connect,
    mock_postgres_connect,
    mock_snowflake_connect,
    postgres_conn,
    mysql_conn,
    snowflake_conn,
):
    for conn in [postgres_conn, mysql_conn, snowflake_conn]:
        conn.table_exists = MagicMock(return_value=True)
        conn.get_table_info = MagicMock(
            return_value={
                ("my_schema", "my_table1"): [
                    ("col_numeric", "integer"),
                    ("col_text", "text"),
                    ("col_boolean", "boolean"),
                ],
                ("my_schema", "my_table2"): [
                    ("col_numeric", "integer"),
                    ("col_text", "text"),
                    ("col_boolean", "boolean"),
                ],
            }
        )
        conn.get_tables_in_schema = MagicMock(return_value=["my_table1", "my_table2"])
        conn.group_tables_by_type = MagicMock(
            return_value={
                ("my_schema", "my_table1"): {
                    "numerical": ["col_numeric"],
                    "text": ["col_text"],
                    "date": [],
                    "boolean": ["col_boolean"],
                },
                ("my_schema", "my_table2"): {
                    "numerical": ["col_numeric"],
                    "text": ["col_text"],
                    "date": [],
                    "boolean": ["col_boolean"],
                },
            }
        )

        df = pd.DataFrame(
            {"col_numeric": [1, 2], "col_text": ["Alex", "Ogechi"], "col_boolean": [True, False]}
        )

        conn.get_group_data = MagicMock(
            return_value=iter(
                [
                    ("my_schema.my_table1.numerical", df[["col_numeric"]]),
                    ("my_schema.my_table2.numerical", df[["col_numeric"]]),
                    ("my_schema.my_table1.text", df[["col_text"]]),
                    ("my_schema.my_table2.text", df[["col_text"]]),
                    ("my_schema.my_table1.boolean", df[["col_boolean"]]),
                    ("my_schema.my_table2.boolean", df[["col_boolean"]]),
                ]
            )
        )

        with conn as db_conn:
            results = list(
                conn.get_group_data(
                    db_conn, schemas="my_schema", table_names=["my_table1", "my_table2"]
                )
            )
            assert results[0][0] == "my_schema.my_table1.numerical"
            assert results[0][1].equals(df[["col_numeric"]])
            assert results[1][0] == "my_schema.my_table2.numerical"
            assert results[1][1].equals(df[["col_numeric"]])
            assert results[2][0] == "my_schema.my_table1.text"
            assert results[2][1].equals(df[["col_text"]])
            assert results[3][0] == "my_schema.my_table2.text"
            assert results[3][1].equals(df[["col_text"]])
            assert results[4][0] == "my_schema.my_table1.boolean"
            assert results[4][1].equals(df[["col_boolean"]])
            assert results[5][0] == "my_schema.my_table2.boolean"
            assert results[5][1].equals(df[["col_boolean"]])
