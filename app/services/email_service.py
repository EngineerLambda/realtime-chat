import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import random
import string
from typing import Literal

load_dotenv()

SMTP_SERVER = os.getenv("ZOHO_SMTP_SERVER", "smtp.zoho.com")
SMTP_PORT = int(os.getenv("ZOHO_SMTP_PORT", "465"))
SMTP_EMAIL = os.getenv("ZOHO_EMAIL")
SMTP_PASSWORD = os.getenv("ZOHO_APP_PASSWORD")


def smtp_is_configured():
    config_ok = bool(SMTP_SERVER and SMTP_PORT and SMTP_EMAIL and SMTP_PASSWORD)
    if not config_ok:
        print(
            "SMTP config incomplete. Server: {}, Port: {}, Email: {}, PasswordSet: {}".format(
                SMTP_SERVER, SMTP_PORT, SMTP_EMAIL, SMTP_PASSWORD is not None
            )
        )
    return config_ok


def send_smtp_email(to: str, subject: str, html: str) -> bool:
    print(f"Preparing to send SMTP email to: {to} | subject: {subject}")
    if not smtp_is_configured():
        print("SMTP settings are not fully configured. Skipping email sending.")
        return False

    assert SMTP_EMAIL is not None
    assert SMTP_PASSWORD is not None

    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))
    try:
        print(f"Connecting to SMTP server at {SMTP_SERVER}:{SMTP_PORT} as {SMTP_EMAIL}")
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            _ = server.login(SMTP_EMAIL, SMTP_PASSWORD)
            _ = server.send_message(msg)
        print(f"Mail sent successfully to {to} via Zoho SMTP.")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(
            f"SMTP Authentication Failed for {to}: {e}. Please check ZOHO_EMAIL and ZOHO_APP_PASSWORD environment variables, and ensure ZOHO_SMTP_SERVER is correct for your account's region."
        )
        return False
    except Exception as e:
        print(f"Failed to send email to {to}: {e}")
        return False


def generate_otp(length: int = 6) -> str:
    """Generates a random OTP of a given length."""
    return "".join(random.choices(string.digits, k=length))


def send_otp_email(user_email: str, code: str, ttl_minutes: int) -> bool:
    print(f"Sending OTP email to {user_email} | code: {code}")
    html_body = f"""
    <html>
        <body>
            <h3>Your Verification Code</h3>
            <p>Use the 6-digit code below to complete verification.</p>
            <div style="font-size: 24px; font-weight: bold; letter-spacing: 4px; margin: 12px 0;">{code}</div>
            <p>This code will expire in {ttl_minutes} minutes.</p>
            <p>If you did not request this, you can ignore this message.</p>
        </body>
    </html>
    """
    return send_smtp_email(
        to=user_email,
        subject="Your Password Reset Code",
        html=html_body,
    )


def send_confirmation_email(user_email: str, purpose: Literal["password"]) -> bool:
    subject = ""
    html_body = ""
    if purpose == "password":
        subject = "Your Password Has Been Reset"
        html_body = """
        <html><body>
            <h3>Password Reset Confirmation</h3>
            <p>Your password has been successfully reset.</p>
            <p>If you did not make this change, please contact our support team immediately.</p>
        </body></html>
        """

    if subject and html_body:
        return send_smtp_email(to=user_email, subject=subject, html=html_body)
    return False