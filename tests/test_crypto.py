"""加密功能测试."""

import tempfile
from pathlib import Path

import pytest

from envsync.config import ConfigManager
from envsync.crypto import CryptoManager


class TestCryptoManager:
    """加密管理器测试."""

    @pytest.fixture
    def temp_dir(self):
        """临时目录."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def crypto_manager(self, temp_dir):
        """加密管理器实例."""
        config_manager = ConfigManager(base_dir=temp_dir)
        config_manager.init_project(name="test")
        crypto = CryptoManager(config_manager)
        crypto.initialize()
        return crypto

    def test_encrypt_decrypt(self, crypto_manager):
        """测试加密解密."""
        original = "secret_password"
        encrypted = crypto_manager.encrypt(original)

        assert encrypted.startswith("ENC:")
        assert encrypted != original

        decrypted = crypto_manager.decrypt(encrypted)
        assert decrypted == original

    def test_is_encrypted(self, crypto_manager):
        """测试加密检测."""
        encrypted = crypto_manager.encrypt("test")
        assert crypto_manager.is_encrypted(encrypted)
        assert not crypto_manager.is_encrypted("plaintext")

    def test_encrypt_config(self, crypto_manager):
        """测试配置加密."""
        data = {
            "database": {
                "host": "localhost",
                "password": "secret",
            },
            "api_key": "key123",
        }

        encrypted = crypto_manager.encrypt_config(
            data, ["database.password", "api_key"]
        )

        assert encrypted["database"]["password"].startswith("ENC:")
        assert encrypted["api_key"].startswith("ENC:")
        assert not encrypted["database"]["host"].startswith("ENC:")

    def test_decrypt_config(self, crypto_manager):
        """测试配置解密."""
        original = {"key": "value"}
        encrypted = crypto_manager.encrypt_config(original, ["key"])
        decrypted = crypto_manager.decrypt_config(encrypted)

        assert decrypted["key"] == "value"

    def test_mask_value(self, crypto_manager):
        """测试值遮罩."""
        assert crypto_manager.mask_value("password") == "pass****"
        assert crypto_manager.mask_value("ab") == "**"
