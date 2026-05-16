import os
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader, select_autoescape

_EMAIL_SUBJECT = "Data Drift Alert"
_RETRIES = 5
_BASE = 1

_SMTP_SETTINGS = {
    "gmail.com": {"server": "smtp.gmail.com", "ssl_port": 465, "tls_port": 587},
    "yahoo.com": {"server": "smtp.mail.yahoo.com", "ssl_port": 465, "tls_port": 587},
    "outlook.com": {"server": "smtp.office365.com", "ssl_port": 587, "tls_port": 587},
}


class Email:
    def __init__(
        self,
        sender: str,
        password: str,
        receiver: str,
        drift_report: str,
        use_ssl: bool = False,
    ):
        self.sender = sender
        self.password = password
        self.receiver = receiver
        self.drift_report = drift_report
        self.use_ssl = use_ssl
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.env = Environment(
            loader=FileSystemLoader(template_dir), autoescape=select_autoescape(["html"])
        )

        domain = sender.split("@")[-1]
        settings = _SMTP_SETTINGS.get(domain)
        if not settings:
            raise ValueError(f"Unsupported email provider: {domain}")
        self.smtp_server = settings["server"]
        self.smtp_port = settings["ssl_port"] if use_ssl else settings["tls_port"]

    def send_email(self, subject=_EMAIL_SUBJECT):
        if self.drift_report is None:
            raise ValueError("Drift report must be provided!")

        template = self.env.get_template("drift_alert.html")
        html_body = template.render(
            timestamp=datetime.now().isoformat(), drift_report=self.drift_report
        )

        message = MIMEMultipart("alternative")
        message["From"] = self.sender
        message["To"] = self.receiver
        message["Subject"] = subject
        message.attach(MIMEText(html_body, "html"))

        attempt = 0
        while attempt < _RETRIES:
            try:
                if self.use_ssl:
                    with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                        server.login(self.sender, self.password)
                        server.sendmail(self.sender, self.receiver, message.as_string())
                else:
                    with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                        server.ehlo()
                        server.starttls()
                        server.login(self.sender, self.password)
                        server.sendmail(self.sender, self.receiver, message.as_string())
                print(f"✅ Email successfully sent to {self.receiver}")
                break
            except Exception as e:
                attempt += 1
                print(f"Attempt {attempt} failed: {e}")
                time.sleep(_BASE * attempt)
        else:
            print(f"Failed to send email after {_RETRIES} retries")
