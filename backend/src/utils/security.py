import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from src.config.settings import JWT_SECRET
def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 210000).hex()
    return f"{salt}${digest}"
def verify_password(password, stored):
    salt, expected = stored.split("$")
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 210000).hex()
    return hmac.compare_digest(actual, expected)
def issue_token(user):
    return jwt.encode({"sub": str(user.id), "exp": datetime.now(timezone.utc)+timedelta(hours=8)}, JWT_SECRET, algorithm="HS256")
