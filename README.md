# 📊🚦 Driftmon: Data Drift Detection & Monitoring Tool
![PyPI](https://img.shields.io/pypi/v/driftmon) ![Python](https://img.shields.io/badge/python-3.11.9-blue)
![License](https://img.shields.io/pypi/l/driftmon)

> *The idea for Driftmon was inspired while reading **Fundamentals of Data Engineering**, where the importance of monitoring data drift in production systems was emphasized. Driftmon aims to provide a practical, extensible solution for real-world data drift detection, alerting, and monitoring across multiple data platforms.*
---
**Driftmon** is a robust tool for monitoring, detecting, and alerting on data drift in production datasets and database/data warehouse tables. It helps ensure data quality and model reliability by automatically profiling data, detecting unexpected changes, and notifying stakeholders via email and Slack. Driftmon also provides a dashboard for visualizing drift trends and data changes over time.


---

## 🚀 Features

- **Baseline Profiling:** Profiles and stores baseline statistics for each column in your tables.
- **Automated Monitoring:** Periodically monitors new data and compares it to historical baselines.
- **Drift Detection:** Detects drift by comparing hashes and statistical summaries of new data against previously recorded baselines.
- **Multi-Database Support:** Works with BigQuery, Snowflake, MySQL, and PostgreSQL across multiple schemas and datasets.
- **Alerting:** Sends real-time alerts via **Email** and **Slack** when drift is detected.
- **Dashboard:** Interactive dashboard (Streamlit) to visualize data distributions, drift events, and trends.
- **Configurable:** Easily configure data sources, alerting methods, and monitoring targets via CLI.
- **CLI Interface:** Simple command-line interface for setup, monitoring, drift detection, and dashboard launch.

---

```
# Package Architecture

+----------------------+
|   driftmon package   |
|pip install driftmon  |
+----------+-----------+
           |
           v
+----------------------+
|     Connectors       |
| BigQuery / Snowflake |
| MySQL / PostgreSQL   |
+----------+-----------+
           |
           v
+----------------------+
| Baseline Profiling   |
| save_profile()       |
| stats / hashes       |
+----------+-----------+
           |
           v
+----------------------+
|   monitoring.json    |
| stored baseline data |
+----------+-----------+
           |
           v
+----------------------+
|  Drift Detection     |
| detect_drift()       |
| compare baselines    |
+-----+---------+------+
      |         |
      |         v
      |   +-------------+
      |   | Alerts      |
      |   | Email/Slack  |
      |   +-------------+
      |
      v
+----------------------+
|     Dashboard        |
| Streamlit            |
| change history       |
+----------------------+
```
## 📦 Installation

```bash
pip install driftmon
```
OR
```bash
git clone https://github.com/Human-Gechi/data_drift_detector.git
cd data_drift_detector
pip install -e .
```
To initialize dashbaord without entering interactive CLI, call **driftmon-dashboard** and streamlit dashbaord comes up

### 🛠️ CLI Commands
| Command        | Description                                               |
|----------------|-----------------------------------------------------------|
| configure      | Set up data source connection and alerting configuration  |
| monitoring     | Profile baseline statistics and monitor for changes       |
| detect-drift   | Detect drift and send alerts via email/Slack              |
| dashboard      | Launch the Streamlit dashboard for visualization          |
| help           | Show CLI help                                             |
|exit/quit       | exit CLI                                                  |

### ⚡️ Quick Start for CLI
![alt text](image.png)
1. Configure Your Connection & Alerts
Set up your database/data warehouse connection and alerting preferences:
```bash
driftmon configure
```
CLI ARCHITECTURE
```
# CLI Architecture

+----------------------+
|        User          |
+----------+-----------+
           |
           v
+----------------------+
|      Driftmon CLI    |
| configure            |
| monitoring           |
| detect-drift         |
| dashboard            |
+----------+-----------+
           |
           v
+----------------------+
|     params.yaml      |
| CLI configuration    |
| connector settings   |
| alert settings       |
+----------+-----------+
           |
           v
+----------------------+
|     Connector        |
| BigQuery / Snowflake |
| MySQL / PostgreSQL   |
+----------+-----------+
           |
           v
+----------------------+
| Baseline Profiling   |
| create profile       |
| compute stats/hashes |
+----------+-----------+
           |
           v
+----------------------+
|   monitoring.json    |
| baseline storage     |
+----------+-----------+
           |
           v
+----------------------+
|  Drift Detection     |
| compare new data     |
| detect changes       |
+-----+---------+------+
      |         |
      |         v
      |   +-------------+
      |   | Alerting    |
      |   | Email/Slack  |
      |   +-------------+
      |
      v
+----------------------+
|     Dashboard        |
| Streamlit UI         |
| trends / drift time  |
+----------------------+
```
You will be prompted for:

- Connection type (bigquery, snowflake, mysql, postgres)
- Database credentials and details
- Tables/schemas/datasets to monitor
- Alerting method (email, slack, or both)
- Email/Slack credentials

2. Baseline Profiling & Monitoring
Profile your data and store baseline statistics:
```bash
driftmon monitoring
```
This command computes and saves baseline statistics and hashes for your monitored tables.

3. Detect Drift & Send Alerts
Detect data drift by comparing new data to the baseline. Alerts are sent via your configured channels:

```bash
driftmon detect-drift
```
If drift is detected, notifications are sent to your email and/ slack channel.

4. Launch the Dashboard
Visualize drift events, data distributions, and trends:
```bash
driftmon dashboard
```
This launches a Streamlit dashboard in your browser.

🔔 Alerting
- Email Alerts: Configure SMTP server, sender, and recipient. Driftmon sends detailed drift reports to your inbox.
- Slack Alerts: Set up a Slack bot token and channel. Driftmon posts drift notifications directly to your Slack workspace.

🗄️ Supported Data Sources
- Google BigQuery (multiple datasets)
- Snowflake (multiple schemas)
- MySQL
- PostgreSQL
You can monitor multiple tables across different schemas/datasets.
---
# Example arguments for initializing connectors

```python
# PostgreSQL Connector
from driftmon.connector.postgres_connector import PostgresConn

pg_conn = PostgresConn(
    host="your_host",
    port=5432,
    user="your_username",
    password="your_password",
    database="your_database"
)

# MySQL Connector
from driftmon.connector.mysql_connector import MySQLConn

mysql_conn = MySQLConn(
    host="your_host",
    port=3306,
    user="your_username",
    password="your_password",
    database="your_database"
)

# Snowflake Connector
from driftmon.connector.snowflake_connector import SnowflakeConn

sf_conn = SnowflakeConn(
    user="your_username",
    password="your_password",
    account="your_account",
    warehouse="your_warehouse",
    database="your_database",
    schema="your_schema"
)
```
---
## 🧪 Code Samples : Using Driftmon with Context Managers

This example demonstrates best practices using context managers and modular functions for connecting, profiling, drift detection, and sending alerts.

```python
from driftmon.connector.bigquery_connector import BigQueryConn
from driftmon.detect.monitoring import save_profile
from driftmon.detect.drift_detector import detect_drift
from driftmon.alerts.email_alert import Email

def export_data(conn, dataset, tables):
    result = conn.get_group_data(datasets=dataset, table_names=tables)
    for key, df in result:
        df.to_csv(f"{key}.csv", index=False)

def profile_and_detect(conn, dataset, tables):
    save_profile(conn_type="bigquery", connector=conn, datasets=dataset, table_names=tables)
    return detect_drift(table_names=tables)

def send_drift_email(drift_report, sender, password, receiver):
    email = Email(
        sender=sender,
        password=password,
        receiver=receiver,
        drift_report=drift_report
    )
    email.send_email()

tables = "test_table2"
dataset = "1306_data"

with BigQueryConn(
    project="meta-spirit-494622-f5",
    credentials_path="meta-spirit-494622-f5-82b375b04e9e.json"
) as conn:
    export_data(conn, dataset, tables)
    drift_report = profile_and_detect(conn, dataset, tables)
    send_drift_email(
        drift_report,
        sender="sender@gmail.com",
        password="your-password",
        receiver="receiver@gmail.com"
    )
```
---
## 🧪 Example: Using Driftmon Without Context Managers (Using `.connect()` Method)

This example shows how to use Driftmon by explicitly calling the `.connect()` method, without context managers for the biquery connector

```python
from driftmon.connector.bigquery_connector import BigQueryConn
from driftmon.detect.monitoring import save_profile
from driftmon.detect.drift_detector import detect_drift
from driftmon.alerts.email_alert import Email

tables = "test_table2"
dataset = "1306_data"
conn = BigQueryConn(
    project="meta-spirit-494622-f5",
    credentials_path="meta-spirit-494622-f5-82b375b04e9e.json"
)
conn.connect()
try:
    result = conn.get_group_data(datasets=dataset, table_names=tables)
    for key, df in result:
        print(key)
        print(df)
except Exception as e:
    print("Error:", e)

save_profile(conn_type="bigquery", connector=conn, datasets=dataset, table_names=tables)
drift_report = detect_drift(table_names=tables)
email = Email(
    sender="sender@gmail.com",
    password="your-password",
    receiver="receiver@gmail.com",
    drift_report=drift_report
)
email.send_email()
```
## 🤝 Contributing

Contributions are welcome and appreciated!

To contribute to Driftmon:

1. **Fork the repository** on GitHub and clone your fork locally.
2. **Create a new branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
    ```
3. Make your changes and add tests if applicable.
4. Commit your changes with clear messages.
5. Push your branch to your fork:
    ```bash
    git push origin feature/your-feature-name
    ```
6. Open a Pull Request on Github describing your changes

Guidelines to follow when contributing to driftmon
1. Please ensure your code follows the existing style and passes linting as indicated in the pyproject.toml file
2. Add or update documentation as needed.
3. Write tests for new features or bug fixes.
4. Be respectful and constructive in code reviews and discussions.
5. If you find a bug or have a feature request, please open an issue.

Thank you for helping improve Driftmon!

---

#### 👤 Author

**Ogechukwu Okoli**

GitHub: [Human-Gechi](https://github.com/Human-Gechi)

Email: okoliogechi74@gmail.com

**Thank you for using Driftmon!
If you have suggestions, questions, or want to contribute, feel free to reach out or open an issue.
Stay ahead of data drift and keep your data pipelines reliable! 🚦📊**
