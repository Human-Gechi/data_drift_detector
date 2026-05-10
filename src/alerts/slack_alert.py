import time
from datetime import datetime
from typing import List

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

_RETRIES = 5
_BASE = 1


class Slack:
    """
    Slack alert handler for sending data drift notifications.

    Sends a formatted Slack message to a specified channel when data drift is detected
    in monitored tables. Uses the Slack WebClient and supports retry logic on failure.

    Args:
        token (str): Slack API token.
        channel (str): Slack channel ID or name.
        tables (List[str], optional): List of table names to monitor.
        file_path (str, optional): Path to the monitoring history file (default: "monitoring_history.jsonl").

    Methods:
        send_notification():
            Runs drift detection and sends a notification message to Slack.
    """
    def __init__(self, token: str, channel: str, tables: List[str] = None, file_path: str = None):
        self.token = token
        self.channel = channel
        self.file_path = file_path or "monitoring_history.jsonl"
        self.tables = tables

    def send_notification(self):
        from src.detect.drift_detector import detect_drift

        client = WebClient(token=self.token)

        attempt = 0
        while attempt < _RETRIES:
            try:
                drift_report = detect_drift(file_path=self.file_path, table_names=self.tables)
                message = (
                    f"*Data Drift Alert*\n"
                    f"Timestamp: `{datetime.now().isoformat()}`\n"
                    f"Detected drift in the following tables:\n"
                    f"```{drift_report}```"
                )
                response = client.chat_postMessage(channel=self.channel, text=message)
                print("✅ Slack notification sent")
                break
            except SlackApiError as e:
                attempt += 1
                print(f"Error sending message: {e.response['error']}")
                time.sleep(_BASE * attempt)
        print(f"Failed to send email after {_RETRIES} retries")
