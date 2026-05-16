import json
from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from driftmon.alerts.email_alert import Email
from driftmon.alerts.slack_alert import Slack


@pytest.fixture
def email_args():
    return {
        "sender": "sender@gmail.com",
        "receiver": "test@gmail.com",
        "password": "valid_password",
        "drift_report": "drift detected in test-table1",
    }


@pytest.fixture
def slack_args():
    return {
        "token": "xoxb-valid-token",
        "channel": "#alerts",
        "drift_report": "drift detected in test-table1",
    }


class TestEmailConnection:
    @patch("smtplib.SMTP_SSL")
    def test_send_email_ssl(self, mock_smtp_ssl, email_args):
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        email_client = Email(**email_args, use_ssl=True)
        email_client.send_email()

        mock_smtp_ssl.assert_called_once_with("smtp.gmail.com", 465)
        mock_server.login.assert_called_once_with(email_args["sender"], email_args["password"])
        mock_server.sendmail.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_email_tls(self, mock_smtp, email_args):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        email_client = Email(**email_args, use_ssl=False)
        email_client.send_email()

        mock_smtp.assert_called_once_with("smtp.gmail.com", 587)
        mock_server.ehlo.assert_called_once()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with(email_args["sender"], email_args["password"])
        mock_server.sendmail.assert_called_once()

    @patch("driftmon.alerts.email_alert.time.sleep")
    @patch("smtplib.SMTP")
    def test_unsuccessful_send_email(self, mock_smtp_class, mock_sleep, email_args, capsys):
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        mock_server.login.side_effect = Exception("Authentication failed")

        email_client = Email(**email_args, use_ssl=False)
        email_client.send_email()

        assert mock_smtp_class.call_count == 5
        assert mock_server.login.call_count == 5
        assert mock_sleep.call_count == 5

        assert mock_server.sendmail.call_count == 0
        captured = capsys.readouterr()
        assert "Failed to send email after 5 retries" in captured.out

    @patch("driftmon.alerts.email_alert.time.sleep")
    @patch("smtplib.SMTP")
    def test_unsuccessful_send_email(self, mock_smtp_class, mock_sleep, email_args, capsys):
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        mock_server.login.side_effect = Exception("Authentication failed")

        email_client = Email(**email_args, use_ssl=False)
        email_client.send_email()

        assert mock_smtp_class.call_count == 5
        assert mock_server.login.call_count == 5
        assert mock_sleep.call_count == 5

        assert mock_server.sendmail.call_count == 0
        captured = capsys.readouterr()
        assert "Failed to send email after 5 retries" in captured.out


class TestSlackConnection:
    @patch("driftmon.alerts.slack_alert.WebClient")
    def test_successful_send_notification(self, mock_webclient_cls, slack_args):
        mock_client = MagicMock()
        mock_webclient_cls.return_value = mock_client

        slack_client = Slack(**slack_args)
        slack_client.send_notification()

        mock_webclient_cls.assert_called_once_with(token=slack_args["token"])
        mock_client.chat_postMessage.assert_called_once()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == slack_args["channel"]
        assert isinstance(call_kwargs["text"], str)
        assert "Data Drift Alert" in call_kwargs["text"]
        assert "Timestamp:" in call_kwargs["text"]
        assert slack_args["drift_report"] in call_kwargs["text"]
        assert mock_client.chat_postMessage.call_count == 1

    @patch("driftmon.alerts.slack_alert.time.sleep")
    @patch("driftmon.alerts.slack_alert.WebClient")
    def test_unsuccessful_send_notification(
        self, mock_webclient_cls, mock_sleep, slack_args, capsys
    ):
        mock_client = MagicMock()
        mock_webclient_cls.return_value = mock_client
        slack_error_response = MagicMock()
        slack_error_response.__getitem__ = lambda self, key: (
            "invalid_auth" if key == "error" else None
        )
        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="invalid_auth", response=slack_error_response
        )

        slack_client = Slack(**slack_args)
        slack_client.send_notification()

        mock_webclient_cls.assert_called_once_with(token=slack_args["token"])
        assert mock_sleep.call_count == 5
        assert mock_client.chat_postMessage.call_count == 5

        captured = capsys.readouterr()
        assert "Failed to send Slack notification after 5 retries" in captured.out
