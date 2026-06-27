"""Tests for security module."""
import pytest
from api.security import (
    create_token, verify_token, sanitize_input, sanitize_email,
    validate_password, check_rate_limit, SecurityHeadersMiddleware
)


class TestJWT:
    def test_create_and_verify_token(self):
        token = create_token("student-123", "test@example.com")
        assert token is not None
        assert "." in token

        payload = verify_token(token)
        assert payload["sub"] == "student-123"
        assert payload["email"] == "test@example.com"

    def test_invalid_token(self):
        with pytest.raises(Exception):
            verify_token("invalid.token.here")

    def test_tampered_token(self):
        token = create_token("student-123", "test@example.com")
        parts = token.split(".")
        tampered = f"{parts[0]}.{parts[1]}.aaaa"
        with pytest.raises(Exception):
            verify_token(tampered)


class TestSanitization:
    def test_sitize_input_basic(self):
        assert sanitize_input("Hello World") == "Hello World"

    def test_sanitize_input_xss(self):
        result = sanitize_input("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;" in result or "&#" in result  # html.escape with quote=True

    def test_sanitize_input_sql_injection(self):
        result = sanitize_input("'; DROP TABLE users; --")
        assert "DROP" not in result

    def test_sanitize_input_max_length(self):
        long_text = "a" * 20000
        result = sanitize_input(long_text, max_length=1000)
        assert len(result) <= 1000

    def test_sanitize_email_valid(self):
        assert sanitize_email("  Test@Example.COM  ") == "test@example.com"

    def test_sanitize_email_invalid(self):
        with pytest.raises(ValueError):
            sanitize_email("not-an-email")

    def test_validate_password_valid(self):
        assert validate_password("SecurePass123") == "SecurePass123"

    def test_validate_password_too_short(self):
        with pytest.raises(ValueError):
            validate_password("Short1")

    def test_validate_password_no_uppercase(self):
        with pytest.raises(ValueError):
            validate_password("lowercase123")

    def test_validate_password_no_digit(self):
        with pytest.raises(ValueError):
            validate_password("NoDigitsHere")


class TestRateLimit:
    def test_rate_limit_allows_within_limit(self):
        key = "test-key-1"
        for _ in range(10):
            assert check_rate_limit(key, max_requests=10, window_seconds=60)

    def test_rate_limit_blocks_over_limit(self):
        key = "test-key-2"
        for _ in range(10):
            check_rate_limit(key, max_requests=10, window_seconds=60)
        assert not check_rate_limit(key, max_requests=10, window_seconds=60)
