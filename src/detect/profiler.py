import json

import numpy as np
import pandas as pd


class SummaryStats:
    """Base column profiling class for analyzing distributions according to data types.

    This class provides foundational profiling capabilities for columns based on their
    detected data type. Contains four static methods, each specialized for a specific
    data type:

    Static Methods:
        profile_numeric(df, num_bins)
            Computes bin edges, expected percentages, and statistical distributions
            for numerical columns (integers, floats).

        profile_bool(df)
            Analyzes boolean distributions counts, unique_counts
            nulls, and value frequencies.

        profile_text(df)
            Profiles text (object/string) columns, determines if each is unstructured text or categorical
            (low or high cardinality) based on average character length and uniqueness ratio.
            Computes statistics such as unique value count, average and standard deviation of
            character length, uniqueness ratio, and provides top labels or sample previews.

        profile_date(df)
            Profiles date/datetime columns, computing count, variance, min, max , max (as epoch time)
            and number of nulls.


    Each method returns a standardized metrics dictionary compatible with the
    base column profiling format.
    """

    @staticmethod
    def profile_numeric(df: pd.DataFrame, num_bins=5) -> str:
        df = df.apply(pd.to_numeric, errors="coerce")
        numeric_df = df.select_dtypes(include=["number"])

        if numeric_df.empty:
            return ""
        stats = {}
        for col in numeric_df.columns:
            series = numeric_df[col].dropna()
            n = len(series)
            if n == 0:
                stats[col] = {
                    "detected_type": "numerical",
                    "bin_edges": None,
                    "expected_percents": None,
                }
                continue
            quantiles = np.linspace(0, 1, num_bins + 1)
            bin_edges = np.quantile(series, quantiles).tolist()
            counts, _ = np.histogram(series, bins=bin_edges)
            expected_percents = (counts / counts.sum()).tolist()

            stats[col] = {
                "detected_type": "numerical",
                "bin_edges": [round(x, 2) for x in bin_edges],
                "expected_percents": expected_percents,
            }
        if stats:
            return json.dumps(stats)

    @staticmethod
    def profile_bool(df: pd.DataFrame) -> str:
        bool_df = df.select_dtypes(include=["bool"])

        if bool_df.empty:
            return ""
        stats = {}
        for col in bool_df.columns:
            series = bool_df[col]
            non_null = series.dropna()
            stats[col] = {
                "detected_type": "boolean",
                "count": len(non_null),
                "value_counts": series.value_counts(dropna=False).to_dict(),
                "nulls": int(series.isnull().sum()),
                "unique_values": series.unique().tolist(),
            }
        if stats:
            return json.dumps(stats)

    @staticmethod
    def profile_date(df: pd.DataFrame) -> str:
        date_df = df.select_dtypes(
            include=["datetime", "datetime64", "datetime64[ns]", "datetimetz"]
        )
        if date_df.empty:
            return ""
        stats = {}
        for col in date_df.columns:
            series = date_df[col].dropna()
            n = len(series)
            if n == 0:
                stats[col] = {
                    "detected_type": "date",
                    "count": 0,
                    "mean": None,
                    "var": None,
                    "min": None,
                    "max": None,
                    "nulls": int(df[col].isnull().sum()),
                }
                continue
            timestamps = series.astype(np.int64) // 10**9
            mean_ts = float(timestamps.mean())
            var_ts = float(timestamps.var()) if n > 1 else 0.0
            stats[col] = {
                "detected_type": "date",
                "count": n,
                "mean": mean_ts,
                "var": var_ts,
                "min": int(series.min().timestamp()),
                "max": int(series.max().timestamp()),
                "nulls": int(df[col].isnull().sum()),
            }
        if stats:
            return json.dumps(stats)

    @staticmethod
    def profile_text(df: pd.DataFrame) -> str:
        text_df = df.select_dtypes(include=["object", "string"])
        stats = {}
        if text_df.empty:
            return ""

        for col in text_df.columns:
            series = df[col].dropna()
            total_rows = len(series)

            if total_rows == 0:
                stats[col] = {
                    "detected_type": "unknown",
                    "status": "empty",
                    "nulls": int(df[col].isnull().sum()),
                }
                continue

            unique_count = series.nunique()
            unique_ratio = unique_count / total_rows
            lengths = series.str.len()
            avg_length = lengths.mean()

            if avg_length > 30:
                detected_type = "unstructured_text"
            elif unique_ratio < 0.20 or unique_count < 25:
                detected_type = "categorical"
            else:
                detected_type = "categorical_high_cardinality"

            stats[col] = {
                "detected_type": detected_type,
                "count": total_rows,
                "nulls": int(df[col].isnull().sum()),
                "unique_values": unique_count,
                "avg_character_length": round(avg_length, 2),
                "std_character_length": round(lengths.std(), 2) if total_rows > 1 else 0,
                "uniqueness_ratio": round(unique_ratio, 4),
            }

            if detected_type.startswith("categorical"):
                full_counts = series.value_counts().to_dict()
                stats[col]["top_labels"] = dict(list(full_counts.items())[:5])

            if detected_type == "unstructured_text":
                stats[col]["sample_preview"] = series.head(3).tolist()

        if stats:
            return json.dumps(stats)
