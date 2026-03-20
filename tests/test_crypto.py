"""Tests for crypto module."""

import json
import tempfile
from pathlib import Path

import pytest

from envsync.crypto import (
    CryptoManager,
    EncryptionService,
    KeyStorage,
    SensitiveFieldManager,
    ENCRYPTION_PREFIX,
)


class TestCryptoManager:
    def test_encrypt_decrypt(self):
        manager = CryptoManager()
        encrypted = manager.encrypt("secret")
        
        assert encrypted.startswith(ENCRYPTION_PREFIX)
        assert manager.decrypt(encrypted) == "secret"

    def test_decrypt_non_encrypted(self):
        manager = CryptoManager()
        result = manager.decrypt("plain text")
        assert result == "plain text"

    def test_is_encrypted(self):
        manager = CryptoManager()
        encrypted = manager.encrypt("secret")
        
        assert manager.is_encrypted(encrypted) is True
        assert manager.is_encrypted("plain text") is False

    def test_password_derived_key(self):
        manager1 = CryptoManager(password="my_password")
        manager2 = CryptoManager(password="my_password")
        
        encrypted = manager1.encrypt("secret")
        decrypted = manager2.decrypt(encrypted)
        
        assert decrypted == "secret"

    def test_different_keys(self):
        manager1 = CryptoManager()
        manager2 = CryptoManager()
        
        encrypted = manager1.encrypt("secret")
        
        with pytest.raises(Exception):
            manager2.decrypt(encrypted)

    def test_set_key(self):
        manager = CryptoManager()
        key = manager.generate_key()
        
        manager.set_key(key)
        encrypted = manager.encrypt("secret")
        
        assert manager.decrypt(encrypted) == "secret"


class TestKeyStorage:
    def test_save_and_load_key(self, tmp_path):
        storage = KeyStorage(tmp_path)
        key = CryptoManager().generate_key()
        
        storage.save_key("test_project", key)
        loaded = storage.load_key("test_project")
        
        assert loaded == key

    def test_load_key_not_found(self, tmp_path):
        storage = KeyStorage(tmp_path)
        
        result = storage.load_key("nonexistent")
        assert result is None

    def test_delete_key(self, tmp_path):
        storage = KeyStorage(tmp_path)
        key = CryptoManager().generate_key()
        
        storage.save_key("test_project", key)
        result = storage.delete_key("test_project")
        
        assert result is True
        assert storage.load_key("test_project") is None

    def test_key_exists(self, tmp_path):
        storage = KeyStorage(tmp_path)
        key = CryptoManager().generate_key()
        
        assert storage.key_exists("test_project") is False
        
        storage.save_key("test_project", key)
        assert storage.key_exists("test_project") is True


class TestSensitiveFieldManager:
    def test_is_sensitive_default_patterns(self):
        crypto = CryptoManager()
        manager = SensitiveFieldManager(crypto)
        
        assert manager.is_sensitive("password") is True
        assert manager.is_sensitive("api_key") is True
        assert manager.is_sensitive("secret_token") is True
        assert manager.is_sensitive("username") is False

    def test_is_sensitive_custom_patterns(self):
        crypto = CryptoManager()
        manager = SensitiveFieldManager(crypto, patterns=["*custom*"])
        
        assert manager.is_sensitive("custom_field") is True
        assert manager.is_sensitive("password") is False

    def test_find_sensitive_fields(self):
        crypto = CryptoManager()
        manager = SensitiveFieldManager(crypto)
        
        data = {
            "username": "admin",
            "password": "secret",
            "database": {
                "host": "localhost",
                "password": "db_secret"
            }
        }
        
        fields = manager.find_sensitive_fields(data)
        
        assert "password" in fields
        assert "database.password" in fields
        assert "username" not in fields

    def test_encrypt_config(self):
        crypto = CryptoManager()
        manager = SensitiveFieldManager(crypto)
        
        data = {
            "username": "admin",
            "password": "secret"
        }
        
        encrypted, fields = manager.encrypt_config(data)
        
        assert "password" in fields
        assert encrypted["username"] == "admin"
        assert encrypted["password"].startswith(ENCRYPTION_PREFIX)

    def test_decrypt_config(self):
        crypto = CryptoManager()
        manager = SensitiveFieldManager(crypto)
        
        data = {"password": "secret"}
        encrypted, _ = manager.encrypt_config(data)
        decrypted = manager.decrypt_config(encrypted)
        
        assert decrypted["password"] == "secret"

    def test_get_set_nested_value(self):
        crypto = CryptoManager()
        manager = SensitiveFieldManager(crypto)
        
        data = {"a": {"b": {"c": 1}}}
        
        assert manager._get_nested_value(data, "a.b.c") == 1
        
        manager._set_nested_value(data, "a.b.c", 2)
        assert data["a"]["b"]["c"] == 2


class TestEncryptionService:
    def test_initialize_with_password(self, tmp_path):
        service = EncryptionService(tmp_path)
        
        key = service.initialize("test_project", password="my_password")
        
        assert key is not None
        assert service.key_storage.key_exists("test_project")

    def test_initialize_without_password(self, tmp_path):
        service = EncryptionService(tmp_path)
        
        key = service.initialize("test_project")
        
        assert key is not None
        assert service.key_storage.key_exists("test_project")

    def test_load_encryption(self, tmp_path):
        service = EncryptionService(tmp_path)
        service.initialize("test_project")
        
        loaded = service.load_encryption("test_project")
        
        assert loaded is not None

    def test_load_encryption_not_found(self, tmp_path):
        service = EncryptionService(tmp_path)
        
        with pytest.raises(ValueError):
            service.load_encryption("nonexistent")

    def test_encrypt_decrypt_environment(self, tmp_path):
        service = EncryptionService(tmp_path)
        service.initialize("test_project")
        
        data = {
            "username": "admin",
            "password": "secret"
        }
        
        encrypted, fields = service.encrypt_environment(data)
        decrypted = service.decrypt_environment(encrypted)
        
        assert decrypted["password"] == "secret"
        assert "password" in fields
