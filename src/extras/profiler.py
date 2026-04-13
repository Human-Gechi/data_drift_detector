import pandas as pd
import json

class SummaryStats:

    @staticmethod
    def profile_numeric(df: pd.DataFrame) -> str:
        stats = {}
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                continue
            if pd.api.types.is_string_dtype(df[col]):
                continue

            series = pd.to_numeric(df[col], errors="coerce")

            if pd.api.types.is_numeric_dtype(series) and not series.dropna().empty:
                stats[col] = {
                    "mean": float(series.mean()),
                    "std": float(series.std()),
                    "min": float(series.min()),
                    "max": float(series.max()),
                    "null_counts": int(df[col].isnull().sum())
                }

        return json.dumps(stats, indent=3)

    @staticmethod
    def profile_bool(df: pd.DataFrame) -> dict:
        stats = {}
        for col in df.columns:
            if pd.api.types.is_bool_dtype(df[col]):
                stats[col] = {
                    "nulls": int(df[col].isnull().sum()),
                    "unique_values": int(df[col].nunique()),
                    "value_counts": int(df[col].value_counts().to_dict())
                }
        return json.dumps(stats, indent=3, default=str)


    @staticmethod
    def profile_date(df: pd.DataFrame) -> dict:
        stats = {}
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]) or isinstance(df[col], pd.DatetimeTZDtype):
                stats[col] = {
                    "min": df[col].min(),
                    "max": df[col].max(),
                    "null_counts": int(df[col].isnull().sum())
                }
        return json.dumps(stats, indent=3, default=str)


    def profile_text(df: pd.DataFrame) -> str:
        stats = {}
        for col in df.columns:
            if pd.api.types.is_string_dtype(df[col]):
                series = df[col].dropna()
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
                    "avg_character_length": round(avg_length, 2),
                    "sample_values": series.head(3).tolist()
                }

                if detected_type.startswith("categorical"):
                    stats[col]["top_labels"] = series.value_counts().head(5).to_dict()

        return json.dumps(stats, indent=3)



