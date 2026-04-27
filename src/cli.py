from rich import print
from rich.console import Console
from typer import Option, Typer

app = Typer()
conn_params = {}


@app.callback()
def main(
    db_type: str = Option(..., help="Database type: snowflake, bigquery, mysql, postgres"),
    host: str = Option(None, help="Host (MySQL/Postgres)"),
    port: int = Option(None, help="Port (MySQL/Postgres)"),
    user: str = Option(None, help="Username"),
    password: str = Option(None, help="Password"),
    database: str = Option(None, help="Database name (MySQL/Postgres, Snowflake)"),
    account: str = Option(None, help="Snowflake account"),
    warehouse: str = Option(None, help="Snowflake warehouse"),
    schema: str = Option(None, help="Snowflake schema"),
    role: str = Option(None, help="Snowflake role"),
    project: str = Option(None, help="BigQuery project"),
    credentials_path: str = Option(None, help="BigQuery credentials JSON path"),
):
    global conn_params
    conn_params = {
        "db_type": db_type,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "account": account,
        "warehouse": warehouse,
        "schema": schema,
        "role": role,
        "project": project,
        "credentials_path": credentials_path,
    }


@app.command()
def show_params():
    pass
