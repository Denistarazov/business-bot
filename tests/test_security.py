from database.db import hash_password, verify_password


def test_hash_password_uses_bcrypt_prefix():
    hashed = hash_password("secret123")
    assert hashed.startswith("$2")


def test_verify_password_supports_new_bcrypt_hashes():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_password_supports_legacy_sha256_hashes():
    legacy_hash = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"
    assert verify_password("admin123", legacy_hash) is True
