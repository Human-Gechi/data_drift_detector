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
    for record in records:
        if record.get("table_name") == table_name:
            metrics = record.get("metrics", {})
            dtypes = [col_info.get("detected_type") for col_info in metrics.values()]
            return Counter(dtypes)
    return Counter()


def nulls_count_tables(records, table_name):
    table_records = [r for r in records if r.get("table_name") == table_name]
    if not table_records:
        return {}

    latest_record = max(table_records, key=lambda r: r.get("timestamp", ""))
    metrics = latest_record.get("metrics", {})
    return {col: col_info.get("nulls", 0) for col, col_info in metrics.items()}


def plot_piechart(records, selected_table, full_table_name):
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
    from src.dashboard.tables_dashboard import get_available_tables, read_file

    records = read_file()

    st.sidebar.header("🔍 Navigation")
    available_tables = get_available_tables(records)

    schemas = sorted(available_tables.keys())
    selected_schema = st.sidebar.selectbox("Choose Schema", schemas)

    tables = sorted(available_tables.get(selected_schema, set()))
    selected_table = st.sidebar.selectbox("Choose Table", tables)

    st.markdown("---")
    st.sidebar.info(f"""
    **Current Selection:**
    - **Schema:** `{selected_schema}`
    - **Table:** `{selected_table}`
    """)

    full_table_name = (
        f"{selected_schema}.{selected_table}" if selected_schema != "default" else selected_table
    )
    st.header("**📈 Dashboard Summary**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total schema Monitored", len(schemas))

    with col2:
        st.metric("Total Tables Monitored", len(set(r.get("table_name") for r in records)))

    with col3:
        st.metric("Total Snapshots", len(records))

    with col4:
        columns_count = sum(len(r.get("metrics", {})) for r in records)
        st.metric("Total Column Metrics", columns_count)

    pie_chart = plot_piechart(records, selected_table, full_table_name)
    nulls = plot_nulls(records, selected_table, full_table_name)
    tables_check = plot_check_tables(records)


main()
