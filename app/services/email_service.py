import datetime
import logging
from threading import Thread
from flask import current_app, render_template
from flask_mail import Message
import boto3
from botocore.exceptions import ClientError
from app import mail

logger = logging.getLogger('cloudvault.email')

def send_async_email(app, msg, email_type, recipient):
    with app.app_context():
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        provider = app.config.get('EMAIL_PROVIDER', 'smtp')

        logger.info(
            f"[MAIL_CONFIG] Provider={provider} "
            f"SENDER={app.config.get('MAIL_DEFAULT_SENDER')} "
            f"Recipient={recipient}"
        )

        try:
            if provider == 'ses':
                # Initialize Amazon SES client using the shared AWS credentials
                ses_client = boto3.client(
                    'ses',
                    aws_access_key_id=app.config.get('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=app.config.get('AWS_SECRET_ACCESS_KEY'),
                    region_name=app.config.get('AWS_REGION', 'ap-south-1')
                )
                
                # Ensure destinations is a list or tuple of email strings
                destinations = msg.recipients if isinstance(msg.recipients, (list, tuple)) else [msg.recipients]
                
                # Send email using SES API over HTTPS
                response = ses_client.send_email(
                    Source=msg.sender,
                    Destination={
                        'ToAddresses': destinations
                    },
                    Message={
                        'Subject': {
                            'Data': msg.subject,
                            'Charset': 'UTF-8'
                        },
                        'Body': {
                            'Html': {
                                'Data': msg.html or msg.body or '',
                                'Charset': 'UTF-8'
                            }
                        }
                    }
                )
                message_id = response.get('MessageId')
                logger.info(
                    f"[EMAIL_SUCCESS] "
                    f"Type={email_type} "
                    f"Recipient={recipient} "
                    f"Time={timestamp} "
                    f"Status=Sent via Amazon SES (MessageId={message_id})"
                )
            else:
                # Default SMTP fallback
                mail.send(msg)
                logger.info(
                    f"[EMAIL_SUCCESS] "
                    f"Type={email_type} "
                    f"Recipient={recipient} "
                    f"Time={timestamp} "
                    f"Status=Sent via SMTP"
                )
        except Exception as e:
            logger.exception(
                f"[EMAIL_FAILED] "
                f"Type={email_type} "
                f"Recipient={recipient} "
                f"Time={timestamp} "
                f"Status=Failed. Reason={str(e)}"
            )

class EmailService:
    def _send_email(self, recipient, subject, html_content, email_type):
        """Helper method to send email with error handling and logging."""
        sender = current_app.config.get('MAIL_DEFAULT_SENDER')
        if not sender:
            # Fallback if config is missing
            sender = "noreply@cloudvault.com"
            
        msg = Message(
            subject=subject,
            recipients=[recipient] if isinstance(recipient, str) else list(recipient),
            html=html_content,
            sender=sender
        )
        
        try:
            app = current_app._get_current_object()
            Thread(target=send_async_email, args=(app, msg, email_type, recipient)).start()
        except Exception as e:
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            logger.error(f"[EMAIL_THREAD_FAILED] Type={email_type} Recipient={recipient} Time={timestamp} Status=Failed Reason=Could not start thread: {str(e)}")
            
        return True

    def send_welcome_email(self, user):
        """Sends a welcome email to the newly registered user."""
        if not user.pref_welcome_email:
            logger.info(f"[EMAIL_SKIPPED] Welcome email disabled by user {user.email}")
            return True
            
        subject = "Welcome to CloudVault - Secure File Storage"
        html_content = render_template('emails/welcome.html', user=user)
        return self._send_email(user.email, subject, html_content, "WELCOME")

    def send_verification_email(self, user, token):
        """Sends an email verification link to the user."""
        # Verification is a critical security email and ignores user preference
        subject = "Verify Your CloudVault Email Address"
        html_content = render_template('emails/verification.html', user=user, token=token)
        return self._send_email(user.email, subject, html_content, "VERIFICATION")

    def send_password_reset_email(self, user, token):
        """Sends a password reset link to the user."""
        # Password reset is a critical security email and ignores user preference
        subject = "Reset Your CloudVault Password"
        html_content = render_template('emails/password_reset.html', user=user, token=token)
        return self._send_email(user.email, subject, html_content, "PASSWORD_RESET")

    def send_password_changed_email(self, user, metadata):
        """Sends a notification that the user's password has changed."""
        if not user.pref_security_alerts:
            logger.info(f"[EMAIL_SKIPPED] Security alert (password change) disabled by user {user.email}")
            return True
            
        subject = "Security Alert: CloudVault Password Changed"
        html_content = render_template('emails/password_changed.html', user=user, metadata=metadata)
        return self._send_email(user.email, subject, html_content, "PASSWORD_CHANGED")

    def send_login_alert(self, user, metadata):
        """Sends a notification of a new login event."""
        if not user.pref_login_alerts:
            logger.info(f"[EMAIL_SKIPPED] Login alert disabled by user {user.email}")
            return True
            
        subject = "Security Alert: New Login to CloudVault Detected"
        html_content = render_template('emails/login_alert.html', user=user, metadata=metadata)
        return self._send_email(user.email, subject, html_content, "LOGIN_ALERT")

    def send_share_email(self, sender, filename, share, emails):
        """Sends share links to one or more recipients."""
        # Recipient preferences are checked on the SENDER side:
        if not sender.pref_share_emails:
            logger.info(f"[EMAIL_SKIPPED] Share emails disabled by sender {sender.email}")
            return True
            
        subject = f"{sender.username} shared a file with you on CloudVault"
        
        # Recipients can be single email or list/tuple of emails
        recipients = [e.strip() for e in emails.split(',')] if isinstance(emails, str) else list(emails)
        
        # Filter empty emails
        recipients = [r for r in recipients if r]
        if not recipients:
            return False
            
        html_content = render_template('emails/share_link.html', sender=sender, filename=filename, share=share)
        return self._send_email(recipients, subject, html_content, "SHARE_LINK")

    def send_storage_warning(self, user, percentage):
        """Sends a warning when user crosses storage limits."""
        if not user.pref_storage_alerts:
            logger.info(f"[EMAIL_SKIPPED] Storage warning disabled by user {user.email}")
            return True
            
        subject = f"Storage Warning: CloudVault Storage at {percentage}%"
        html_content = render_template('emails/storage_warning.html', user=user, percentage=percentage)
        return self._send_email(user.email, subject, html_content, "STORAGE_WARNING")

    def send_contact_email(self, name, email, subject, message):
        """Sends a support message to the administrator."""
        admin_email = current_app.config.get('ADMIN_EMAIL')
        if not admin_email:
            logger.error("[EMAIL_FAILED] ADMIN_EMAIL configuration is missing.")
            return False
            
        email_subject = f"Support Inquiry: {subject}"
        html_content = render_template('emails/contact_support.html', name=name, email=email, subject=subject, message=message)
        return self._send_email(admin_email, email_subject, html_content, "CONTACT_SUPPORT")

    def send_admin_notification(self, subject, text_content):
        """Sends a generic notification to the administrator."""
        admin_email = current_app.config.get('ADMIN_EMAIL')
        if not admin_email:
            logger.error("[EMAIL_FAILED] ADMIN_EMAIL configuration is missing.")
            return False
            
        email_subject = f"Admin Notification: {subject}"
        html_content = render_template('emails/admin_notification.html', subject=subject, content=text_content)
        return self._send_email(admin_email, email_subject, html_content, "ADMIN_NOTIFICATION")

    def send_failed_login_alert(self, user, metadata):
        """Sends an alert about multiple failed login attempts."""
        if not user.pref_security_alerts:
            logger.info(f"[EMAIL_SKIPPED] Security alert (failed login) disabled by user {user.email}")
            return True
            
        subject = "Security Alert: Multiple Failed Login Attempts Detected"
        html_content = render_template('emails/failed_login_alert.html', user=user, metadata=metadata)
        return self._send_email(user.email, subject, html_content, "FAILED_LOGIN_ALERT")

email_service = EmailService()
