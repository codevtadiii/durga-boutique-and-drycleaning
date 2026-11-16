import hashlib
import hmac
import secrets

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import get_settings


password_hash = PasswordHash.recommended()
_dummy_pin_hash = password_hash.hash("000000")


def hash_secret(value: str) -> str:
    key = get_settings().session_secret.encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_pin(pin: str, encoded_hash: str | None) -> bool:
    try:
        return password_hash.verify(pin, encoded_hash or _dummy_pin_hash)
    except UnknownHashError:
        return False


def new_session_secret() -> str:
    return secrets.token_urlsafe(32)


def new_qr_secret() -> str:
    return secrets.token_urlsafe(32)
