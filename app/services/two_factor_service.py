import pyotp
import qrcode
import io
import base64
import json
import secrets
from flask import current_app
from app.models import User
from app import db, bcrypt

class TwoFactorService:
    @staticmethod
    def generate_secret():
        """Generates a random base32 string for the TOTP secret."""
        return pyotp.random_base32()
        
    @staticmethod
    def get_totp_uri(email, secret):
        """Generates the provisioning URI for authenticators like Google Authenticator."""
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=email,
            issuer_name="CloudVault"
        )
        
    @staticmethod
    def generate_qr_code(uri):
        """Generates a base64 encoded PNG of the QR code."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
        
    @staticmethod
    def verify_totp(secret, token):
        """Verifies a TOTP token against a secret."""
        if not secret or not token:
            return False
        totp = pyotp.TOTP(secret)
        return totp.verify(token)
        
    @staticmethod
    def generate_recovery_codes(user):
        """Generates 10 secure, hashed recovery codes and stores them."""
        # Generate 10 random 8-character codes
        raw_codes = [secrets.token_hex(4).upper() for _ in range(10)]
        
        # Hash codes for storage to prevent db leak compromise
        hashed_codes = [bcrypt.generate_password_hash(code).decode('utf-8') for code in raw_codes]
        
        user.backup_codes = json.dumps(hashed_codes)
        db.session.commit()
        
        # Return plain codes just once to be shown to the user
        return raw_codes
        
    @staticmethod
    def verify_recovery_code(user, token):
        """Verifies a recovery code. If valid, consumes it."""
        if not user.backup_codes:
            return False
            
        try:
            hashed_codes = json.loads(user.backup_codes)
        except:
            return False
            
        for i, hashed_code in enumerate(hashed_codes):
            if bcrypt.check_password_hash(hashed_code, token):
                # Consume the code
                hashed_codes.pop(i)
                user.backup_codes = json.dumps(hashed_codes)
                db.session.commit()
                return True
                
        return False

two_factor_service = TwoFactorService()
