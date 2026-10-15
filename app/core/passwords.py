"""Password hashes independent of token signing keys; explicit legacy migration."""
import hashlib
import hmac
import re

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError


# OWASP Argon2id minimum: 19 MiB, two iterations, one lane. Random per-hash salt.
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1,
                         hash_len=32, salt_len=16, type=Type.ID)
_legacy_pattern = re.compile(r"[0-9a-f]{64}\Z")
# A syntactically valid hash for the missing-user path; never attached to an account.
_dummy_hash = "$argon2id$v=19$m=19456,t=2,p=1$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, encoded: str, *, legacy_secret: str | None = None) -> tuple[bool, bool]:
    """Return (valid, needs_upgrade). Never accept a legacy digest as the password."""
    if not isinstance(encoded, str) or len(encoded) > 255:
        return False, False
    if _legacy_pattern.fullmatch(encoded):
        if not legacy_secret:
            return False, False
        candidate = hashlib.sha256(f"{password}:{legacy_secret}".encode("utf-8")).hexdigest()
        valid = hmac.compare_digest(candidate, encoded)
        return valid, valid
    try:
        params = extract_parameters(encoded)
        # Bound work before invoking the native verifier on malformed/stale DB data.
        if not (params.type == Type.ID and params.version == 19
                and 8 <= params.memory_cost <= 65536 and 1 <= params.time_cost <= 4
                and 1 <= params.parallelism <= 4 and 8 <= params.salt_len <= 64
                and 16 <= params.hash_len <= 64):
            return False, False
        valid = _hasher.verify(encoded, password)
        upgrade = params.memory_cost < 19456 or params.time_cost < 2 or params.salt_len < 16 or params.hash_len < 32
        return valid, valid and upgrade
    except (VerificationError, InvalidHashError, ValueError, TypeError):
        return False, False


def consume_dummy_verification(password: str) -> None:
    """Pay the password verification cost also for missing/legacy-invalid users."""
    verify_password(password, _dummy_hash)
