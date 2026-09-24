import os
import json
import uuid
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from flask import current_app

logger = logging.getLogger("cloudpulse_service")

class CloudPulseService:
    """
    CloudPulse Integration Service for CloudVault.
    Safely dispatches structured application events to the CloudPulse serverless log ingestion API.
    Guarantees that CloudVault operations will never fail if CloudPulse is unreachable or errors.
    """

    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize with Flask app configuration."""
        self.app = app

    def _get_config(self):
        """Retrieve dynamic configuration from current Flask app context or environment variables."""
        enabled = True
        api_url = ""
        service_name = "CloudVault"
        timeout = 3.0

        if current_app:
            enabled = current_app.config.get("CLOUDPULSE_ENABLED", True)
            api_url = current_app.config.get("CLOUDPULSE_API_URL", "")
            service_name = current_app.config.get("CLOUDPULSE_SERVICE_NAME", "CloudVault")
            timeout = float(current_app.config.get("CLOUDPULSE_TIMEOUT", 3.0))
        else:
            enabled = os.environ.get("CLOUDPULSE_ENABLED", "true").lower() in ("true", "1", "yes", "on")
            api_url = os.environ.get("CLOUDPULSE_API_URL", "")
            service_name = os.environ.get("CLOUDPULSE_SERVICE_NAME", "CloudVault")
            try:
                timeout = float(os.environ.get("CLOUDPULSE_TIMEOUT", 3.0))
            except (ValueError, TypeError):
                timeout = 3.0

        return enabled, api_url, service_name, timeout

    def send_log(self, level="INFO", message="", event=None, user_id=None, file_id=None, file_name=None, metadata=None, request_id=None):
        """
        Sends a structured log event to CloudPulse ingestion API.
        Returns True if successfully ingested, False otherwise.
        Never raises exceptions to caller.
        """
        try:
            enabled, api_url, service_name, timeout = self._get_config()
            if not enabled or not api_url:
                return False

            valid_levels = {"INFO", "WARNING", "ERROR", "CRITICAL"}
            clean_level = level.upper() if isinstance(level, str) and level.upper() in valid_levels else "INFO"

            clean_request_id = str(request_id) if request_id else str(uuid.uuid4())
            clean_timestamp = datetime.now(timezone.utc).isoformat()

            # Ensure safe string formatting for message
            if not message:
                message = f"CloudVault operational event: {event or 'GENERAL'}"

            # Standard CloudPulse payload structure conforming to schema
            payload = {
                "timestamp": clean_timestamp,
                "service": service_name,
                "level": clean_level,
                "message": str(message),
                "request_id": clean_request_id,
            }

            # Optional standard metadata
            if event:
                payload["event"] = str(event)
            if user_id is not None:
                payload["user_id"] = str(user_id)
            if file_id is not None:
                payload["file_id"] = str(file_id)
            if file_name:
                payload["file_name"] = str(file_name)

            if metadata and isinstance(metadata, dict):
                # Clean metadata of sensitive data
                sanitized_meta = {}
                sensitive_keys = {"password", "token", "secret", "key", "authorization", "auth", "hash"}
                for k, v in metadata.items():
                    if not any(sk in str(k).lower() for sk in sensitive_keys):
                        # Ensure value is JSON serializable
                        if isinstance(v, (str, int, float, bool, list, dict)) or v is None:
                            sanitized_meta[str(k)] = v
                        else:
                            sanitized_meta[str(k)] = str(v)
                payload["metadata"] = sanitized_meta

            # Make HTTP POST request with timeout
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                api_url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status in (200, 201, 202):
                    return True
                else:
                    self._log_internal(logging.WARNING, f"CloudPulse unexpected status: {response.status}")
                    return False

        except urllib.error.HTTPError as he:
            self._log_internal(logging.WARNING, f"CloudPulse HTTP error: {he.code} {he.reason}")
            return False
        except urllib.error.URLError as ue:
            self._log_internal(logging.WARNING, f"CloudPulse connection error: {ue.reason}")
            return False
        except TimeoutError:
            self._log_internal(logging.WARNING, "CloudPulse log delivery timed out")
            return False
        except Exception as e:
            self._log_internal(logging.WARNING, f"CloudPulse integration error: {str(e)}")
            return False

    def _log_internal(self, log_level, message):
        """Safely logs internal integration warnings to Flask's app.logger or standard logging."""
        try:
            if current_app:
                current_app.logger.log(log_level, f"[CloudPulse Integration] {message}")
            else:
                logger.log(log_level, f"[CloudPulse Integration] {message}")
        except Exception:
            pass

    # ==========================================
    # High-level Convenience Helpers
    # ==========================================

    def log_upload(self, user=None, file_name="", file_id=None, file_size=None, is_version=False, version_num=None, success=True, error=None, ip_address=None):
        """Log a file upload or version upload event."""
        username = user.username if hasattr(user, "username") else (str(user) if user else "Unknown")
        user_id = user.id if hasattr(user, "id") else (user if isinstance(user, int) else None)

        if success:
            level = "INFO"
            if is_version:
                msg = f"User '{username}' uploaded new version (V{version_num or 2}) of file '{file_name}' ({file_size or 0} bytes)"
            else:
                msg = f"User '{username}' uploaded file '{file_name}' successfully ({file_size or 0} bytes)"
        else:
            level = "ERROR"
            msg = f"Failed to upload file '{file_name}' for user '{username}': {error or 'Storage/S3 error'}"

        meta = {
            "is_version": is_version,
            "version_number": version_num,
            "file_size": file_size,
            "ip_address": ip_address,
            "success": success
        }
        if error:
            meta["error"] = str(error)

        return self.send_log(
            level=level,
            message=msg,
            event="FILE_UPLOAD",
            user_id=user_id,
            file_id=file_id,
            file_name=file_name,
            metadata=meta
        )

    def log_download(self, user=None, file_name="", file_id=None, version_num=None, is_public=False, success=True, error=None, ip_address=None):
        """Log a file download event."""
        username = user.username if hasattr(user, "username") else (str(user) if user else "Public")
        user_id = user.id if hasattr(user, "id") else (user if isinstance(user, int) else None)

        if success:
            level = "INFO"
            if is_public:
                msg = f"Public user downloaded shared file '{file_name}'"
            elif version_num:
                msg = f"User '{username}' downloaded version V{version_num} of file '{file_name}'"
            else:
                msg = f"User '{username}' downloaded file '{file_name}'"
        else:
            level = "ERROR"
            msg = f"Failed download attempt for file '{file_name}': {error or 'Download error'}"

        meta = {
            "version_number": version_num,
            "is_public": is_public,
            "ip_address": ip_address,
            "success": success
        }
        if error:
            meta["error"] = str(error)

        return self.send_log(
            level=level,
            message=msg,
            event="FILE_DOWNLOAD",
            user_id=user_id,
            file_id=file_id,
            file_name=file_name,
            metadata=meta
        )

    def log_delete(self, user=None, file_name="", file_id=None, permanent=False, is_folder=False, ip_address=None):
        """Log a file or folder deletion event (soft delete to trash or permanent)."""
        username = user.username if hasattr(user, "username") else (str(user) if user else "Unknown")
        user_id = user.id if hasattr(user, "id") else (user if isinstance(user, int) else None)

        entity_type = "folder" if is_folder else "file"
        level = "WARNING" if permanent else "INFO"

        if permanent:
            msg = f"User '{username}' permanently deleted {entity_type} '{file_name}'"
        else:
            msg = f"User '{username}' moved {entity_type} '{file_name}' to trash"

        meta = {
            "permanent": permanent,
            "is_folder": is_folder,
            "ip_address": ip_address
        }

        return self.send_log(
            level=level,
            message=msg,
            event="FILE_DELETE",
            user_id=user_id,
            file_id=file_id,
            file_name=file_name,
            metadata=meta
        )

    def log_share(self, user=None, file_name="", file_id=None, action="create", share_id=None, ip_address=None):
        """Log a file share creation or revocation event."""
        username = user.username if hasattr(user, "username") else (str(user) if user else "Unknown")
        user_id = user.id if hasattr(user, "id") else (user if isinstance(user, int) else None)

        if action == "revoke":
            msg = f"User '{username}' revoked share link for file '{file_name}'"
        elif action == "expire":
            msg = f"Share link for file '{file_name}' expired"
        else:
            msg = f"User '{username}' created public share link for file '{file_name}'"

        meta = {
            "action": action,
            "share_id": share_id,
            "ip_address": ip_address
        }

        return self.send_log(
            level="INFO",
            message=msg,
            event="FILE_SHARE",
            user_id=user_id,
            file_id=file_id,
            file_name=file_name,
            metadata=meta
        )

    def log_login_success(self, user=None, ip_address=None, auth_method="password"):
        """Log a successful login event."""
        username = user.username if hasattr(user, "username") else (str(user) if user else "Unknown")
        user_id = user.id if hasattr(user, "id") else (user if isinstance(user, int) else None)
        email = user.email if hasattr(user, "email") else ""

        msg = f"User '{username}' ({email}) logged in successfully via {auth_method}"

        meta = {
            "email": email,
            "auth_method": auth_method,
            "ip_address": ip_address
        }

        return self.send_log(
            level="INFO",
            message=msg,
            event="LOGIN_SUCCESS",
            user_id=user_id,
            metadata=meta
        )

    def log_login_failure(self, email="", ip_address=None, attempts=1, reason="invalid_credentials"):
        """Log a failed login attempt event."""
        level = "ERROR" if attempts >= 5 else "WARNING"
        msg = f"Failed login attempt for email '{email}' (attempts: {attempts}, reason: {reason})"

        meta = {
            "email": email,
            "attempts": attempts,
            "reason": reason,
            "ip_address": ip_address
        }

        return self.send_log(
            level=level,
            message=msg,
            event="LOGIN_FAILURE",
            metadata=meta
        )

    def log_restore(self, user=None, file_name="", file_id=None, is_version=False, version_num=None, is_folder=False, ip_address=None):
        """Log a file, folder, or version restore event."""
        username = user.username if hasattr(user, "username") else (str(user) if user else "Unknown")
        user_id = user.id if hasattr(user, "id") else (user if isinstance(user, int) else None)

        if is_version:
            event = "FILE_VERSION"
            msg = f"User '{username}' restored file '{file_name}' to version V{version_num}"
        elif is_folder:
            event = "FILE_RESTORE"
            msg = f"User '{username}' restored folder '{file_name}' from trash"
        else:
            event = "FILE_RESTORE"
            msg = f"User '{username}' restored file '{file_name}' from trash"

        meta = {
            "is_version": is_version,
            "version_number": version_num,
            "is_folder": is_folder,
            "ip_address": ip_address
        }

        return self.send_log(
            level="INFO",
            message=msg,
            event=event,
            user_id=user_id,
            file_id=file_id,
            file_name=file_name,
            metadata=meta
        )

cloudpulse_service = CloudPulseService()
