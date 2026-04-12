from connector.db_connector import PostgresConn, SnowflakeConn, MySQLConnector, BigQueryConn
from log import get_ingest_logger

data_logger = get_ingest_logger()

class ReadTable:
    def __init__(self, conn_type):
        self.conn_type = conn_type

    def read_table(self):
        pass