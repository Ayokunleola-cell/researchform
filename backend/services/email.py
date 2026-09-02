# backend/services/email.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings
import logging

logger = logging.getLogger(__name__)

async def send_otp_email(to_email: str, otp_code: str):
    subject = f"Your ResearchForm Verification Code: {otp_code}"
    body = f"""
    Hello,
    
    Your verification code for ResearchForm is: {otp_code}
    
    This code will expire in 10 minutes.
    
    If you did not request this code, please ignore this email.
    
    Thanks,
    ResearchForm Team
    """

    # If in DEV_MODE, print to terminal instead of sending actual email
    if getattr(settings, 'DEV_MODE', True):
        print("="*50)
        print(f"MOCK EMAIL TO: {to_email}")
        print(f"SUBJECT: {subject}")
        print(f"BODY:\n{body}")
        print("="*50)
        return True
        
    # Standard SMTP sending
    # These would typically be in config.py: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
    smtp_host = getattr(settings, 'SMTP_HOST', None)
    smtp_port = getattr(settings, 'SMTP_PORT', 587)
    smtp_user = getattr(settings, 'SMTP_USER', None)
    smtp_pass = getattr(settings, 'SMTP_PASSWORD', None)
    
    if not all([smtp_host, smtp_user, smtp_pass]):
        logger.warning(f"SMTP not configured. Failed to send OTP to {to_email}")
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_host, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False

async def send_dataset_review_email(to_email: str, dataset_title: str, status: str, reason: str = None):
    if status == "verified":
        subject = f"Your dataset '{dataset_title}' has been verified and listed!"
        body = f"""
        Hello,
        
        Great news! Your dataset '{dataset_title}' has passed our administrative review and is now officially listed on the DataNest Marketplace.
        
        Thank you for contributing to the research community.
        
        Best,
        DataNest Team
        """
    else:
        subject = f"Update on your dataset '{dataset_title}'"
        body = f"""
        Hello,
        
        We have reviewed your dataset '{dataset_title}'. Unfortunately, it has not passed our verification process and has been rejected for the following reason:
        
        {reason or 'No specific reason provided.'}
        
        You may update your dataset based on this feedback and resubmit it for verification from your seller dashboard.
        
        Best,
        DataNest Team
        """

    if getattr(settings, 'DEV_MODE', True):
        print("="*50)
        print(f"MOCK EMAIL TO: {to_email}")
        print(f"SUBJECT: {subject}")
        print(f"BODY:\n{body}")
        print("="*50)
        return True
        
    smtp_host = getattr(settings, 'SMTP_HOST', None)
    smtp_port = getattr(settings, 'SMTP_PORT', 587)
    smtp_user = getattr(settings, 'SMTP_USER', None)
    smtp_pass = getattr(settings, 'SMTP_PASSWORD', None)
    
    if not all([smtp_host, smtp_user, smtp_pass]):
        logger.warning(f"SMTP not configured. Failed to send review email to {to_email}")
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_host, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send review email to {to_email}: {e}")
        return False

async def send_kyc_status_email(to_email: str, status: str, reason: str = None):
    if status == "in_process":
        subject = "Your KYC & Bank Details Verification is In Process"
        body = """
        Hello,
        
        We have received your KYC document and bank account details for payout verification. 
        Our admin team is currently reviewing your submission. We will notify you once the review is complete.
        
        Best,
        ResearchForm Team
        """
    elif status == "approved":
        subject = "Your Payout Account has been Approved!"
        body = """
        Hello,
        
        Great news! Your KYC document and bank details have been verified and approved. 
        Your account is now valid to receive payouts for your dataset sales.
        
        Note: When you request a withdrawal, please allow 2 working days for the payment to be processed and disbursed to your account.
        
        Best,
        ResearchForm Team
        """
    elif status == "denied":
        subject = "Action Required: Payout Account Verification Denied"
        body = f"""
        Hello,
        
        We have reviewed your KYC submission and unfortunately, it could not be approved for the following reason:
        
        {reason or 'No specific reason provided.'}
        
        Please log into your ResearchForm settings to update your information and resubmit.
        
        Best,
        ResearchForm Team
        """
    else:
        return False

    if getattr(settings, 'DEV_MODE', True):
        print("="*50)
        print(f"MOCK KYC EMAIL TO: {to_email}")
        print(f"SUBJECT: {subject}")
        print(f"BODY:\n{body}")
        print("="*50)
        return True
        
    smtp_host = getattr(settings, 'SMTP_HOST', None)
    smtp_port = getattr(settings, 'SMTP_PORT', 587)
    smtp_user = getattr(settings, 'SMTP_USER', None)
    smtp_pass = getattr(settings, 'SMTP_PASSWORD', None)
    
    if not all([smtp_host, smtp_user, smtp_pass]):
        logger.warning(f"SMTP not configured. Failed to send KYC email to {to_email}")
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_host, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send KYC email to {to_email}: {e}")
        return False
