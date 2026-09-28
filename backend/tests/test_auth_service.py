"""TDD contracts for password and opaque-token cryptographic primitives."""

import pytest

import app.services.auth_service as auth_service

from app.services.auth_service import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    digest_token,
    generate_token,
    hash_password,
    token_matches,
    validate_password,
    verify_password,
    verify_password_constant_shape,
)


def test_password_hash_uses_argon2id_and_never_contains_plaintext():
    password = "a-long-and-unique password 2026!"

    encoded = hash_password(password)

    assert encoded.startswith("$argon2id$")
    assert password not in encoded
    assert encoded != password


def test_password_verification_accepts_only_the_matching_password():
    encoded = hash_password("correct horse battery staple 2026!")

    assert verify_password("correct horse battery staple 2026!", encoded) is True
    assert verify_password("wrong horse battery staple 2026!", encoded) is False


def test_password_hashes_are_salted():
    password = "same password, independently stored 2026!"

    first = hash_password(password)
    second = hash_password(password)

    assert first != second
    assert verify_password(password, first) is True
    assert verify_password(password, second) is True


@pytest.mark.parametrize(
    ("password", "accepted"),
    [
        ("x" * (MIN_PASSWORD_LENGTH - 1), False),
        ("x" * MIN_PASSWORD_LENGTH, True),
        ("x" * MAX_PASSWORD_LENGTH, True),
        ("x" * (MAX_PASSWORD_LENGTH + 1), False),
    ],
)
def test_password_policy_enforces_inclusive_length_boundaries(password, accepted):
    if accepted:
        assert validate_password(password) == password
    else:
        with pytest.raises(ValueError):
            validate_password(password)


def test_password_verification_fails_closed_for_a_malformed_hash():
    assert verify_password("a candidate password", "not-an-encoded-hash") is False


def test_unknown_identity_still_performs_one_password_verification(monkeypatch):
    calls = []

    def record_verification(password, encoded_hash):
        calls.append((password, encoded_hash))
        return False

    monkeypatch.setattr(auth_service, "verify_password", record_verification)

    assert verify_password_constant_shape("submitted password", None) is False
    assert len(calls) == 1
    assert calls[0][0] == "submitted password"
    assert calls[0][1].startswith("$argon2id$")


def test_token_generation_is_opaque_unique_and_at_least_256_bits():
    first = generate_token()
    second = generate_token()

    assert first != second
    # A URL-safe encoding of 32 random bytes has 43 characters without padding.
    assert len(first) >= 43
    assert len(second) >= 43


def test_token_digest_is_deterministic_sha256_and_not_the_raw_token():
    raw = "verification-token-visible-only-to-the-user"

    first = digest_token(raw)
    second = digest_token(raw)

    assert first == second
    assert len(first) == 64
    assert first != raw
    assert raw not in first


def test_token_digest_comparison_accepts_only_the_original_token():
    raw = generate_token()
    stored_digest = digest_token(raw)

    assert token_matches(raw, stored_digest) is True
    assert token_matches("the-wrong-token", stored_digest) is False


def test_token_digest_comparison_uses_constant_time_primitive(monkeypatch):
    comparisons = []

    def record_comparison(candidate_digest, stored_digest):
        comparisons.append((candidate_digest, stored_digest))
        return candidate_digest == stored_digest

    monkeypatch.setattr(auth_service.hmac, "compare_digest", record_comparison)
    raw = generate_token()
    stored_digest = digest_token(raw)

    assert token_matches(raw, stored_digest) is True
    assert comparisons == [(stored_digest, stored_digest)]
