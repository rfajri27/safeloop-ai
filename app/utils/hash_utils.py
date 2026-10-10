from config.settings import env
import hmac
import hashlib
import base64

class HashUtils:
    """Utility class for hashing and verifying passwords."""
    def __init__(self, secret_key=env.jwt_secret_key):
        """Initialize HashUtils with environment configuration."""
        self.secret_key = secret_key

    async def hash_password(self, password: str) -> str:
        """Hash password using HMAC-SHA256 (local login only)."""
        return hmac.new(self.secret_key.encode('utf-8'), password.encode('utf-8'), hashlib.sha256).hexdigest()

    async def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against a hashed password (local login only)."""
        hashed_password_req = await self.hash_password(password=password)
        return hashed_password_req == hashed_password