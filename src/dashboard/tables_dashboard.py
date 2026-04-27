import json
import os
import sys
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

st.set_page_config(page_title="Data Drift Monitor", page_icon="📡", layout="wide")
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
                timestamps.append(
                    datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
                )
                bin_edges_list.append(col_metrics.get("bin_edges", []))
                expected_percents_list.append(col_metrics.get("expected_percents", []))

    return timestamps, bin_edges_list, expected_percents_list


def extract_historical_date_data(records, table_name, column_name):
    timestamps = []
    min_dates = []
    max_dates = []
    count_dates = []
    null_count = []

    for record in records:
        if record.get("table_name") == table_name and column_name in record.get("metrics", {}):
            col_metrics = record["metrics"][column_name]
            if col_metrics.get("detected_type") == "date":
                timestamps.append(
                    datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
                )
                max_dates.append(col_metrics.get("max", 0))
                min_dates.append(col_metrics.get("min", 0))
                count_dates.append(col_metrics.get("count", 0))
                null_count.append(col_metrics.get("null_counts", 0))

    return timestamps, min_dates, max_dates, count_dates, null_count


def extract_historical_categorical_data(records, table_name, column_name):
    timestamps = []
    top_labels_list = []
    uniqueness_ratio_list = []
    unique_values_list = []

    for record in records:
        if record.get("table_name") == table_name and column_name in record.get("metrics", {}):
            col_metrics = record["metrics"][column_name]
            if col_metrics.get("detected_type") in ["categorical", "categorical_high_cardinality"]:
                timestamps.append(
                    datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
                )
                top_labels_list.append(col_metrics.get("top_labels", {}))
                uniqueness_ratio_list.append(col_metrics.get("uniqueness_ratio", 0))
                unique_values_list.append(col_metrics.get("unique_values", 0))

    return timestamps, top_labels_list, uniqueness_ratio_list, unique_values_list


def extract_historical_bool_data(records, table_name, column_name):
    timestamps = []
    counts = []
    nulls = []
    value_counts_list = []

    for record in records:
        if record.get("table_name") == table_name and column_name in record.get("metrics", {}):
            col_metrics = record["metrics"][column_name]
            if col_metrics.get("detected_type") in "boolean":
                timestamps.append(
                    datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
                )
                counts.append(col_metrics.get("count", 0))
                nulls.append(col_metrics.get("nulls", 0))
                value_counts_list.append(col_metrics.get("value_counts", {}))

    return timestamps, counts, nulls, value_counts_list


def filter_by_date(timestamps, *args, year=None, month=None, day=None):
    indices = list(range(len(timestamps)))
    if year is not None:
        indices = [i for i in indices if timestamps[i].year == year]
    if month is not None:
        indices = [i for i in indices if timestamps[i].month == month]
    if day is not None:
        indices = [i for i in indices if timestamps[i].day == day]
    filtered = [[lst[i] for i in indices] for lst in (timestamps,) + args]
    return filtered


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
            st.info(
                f"Only {len(timestamps)} snapshot(s) available. Add more data to see drift trends."
            )
        return None

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"📈 {column_name} - PSI Drift Over Time")

        psi_scores = []
        drift_timestamps = []

        for i in range(1, len(expected_percents_list)):
            if len(expected_percents_list[i]) > 0 and len(expected_percents_list[i - 1]) > 0:
                psi = calculate_psi(expected_percents_list[i - 1], expected_percents_list[i])

                psi_scores.append(psi)
                drift_timestamps.append(timestamps[i])

        if psi_scores:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=drift_timestamps,
                    y=psi_scores,
                    mode="markers",
                    name="PSI Score",
                    line=dict(color="red", width=2),
                    marker=dict(size=8, color=psi_scores, colorscale="RdYlGn_r", showscale=True)
                )
            )

            fig.add_hrect(
                y0=0,
                y1=0.1,
                line_width=0,
                fillcolor="green",
                opacity=0.1,
                annotation_text="Stable (<0.1)",
                annotation_position="top left"
            )
            fig.add_hrect(
                y0=0.1,
                y1=0.25,
                line_width=0,
                fillcolor="orange",
                opacity=0.1,
                annotation_text="Moderate Shift (0.1 - 0.25)",
                annotation_position="top left"
            )
            fig.add_hrect(
                y0=0.25,
                y1=1.0,
                line_width=0,
                fillcolor="red",
                opacity=0.1,
                annotation_text="Significant Change (≥0.25)",
                annotation_position="top left"
            )

            fig.add_hline(
                y=0.1, line_dash="dash", line_color="orange", annotation_text="Moderate Shift (0.1)"
            )
            fig.add_hline(
                y=0.25,
                line_dash="dash",
                line_color="red",
                annotation_text="Significant Change (0.25)"
            )
            fig.update_layout(
                title=f"Population Stability Index (PSI) Over Time",
                xaxis_title="Timestamp",
                yaxis_title="PSI Score",
                height=450,
                hovermode="x unified"
            )
            st.plotly_chart(fig, width="stretch")

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
        st.subheader(f"{column_name}: Current Bins Distribution Comparison")

        if len(expected_percents_list) >= 2:
            first_percents = expected_percents_list[-2]
            latest_percents = expected_percents_list[-1]

            latest_bins = bin_edges_list[-1]

            if first_percents and latest_percents and latest_bins:
                bin_labels = []
                for i in range(len(latest_bins) - 1):
                    bin_labels.append(f"[{latest_bins[i]:.1f}, {latest_bins[i + 1]:.1f})")

                comparison_percents = first_percents
                current_percents = latest_percents

                overall_psi = calculate_psi(comparison_percents, current_percents)
                st.metric("Overall PSI (Previous vs Latest)", f"{overall_psi:.4f}")

                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        x=bin_labels,
                        y=comparison_percents,
                        name=f"Previous ({timestamps[-2].strftime('%Y-%m-%d')})",
                        marker_color="lightblue",
                        opacity=0.7
                    )
                )
                fig.add_trace(
                    go.Bar(
                        x=bin_labels,
                        y=current_percents,
                        name=f"Latest ({timestamps[-1].strftime('%Y-%m-%d')})",
                        marker_color="steelblue",
                        opacity=0.9
                    )
                )

                fig.update_layout(
                    title="Previous vs Latest Distribution",
                    xaxis_title="Value Ranges",
                    yaxis_title="Proportion",
                    height=450,
                    barmode="group",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, width="stretch")

        st.info(f"""
        **Column Statistics:**
        - Number of snapshots: {len(timestamps)}
        - Number of bins: {len(bin_edges_list[-1]) - 1 if bin_edges_list else 0}
        - Previous snapshot: {timestamps[-2].strftime("%Y-%m-%d %H:%M")}
        - Latest snapshot: {timestamps[-1].strftime("%Y-%m-%d %H:%M")}
        """)


def plot_categorical_drift(
    timestamps, top_labels_list, uniqueness_ratio_list, unique_values_list, column_name
):
    if not timestamps or len(timestamps) < 2:
        st.warning(f"Need at least 2 snapshots to calculate drift for {column_name}")
        if timestamps:
            st.info(
                f"Only {len(timestamps)} snapshot(s) available. Add more data to see drift trends."
            )
        return

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"🏷️ {column_name} - Categorical Drift (JSD)")

        jsd_scores = []
        drift_timestamps = []

        for i in range(1, len(top_labels_list)):
            if top_labels_list[i - 1] and top_labels_list[i]:
                all_categories = set(top_labels_list[i - 1].keys()) | set(top_labels_list[i].keys())

                total_counts_prev = sum(top_labels_list[i - 1].values())
                total_counts_curr = sum(top_labels_list[i].values())

                dist_prev = []
                dist_curr = []

                for category in all_categories:
                    count_prev = top_labels_list[i - 1].get(category, 0)
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
                    colors.append("green")
                elif score < 0.10:
                    colors.append("yellowgreen")
                elif score < 0.20:
                    colors.append("orange")
                elif score < 0.35:
                    colors.append("red")
                else:
                    colors.append("darkred")

            fig.add_trace(
                go.Scatter(
                    x=drift_timestamps,
                    y=jsd_scores,
                    mode="markers",
                    name="JSD Score",
                    line=dict(color="blue", width=2),
                    marker=dict(
                        size=10, color=colors, symbol="circle", line=dict(color="black", width=1)
                    )
                )
            )

            fig.add_hrect(
                y0=0,
                y1=0.05,
                line_width=0,
                fillcolor="green",
                opacity=0.1,
                annotation_text="Very Low Drift",
                annotation_position="top left"
            )
            fig.add_hrect(
                y0=0.05,
                y1=0.10,
                line_width=0,
                fillcolor="yellow",
                opacity=0.1,
                annotation_text="Low Drift",
                annotation_position="top left"
            )
            fig.add_hrect(
                y0=0.10,
                y1=0.20,
                line_width=0,
                fillcolor="orange",
                opacity=0.1,
                annotation_text="Moderate Drift",
                annotation_position="top left"
            )
            fig.add_hrect(
                y0=0.20,
                y1=0.35,
                line_width=0,
                fillcolor="red",
                opacity=0.1,
                annotation_text="High Drift",
                annotation_position="top left"
            )
            fig.add_hrect(
                y0=0.35,
                y1=1.0,
                line_width=0,
                fillcolor="darkred",
                opacity=0.1,
                annotation_text="Very High Drift",
                annotation_position="top left"
            )

            fig.add_hline(
                y=0.05, line_dash="dash", line_color="green", annotation_position="bottom right"
            )
            fig.add_hline(
                y=0.10, line_dash="dash", line_color="orange", annotation_position="bottom right"
            )
            fig.add_hline(
                y=0.20, line_dash="dash", line_color="red", annotation_position="bottom right"
            )
            fig.add_hline(
                y=0.35, line_dash="dash", line_color="darkred", annotation_position="bottom right"
            )

            fig.update_layout(
                title=f"Jensen-Shannon Divergence (JSD) Over Time",
                xaxis_title="Timestamp",
                yaxis_title="JSD Score (0 = identical, 1 = completely different)",
                height=500,
                hovermode="x unified"
            )
            st.plotly_chart(fig, width="stretch")

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
                - **JSD > 0.20** for production ML models or data models 
                
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
                    st.warning(
                        f"📈 **Upward trend detected!** JSD increasing by {trend:.4f}"
                        "per snapshot. Drift is worsening over time."
                    )
                elif trend < -0.01:
                    st.info(
                        f"📉 **Downward trend detected!** JSD decreasing by {abs(trend):.4f}"
                        "per snapshot. Distribution stabilizing."
                    )
                else:
                    st.success(
                        f"➡️ **Stable trend** - No significant increase or decrease in drift."
                    )

        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(
                x=drift_timestamps,
                y=uniqueness_ratio_list,
                mode="markers",
                name="Uniqueness Ratio",
                line=dict(color="green", width=2),
                marker=dict(
                    size=8, color=uniqueness_ratio_list, colorscale="Viridis", showscale=True
                )
            )
        )

        fig2.update_layout(
            title=f"Category Uniqueness Over Time (Lower = More Repetitive, Higher = More Diverse)",
            xaxis_title="Timestamp",
            yaxis_title="Uniqueness Ratio",
            height=300,
            hovermode="x unified"
        )
        st.plotly_chart(fig2, use_container_width=True)

        if uniqueness_ratio_list:
            current_uniqueness = uniqueness_ratio_list[-1]
            if current_uniqueness < 0.2:
                st.caption("🔴 **High repetition** - Most values are repeated frequently")
            elif current_uniqueness < 0.5:
                st.caption("🟡 **Moderate diversity** - Some repetition, some unique values")
            else:
                st.caption(
                    "🟢 **High cardinality** - Many unique values, typical for IDs or free text"
                )

    with col2:
        st.subheader(f"🔝 {column_name} - Top Categories Comparison")

        if len(top_labels_list) >= 2 and top_labels_list[0] and top_labels_list[-1]:
            first_top = top_labels_list[-2]
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
                    pct_change = float("inf") if latest > 0 else 0
                pct_changes.append(pct_change)

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=categories,
                    y=first_counts,
                    name=f"Baseline ({timestamps[-2].strftime('%Y-%m-%d')})",
                    marker_color="lightcoral",
                    text=first_counts,
                    textposition="auto"
                )
            )
            fig.add_trace(
                go.Bar(
                    x=categories,
                    y=latest_counts,
                    name=f"Latest ({timestamps[-1].strftime('%Y-%m-%d')})",
                    marker_color="coral",
                    text=latest_counts,
                    textposition="auto"
                )
            )

            fig.update_layout(
                title="Top Categories: Baseline vs Latest",
                xaxis_title="Category",
                yaxis_title="Frequency",
                height=400,
                barmode="group"
            )
            st.plotly_chart(fig, width="stretch")

            st.subheader("Category Frequency Changes")
            for cat, pct in zip(categories, pct_changes):
                if pct == float("inf"):
                    st.warning(
                        f"""🆕 **{cat}**:New category (was 0,now 
                        {latest_counts[categories.index(cat)]})"""
                    )
                elif pct > 20:
                    st.error(f"📈 **{cat}**: Increased by {pct:.1f}%")
                elif pct < -20:
                    st.error(f"📉 **{cat}**: Decreased by {abs(pct):.1f}%")
                elif abs(pct) > 10:
                    st.warning(f"⚠️ **{cat}**: Changed by {pct:.1f}%")
                else:
                    st.info(f"✅ **{cat}**: Stable ({pct:.1f}% change)")

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
                st.success(
                    f"✅ **Overall JSD (Baseline vs Latest):** {overall_jsd:.4f}"
                    "- Very Low Drift|No Drift"
                )
            elif overall_jsd < 0.10:
                st.info(f"📊 **Overall JSD (Baseline vs Latest):** {overall_jsd:.4f} - Low Drift")
            elif overall_jsd < 0.20:
                st.warning(
                    f"⚠️ **Overall JSD (Baseline vs Latest):** {overall_jsd:.4f} - Moderate Drift"
                )
            else:
                st.error(
                    f"🚨 **Overall JSD (Baseline vs Latest):** {overall_jsd:.4f} - High/High Drift"
                )

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


def plot_date_drift(
    timestamps,
    min_dates,
    max_dates,
    count_dates,
    null_count,
    column_name,
    selected_year=None,
    selected_month=None
):
    curr_null_count = null_count[-1]
    curr_count_dates = count_dates[-1]

    if selected_year is not None:
        indices = [i for i, dt in enumerate(timestamps) if dt.year == selected_year]
        timestamps = [timestamps[i] for i in indices]
        min_dates = [min_dates[i] for i in indices]
        max_dates = [max_dates[i] for i in indices]

    if selected_month is not None:
        indices = [i for i, dt in enumerate(timestamps) if dt.month == selected_month]
        timestamps = [timestamps[i] for i in indices]
        min_dates = [min_dates[i] for i in indices]
        max_dates = [max_dates[i] for i in indices]

    timestamp = [dt for dt in timestamps]
    min_dates_dt = [datetime.fromtimestamp(m) for m in min_dates]
    max_dates_dt = [datetime.fromtimestamp(m) for m in max_dates]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=timestamp,
            y=min_dates_dt,
            mode="lines+markers",
            name="Min Date",
            line=dict(color="blue", width=2),
            marker=dict(size=8)
        )
    )

    fig.add_trace(
        go.Scatter(
            x=timestamp,
            y=max_dates_dt,
            mode="lines+markers",
            name="Max Date",
            line=dict(color="red", width=2),
            marker=dict(size=8)
        )
    )

    fig.add_trace(
        go.Scatter(
            x=timestamp + timestamp[::-1],
            y=min_dates_dt + max_dates_dt[::-1],
            fill="toself",
            fillcolor="rgba(128, 128, 128, 0.2)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Date Range",
            showlegend=True
        )
    )

    fig.update_yaxes(tickformat="%Y-%m-%d")

    fig.update_layout(
        title=f"{column_name}: min/max date tracking",
        xaxis_title="Run Date",
        yaxis_title="Date Value",
        height=500,
        hovermode="x unified",
        template="plotly_white"
    )

    st.plotly_chart(fig, width="stretch")

    col1, col2 = st.columns(2)

    with col1:
        null_pct = (curr_null_count / curr_count_dates * 100) if curr_count_dates > 0 else 0
        st.metric(
            "📊 Current Data Completeness",
            f"{(100 - null_pct):.1f}%",
            delta=f"{curr_null_count} null values" if curr_null_count > 0 else "No missing data",
            delta_color="off"
        )

    with col2:
        st.metric(
            "📋 Current Unique Date Count",
            f"{curr_count_dates:,}",
            help="Total number of non-null date values"
        )


def plot_bool_drift(
    timestamps,
    counts,
    nulls,
    value_counts_list,
    column_name,
    selected_year=None,
    selected_month=None,
    selected_days=None
):
    all_keys = set()
    for vc in value_counts_list:
        all_keys.update(vc.keys())
    all_keys = sorted([str(k) for k in all_keys])

    fig = go.Figure()
    colors = ["#2ecc71", "#e74c3c", "#3498db", "#f39c12"]

    for i, key in enumerate(all_keys):
        proportions = []
        for vc in value_counts_list:
            total = sum(vc.values())
            count = 0
            if key in vc:
                count = vc[key]
            elif key == "True" and True in vc:
                count = vc[True]
            elif key == "False" and False in vc:
                count = vc[False]
            proportions.append(count / total if total > 0 else 0)

        fig.add_trace(
            go.Bar(
                x=timestamps,
                y=proportions,
                name=str(key),
                marker_color=colors[i % len(colors)],
                text=[f"{p:.1%}" for p in proportions],
                textposition="auto",
                hovertemplate=f"{key}: %{{y:.1%}}<br>Timestamp: %{{x}}<extra></extra>"
            )
        )

    fig.update_layout(
        title=f"Value Distribution by Snapshot - {column_name}",
        xaxis_title="Timestamp",
        yaxis_title="Proportion",
        yaxis=dict(tickformat=".0%", range=[0, 1]),
        barmode="group",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        template="plotly_white",
        height=500
    )
    st.plotly_chart(fig, width="stretch")

    curr_count = counts[-1]
    curr_null_count = nulls[-1]

    col1, col2 = st.columns(2)

    with col1:
        null_pct = (curr_null_count / curr_count * 100) if curr_count > 0 else 0
        st.metric(
            "📊 Current Data Completeness",
            f"{(100 - null_pct):.1f}%",
            delta=f"{curr_null_count} null values" if curr_null_count > 0 else "No missing data",
            delta_color="off"
        )

    with col2:
        st.metric(
            "📋 Current Unique Date Count",
            f"{curr_count:,}",
            help="Total number of non-null date values"
        )


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

    full_table_name = f"{selected_schema}.{selected_table}"

    st.sidebar.markdown("---")
    st.sidebar.info(f"""
    **Current Selection:**
    - **Schema:** `{selected_schema}`
    - **Table:** `{selected_table}`
    """)

    st.header(f"Table: {selected_table}")

    table_records = [r for r in records if r.get("table_name") == full_table_name]

    if not table_records:
        st.warning(f"No metrics found for table {tables}")
        return

    latest_record = table_records[-1]
    timestamp = datetime.fromisoformat(latest_record["timestamp"].replace("Z", "+00:00"))
    st.caption(f"Latest update: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    metrics = latest_record.get("metrics", {})
    columns = list(metrics.keys())

    if not columns:
        st.warning("No columns found in metrics")
        return

    selected_column = st.selectbox("Select Column to Analyse", columns)

    if selected_column:
        col_metrics = metrics[selected_column]
        detected_type = col_metrics.get("detected_type", "unknown")

        st.markdown(f"### Analysis for column: `{selected_column}`")
        st.markdown(f"**Detected Type:** `{detected_type}`")

        if detected_type == "numerical":
            timestamps, bin_edges, expected_percents = extract_historical_numerical_data(
                table_records, full_table_name, selected_column
            )
            plot_numerical_drift(timestamps, bin_edges, expected_percents, selected_column)

        elif detected_type in ["categorical", "categorical_high_cardinality", "unstructured_text"]:
            timestamps, top_labels, uniqueness_ratio, unique_values = (
                extract_historical_categorical_data(table_records, full_table_name, selected_column)
            )
            plot_categorical_drift(
                timestamps, top_labels, uniqueness_ratio, unique_values, selected_column
            )
        elif detected_type == "date":
            timestamps, min_dates, max_dates, count_dates, null_count = (
                extract_historical_date_data(table_records, full_table_name, selected_column)
            )
            years = sorted(set(dt.year for dt in timestamps))
            selected_year = st.selectbox("Year", years)
            months = sorted(set(dt.month for dt in timestamps if dt.year == selected_year))
            selected_month = st.selectbox("Month", months)

            plot_date_drift(
                timestamps,
                min_dates,
                max_dates,
                count_dates,
                null_count,
                selected_column,
                selected_year,
                selected_month
            )
        elif detected_type == "boolean":
            timestamps, counts, nulls, value_counts_list = extract_historical_bool_data(
                table_records, full_table_name, selected_column
            )
            years = sorted(set(dt.year for dt in timestamps))
            selected_year = st.selectbox("Year", years)

            months = ["All"] + sorted(
                set(dt.month for dt in timestamps if dt.year == selected_year)
            )
            selected_month = st.selectbox("Month", months)

            if selected_month == "All":
                days = ["All"]
            else:
                days = ["All"] + sorted(
                    set(
                        dt.day
                        for dt in timestamps
                        if dt.year == selected_year and dt.month == selected_month
                    )
                )
            selected_days = st.selectbox("Day", days)

            filtered = filter_by_date(
                timestamps,
                counts,
                nulls,
                value_counts_list,
                year=selected_year,
                month=None if selected_month == "All" else selected_month,
                day=None if selected_days == "All" else selected_days
            )

            timestamps_f, counts_f, nulls_f, value_counts_list_f = filtered

            plot_bool_drift(
                timestamps=timestamps_f,
                counts=counts_f,
                nulls=nulls_f,
                value_counts_list=value_counts_list_f,
                column_name=selected_column
            )
        else:
            st.warning(f"Unknown column type: {detected_type}")

        with st.expander("📄 View Raw Metrics Data"):
            st.json(col_metrics)

    st.subheader("Update Timeline for Data Drift")
    timestamps_all = []
    valid_records = []

    for r in records:
        if r.get("table_name", "unknown") == full_table_name:
            try:
                ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                timestamps_all.append(ts)
                valid_records.append(r)
            except Exception:
                continue

    if timestamps_all:
        timeline_df = pd.DataFrame({"Timestamp": timestamps_all, "Table": full_table_name})
        timeline_years = sorted(set(dt.year for dt in timestamps_all))
        timeline_selected_year = st.selectbox("Timeline Year", timeline_years)
        timeline_months = ["All"] + sorted(
            set(dt.month for dt in timestamps_all if dt.year == timeline_selected_year)
        )
        timeline_selected_month = st.selectbox("Timeline Month", timeline_months)
        if timeline_selected_month == "All":
            timeline_days = ["All"]
        else:
            timeline_days = ["All"] + sorted(
                set(
                    dt.day
                    for dt in timestamps_all
                    if dt.year == timeline_selected_year and dt.month == timeline_selected_month
                )
            )
        timeline_selected_days = st.selectbox("Timeline Day", timeline_days)

        filtered_df = timeline_df[(timeline_df["Timestamp"].dt.year == timeline_selected_year)]
        if timeline_selected_month != "All":
            filtered_df = filtered_df[filtered_df["Timestamp"].dt.month == timeline_selected_month]
        if timeline_selected_days != "All":
            filtered_df = filtered_df[filtered_df["Timestamp"].dt.day == timeline_selected_days]

        fig = px.scatter(
            filtered_df,
            x="Timestamp",
            y="Table",
            title="Monitoring Updates Over Time",
            labels={"Timestamp": "Time", "Table": "Table Name"},
            color="Table",
            hover_data={"Timestamp": ":%Y-%m-%d %H:%M:%S"}
        )

        fig.update_layout(height=400, showlegend=True)
        st.plotly_chart(fig, width="stretch")


main()
