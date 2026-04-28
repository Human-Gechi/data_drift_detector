from rich import print
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from typer import Option, Typer

app = Typer()
conn_params = {}


@app.callback()
def main(
    type: str = Option(
        ..., show_default="file", help="Connection type: snowflake, bigquery, mysql, postgres, file"
    ),
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
        "type": type,
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
def monitoring(
    file_path: str = Option(None, help="Path to the file (for file connection type)"),
    output_file: str = Option(
        "monitoring_history.jsonl", help="Output file for monitoring history"
    ),
    table_names: list[str] = Option(None, help="List of table names"),
    schemas: list[str] = Option(None, help="List of schemas"),
    datasets: list[str] = Option(None, help="List of datasets"),
):
    from src.detect.monitoring import append_profiles_hash

    params = {k: v for k, v in conn_params.items() if v is not None and k != "type"}

    result = append_profiles_hash(
        conn_params=params if params else None,
        conn_type=conn_params["type"],
        file_path=file_path,
        output_file=output_file,
        table_names=table_names,
        schemas=schemas,
        datasets=datasets,
    )
    print(result)


@app.command()
def detect_drift():
    pass


if __name__ == "__main__":
    app()
