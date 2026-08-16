import hashlib
import hmac


def compute_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(body: bytes, header_value: str | None, secret: str) -> bool:
    if not header_value or not secret:
        return False
    expected = compute_signature(body, secret)
    return hmac.compare_digest(expected, header_value.strip())
