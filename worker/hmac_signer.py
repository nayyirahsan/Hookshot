import hashlib
import hmac
import json


def sign_payload(payload: dict, secret: str) -> str:
    """Returns 'sha256=<hex_digest>'"""
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={sig}"
