import time
from datetime import datetime

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

_RETRIES = 5
_BASE = 1


class Slack:
    """
    Slack alert handler for sending data drift notifications.

    Args:
        token (str): Slack API token.
        channel (str): Slack channel ID or name.
        drift_report (str): The drift report to send as a message.

    Methods:
        send_notification():
            Sends a notification message to Slack.
    """

    def __init__(self, token: str, channel: str, drift_report: str):
        self.token = token
        self.channel = channel
        self.drift_report = drift_report

    def send_notification(self):
        client = WebClient(token=self.token)

        attempt = 0
        while attempt < _RETRIES:
            try:
                message = (
                    f"*Data Drift Alert*\n"
                    f"Timestamp: `{datetime.now().isoformat()}`\n"
                    f"Detected drift in the following tables:\n"
                    f"```{self.drift_report}```"
                )
                response = client.chat_postMessage(channel=self.channel, text=message)
                print("✅ Slack notification sent")
                break
            except SlackApiError as e:
                attempt += 1
                print(f"Error sending message: {e.response['error']}")
                time.sleep(_BASE * attempt)
        else:
            print(f"Failed to send Slack notification after {_RETRIES} retries")
