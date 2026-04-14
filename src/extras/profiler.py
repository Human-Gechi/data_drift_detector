import pandas as pd
import numpy as np
import json
from src.connector.mysql_connector import MySQLConnector

class SummaryStats:

    @staticmethod
    def profile_numeric(df: pd.DataFrame) -> str:
        numeric_df = df.select_dtypes(include=['number'])

        if numeric_df.empty:
            return ""
        stats = {}
        for col in numeric_df.columns:
            series = numeric_df[col]
            stats[col] = {
                "mean": float(series.mean()),
                "std": float(series.std()) if len(series) > 1 else 0.0,
                "min": float(series.min()),
                "max": float(series.max()),
                "null_counts": int(series.isnull().sum())
            }
        if stats:
            return json.dumps(stats, indent=3)

    @staticmethod
    def profile_bool(df: pd.DataFrame) -> dict:
        bool_df = df.select_dtypes(include=['bool'])

        if bool_df.empty:
            return ""
        stats = {}
        for col in bool_df.columns:
            series = bool_df[col]
            stats[col] = {
                    "nulls": int(series.isnull().sum()),
                    "unique_values": int(series.nunique()),
                    "value_counts": int(series.value_counts().to_dict())
                }
        if stats:
            return json.dumps(stats, indent=3, default=str)


    @staticmethod
    def profile_date(df: pd.DataFrame) -> dict:
        date_df = df.select_dtypes(include=["datetime", "datetime64", "datetime64[ns]", "datetimetz"])

        if date_df.empty:
            return ""
        stats = {}
        for col in date_df.columns:
            series = date_df[col]
            stats[col] = {
                    "min": series.min(),
                    "max": series.max(),
                    "null_counts": int(series.isnull().sum())
                }
        if stats:
            return json.dumps(stats, indent=3, default=str)

    def profile_text(df: pd.DataFrame) -> str:
        text_df = df.select_dtypes(include=['object','string'])
        stats = {}
        if text_df.empty:
            return ""
        for col in text_df.columns:
                series = text_df[col].dropna()
                total_rows = len(series)

                if total_rows == 0:
                    stats[col] = {"status": "empty"}
                    continue

                unique_count = series.nunique()
                unique_ratio = unique_count / total_rows
                avg_length = series.str.len().mean()

                if unique_ratio < 0.20 or unique_count < 25:
                    detected_type = "categorical"
                elif avg_length > 30:
                    detected_type = "unstructured_text"
                else:
                    detected_type = "categorical_high_cardinality"


                stats[col] = {
                    "detected_type": detected_type,
                    "nulls": int(df[col].isnull().sum()),
                    "unique_values": unique_count,
                    "avg_character_length": round(avg_length, 2)
                }

                if detected_type.startswith("categorical"):
                    stats[col]["top_labels"] = series.value_counts().head(5).to_dict()

        if stats:
            return json.dumps(stats, indent=3)