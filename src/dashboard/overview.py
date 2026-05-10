import os
import sys
from collections import Counter
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

st.set_page_config(page_title="Overview Dashboard", page_icon="🔄️", layout="wide")
st.title("Data Drift overview")


def count_dtypes_for_table(records, table_name):
    """Count data types avaialble in each table using Counter()"""
    for record in records:
        if record.get("table_name") == table_name:
            metrics = record.get("metrics", {})
            dtypes = [col_info.get("detected_type") for col_info in metrics.values()]
            return Counter(dtypes)
    return Counter()


def nulls_count_tables(records, table_name):
    "Function to count all nulls across columns in a table"
    table_records = [r for r in records if r.get("table_name") == table_name]
    if not table_records:
        return {}

    latest_record = max(table_records, key=lambda r: r.get("timestamp", ""))
    metrics = latest_record.get("metrics", {})
    return {col: col_info.get("nulls", 0) for col, col_info in metrics.items()}


def plot_piechart(records, selected_table, full_table_name):
    """
    Create a pie chart showing the proportion of each data type (numerical, boolean, date,
    categorical, categorical_high_cardinality, unstructured_text) in a table's columns."""
    if selected_table:
        dtype_counts = count_dtypes_for_table(records, full_table_name)

        if dtype_counts:
            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=list(dtype_counts.keys()),
                        values=list(dtype_counts.values()),
                        hole=0.3,
                        marker=dict(colors=["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]),
                    )
                ]
            )

            fig.update_traces(
                textinfo="value+percent",
            )
            fig.update_layout(
                title=f"Data Type Distribution - {selected_table}", height=500, showlegend=True
            )

            st.plotly_chart(fig, width="stretch")
        else:
            st.warning(f"No metrics found for table '{selected_table}'")
    else:
        st.info("Please select a table to view dtype distribution")


def plot_nulls(records, selected_table, full_table_name):
    """
    Plot a heatmap visualizing null value distribution across table columns.
    """
    if selected_table:
        null_counts = nulls_count_tables(records, full_table_name)
        if null_counts:
            df = pd.DataFrame([null_counts])
            fig = px.imshow(
                df,
                labels=dict(x="Columns", y="Table", color="Null Count"),
                x=df.columns,
                y=[selected_table],
                text_auto=True,
                aspect="auto",
                color_continuous_scale="Reds",
            )

            fig.update_layout(height=300)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No nulls data available for this table.")
    else:
        st.info("Please select a table to view null counts.")


def plot_check_tables(records):
    """
    Generate a scatter plot showing the distribution of table check times
    throughout the monitoring period.

    Helps identify:
    - Which tables were checked frequently or infrequently
    - Time gaps between checks
    - Overall monitoring coverage

    Args:
        records
    """
    st.subheader("Update Timeline")
    timestamps_all = []
    valid_records = []

    for r in records:
        try:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            timestamps_all.append(ts)
            valid_records.append(r)
        except Exception:
            continue

    if timestamps_all:
        timeline_df = pd.DataFrame(
            {
                "Timestamp": timestamps_all,
                "Table": [r.get("table_name", "unknown") for r in valid_records],
            }
        )

        years = sorted(set(dt.year for dt in timestamps_all))
        selected_year = st.selectbox("Year", years)

        months = ["All"] + sorted(
            set(dt.month for dt in timestamps_all if dt.year == selected_year)
        )
        selected_month = st.selectbox("Month", months)

        if selected_month == "All":
            days = ["All"]
        else:
            days = ["All"] + sorted(
                set(
                    dt.day
                    for dt in timestamps_all
                    if dt.year == selected_year and dt.month == selected_month
                )
            )
        selected_days = st.selectbox("Day", days)

        filtered_df = timeline_df[
            (timeline_df["Timestamp"].dt.year == selected_year)
            & (
                (timeline_df["Timestamp"].dt.month == selected_month)
                if selected_month != "All"
                else True
            )
            & (
                (timeline_df["Timestamp"].dt.day == selected_days)
                if selected_days != "All"
                else True
            )
        ]

        fig = px.scatter(
            filtered_df,
            x="Timestamp",
            y="Table",
            title="Monitoring Updates Over Time",
            labels={"Timestamp": "Time", "Table": "Table Name"},
            color="Table",
            hover_data={"Timestamp": ":%Y-%m-%d %H:%M:%S"},
        )

        fig.update_layout(height=400, showlegend=True)
        st.plotly_chart(fig, width="stretch")


def main():
    "Main function for running all functions in the overview.py file"
    from src.dashboard.tables_dashboard import get_available_tables, read_file

    records = read_file()

    st.sidebar.header("🔍 Navigation")
    bq_grouped, db_grouped = get_available_tables(records)
    db_types = []
    if bq_grouped:
        db_types.append("BigQuery")
    if db_grouped:
        db_types.append("Database")

    if not db_types:
        st.warning("No tables found.")
        st.stop()
    selected_db_type = st.sidebar.selectbox(
        "Select Source Type", db_types, key="Overview_select_source_tyoe"
    )

    if selected_db_type == "BigQuery":
        projects = sorted(set(p for p, d in bq_grouped.keys()))
        selected_project = st.sidebar.selectbox(
            "Select Project", projects, key="overview_bq_project"
        )
        datasets = sorted(set(d for p, d in bq_grouped.keys() if p == selected_project))
        selected_dataset = st.sidebar.selectbox(
            "Select Dataset", datasets, key="overview_bq_dataset"
        )
        tables = sorted(bq_grouped[(selected_project, selected_dataset)])
        selected_table = st.sidebar.selectbox("Select Table", tables, key="overview_bq_table")
        full_table_name = f"{selected_project}.{selected_dataset}.{selected_table}"
    elif selected_db_type == "Database":
        schemas = sorted(db_grouped.keys())
        selected_schema = st.sidebar.selectbox("Select Schema", schemas, key="overview_db_schema")
        tables = sorted(db_grouped[selected_schema])
        selected_table = st.sidebar.selectbox("Select Table", tables, key="overview_db_table")
        full_table_name = f"{selected_schema}.{selected_table}"
    else:
        st.warning("No tables found.")
        st.stop()

        st.sidebar.markdown("---")

    if selected_db_type == "BigQuery":
        st.sidebar.info(f"""
        **Current Selection:**
        - **Project:** `{selected_project}`
        - **Dataset:** `{selected_dataset}`
        - **Table:** `{selected_table}
        """)
    elif selected_db_type == "Database":
        st.sidebar.info(f"""
        **Current Selection:**
        - **Schema:** `{selected_schema}`
        - **Table:** `{selected_table}`
        """)
    else:
        st.warning("No tables found.")
        st.stop()

    st.header("**📈 Dashboard Summary**")
    col1, col2, col3, col4 = st.columns(4)

    if selected_db_type == "Database":
        all_tables = set(table for tables in db_grouped.values() for table in tables)
        col1.metric("Total Schemas Monitored", len(schemas))
        col2.metric("Total Tables Monitored", len(all_tables))
        schema_records = [
            r for r in records if r.get("table_name", "").startswith(f"{selected_schema}.")
        ]
        col3.metric("Total Snapshots", len(schema_records))
        columns_count = sum(len(r.get("metrics", {})) for r in schema_records)
        col4.metric("Total Column Metrics", columns_count)
    elif selected_db_type == "BigQuery":
        all_tables = set(table for table in bq_grouped.values() for table in tables)
        col1.metric("Total Datasets Monitored", len(datasets))
        col2.metric("Total Tables Monitored", len(all_tables))
        dataset_prefix = f"{selected_project}.{selected_dataset}."
        dataset_records = [r for r in records if r.get("table_name", "").startswith(dataset_prefix)]
        col3.metric("Total Snapshots", len(dataset_records))
        columns_count = sum(len(r.get("metrics", {})) for r in dataset_records)
        col4.metric("Total Column Metrics", columns_count)

    pie_chart = plot_piechart(records, selected_table, full_table_name)
    nulls = plot_nulls(records, selected_table, full_table_name)
    tables_check = plot_check_tables(records)


main()
