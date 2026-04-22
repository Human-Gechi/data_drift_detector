import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

subject = "Data Drift Report"
RETRIES = 5
BASE = 1


class Email:
    def __init__(
        self, sender_email: str, receiver_email: str, sender_password: str, tables: List[str]
    ):
        self.sender_email = sender_email
        self.receiver_email = receiver_email
        self.sender_password = sender_password
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.file_path = "monitoring_history.jsonl"
        self.tables = tables

    def send_email(self, subject=subject, body=None):
        from src.extras.drift_detector import check_and_alert

        drift_report = check_and_alert(self.file_path, self.tables)

        if body is None:
            body = drift_report

        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = self.receiver_email
        message["Subject"] = subject

        message.attach(MIMEText(body, "plain"))

        attempt = 0
        while attempt < RETRIES:
            try:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.sender_email, self.sender_password)
                    server.sendmail(self.sender_email, self.receiver_email, message.as_string())
                return f"Email sucessfully sent to {self.receiver_email}"
            except Exception as e:
                attempt += 1
                print(f"Attempt {attempt} failed: {e}")
                time.sleep(BASE * attempt)
        return f"Failed to send email after retries {RETRIES}"