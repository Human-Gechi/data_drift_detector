import os
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

_EMAIL_SUBJECT = "Data Drift Alert"
_RETRIES = 5
_BASE = 1


class Email:
    def __init__(
        self, sender_email: str, receiver_email: str, sender_password: str, tables: List[str], file_path: str = None
    ):
        self.sender_email = sender_email
        self.receiver_email = receiver_email
        self.sender_password = sender_password
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 465
        self.file_path = file_path or "monitoring_history.jsonl"
        self.tables = tables

        template_dir = os.path.join(os.path.dirname(__file__), "templates")

        self.env = Environment(
            loader=FileSystemLoader(template_dir), autoescape=select_autoescape(["html"])
        )

    def send_email(self, subject=_EMAIL_SUBJECT, html_body: str = None):
        from src.detect.drift_detector import detect_drift

        drift_report = detect_drift(self.file_path, self.tables)

        template = self.env.get_template("drift_alert.html")
        html_body = template.render(timestamp=datetime.now().isoformat(), drift_report=drift_report)

        message = MIMEMultipart("alternative")
        message["From"] = self.sender_email
        message["To"] = self.receiver_email
        message["Subject"] = subject

        message.attach(MIMEText(html_body, "html"))

        attempt = 0
        while attempt < _RETRIES:
            try:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.sender_email, self.sender_password)
                    server.sendmail(self.sender_email, self.receiver_email, message.as_string())
                print(f"✅ Email successfully sent to {self.receiver_email}")
                break
            except Exception as e:
                attempt += 1
                print(f"Attempt {attempt} failed: {e}")
                time.sleep(_BASE * attempt)
        else:
            print(f"Failed to send email after {_RETRIES} retries")
