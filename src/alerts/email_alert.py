import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.extras.drift_detector import check_and_alert


class Email:
    def __init__(self, sender_email, receiver_email, sender_password, smtp_server, smtp_port):
        self.sender_email = sender_email
        self.receiver_email = receiver_email
        self.sender_password = sender_password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port

    