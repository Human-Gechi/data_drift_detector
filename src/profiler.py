import pandas as pd
import json

class SummaryStats:

    @staticmethod
    def profile_numeric(df: pd.DataFrame) -> dict:
        stats = {}
        for col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            if pd.api.types.is_numeric_dtype(series):
                stats[col] = {
                    "mean": series.mean(),
                    "std": series.std(),
                    "min": series.min(),
                    "max": series.max(),
                    "nulls": series.isnull().sum()
                }
        return json.dumps(stats, indent=3, default=str)

    @staticmethod
    def profile_bool(df: pd.DataFrame) -> dict:
        stats = {}
        for col in df.columns:
            if pd.api.types.is_bool_dtype(df[col]):
                stats[col] = {
                    "nulls": df[col].isnull().sum(),
                    "unique": df[col].nunique(),
                    "value_counts": df[col].value_counts().to_dict()
                }
        return json.dumps(stats, indent=3, default=str)


    @staticmethod
    def profile_date(df: pd.DataFrame) -> dict:
        stats = {}
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                stats[col] = {
                    "min": df[col].min(),
                    "max": df[col].max(),
                    "nulls": df[col].isnull().sum(),
                    "value_counts": df[col].value_counts().to_dict()
                }
        return json.dumps(stats, indent=3, default=str)


    @staticmethod
    def profile_text(df: pd.DataFrame) -> dict:
        stats = {}
        for col in df.columns:
            if pd.api.types.is_string_dtype(df[col]):
                non_null = df[col].dropna()
                stat_dict = {"nulls": df[col].isnull().sum()}
                if not non_null.empty:
                    stat_dict["min_length"] = non_null.map(len).min()
                    stat_dict["max_length"] = non_null.map(len).max()
                stats[col] = stat_dict




