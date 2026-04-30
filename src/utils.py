import time


class TimedConnection:
    def __init__(self, conn, timeout=600):
        self.conn = (conn,)
        self.created_at = time.time()
        self.timeout = timeout

    def is_valid(self):
        return (time.time()) - self.created_at < self.timeout

    def get_conn(self):
        if self.is_valid():
            return self.conn
        else:
            raise Exception("Connection expired")
