import hashlib
import hmac
import secrets


def generate_connection_key() -> str:
    return f"TJ_{secrets.token_urlsafe(24)}"


def hash_connection_key(key: str, secret: str) -> str:
    return hmac.new(secret.encode(), key.encode(), hashlib.sha256).hexdigest()


def verify_connection_key(key: str, key_hash: str, secret: str) -> bool:
    candidate = hash_connection_key(key, secret)
    return hmac.compare_digest(candidate, key_hash)
