import time


class TimedConnection:
    "Mimicks Connection timeing to differen connectors"

    def __init__(self, conn, timeout=600):
        self.conn = conn
        self.created_at = time.time()
        self.timeout = timeout

    def is_valid(self):
        """Check if connection is valid (active and not exceeding configured timeout threshold)."""
        return (time.time()) - self.created_at < self.timeout

    def get_conn(self):
        """Retrieve conection object"""
        if self.is_valid():
            return self.conn
        else:
            raise Exception("Connection expired")
