"""Test suite for Phase 01: Authoritative Configuration & Test Isolation (GQA-007, GQA-008)."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import pytest

from central_platform.config import (
    DEFAULT_INSECURE_SECRET,
    MIN_SECRET_LENGTH,
    WEAK_SECRETS,
    PlatformSettings,
    get_authoritative_settings,
    get_environment,
    is_production_mode,
    resolve_environment,
    resolve_jwt_secret,
    resolve_encryption_key,
    resolve_cors_origins,
    resolve_database_path,
    validate_production_config,
)
from central_platform.deployment.validator import (
    DeploymentValidator,
    ValidationCategory,
    ValidationStatus,
)
from central_platform.auth.tokens import get_jwt_secret_key
from scripts.migrate_db import run_all_migrations


class TestEnvironmentResolution:
    def test_canonical_environment_detection(self):
        assert resolve_environment({"GAYATRI_ENV": "production"}) == "production"
        assert resolve_environment({"GAYATRI_ENV": "development"}) == "development"
        assert resolve_environment({"GAYATRI_ENV": "test"}) == "test"

    def test_alias_app_env_detection(self):
        assert resolve_environment({"APP_ENV": "production"}) == "production"
        assert resolve_environment({"APP_ENV": "staging"}) == "staging"

    def test_conflicting_environment_flags_raise_runtime_error(self):
        with pytest.raises(RuntimeError, match="Conflicting environment configuration"):
            resolve_environment({"GAYATRI_ENV": "production", "APP_ENV": "development"})

    def test_consistent_environment_flags_accepted(self):
        assert resolve_environment({"GAYATRI_ENV": "production", "APP_ENV": "production"}) == "production"


class TestJWTSecretResolution:
    def test_canonical_jwt_secret_valid(self):
        valid_secret = "a_very_secure_high_entropy_secret_key_32_chars_long!"
        assert resolve_jwt_secret({"GAYATRI_JWT_SECRET": valid_secret}, is_prod=True) == valid_secret

    def test_alias_jwt_secret_valid(self):
        valid_secret = "a_very_secure_high_entropy_secret_key_32_chars_long!"
        assert resolve_jwt_secret({"JWT_SECRET": valid_secret}, is_prod=True) == valid_secret

    def test_alias_secret_key_valid(self):
        valid_secret = "a_very_secure_high_entropy_secret_key_32_chars_long!"
        assert resolve_jwt_secret({"SECRET_KEY": valid_secret}, is_prod=True) == valid_secret

    def test_conflicting_jwt_secret_aliases_raise_runtime_error(self):
        secret1 = "a_very_secure_high_entropy_secret_key_32_chars_long_1!"
        secret2 = "a_very_secure_high_entropy_secret_key_32_chars_long_2!"
        with pytest.raises(RuntimeError, match="Conflicting JWT secret configurations"):
            resolve_jwt_secret({"GAYATRI_JWT_SECRET": secret1, "JWT_SECRET": secret2}, is_prod=True)

    def test_weak_jwt_secret_rejected_in_production(self):
        with pytest.raises(RuntimeError, match="too weak or uses a default value"):
            resolve_jwt_secret({"GAYATRI_JWT_SECRET": "admin"}, is_prod=True)

    def test_short_jwt_secret_rejected_in_production(self):
        with pytest.raises(RuntimeError, match="minimum 32 characters"):
            resolve_jwt_secret({"GAYATRI_JWT_SECRET": "short_secret_under_32_chars"}, is_prod=True)

    def test_missing_jwt_secret_rejected_in_production(self):
        with pytest.raises(RuntimeError, match="Missing required GAYATRI_JWT_SECRET"):
            resolve_jwt_secret({}, is_prod=True)

    def test_tokens_get_jwt_secret_key_delegates_to_authoritative_config(self, monkeypatch):
        valid_secret = "canonical_authoritative_jwt_secret_key_32_chars!"
        monkeypatch.setenv("GAYATRI_ENV", "production")
        monkeypatch.setenv("GAYATRI_JWT_SECRET", valid_secret)
        monkeypatch.delenv("JWT_SECRET", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)
        assert get_jwt_secret_key() == valid_secret


class TestEncryptionKeyResolution:
    def test_missing_encryption_key_in_production_raises(self):
        with pytest.raises(RuntimeError, match="Missing required GAYATRI_ENCRYPTION_KEY"):
            resolve_encryption_key({"GAYATRI_ENFORCE_ENCRYPTION_KEY": "true"}, is_prod=True)

    def test_platform_dpapi_allowed_by_default_on_windows(self):
        if os.name == "nt":
            key = resolve_encryption_key({}, is_prod=True)
            assert key is None

    def test_weak_encryption_key_rejected(self):
        with pytest.raises(RuntimeError, match="insecure or too short"):
            resolve_encryption_key({"GAYATRI_ENCRYPTION_KEY": "weak_key"}, is_prod=True)

    def test_conflicting_encryption_key_aliases_rejected(self):
        with pytest.raises(RuntimeError, match="Conflicting encryption key"):
            resolve_encryption_key({"GAYATRI_ENCRYPTION_KEY": "key1_16_chars_len!", "ENCRYPTION_KEY": "key2_16_chars_len!"}, is_prod=True)


class TestCORSResolution:
    def test_wildcard_cors_rejected_in_production(self):
        with pytest.raises(RuntimeError, match="Wildcard CORS"):
            resolve_cors_origins({"GAYATRI_ALLOWED_ORIGINS": "*"}, is_prod=True)

    def test_empty_cors_rejected_in_production(self):
        with pytest.raises(RuntimeError, match="must be explicitly configured"):
            resolve_cors_origins({}, is_prod=True)

    def test_valid_cors_origins(self):
        origins = resolve_cors_origins({"GAYATRI_ALLOWED_ORIGINS": "https://app.gayatri.edu, https://admin.gayatri.edu"}, is_prod=True)
        assert origins == ["https://app.gayatri.edu", "https://admin.gayatri.edu"]


class TestValidatorHarmonization:
    def test_validator_fails_on_conflicting_environments(self):
        v = DeploymentValidator(env_vars={"GAYATRI_ENV": "production", "APP_ENV": "development"})
        res = v.validate_environment()
        assert res.status == ValidationStatus.FAIL
        assert "Conflicting environment configuration" in res.message

    def test_validator_fails_on_weak_secret_in_strict_mode(self):
        v = DeploymentValidator(env_vars={"APP_ENV": "production", "GAYATRI_JWT_SECRET": "weak"})
        res = v.validate_secrets()
        assert res.status == ValidationStatus.FAIL

    def test_validator_passes_on_valid_canonical_secret(self):
        valid_secret = "a_very_secure_high_entropy_secret_key_32_chars_long!"
        v = DeploymentValidator(env_vars={
            "GAYATRI_ENV": "production",
            "GAYATRI_JWT_SECRET": valid_secret,
            "GAYATRI_ENCRYPTION_KEY": "valid_encryption_key_16_chars!",
            "GAYATRI_ALLOWED_ORIGINS": "https://gayatri.edu",
        })
        res = v.validate_secrets()
        assert res.status == ValidationStatus.PASS


class TestDiagnosticsAndIsolation:
    def test_safe_diagnostics_omits_secrets(self):
        settings = PlatformSettings(
            environment="production",
            is_production=True,
            jwt_secret="super_secret_jwt_key_that_must_not_leak_in_logs!",
            encryption_key="super_secret_enc_key!",
            allowed_origins=["https://gayatri.edu"],
            db_path=":memory:",
            debug=False,
            reload=False,
            docs_enabled=False,
        )
        diag = settings.safe_diagnostics()
        diag_str = str(diag)
        assert "super_secret_jwt_key" not in diag_str
        assert "super_secret_enc_key" not in diag_str
        assert diag["jwt_secret_configured"] is True
        assert diag["jwt_secret_length"] > 0

    def test_database_isolation_between_two_test_dbs(self, tmp_path):
        db1_path = tmp_path / "test1.db"
        db2_path = tmp_path / "test2.db"

        conn1 = sqlite3.connect(str(db1_path))
        conn2 = sqlite3.connect(str(db2_path))

        run_all_migrations(conn1)
        run_all_migrations(conn2)

        # Mutate db1
        conn1.execute("INSERT INTO users (id, email, full_name, role, created_at, updated_at) VALUES ('u1', 'u1@test.com', 'User 1', 'student', '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z')")
        conn1.commit()

        # db2 must not see db1's records
        cursor = conn2.execute("SELECT COUNT(*) FROM users WHERE id = 'u1'")
        assert cursor.fetchone()[0] == 0

        conn1.close()
        conn2.close()


class TestMigrationEngine:
    def test_migration_from_empty_database_and_idempotency(self, tmp_path):
        db_path = tmp_path / "empty_mig.db"
        conn = sqlite3.connect(str(db_path))

        # First run: applies all migrations
        applied1 = run_all_migrations(conn)
        assert len(applied1) > 0

        # Verify tables created
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        assert cur.fetchone() is not None

        # Second run: idempotent, applies 0 new migrations
        applied2 = run_all_migrations(conn)
        assert len(applied2) == 0

        conn.close()

    def test_migration_checksum_tampering_raises(self, tmp_path, monkeypatch):
        from scripts.migrate_db import apply_migration_file, MigrationChecksumMismatchError

        db_path = tmp_path / "tamper_test.db"
        conn = sqlite3.connect(str(db_path))

        # Create dummy migration 1
        m1 = tmp_path / "099_test.sql"
        m1.write_text("CREATE TABLE test_table_1 (id TEXT PRIMARY KEY);", encoding="utf-8")

        # Apply once
        applied = apply_migration_file(conn, m1, version="099", description="test migration")
        assert applied is True

        # Tamper with file
        m1.write_text("CREATE TABLE test_table_tampered (id TEXT PRIMARY KEY);", encoding="utf-8")

        # Re-applying tampered migration must raise MigrationChecksumMismatchError
        with pytest.raises(MigrationChecksumMismatchError):
            apply_migration_file(conn, m1, version="099", description="test migration")

        conn.close()
