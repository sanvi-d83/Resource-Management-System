import os
import smtplib
from email.message import EmailMessage


def send_low_resource_email(building_name, building_id, resource, current_value, threshold, unit):
    """Send an alert if SMTP settings are configured; otherwise report demo mode."""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("ALERT_FROM") or smtp_user
    recipient = os.environ.get("ALERT_TO")

    if not all([smtp_host, smtp_user, smtp_password, sender, recipient]):
        print(
            f"[EMAIL NOT SENT - SMTP NOT CONFIGURED] {resource} low in "
            f"{building_name} ({building_id}): {current_value} {unit}; "
            f"threshold {threshold} {unit}"
        )
        return "SMTP not configured (logged to console)"

    msg = EmailMessage()
    msg["Subject"] = f"Low {resource} Alert - {building_name}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(
        f"""Resource Management System Alert

Building: {building_name} ({building_id})
Resource: {resource}
Current level: {current_value} {unit}
Admin minimum limit: {threshold} {unit}

The current resource level is below the configured minimum.
Please investigate and take appropriate action.
"""
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return f"Email sent to {recipient}"
    except Exception as exc:
        print(f"[EMAIL ERROR] {exc}")
        return f"Email failed: {exc}"
