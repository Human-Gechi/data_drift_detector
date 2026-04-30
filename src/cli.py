import typer
from prompt_toolkit import PromptSession
from rich import print
from rich.progress import Progress, SpinnerColumn, TextColumn
from typer import Option, Typer

from src.config import load_conn_params, save_conn_params
from src.utils import TimedConnection

app = Typer()
timed_conn = None

email_client = None
slack_client = None


def create_connector_and_params(params):
    conn_type = params["type"]
    if conn_type == "bigquery":
        from src.connector.bigquery_connector import BigQueryConn

        connector = BigQueryConn(
            project=params["project"],
            credentials_path=params["credentials_path"],
            location=params["location"],
        )
        return connector
    elif conn_type == "snowflake":
        from src.connector.snowflake_connector import SnowflakeConn

        connector = SnowflakeConn(
            user=params["user"],
            password=params["password"],
            account=params["account"],
            database=params["database"],
            warehouse=params["warehouse"],
            schema=params.get("schema"),
            role=params.get("role"),
        )
        return connector
    elif conn_type == "postgres":
        from src.connector.postgres_connector import PostgresConn

        connector = PostgresConn(
            host=params["host"],
            port=params["port"],
            user=params["user"],
            password=params["password"],
            database=params["database"],
        )
        return connector
    elif conn_type == "mysql":
        from src.connector.mysql_connector import MySQLConn

        connector = MySQLConn(
            host=params["host"],
            port=params["port"],
            user=params["user"],
            password=params["password"],
            database=params["database"],
        )
        return connector
    else:
        raise ValueError(f"Unsupported connection type: {conn_type}")


def setup_alert_clients(tables=None):
    from src.alerts.email_alert import Email
    from src.alerts.slack_alert import Slack

    global email_client, slack_client
    alert_config = load_conn_params("alerts.yaml")
    if alert_config.get("email", {}).get("enabled"):
        email_client = Email(
            sender_email=alert_config["email"]["sender"],
            receiver_email=alert_config["email"]["recipient"],
            sender_password=alert_config["email"]["password"],
            tables=tables or alert_config.get("tables", []),
        )
    if alert_config.get("slack", {}).get("enabled"):
        slack_client = Slack(
            token=alert_config["slack"]["token"],
            channel=alert_config["slack"]["channel"],
            tables=tables or alert_config.get("tables", []),
        )


@app.command()
def configure():
    conn_type = typer.prompt("Connection type (snowflake, bigquery, mysql, postgres)")
    params = {"type": conn_type}
    if conn_type == "bigquery":
        params["project"] = typer.prompt("BigQuery project")
        params["credentials_path"] = typer.prompt("BigQuery credentials JSON path")
        params["location"] = typer.prompt("BigQuery location", default="")
    elif conn_type == "snowflake":
        params["user"] = typer.prompt("Snowflake username")
        params["password"] = typer.prompt("Snowflake password", hide_input=True)
        params["account"] = typer.prompt("Snowflake account")
        params["database"] = typer.prompt("Snowflake database")
        params["warehouse"] = typer.prompt("Snowflake warehouse")
        params["schema"] = typer.prompt("Snowflake schema", default="")
        params["role"] = typer.prompt("Snowflake role", default="")
    elif conn_type == "postgres" or conn_type == "mysql":
        params["host"] = typer.prompt(f"{conn_type.capitalize()} host")
        params["port"] = typer.prompt(f"{conn_type.capitalize()} port", type=int)
        params["user"] = typer.prompt(f"{conn_type.capitalize()} username")
        params["password"] = typer.prompt(f"{conn_type.capitalize()} password", hide_input=True)
        params["database"] = typer.prompt(f"{conn_type.capitalize()} database")
    else:
        typer.echo("Unsupported connection type.")
        raise typer.Exit()

    alert_method = typer.prompt("Alert method (email, slack, both)", default="both")
    email_enabled = alert_method in ("email", "both")
    slack_enabled = alert_method in ("slack", "both")

    email_config = {
        "enabled": email_enabled,
        "smtp_server": typer.prompt("SMTP server for email alerts", default="smtp.gmail.com")
        if email_enabled
        else "",
        "sender": typer.prompt("Sender email address") if email_enabled else "",
        "recipient": typer.prompt("Recipient email address") if email_enabled else "",
        "password": typer.prompt("Sender email password", hide_input=True) if email_enabled else "",
    }

    slack_config = {
        "enabled": slack_enabled,
        "token": typer.prompt("Slack bot token", hide_input=True) if slack_enabled else "",
        "channel": typer.prompt("Slack channel") if slack_enabled else "",
    }

    tables_input = typer.prompt("Comma-separated list of tables to monitor for alerts", default="")
    tables = [t.strip() for t in tables_input.split(",") if t.strip()]

    params["email"] = email_config
    params["slack"] = slack_config
    params["tables"] = tables

    save_conn_params(params)
    print("[green]Connection established.[/green]")


@app.command()
def monitoring(
    output_file: str = Option(
        "monitoring_history.jsonl", help="Output file for monitoring history"
    ),
    table_names: list[str] = Option(None, help="List of table names"),
    schemas: list[str] = Option(None, help="List of schemas"),
    datasets: list[str] = Option(None, help="List of datasets"),
    timeout: int = Option(600, help="Session timeout in seconds"),
):
    from src.detect.monitoring import append_profiles_hash

    params = load_conn_params()
    if not params:
        typer.echo("Run 'configure' first")
        raise typer.Exit()

    global timed_conn
    connector = create_connector_and_params(params)

    if timed_conn is None or not timed_conn.is_valid():
        with connector as conn:
            timed_conn = TimedConnection(conn, timeout=timeout)
            typer.secho(
                f"New connection established. Session valid for {timeout} seconds.",
                fg=typer.colors.BRIGHT_GREEN,
            )
    else:
        typer.secho("Using existing valid connection.", fg=typer.colors.BRIGHT_MAGENTA)

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}")
    ) as progress:
        monitor_task = progress.add_task(description="Running monitoring...", total=None)
        with connector as conn:
            result = append_profiles_hash(
                conn_type=params["type"],
                connector=connector,
                conn=conn,
                output_file=output_file,
                table_names=table_names,
                schemas=schemas,
                datasets=datasets,
            )
            print(result)
        progress.stop_task(monitor_task)


@app.command()
def detect_drift():
    params = load_conn_params()
    tables = params.get("tables", []) if params else []
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}")
    ) as progress:
        detect_alert_task = progress.add_task(
            description="Running drift detection and alerting...", total=None
        )
        setup_alert_clients(tables=tables)
        if email_client:
            email_client.send_email()
        if slack_client:
            slack_client.send_notification()
    typer.secho("Drift detection completed and Email sent!", fg=typer.colors.BRIGHT_GREEN)
    progress.start_task(detect_alert_task)


@app.command()
def dashboard():
    from src.dashboard import main

    pass


def main_shell():
    session = PromptSession()
    typer.secho(
        "Welcome to Data Drift Detector shell! Type 'exit' to quit.", fg=typer.colors.BRIGHT_GREEN
    )
    typer.secho("Available commands:", fg=typer.colors.BRIGHT_CYAN)
    typer.secho(
        "  configure      - Set up a data source connection and alert configs",
        fg=typer.colors.YELLOW,
    )
    typer.secho("  monitoring     - Run monitoring on your data", fg=typer.colors.YELLOW)
    typer.secho("  detect-drift   - Detect data drift and send alerts", fg=typer.colors.RED)
    typer.secho("  help           - Show Typer help", fg=typer.colors.YELLOW)
    typer.secho("  exit           - Quit the shell\n", fg=typer.colors.YELLOW)
    while True:
        try:
            text = session.prompt("dlv> ")
            if text.strip() in {"exit", "quit"}:
                typer.secho("Goodbye!", fg=typer.colors.BRIGHT_YELLOW)
                break
            elif text.strip() == "help":
                app(args=["--help"], standalone_mode=False)
            elif text.strip():
                import shlex

                args = shlex.split(text)
                app(args=args, standalone_mode=False)
        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        except Exception as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        app()
    else:
        main_shell()
