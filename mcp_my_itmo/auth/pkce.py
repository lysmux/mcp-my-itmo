import base64
import hashlib
import secrets


UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


def make_verifier() -> str:
    length = secrets.randbelow(128 - 43 + 1) + 43
    return "".join(secrets.choice(UNRESERVED) for _ in range(length))


def make_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode()
    return challenge.rstrip("=")


def make_state() -> str:
    return secrets.token_urlsafe(32)
