# 📊🚦 Driftmon: Data Drift Detection & Monitoring Tool

![PyPI](https://img.shields.io/pypi/v/driftmon) ![Python](https://img.shields.io/badge/python-3.11.9-blue)
![License](https://img.shields.io/pypi/l/driftmon)

> Driftmon is a practical, extensible tool for profiling tables, detecting drift, and visualizing change over time across database and warehouse environments.

---

## 1. Overview

Driftmon monitors table snapshots over time, compares current data to historical baselines, and surfaces drift using statistical tests, hash comparisons, and interactive dashboard views. It supports multiple table types and column categories, with alerts and visualization for operational use.
<img width="1905" height="897" alt="image" src="https://github.com/user-attachments/assets/60d78400-7c70-4b1b-8e69-e8f175218c21" />


---

## 2. Core Capabilities

- Baseline profiling for tables and columns
- Historical monitoring and comparison of snapshots
- Drift detection using statistical tests and distribution measures
- Support for multiple database platforms and schemas/datasets
- Streamlit dashboard for drift exploration and timeline review
- Email and Slack alerting
- CLI-driven workflows for setup, monitoring, and inspection

---

## 3. How Driftmon Works

1. A table snapshot is profiled and stored in `monitoring_history.jsonl`.
2. Each new run adds a new record with hashes and per-column metrics.
3. Drift detection compares the latest snapshot against the previous one.
4. If hashes differ, statistical tests are applied per column type.
5. The dashboard visualizes trends, comparisons, and severity levels.

---

## 4. Supported Column Categories and Classification

Driftmon classifies columns using the `detected_type` field in the stored metrics.

### 4.1 Numerical
Used for continuous or discrete numeric columns.

Typical metrics:
- `bin_edges`
- `expected_percents`

### 4.2 Categorical
Used for low-cardinality categorical columns.

Typical metrics:
- `full_counts`
- top category frequencies
- category proportions

### 4.3 Categorical High Cardinality
Used for categorical-like columns with many distinct values.

Handled similarly to categorical columns, but often with PSI-style comparison.

### 4.4 Unstructured Text
Used for text-heavy fields where exact category frequencies are less useful.

Typical metrics:
- `avg_character_length`
- `std_character_length`
- `unique_values`
- `uniqueness_ratio`

### 4.5 Date
Used for date or timestamp-like columns.

Typical metrics:
- `min`
- `max`
- `count`
- `null_counts`

### 4.6 Boolean
Used for true/false-like fields.

Typical metrics:
- `count`
- `nulls`
- `value_counts`

### 4.7 Unknown / Unsupported
Columns that do not match a supported `detected_type` are surfaced as unknown.

---

## 5. Statistical Tests and Drift Logic

### 5.1 Numerical Columns
**Metric used:** Population Stability Index (PSI)

- PSI compares bucketed distributions between snapshots.
- Lower values indicate stable distributions.
- Typical interpretation:
  - `< 0.10` stable
  - `0.10–0.25` moderate drift
  - `>= 0.25` significant drift

**Dashboard use:**
- PSI trend over time
- Previous vs latest distribution comparison

### 5.2 Categorical Columns
**Metric used:** Jensen-Shannon Divergence (JSD) in the dashboard, and Pearson Chi-Square in detection logic

- The dashboard computes JSD from category probability distributions.
- Detection logic uses:
  - **Pearson Chi-Square test** for standard categorical columns
  - **PSI** for categorical high-cardinality columns

### 5.3 Unstructured Text Columns
**Tests used:** Z-test for average text length, plus uniqueness-ratio comparison

- Average character length is compared using a z-score-based test.
- Uniqueness ratio is compared using an absolute threshold.
- Drift is flagged when either signal changes meaningfully.

### 5.4 Boolean Columns
**Test used:** Two-sample proportions z-test

- Compares the proportion of `True`/`False` values across snapshots.
- Useful for detecting changes in binary distributions.

### 5.5 Date Columns
**Logic used:** Range shift / data completeness checks

- Compares latest min/max date values against the previous snapshot.
- Flags:
  - backfilled or stale data
  - large gaps
  - insufficient data / zero-epoch values
- Also tracks completeness through null counts.

### 5.6 Hash-Based Change Detection
Before statistical comparison, Driftmon checks whether the latest table hash differs from the previous one.

- If hashes match, drift is unlikely.
- If hashes differ, statistical drift analysis is performed.
- The dashboard and detector use hash history to reduce unnecessary computation.
<img width="1120" height="812" alt="image" src="https://github.com/user-attachments/assets/41eb8e88-0c9c-417e-a12b-b384fb86b07b" />

## 6. Dashboard Views

The Streamlit dashboard provides:

- PSI trends for numerical columns
- JSD trends for categorical columns
- Text-length and uniqueness trend views
- Date range evolution and completeness metrics
- Boolean proportion charts
- Timeline of monitoring runs
- Raw metric inspection for each selected column
<img width="1559" height="888" alt="image" src="https://github.com/user-attachments/assets/e2e737c2-c2af-45d4-955e-dde3073e0eea" />


<img width="1920" height="921" alt="image" src="https://github.com/user-attachments/assets/f48e4940-0f82-4ce7-a4a8-a3ef0f1ad8ae" />


<img width="1588" height="667" alt="image" src="https://github.com/user-attachments/assets/d8a49290-d155-489e-a8b7-f18dda326e42" />



---

## 7. Hash Retrieval Strategy and `mmap` Trade-offs

Driftmon uses `mmap` when reading the latest hashes from the history file.

### Why `mmap` was used
- Faster reverse-style scanning from the end of large files
- Lower overhead than loading the full file into Python objects
- Efficient for newline-delimited JSON history logs
- Useful when only the most recent entries are needed

### Trade-offs
- Best suited for local, seekable files
- Adds implementation complexity compared to normal line iteration
- Less portable for non-file-like sources such as streams
- Mapping very large files still depends on OS virtual memory behavior
- Reverse scanning logic is more specialized than a simple forward parser

### Practical impact
This approach is efficient for monitoring history files that grow over time, where the most recent hashes are usually the only values needed for drift comparison.

---

## 8. Architecture
```
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
---

## 9. Installation

```bash
pip install driftmon
```

Or from source:

```bash
git clone https://github.com/Human-Gechi/data_drift_detector.git
cd data_drift_detector
pip install -e .
```

---

## 10. CLI Commands

| Command      | Description                                      |
|--------------|--------------------------------------------------|
| configure    | Set up source connection and alerting settings   |
| monitoring   | Profile and store baseline statistics            |
| detect-drift | Run drift detection and generate reports         |
| dashboard    | Launch the Streamlit dashboard                   |
| help         | Show CLI help                                    |
| exit/quit    | Exit the CLI                                     |

---

## 11. Quick Start

### CLI Preview
![Driftmon CLI preview](image.png)

### 1. Configure
```bash
driftmon configure
```

### 2. Profile and Monitor
```bash
driftmon monitoring
```

### 3. Detect Drift
```bash
driftmon detect-drift
```

### 4. Launch Dashboard
```bash
driftmon dashboard
```

---

## 12. Supported Data Sources

- Google BigQuery
- Snowflake
- MySQL
- PostgreSQL

---

## 13. Example Usage

### Using Context Managers

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

### Without Context Managers

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

---

## 14. Contributing

Contributions are welcome.

Guidelines:
- follow existing code style
- add tests for behavior changes
- update docs when behavior changes
- keep changes focused and reviewable

---

## 15. Author

**Ogechukwu Okoli**

GitHub: [Human-Gechi](https://github.com/Human-Gechi)
Email: okoliogechi74@gmail.com

---
## 16. Thank you for using Driftmon
Stay ahead of data drift and keep pipelines reliable.
