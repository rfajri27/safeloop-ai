"""JWT utility functions for token creation and validation."""
from datetime import datetime, timedelta
from typing import Optional
import jwt
from config.settings import env


class JwtUtils:
    """Utility class for JWT token operations."""

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.

        Args:
            data: Payload data to encode in the token
            expires_delta: Optional custom expiration time

        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now() + expires_delta
        else:
            if data.get("token_type") == "refresh":
                expire = datetime.now() + timedelta(minutes=env.jwt_expire_minutes*60)
            else:
                expire = datetime.now() + timedelta(minutes=env.jwt_expire_minutes)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, env.jwt_secret_key, algorithm=env.jwt_algorithm)
        return encoded_jwt

    @staticmethod
    def decode_access_token(token: str) -> dict:
        """
        Decode and validate a JWT access token.

        Args:
            token: JWT token string to decode

        Returns:
            Decoded payload dict, or None if token is invalid/expired
        """
        try:
            payload = jwt.decode(token, env.jwt_secret_key, algorithms=[env.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.PyJWTError:
            return None

