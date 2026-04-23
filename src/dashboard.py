import json
from collections import defaultdict
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy import stats

st.set_page_config(page_title="Data Drift Monitor", layout="wide")
st.title("📊 Data Drift Monitoring Dashboard")

def read_file(file_path: str = "monitoring_history.jsonl"):
    records = []
    try:
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
    except FileNotFoundError:
        st.error(f"File {file_path} not found!")
        return []
    return records

def get_available_tables(records):
    grouped = defaultdict(set)
    for record in records:
        if "table_name" in record and "." in record["table_name"]:
            schema, table = record["table_name"].split(".", 1)
            grouped[schema].add(table)
        elif "table_name" in record:
            grouped["default"].add(record["table_name"])
    return grouped

def extract_historical_numerical_data(records, table_name, column_name):
    timestamps = []
    bin_edges_list = []
    expected_percents_list = []

    for record in records:
        if record.get("table_name") == table_name and column_name in record.get("metrics", {}):
            col_metrics = record["metrics"][column_name]
            if col_metrics.get("detected_type") == "numerical":
                timestamps.append(datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00")))
                bin_edges_list.append(col_metrics.get("bin_edges", []))
                expected_percents_list.append(col_metrics.get("expected_percents", []))

    return timestamps, bin_edges_list, expected_percents_list

def extract_historical_categorical_data(records, table_name, column_name):
    timestamps = []
    top_labels_list = []
    uniqueness_ratio_list = []
    unique_values_list = []

    for record in records:
        if record.get("table_name") == table_name and column_name in record.get("metrics", {}):
            col_metrics = record["metrics"][column_name]
            if col_metrics.get("detected_type") in ["categorical", "categorical_high_cardinality"]:
                timestamps.append(datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00")))
                top_labels_list.append(col_metrics.get("top_labels", {}))
                uniqueness_ratio_list.append(col_metrics.get("uniqueness_ratio", 0))
                unique_values_list.append(col_metrics.get("unique_values", 0))

    return timestamps, top_labels_list, uniqueness_ratio_list, unique_values_list

def calculate_psi(expected, actual):
    psi_values = []

    for exp, act in zip(expected, actual):
        exp = max(exp, 1e-10)
        act = max(act, 1e-10)

        psi_value = (act - exp) * np.log(act / exp)
        psi_values.append(psi_value)

    return sum(psi_values)

def calculate_js_divergence(p, q):
    p = np.array(p, dtype=np.float64)
    q = np.array(q, dtype=np.float64)

    epsilon = 1e-10
    p = np.clip(p, epsilon, 1)
    q = np.clip(q, epsilon, 1)

    p = p / p.sum()
    q = q / q.sum()

    m = 0.5 * (p + q)
    js_div = 0.5 * (stats.entropy(p, m) + stats.entropy(q, m))
    return js_div


def plot_numerical_drift(timestamps, bin_edges_list, expected_percents_list, column_name):
    if not timestamps or len(timestamps) < 2:
        st.warning(f"Need at least 2 snapshots to calculate drift for {column_name}")
        if timestamps:
            st.info(f"Only {len(timestamps)} snapshot(s) available. Add more monitoring data to see drift trends.")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"📈 {column_name} - PSI Drift Over Time")

        psi_scores = []
        drift_timestamps = []

        for i in range(1, len(expected_percents_list)):
            if len(expected_percents_list[i]) > 0 and len(expected_percents_list[i-1]) > 0:
                psi = calculate_psi(
                        expected_percents_list[i-1],
                        expected_percents_list[i]
                    )

                psi_scores.append(psi)
                drift_timestamps.append(timestamps[i])

        if psi_scores:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=drift_timestamps,
                y=psi_scores,
                mode='lines+markers',
                name='PSI Score',
                line=dict(color='red', width=2),
                marker=dict(size=8, color=psi_scores, colorscale='RdYlGn_r', showscale=True)
            ))

            fig.add_hrect(y0=0, y1=0.1, line_width=0, fillcolor="green", opacity=0.1,
              annotation_text="Stable (<0.1)", annotation_position="top left")
            fig.add_hrect(y0=0.1, y1=0.25, line_width=0, fillcolor="orange", opacity=0.1,
                        annotation_text="Moderate Shift (0.1-0.25)", annotation_position="top left")
            fig.add_hrect(y0=0.25, y1=1.0, line_width=0, fillcolor="red", opacity=0.1,
                        annotation_text="Significant Change (≥0.25)", annotation_position="top left")

            fig.add_hline(y=0.1, line_dash="dash", line_color="orange",
                        annotation_text="Moderate Shift (0.1)")
            fig.add_hline(y=0.25, line_dash="dash", line_color="red",
                        annotation_text="Significant Change (0.25)")
            fig.update_layout(
                title=f"Population Stability Index (PSI) Over Time",
                xaxis_title="Timestamp",
                yaxis_title="PSI Score",
                height=450,
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)

            if psi_scores and psi_scores[-1] >= 0.2:
                st.error(f"⚠️ **Significant Numerical Drift!** Latest PSI: {psi_scores[-1]:.4f}")
            elif psi_scores and psi_scores[-1] >= 0.1:
                st.warning(f"⚠️ **Moderate Numerical Drift!** Latest PSI: {psi_scores[-1]:.4f}")
            else:
                st.success(f"✅ **Stable Distribution** Latest PSI: {psi_scores[-1]:.4f}")

            with st.expander("📖 PSI Interpretation Guide"):
                st.markdown("""
                **Population Stability Index (PSI) Interpretation:**
                - **PSI < 0.1**: No significant drift - distributions are similar
                - **0.1 ≤ PSI < 0.25**: Moderate drift - some distribution changes detected
                - **PSI ≥ 0.25**: Significant drift - major distribution shift detected
                
                PSI measures how much your numerical feature's distribution has changed over time.
                """)
        else:
            st.info("Insufficient data to calculate PSI scores")

    with col2:
        st.subheader(f"📊 {column_name} - Distribution Comparison")

        if len(expected_percents_list) >= 2:
            first_percents = expected_percents_list[0]
            latest_percents = expected_percents_list[-1]
            latest_bins = bin_edges_list[-1]

            if first_percents and latest_percents and latest_bins:
                bin_labels = []
                for i in range(len(latest_bins)-1):
                    bin_labels.append(f"[{latest_bins[i]:.1f}, {latest_bins[i+1]:.1f})")

                comparison_percents = first_percents
                current_percents = latest_percents

                overall_psi = calculate_psi(comparison_percents, current_percents)
                st.metric("Overall PSI (Baseline vs Latest)", f"{overall_psi:.4f}")

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=bin_labels,
                    y=comparison_percents,
                    name=f'Baseline ({timestamps[0].strftime("%Y-%m-%d")})',
                    marker_color='lightblue',
                    opacity=0.7
                ))
                fig.add_trace(go.Bar(
                    x=bin_labels,
                    y=current_percents,
                    name=f'Latest ({timestamps[-1].strftime("%Y-%m-%d")})',
                    marker_color='steelblue',
                    opacity=0.9
                ))

                fig.update_layout(
                    title="Baseline vs Latest Distribution",
                    xaxis_title="Value Ranges",
                    yaxis_title="Proportion",
                    height=450,
                    barmode='group',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

        st.info(f"""
        **Column Statistics:**
        - Number of snapshots: {len(timestamps)}
        - Number of bins: {len(bin_edges_list[-1]) - 1 if bin_edges_list else 0}
        - First snapshot: {timestamps[0].strftime('%Y-%m-%d %H:%M')}
        - Latest snapshot: {timestamps[-1].strftime('%Y-%m-%d %H:%M')}
        """)

def plot_categorical_drift(timestamps, top_labels_list, uniqueness_ratio_list, unique_values_list, column_name):
    if not timestamps or len(timestamps) < 2:
        st.warning(f"Need at least 2 snapshots to calculate drift for {column_name}")
        if timestamps:
            st.info(f"Only {len(timestamps)} snapshot(s) available. Add more monitoring data to see drift trends.")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"🏷️ {column_name} - Categorical Drift (JSD)")

        jsd_scores = []
        drift_timestamps = []

        for i in range(1, len(top_labels_list)):
            if top_labels_list[i-1] and top_labels_list[i]:
                all_categories = set(top_labels_list[i-1].keys()) | set(top_labels_list[i].keys())

                total_counts_prev = sum(top_labels_list[i-1].values())
                total_counts_curr = sum(top_labels_list[i].values())

                dist_prev = []
                dist_curr = []

                for category in all_categories:
                    count_prev = top_labels_list[i-1].get(category, 0)
                    count_curr = top_labels_list[i].get(category, 0)
                    dist_prev.append(count_prev / total_counts_prev if total_counts_prev > 0 else 0)
                    dist_curr.append(count_curr / total_counts_curr if total_counts_curr > 0 else 0)

                js_div = calculate_js_divergence(dist_prev, dist_curr)
                jsd_scores.append(js_div)
                drift_timestamps.append(timestamps[i])

        if jsd_scores:
            fig = go.Figure()

            colors = []
            for score in jsd_scores:
                if score < 0.05:
                    colors.append('green')
                elif score < 0.10:
                    colors.append('yellowgreen')
                elif score < 0.20:
                    colors.append('orange')
                elif score < 0.35:
                    colors.append('red')
                else:
                    colors.append('darkred')

            fig.add_trace(go.Scatter(
                x=drift_timestamps,
                y=jsd_scores,
                mode='lines+markers',
                name='JSD Score',
                line=dict(color='blue', width=2),
                marker=dict(size=10, color=colors,
                          symbol='circle',
                          line=dict(color='black', width=1))
            ))

            fig.add_hrect(y0=0, y1=0.05, line_width=0, fillcolor="green", opacity=0.1,
                         annotation_text="Very Low Drift", annotation_position="top left")
            fig.add_hrect(y0=0.05, y1=0.10, line_width=0, fillcolor="yellow", opacity=0.1,
                         annotation_text="Low Drift", annotation_position="top left")
            fig.add_hrect(y0=0.10, y1=0.20, line_width=0, fillcolor="orange", opacity=0.1,
                         annotation_text="Moderate Drift", annotation_position="top left")
            fig.add_hrect(y0=0.20, y1=0.35, line_width=0, fillcolor="red", opacity=0.1,
                         annotation_text="High Drift", annotation_position="top left")
            fig.add_hrect(y0=0.35, y1=1.0, line_width=0, fillcolor="darkred", opacity=0.1,
                         annotation_text="Very High Drift", annotation_position="top left")

            fig.add_hline(y=0.05, line_dash="dash", line_color="green",
                         annotation_position="bottom right")
            fig.add_hline(y=0.10, line_dash="dash", line_color="orange",
                          annotation_position="bottom right")
            fig.add_hline(y=0.20, line_dash="dash", line_color="red",
                          annotation_position="bottom right")
            fig.add_hline(y=0.35, line_dash="dash", line_color="darkred",
                          annotation_position="bottom right")

            fig.update_layout(
                title=f"Jensen-Shannon Divergence (JSD) Over Time",
                xaxis_title="Timestamp",
                yaxis_title="JSD Score (0 = identical, 1 = completely different)",
                height=500,
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)

            latest_jsd = jsd_scores[-1]

            if latest_jsd >= 0.35:
                st.error(f"""
                🚨 **EXTREME CATEGORICAL DRIFT DETECTED!** 
                
                Latest JSD: **{latest_jsd:.4f}** (Very High Drift)
                
                **Immediate Action Required:**
                - Category distribution has changed dramatically
                - Check for data pipeline errors or upstream schema changes
                - Review if business logic or categories have been redefined
                - Model predictions or dashboards may be severely impacted
                - Alert data engineering team
                """)
            elif latest_jsd >= 0.20:
                st.error(f"""
                ⚠️ **HIGH CATEGORICAL DRIFT DETECTED!**
                
                Latest JSD: **{latest_jsd:.4f}** (High Drift)
                
                **Actions to Take:**
                - Investigate what categories have changed significantly
                - Consider retraining models that depend on this feature
                - Review if new categories were introduced
                - Alert data engineering team
                """)
            elif latest_jsd >= 0.10:
                st.warning(f"""
                📊 **MODERATE CATEGORICAL DRIFT DETECTED**
                
                Latest JSD: **{latest_jsd:.4f}** (Moderate Drift)
                
                **Recommended Actions:**
                - Monitor this feature more closely
                - Review category frequency changes in the comparison chart
                - Consider if this is expected behavior (seasonal, business change)
                """)
            elif latest_jsd >= 0.05:
                st.info(f"""
                ℹ️ **LOW CATEGORICAL DRIFT DETECTED**
                
                Latest JSD: **{latest_jsd:.4f}** (Low Drift)
                
                **Note:** Minor changes detected - continue monitoring for trends.
                """)
            else:
                st.success(f"""
                ✅ **STABLE CATEGORICAL DISTRIBUTION**
                
                Latest JSD: **{latest_jsd:.4f}** (Very Low/No Drift)
                
                Category distribution is stable - no action needed.
                """)

            st.subheader("Current Drift Severity")
            severity = min(int(latest_jsd * 100), 100)
            st.progress(severity, text=f"Drift Severity: {severity}%")

            with st.expander("📖 Detailed JSD Interpretation Guide for Categorical Data"):
                st.markdown("""
                ### Jensen-Shannon Divergence (JSD) for Categorical/Text Data
                
                **What is JSD?**
                - Measures similarity between two probability distributions
                - Ranges from **0** (identical distributions) to **1** (completely different)
                - Symmetric and bounded, making it easy to interpret
                
                **Interpretation Guidelines:**
                
                | JSD Range | Severity | Meaning | Business Impact |
                |-----------|----------|---------|-----------------|
                | **0.00 - 0.05** | Very Low | Distributions nearly identical | No impact |
                | **0.05 - 0.10** | Low | Minor differences | Monitoring recommended |
                | **0.10 - 0.20** | Moderate | Noticeable shift | Investigate cause |
                | **0.20 - 0.35** | High | Significant change | Immediate investigation |
                | **0.35 - 0.50** | Very High | Major divergence | Critical alert |
                | **0.50 - 1.00** | Extreme | Completely different | System failure likely |
                
                **When to be concerned:**
                - **Rapid increases** in JSD over short time periods
                - **Sustained JSD > 0.10** for critical features
                - **JSD > 0.20** for production models
                
                **Common causes of high JSD:**
                1. Data pipeline errors or missing data
                2. Changes in business logic or category definitions
                3. New categories introduced without notice
                4. Sampling bias in data collection
                5. Seasonal or behavioral shifts in user base
                """)

            if len(jsd_scores) >= 3:
                trend = np.polyfit(range(len(jsd_scores)), jsd_scores, 1)[0]
                if trend > 0.01:
                    st.warning(f"📈 **Upward trend detected!** JSD increasing by {trend:.4f} per snapshot. Drift is worsening over time.")
                elif trend < -0.01:
                    st.info(f"📉 **Downward trend detected!** JSD decreasing by {abs(trend):.4f} per snapshot. Distribution stabilizing.")
                else:
                    st.success(f"➡️ **Stable trend** - No significant increase or decrease in drift.")

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=timestamps,
            y=uniqueness_ratio_list,
            mode='lines+markers',
            name='Uniqueness Ratio',
            line=dict(color='green', width=2),
            marker=dict(size=8, color=uniqueness_ratio_list,
                      colorscale='Viridis', showscale=True)
        ))

        fig2.update_layout(
            title=f"Category Uniqueness Over Time (Lower = More Repetitive, Higher = More Diverse)",
            xaxis_title="Timestamp",
            yaxis_title="Uniqueness Ratio",
            height=300,
            hovermode='x unified'
        )
        st.plotly_chart(fig2, use_container_width=True)

        if uniqueness_ratio_list:
            current_uniqueness = uniqueness_ratio_list[-1]
            if current_uniqueness < 0.1:
                st.caption("🔴 **High repetition** - Most values are repeated frequently")
            elif current_uniqueness < 0.3:
                st.caption("🟡 **Moderate diversity** - Some repetition, some unique values")
            else:
                st.caption("🟢 **High cardinality** - Many unique values, typical for IDs or free text")

    with col2:
        st.subheader(f"🔝 {column_name} - Top Categories Comparison")

        if len(top_labels_list) >= 2 and top_labels_list[0] and top_labels_list[-1]:
            first_top = top_labels_list[0]
            latest_top = top_labels_list[-1]

            latest_items = list(latest_top.items())[:5]
            categories = [item[0] for item in latest_items]

            first_counts = [first_top.get(cat, 0) for cat in categories]
            latest_counts = [item[1] for item in latest_items]

            pct_changes = []
            for first, latest in zip(first_counts, latest_counts):
                if first > 0:
                    pct_change = ((latest - first) / first) * 100
                else:
                    pct_change = float('inf') if latest > 0 else 0
                pct_changes.append(pct_change)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=categories,
                y=first_counts,
                name=f'Baseline ({timestamps[0].strftime("%Y-%m-%d")})',
                marker_color='lightcoral',
                text=first_counts,
                textposition='auto'
            ))
            fig.add_trace(go.Bar(
                x=categories,
                y=latest_counts,
                name=f'Latest ({timestamps[-1].strftime("%Y-%m-%d")})',
                marker_color='coral',
                text=latest_counts,
                textposition='auto'
            ))

            fig.update_layout(
                title="Top Categories: Baseline vs Latest",
                xaxis_title="Category",
                yaxis_title="Frequency",
                height=400,
                barmode='group'
            )
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Category Frequency Changes")
            for cat, pct in zip(categories, pct_changes):
                if pct == float('inf'):
                    st.warning(f"🆕 **{cat}**: New category (was 0, now {latest_counts[categories.index(cat)]})")
                elif pct > 20:
                    st.error(f"📈 **{cat}**: Increased by {pct:.1f}%")
                elif pct < -20:
                    st.error(f"📉 **{cat}**: Decreased by {abs(pct):.1f}%")
                elif abs(pct) > 10:
                    st.warning(f"⚠️ **{cat}**: Changed by {pct:.1f}%")
                else:
                    st.info(f"✓ **{cat}**: Stable ({pct:.1f}% change)")

            all_categories = set(first_top.keys()) | set(latest_top.keys())
            total_first = sum(first_top.values())
            total_latest = sum(latest_top.values())

            dist_first = []
            dist_latest = []
            for cat in all_categories:
                dist_first.append(first_top.get(cat, 0) / total_first if total_first > 0 else 0)
                dist_latest.append(latest_top.get(cat, 0) / total_latest if total_latest > 0 else 0)

            overall_jsd = calculate_js_divergence(dist_first, dist_latest)


            if overall_jsd < 0.05:
                st.success(f"✅ **Overall JSD (Baseline vs Latest):** {overall_jsd:.4f} - Very Low Drift| No Drrift")
            elif overall_jsd < 0.10:
                st.info(f"📊 **Overall JSD (Baseline vs Latest):** {overall_jsd:.4f} - Low Drift")
            elif overall_jsd < 0.20:
                st.warning(f"⚠️ **Overall JSD (Baseline vs Latest):** {overall_jsd:.4f} - Moderate Drift")
            else:
                st.error(f"🚨 **Overall JSD (Baseline vs Latest):** {overall_jsd:.4f} - High/Very High Drift")


            st.info(f"""
            **Column Statistics:**
            - Unique values (latest): {unique_values_list[-1]:,}
            - Uniqueness ratio: {uniqueness_ratio_list[-1]:.4f}
            - Total snapshots: {len(timestamps)}
            - Total categories tracked: {len(all_categories):,}
            """)

            new_categories = set(latest_top.keys()) - set(first_top.keys())
            if new_categories:
                with st.expander(f"🆕 New Top Categories Detected ({len(new_categories)})"):
                    st.write("New top categories found in latest snapshot:")
                    for cat in list(new_categories)[:10]:
                        st.write(f"- {cat}: {latest_top.get(cat, 0)} occurrences")
                    if len(new_categories) > 10:
                        st.write(f"... and {len(new_categories) - 10} more")
        else:
            st.warning("No top labels data available for comparison")

def main():
    records = read_file()

    if not records:
        st.error("No monitoring data found. Please check the file path.")
        return

    st.sidebar.header("🔍 Navigation")
    available_tables = get_available_tables(records)

    schemas = sorted(available_tables.keys())
    selected_schema = st.sidebar.selectbox("Select Schema", schemas)

    tables = sorted(available_tables.get(selected_schema, set()))
    selected_table = st.sidebar.selectbox("Select Table", tables)

    full_table_name = f"{selected_schema}.{selected_table}" if selected_schema != "default" else selected_table

    st.sidebar.markdown("--")
    st.sidebar.info(f"""
    **Current Selection:**
    - Schema: `{selected_schema}`
    - Table: `{selected_table}`
    """)

    st.header(f"Table: {full_table_name}")

    table_records = [r for r in records if r.get("table_name") == full_table_name]

    if not table_records:
        st.warning(f"No metrics found for table {full_table_name}")
        return

    latest_record = table_records[-1]
    timestamp = datetime.fromisoformat(latest_record["timestamp"].replace("Z", "+00:00"))
    st.caption(f"Latest update: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    metrics = latest_record.get("metrics", {})
    columns = list(metrics.keys())

    if not columns:
        st.warning("No columns found in metrics")
        return

    selected_column = st.selectbox("Select Column to Analyze", columns)

    if selected_column:
        col_metrics = metrics[selected_column]
        detected_type = col_metrics.get("detected_type", "unknown")

        st.markdown(f"### Analysis for: `{selected_column}`")
        st.markdown(f"**Detected Type:** `{detected_type}`")

        if detected_type == "numerical":
            timestamps, bin_edges, expected_percents = extract_historical_numerical_data(
                table_records, full_table_name, selected_column
            )
            plot_numerical_drift(timestamps, bin_edges, expected_percents, selected_column)

        elif detected_type in ["categorical", "categorical_high_cardinality", "unstructured_text"]:
            timestamps, top_labels, uniqueness_ratio, unique_values = extract_historical_categorical_data(
                table_records, full_table_name, selected_column
            )
            plot_categorical_drift(timestamps, top_labels, uniqueness_ratio, unique_values, selected_column)
        else:
            st.warning(f"Unknown column type: {detected_type}")

        with st.expander("📄 View Raw Metrics Data"):
            st.json(col_metrics)

    st.markdown("---")
    st.header("📈 Dashboard Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Tables Monitored", len(set(r.get("table_name") for r in records)))

    with col2:
        st.metric("Total Snapshots", len(records))

    with col3:
        columns_count = sum(len(r.get("metrics", {})) for r in records)
        st.metric("Total Column Metrics", columns_count)

    st.subheader("Update Timeline")
    timestamps_all = []
    valid_records = []

    for r in records:
        try:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            timestamps_all.append(ts)
            valid_records.append(r)
        except:
            continue

    if timestamps_all:
        timeline_df = pd.DataFrame({
            "Timestamp": timestamps_all,
            "Table": [r.get("table_name", "unknown") for r in valid_records]
        })

        fig = px.scatter(timeline_df, x="Timestamp", y="Table",
                         title="Monitoring Updates Over Time",
                         labels={"Timestamp": "Time", "Table": "Table Name"},
                         color="Table",
                         hover_data={"Timestamp": ":%Y-%m-%d %H:%M:%S"})

        fig.update_layout(height=400, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()