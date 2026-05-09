import json

import pandas as pd

from src.detect.profiler import SummaryStats


def test_profile_numeric():
    df = pd.DataFrame({"col1": [1, 2, 3, 4, 5]})
    result = SummaryStats.profile_numeric(df, num_bins=2)
    stats = json.loads(result)
    assert "col1" in stats
    assert stats["col1"]["detected_type"] == "numerical"
    assert stats["col1"]["bin_edges"] == [1.0, 3.0, 5.0]
    assert sum(stats["col1"]["expected_percents"]) == 1.0


def test_profile_bool():
    df = pd.DataFrame({"col1": [True, False, True, False, False, True]})
    result = SummaryStats.profile_bool(df)
    stats = json.loads(result)

    assert "col1" in stats
    assert stats["col1"]["detected_type"] == "boolean"
    assert stats["col1"]["count"] == 6
    assert stats["col1"]["nulls"] == 0
    assert set(stats["col1"]["unique_values"]) == {True, False}
    assert stats["col1"]["value_counts"] == {"true": 3, "false": 3}


def test_profile_date():
    df = pd.DataFrame({"col1": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03", None])})
    result = SummaryStats.profile_date(df)
    stats = json.loads(result)
    assert "col1" in stats
    assert stats["col1"]["detected_type"] == "date"
    assert stats["col1"]["count"] == 3
    assert stats["col1"]["nulls"] == 1
    assert stats["col1"]["min"] <= stats["col1"]["max"]


def test_profile_text():
    df = pd.DataFrame(
        {
            "col1": ["apple", "banana", "apple", "orange", "banana", "apple"],
            "col2": [
                "This is a long unstructured text with very long words and extra padding to exceed thirty characters.",
                "Another unique sentence with more words and different content, making sure it's long enough for the test.",
                "Yet another completely different sentence for testing, with enough length to pass the threshold.",
                "Unstructured data is often verbose and unique, especially when the sentences are long enough.",
                "Text analytics is fun with lots of unique sentences, especially when they are long and detailed.",
                "Machine learning loves unstructured text columns, particularly when the text is sufficiently lengthy.",
            ],
        }
    )
    result = SummaryStats.profile_text(df)
    stats = json.loads(result)
    assert "col1" in stats
    assert stats["col1"]["detected_type"].startswith("categorical")
    assert stats["col1"]["count"] == 6
    assert stats["col1"]["nulls"] == 0
    assert stats["col1"]["unique_values"] == 3
    assert "top_labels" in stats["col1"]

    assert "col2" in stats
    assert stats["col2"]["detected_type"] == "unstructured_text"
    assert stats["col2"]["count"] == 6
    assert "avg_character_length" in stats["col2"]
    assert "sample_preview" in stats["col2"]
