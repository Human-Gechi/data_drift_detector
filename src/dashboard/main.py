import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Main entry point
page_1 = st.Page(page="overview.py", title="Overview")
page_2 = st.Page(page="tables_dashboard.py", title="Data Drift Monitoring")

pg = st.navigation([page_1, page_2])

pg.run()
