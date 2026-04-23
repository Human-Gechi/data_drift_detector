import json
from collections import defaultdict

import pandas as pd
import streamlit as st

st.title("Data Drift Report")


def read_file(file_path: str = "monitoring_history.jsonl"):
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def navigation_bar():
    grouped = defaultdict(list)
    for record in read_file():
        schema, table = record["table_name"].split(".", 1)
        grouped[schema].append(table)
    selected_schema = st.sidebar.selectbox("Select Schema", sorted(grouped.keys()))
    selected_table = st.sidebar.selectbox("Select Table", set(sorted(grouped[selected_schema])))
    st.write(f"Selected schema: {selected_schema}, table: {selected_table}")


def plot_numerical():
    pass
