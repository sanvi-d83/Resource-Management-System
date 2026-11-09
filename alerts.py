import os
import smtplib
from email.message import EmailMessage


def _send_message(recipient, subject, body):
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("ALERT_FROM") or smtp_user

    if not all([smtp_host, smtp_user, smtp_password, sender, recipient]):
        return "Email not sent: configure sender Gmail and App Password in Admin Settings."

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return f"Email sent to {recipient}"
    except Exception as exc:
        print(f"[EMAIL ERROR] {exc}")
        return f"Email failed: {exc}"


def send_low_resource_summary_email(recipient, alerts):
    count = len(alerts)

    body = f"""Resource Management System
Low Resource Alert Summary

There {"is" if count == 1 else "are"} {count} new low-resource alert{"s" if count != 1 else ""}.

"""

    for index, alert in enumerate(alerts, start=1):
        body += f"""Alert {index}
Building: {alert['building_name']} ({alert['building_id']})
Resource: {alert['resource']}
Current level: {alert['current_value']:g} {alert['unit']}
Admin minimum limit: {alert['threshold']:g} {alert['unit']}

"""

    body += """Please investigate these low-resource alerts.

This email groups alerts generated during one monitoring cycle.
"""

    subject = f"ResourceFlow - {count} Low Resource Alert{'s' if count != 1 else ''}"

    return _send_message(recipient, subject, body)

