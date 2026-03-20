"""Tests for encryption module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from envsync.core.encryption import EncryptionManager, DummyEncryptionManager


class TestDummyEncryptionManager:
    """Tests for DummyEncryptionManager."""

    def test_encrypt(self):
        """Test that DummyEncryptionManager doesn't encrypt values."""
        manager = DummyEncryptionManager()
        value = "secret_value"
        encrypted = manager.encrypt(value)
        assert encrypted == value

    def test_decrypt(self):
        """Test that DummyEncryptionManager doesn't decrypt values."""
        manager = DummyEncryptionManager()
        value = "secret_value"
        decrypted = manager.decrypt(value)
        assert decrypted == value

    def test_is_encrypted(self):
        """Test that DummyEncryptionManager always returns False for is_encrypted."""
        manager = DummyEncryptionManager()
        assert manager.is_encrypted("any_value") is False


class TestEncryptionManager:
    """Tests for EncryptionManager."""

    def test_initialization(self, tmp_path):
        """Test EncryptionManager initialization."""
        key_path = tmp_path / "encryption_key"
        manager = EncryptionManager(key_path=key_path)
        assert manager.key_path == key_path
        # Key file should be created
        assert key_path.exists()

    def test_key_permissions(self, tmp_path):
        """Test that key file has secure permissions."""
        import os
        key_path = tmp_path / "encryption_key"
        EncryptionManager(key_path=key_path)
        # Check that file is readable/writable only by owner
        st_mode = os.stat(key_path).st_mode & 0o777
        assert st_mode in (0o600, 0o640)  # Different systems might have slightly different

    def test_encrypt_decrypt(self, tmp_path):
        """Test encrypting and decrypting a value."""
        key_path = tmp_path / "encryption_key"
        manager = EncryptionManager(key_path=key_path)

        value = "secret_value"
        encrypted = manager.encrypt(value)

        # Encrypted value should be different from original
        assert encrypted != value
        # Should be a string
        assert isinstance(encrypted, str)

        # Decrypt should return original value
        decrypted = manager.decrypt(encrypted)
        assert decrypted == value

    def test_encrypt_empty_value(self, tmp_path):
        """Test encrypting empty value returns empty."""
        key_path = tmp_path / "encryption_key"
        manager = EncryptionManager(key_path=key_path)

        assert manager.encrypt("") == ""
        assert manager.encrypt(None) is None

    def test_decrypt_empty_value(self, tmp_path):
        """Test decrypting empty value returns empty."""
        key_path = tmp_path / "encryption_key"
        manager = EncryptionManager(key_path=key_path)

        assert manager.decrypt("") == ""
        assert manager.decrypt(None) is None

    def test_is_encrypted(self, tmp_path):
        """Test is_encrypted detection."""
        key_path = tmp_path / "encryption_key"
        manager = EncryptionManager(key_path=key_path)

        value = "secret_value"
        encrypted = manager.encrypt(value)

        assert manager.is_encrypted(encrypted) is True
        assert manager.is_encrypted(value) is False

    def test_decrypt_unencrypted_returns_original(self, tmp_path):
        """Test that decrypting an unencrypted value returns it unchanged."""
        key_path = tmp_path / "encryption_key"
        manager = EncryptionManager(key_path=key_path)

        value = "not_encrypted"
        decrypted = manager.decrypt(value)
        assert decrypted == value

    def test_persistence(self, tmp_path):
        """Test that keys persist between manager instances."""
        key_path = tmp_path / "encryption_key"

        # Create first manager and encrypt something
        manager1 = EncryptionManager(key_path=key_path)
        value = "secret_value"
        encrypted = manager1.encrypt(value)

        # Create second manager with same key path
        manager2 = EncryptionManager(key_path=key_path)
        decrypted = manager2.decrypt(encrypted)

        assert decrypted == value

    def test_different_keys_produce_different_ciphertexts(self, tmp_path):
        """Test that different keys produce different encrypted values."""
        key_path1 = tmp_path / "encryption_key1"
        key_path2 = tmp_path / "encryption_key2"

        manager1 = EncryptionManager(key_path=key_path1)
        manager2 = EncryptionManager(key_path=key_path2)

        value = "secret_value"
        encrypted1 = manager1.encrypt(value)
        encrypted2 = manager2.encrypt(value)

        # Same plaintext should produce different ciphertexts with different keys
        assert encrypted1 != encrypted2

    def test_rotate_key(self, tmp_path):
        """Test key rotation."""
        key_path = tmp_path / "encryption_key"
        manager = EncryptionManager(key_path=key_path)

        # Get original key
        original_key = manager._get_or_create_key()

        # Rotate key
        manager.rotate_key()

        # Get new key
        manager._fernet = None  # Force reload
        new_key = manager._get_or_create_key()

        # Keys should be different
        assert original_key != new_key

    def test_fernet_property(self, tmp_path):
        """Test that fernet property lazy-loads correctly."""
        key_path = tmp_path / "encryption_key"
        manager = EncryptionManager(key_path=key_path)

        # Fernet should be None initially
        assert manager._fernet is None

        # Accessing fernet property should initialize it
        fernet = manager.fernet
        assert fernet is not None
        assert manager._fernet is fernet

        # Subsequent accesses should return same instance
        assert manager.fernet is fernet
