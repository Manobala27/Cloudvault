import datetime
import logging
from threading import Thread
import urllib.request
import urllib.error
import json
from flask import current_app, render_template

logger = logging.getLogger('cloudvault.email')

def send_async_email(app, msg, email_type, recipient):
    with app.app_context():
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        sender_email = msg.get('sender') or app.config.get('MAIL_DEFAULT_SENDER') or 'noreply@cloudvault.com'

        logger.info(
            f"[MAIL_CONFIG] "
            f"SENDER={sender_email} "
            f"Recipient={recipient}"
        )

        api_key = app.config.get('BREVO_API_KEY')
        if not api_key:
            logger.error(
                f"[EMAIL_FAILED] "
                f"Type={email_type} "
                f"Recipient={recipient} "
                f"Time={timestamp} "
                f"Status=Failed. Reason=BREVO_API_KEY configuration is missing."
            )
            return

        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        }

        # Format destinations list for Brevo API
        if isinstance(recipient, (list, tuple)):
            to_list = [{"email": r} for r in recipient]
        else:
            to_list = [{"email": recipient}]

        payload = {
            "sender": {"email": sender_email},
            "to": to_list,
            "subject": msg.get('subject', ''),
            "htmlContent": msg.get('html', '')
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                status_code = response.getcode()
                response_body = response.read().decode('utf-8')
                logger.info(
                    f"[EMAIL_SUCCESS] "
                    f"Type={email_type} "
                    f"Recipient={recipient} "
                    f"Time={timestamp} "
                    f"Status=Sent via Brevo HTTP API (HTTP {status_code}) "
                    f"Response={response_body}"
                )
        except urllib.error.HTTPError as e:
            status_code = e.code
            error_body = e.read().decode('utf-8')
            logger.error(
                f"[EMAIL_FAILED] "
                f"Type={email_type} "
                f"Recipient={recipient} "
                f"Time={timestamp} "
                f"Status=Failed. HTTPStatus={status_code} "
                f"ErrorResponse={error_body}"
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
            
        msg = {
            'subject': subject,
            'recipients': [recipient] if isinstance(recipient, str) else list(recipient),
            'html': html_content,
            'sender': sender
        }
        
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
