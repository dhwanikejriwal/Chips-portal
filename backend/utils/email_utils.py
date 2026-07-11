import os
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from dotenv import load_dotenv

load_dotenv(override=True)

# Setup Connection Config
conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', ''),
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', ''),
    MAIL_FROM = os.getenv('MAIL_FROM') or 'noreply@chips-portal.in',
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587)),
    MAIL_SERVER = os.getenv('MAIL_SERVER', ''),
    MAIL_FROM_NAME = os.getenv('MAIL_FROM_NAME', 'CHiPS Admin Portal'),
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

async def send_approval_email(email_to: str, name: str, username: str, raw_password: str):
    """
    Sends an automated HTML email to the candidate upon approval,
    containing their login credentials.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f1f5f9;
                padding: 20px;
                color: #334155;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 20px;
                margin-bottom: 20px;
            }}
            .header h2 {{
                color: #10b981;
                margin: 0;
            }}
            .content p {{
                font-size: 16px;
                line-height: 1.5;
            }}
            .credentials-box {{
                background-color: #f8fafc;
                border-left: 4px solid #3b82f6;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            .credentials-box strong {{
                color: #0f172a;
            }}
            .footer {{
                margin-top: 30px;
                text-align: center;
                font-size: 14px;
                color: #64748b;
                border-top: 1px solid #e2e8f0;
                padding-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Application Approved!</h2>
            </div>
            <div class="content">
                <p>Dear {name},</p>
                <p>Congratulations! Your application has been successfully approved by the Administrator.</p>
                <p>You can now log in to the portal using the credentials below:</p>
                
                <div class="credentials-box">
                    <p><strong>Username:</strong> {username}</p>
                    <p><strong>Password:</strong> {raw_password}</p>
                </div>
                
                <p>For security reasons, we strongly recommend that you change your password upon your first login.</p>
                <p>Best regards,<br>The CHiPS Administration Team</p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply directly to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """

    message = MessageSchema(
        subject="Your Application has been Approved - CHiPS Portal",
        recipients=[email_to],
        body=html_content,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
    except Exception as e:
        print(f"Failed to send email to {email_to}: {e}")
        raise e

async def send_lms_approval_email(email_to: str, name: str, username: str, raw_password: str, lms_link: str):
    """
    Sends an automated HTML email to the candidate upon LMS approval,
    containing their LMS login credentials and portal link.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f1f5f9;
                padding: 20px;
                color: #334155;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 20px;
                margin-bottom: 20px;
            }}
            .header h2 {{
                color: #0f172a;
                margin: 0;
            }}
            .content {{
                line-height: 1.6;
            }}
            .credentials-box {{
                background-color: #f8fafc;
                border-left: 4px solid #10b981;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            .credentials-box p {{
                margin: 5px 0;
            }}
            .btn {{
                display: inline-block;
                background-color: #0f172a;
                color: #ffffff;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 6px;
                margin-top: 15px;
                font-weight: 500;
            }}
            .footer {{
                text-align: center;
                font-size: 14px;
                color: #64748b;
                border-top: 1px solid #e2e8f0;
                padding-top: 20px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>LMS Application Approved</h2>
            </div>
            <div class="content">
                <p>Hello {name},</p>
                <p>Congratulations! Your LMS application has been reviewed and approved by the CHiPS Administration.</p>
                <p>You can now log in to the LMS portal using the credentials below:</p>
                
                <div class="credentials-box">
                    <p><strong>Username:</strong> {username}</p>
                    <p><strong>Password:</strong> {raw_password}</p>
                </div>
                
                <p>Please click the button below to access the LMS portal:</p>
                <a href="{lms_link}" class="btn" style="color: #ffffff;">Go to LMS Portal</a>
                
                <p>For security reasons, we strongly recommend that you change your password upon your first login.</p>
                <p>Best regards,<br>The CHiPS Administration Team</p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply directly to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """

    message = MessageSchema(
        subject="Your LMS Application has been Approved - CHiPS Portal",
        recipients=[email_to],
        body=html_content,
        subtype=MessageType.html
    )

    # Bypass email sending if SMTP server is not configured
    if not conf.MAIL_SERVER:
        print(f"\n======================================")
        print(f"MOCK EMAIL TO: {email_to}")
        print(f"SUBJECT: Your LMS Application has been Approved - CHiPS Portal")
        print(f"Username: {username}")
        print(f"Password: {raw_password}")
        print(f"LMS Link: {lms_link}")
        print(f"======================================\n")
        return

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
    except Exception as e:
        print(f"Failed to send LMS approval email to {email_to}: {e}")
        raise e

async def send_rejection_email(email_to: str, name: str, reason: str):
    """
    Sends an automated HTML email to the candidate upon rejection,
    containing the reason for rejection.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f1f5f9;
                padding: 20px;
                color: #334155;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 20px;
                margin-bottom: 20px;
            }}
            .header h2 {{
                color: #ef4444;
                margin: 0;
            }}
            .content p {{
                font-size: 16px;
                line-height: 1.5;
            }}
            .reason-box {{
                background-color: #fef2f2;
                border-left: 4px solid #ef4444;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
                color: #b91c1c;
            }}
            .footer {{
                margin-top: 30px;
                text-align: center;
                font-size: 14px;
                color: #64748b;
                border-top: 1px solid #e2e8f0;
                padding-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Application Update</h2>
            </div>
            <div class="content">
                <p>Dear {name},</p>
                <p>We are writing to inform you that your onboarding request for Aadhaar Operator has not been approved at this time.</p>
                <p>The Administrator provided the following reason for this decision:</p>
                
                <div class="reason-box">
                    <p><strong>Reason:</strong> {reason}</p>
                </div>
                
                <p>If you have any questions or require further clarification, please contact your district coordinator.</p>
                <p>Best regards,<br>The CHiPS Administration Team</p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply directly to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """

    message = MessageSchema(
        subject="Update on your CHiPS Portal Application",
        recipients=[email_to],
        body=html_content,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
    except Exception as e:
        print(f"Failed to send email to {email_to}: {e}")
        raise e

async def send_password_reset_email(email_to: str, name: str, reset_link: str):
    """
    Sends an automated HTML email for password reset.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f1f5f9;
                padding: 20px;
                color: #334155;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 20px;
                margin-bottom: 20px;
            }}
            .header h2 {{
                color: #3b82f6;
                margin: 0;
            }}
            .content p {{
                font-size: 16px;
                line-height: 1.5;
            }}
            .btn-reset {{
                display: inline-block;
                background-color: #3b82f6;
                color: white !important;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 4px;
                font-weight: 600;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 30px;
                text-align: center;
                font-size: 14px;
                color: #64748b;
                border-top: 1px solid #e2e8f0;
                padding-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Password Reset Request</h2>
            </div>
            <div class="content">
                <p>Dear {name},</p>
                <p>We received a request to reset your password for the CHiPS Admin Portal.</p>
                <p>Click the button below to set a new password. This link is valid for 15 minutes.</p>
                
                <div style="text-align: center;">
                    <a href="{reset_link}" class="btn-reset">Reset Password</a>
                </div>
                
                <p>If you did not request a password reset, please ignore this email or contact support if you have concerns.</p>
                <p>Best regards,<br>The CHiPS Administration Team</p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply directly to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """

    message = MessageSchema(
        subject="Password Reset - CHiPS Portal",
        recipients=[email_to],
        body=html_content,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
    except Exception as e:
        print(f"Failed to send email to {email_to}: {e}")

async def send_password_reset_otp_email(email_to: str, name: str, otp_code: str):
    """
    Sends an automated HTML email for password reset via OTP.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f1f5f9;
                padding: 20px;
                color: #334155;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 20px;
                margin-bottom: 20px;
            }}
            .header h2 {{
                color: #3b82f6;
                margin: 0;
            }}
            .content p {{
                font-size: 16px;
                line-height: 1.5;
            }}
            .otp-box {{
                background-color: #f8fafc;
                border-left: 4px solid #3b82f6;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
                font-size: 24px;
                font-weight: bold;
                letter-spacing: 5px;
                text-align: center;
                color: #0f172a;
            }}
            .footer {{
                margin-top: 30px;
                text-align: center;
                font-size: 14px;
                color: #64748b;
                border-top: 1px solid #e2e8f0;
                padding-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Password Reset Request</h2>
            </div>
            <div class="content">
                <p>Dear {name},</p>
                <p>We received a request to reset your password for the CHiPS Admin Portal.</p>
                <p>Please use the following One-Time Password (OTP) to reset your password. This OTP is valid for 15 minutes.</p>
                
                <div class="otp-box">
                    {otp_code}
                </div>
                
                <p>If you did not request a password reset, please ignore this email or contact support if you have concerns.</p>
                <p>Best regards,<br>The CHiPS Administration Team</p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply directly to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """

    message = MessageSchema(
        subject="Password Reset OTP - CHiPS Portal",
        recipients=[email_to],
        body=html_content,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
    except Exception as e:
        print(f"Failed to send email to {email_to}: {e}")


async def send_otp_email(email_to: str, otp_code: str):
    """
    Sends an automated HTML email containing the verification OTP.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f1f5f9;
                padding: 20px;
                color: #334155;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 20px;
                margin-bottom: 20px;
            }}
            .header h2 {{
                color: #3b82f6;
                margin: 0;
            }}
            .content p {{
                font-size: 16px;
                line-height: 1.5;
            }}
            .otp-box {{
                background-color: #f8fafc;
                border: 2px dashed #3b82f6;
                padding: 20px;
                margin: 20px 0;
                border-radius: 4px;
                text-align: center;
                font-size: 32px;
                letter-spacing: 5px;
                font-weight: bold;
                color: #0f172a;
            }}
            .footer {{
                margin-top: 30px;
                text-align: center;
                font-size: 14px;
                color: #64748b;
                border-top: 1px solid #e2e8f0;
                padding-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Email Verification</h2>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>Please use the following One-Time Password (OTP) to verify your email address during registration. This code is valid for 3 minutes.</p>
                
                <div class="otp-box">
                    {otp_code}
                </div>
                
                <p>If you did not request this, please ignore this email.</p>
                <p>Best regards,<br>The CHiPS Administration Team</p>
            </div>
            <div class="footer">
                <p>This is an automated email. Please do not reply directly to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """

    message = MessageSchema(
        subject="Your Registration OTP - CHiPS Portal",
        recipients=[email_to],
        body=html_content,
        subtype=MessageType.html,
        headers={
            "Reply-To": conf.MAIL_FROM,
            "X-Mailer": "CHiPS-Portal-Mailer"
        }
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        return True
    except Exception as e:
        print(f"Failed to send email to {email_to}: {e}")
        return False
