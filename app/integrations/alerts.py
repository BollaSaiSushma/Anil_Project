# app/integrations/alerts.py
import smtplib
from email.mime.text import MIMEText

def send_alert(subject: str, message: str):
    """
    Simple placeholder alert — prints locally.
    You can later extend this to email or Slack.
    """
    print(f"[ALERT] {subject}: {message}")

    # Example: (optional) email alert setup
    try:
        # If you have .env EMAIL_USER and EMAIL_PASSWORD
        from app.utils.config_loader import SETTINGS
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = SETTINGS.email_user
        msg["To"] = SETTINGS.email_user

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SETTINGS.email_user, SETTINGS.email_password)
            server.send_message(msg)

        print("✅ Email alert sent successfully.")
    except Exception as e:
        print("⚠️ Alert email skipped or failed:", e)
