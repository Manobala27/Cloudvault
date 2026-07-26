import os
import json
import threading

class SettingsService:
    def __init__(self):
        self.filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings.json')
        self.lock = threading.Lock()
        self.defaults = {
            'upload_limit_mb': 10,
            'storage_limit_gb': 15,
            'allowed_extensions': 'png,jpg,jpeg,gif,pdf,doc,docx,xls,xlsx,zip,txt',
            'maintenance_mode': False,
            'registration_enabled': True,
            'email_verification_required': True,
            'password_min_length': 8,
            'smtp_host': '',
            'smtp_port': 587,
            'smtp_user': '',
            'smtp_password': '',
            'smtp_default_sender': 'noreply@cloudvault.com'
        }
        self._load_settings()

    def _load_settings(self):
        with self.lock:
            if not os.path.exists(self.filepath):
                self._save_settings_unlocked(self.defaults)
                self.settings = dict(self.defaults)
            else:
                try:
                    with open(self.filepath, 'r', encoding='utf-8') as f:
                        loaded = json.load(f)
                    # Merge with defaults to ensure all keys are present
                    self.settings = dict(self.defaults)
                    for k, v in loaded.items():
                        self.settings[k] = v
                except Exception:
                    self.settings = dict(self.defaults)

    def _save_settings_unlocked(self, data):
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def get_all(self):
        return dict(self.settings)

    def update(self, key_values):
        with self.lock:
            for k, v in key_values.items():
                if k in self.defaults:
                    # Coerce types
                    if isinstance(self.defaults[k], bool):
                        self.settings[k] = bool(v)
                    elif isinstance(self.defaults[k], int):
                        try:
                            self.settings[k] = int(v)
                        except ValueError:
                            pass
                    else:
                        self.settings[k] = str(v)
            self._save_settings_unlocked(self.settings)

settings_service = SettingsService()
