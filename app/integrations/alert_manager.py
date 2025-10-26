import smtplib
from email.mime.text import MIMEText
from app.utils.config_loader import SETTINGS
from app.utils.logger import logger

def send_alert(subject: str, body: str, to_email: str | None = None):
    to_email = to_email or SETTINGS.email_user

    if not SETTINGS.email_user or not SETTINGS.email_password:
        logger.warning("Email creds missing — skipping alert: %s", subject)
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SETTINGS.email_user
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SETTINGS.email_user, SETTINGS.email_password)
        s.send_message(msg)
