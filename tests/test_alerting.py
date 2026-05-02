import pytest
from unittest.mock import patch, MagicMock
from src.alerts.email_alert import Email
from src.alerts.slack_alert import Slack
import json

@pytest.fixture
def mock_jsonl_file(tmp_path):
        jsonl_path = tmp_path / "monitoring_history.jsonl"
        test_tables = ["test-table1", "test-table2", "test-table3"]

        with open(jsonl_path, 'w') as f:
            for table in test_tables:
                data = {
                    "table_name": table,
                    "drift_score": 0.5,
                    "timestamp": "2026-05-02",
                    "metric": "data_drift"
                }
                f.write(json.dumps(data) + '\n')

        return str(jsonl_path), test_tables

class TestEmailConnection:
    @patch('smtplib.SMTP_SSL')
    def test_successful_send_email(self, mock_smtp_class, mock_jsonl_file):
        jsonl_path, test_tables = mock_jsonl_file

        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        sender_email = "sender@gmail.com"
        receiver_email = 'test@gmail.com'
        sender_password = 'valid_password'
        tables = test_tables

        email_client = Email(
            sender_email=sender_email,
            receiver_email=receiver_email,
            sender_password=sender_password,
            tables=tables,
            file_path=jsonl_path
        )

        email_client.send_email()
        subject = "Data Drift Alert"

        mock_smtp_class.assert_called_once_with('smtp.gmail.com', 465)
        mock_server.login.assert_called_once_with(sender_email, sender_password)
        mock_server.sendmail.assert_called_once()

        call_args = mock_server.sendmail.call_args[0]
        assert call_args[0] == sender_email
        assert call_args[1] == receiver_email
        assert isinstance(call_args[2], str)

        email_content = call_args[2]
        assert subject in email_content

        assert mock_server.sendmail.call_count == 1
        assert mock_server.login.call_count == 1

    @patch('smtplib.SMTP_SSL')
    def test_unsuccessful_send_email(self, mock_smtp_class, mock_jsonl_file, capsys):
        jsonl_path, test_tables = mock_jsonl_file

        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        mock_server.login.side_effect = Exception("Authentication failed")

        sender_email = "invalid@gmail.com"
        receiver_email = 'test@gmail.com'
        sender_password = 'invalid_password'
        tables = test_tables

        email_client = Email(
            sender_email=sender_email,
            receiver_email=receiver_email,
            sender_password=sender_password,
            tables=tables,
            file_path=jsonl_path
        )

        email_client.send_email()

        assert mock_smtp_class.call_count == 5
        assert mock_server.login.call_count == 5

        assert mock_server.sendmail.call_count == 0
        captured = capsys.readouterr()

        assert "Failed to send email after 5 retries" in captured.out

class TestSlackConnection:
    def test_successful_send_notification(self, mock_webclient, mock_jsonl_file):
        jsonl_path, test_tables = mock_jsonl_file

        mock_client = MagicMock()
        token = "xxoitesttoken"
        channel = 'datateam'

        slack_client = Slack(
            token = token,
            channel = channel,
            file_path = jsonl_path,
            tables = test_tables
        )
