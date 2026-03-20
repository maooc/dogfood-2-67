"""敏感字段加密功能."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from envsync.config import ConfigManager
from envsync.models import ConfigFile, ConfigFormat


class CryptoManager:
    """加密管理器."""

    KEY_FILE = "master.key"
    SALT_FILE = "salt.key"
    ENCRYPTED_PREFIX = "ENC:"

    def __init__(self, config_manager: ConfigManager) -> None:
        """初始化加密管理器.

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self._key: Optional[bytes] = None
        self._fernet: Optional[Fernet] = None

    @property
    def key_path(self) -> Path:
        """获取密钥文件路径."""
        if self.config_manager.config.encryption_key_path:
            return self.config_manager.config.encryption_key_path
        return self.config_manager.base_dir / ".envsync" / "keys" / self.KEY_FILE

    @property
    def salt_path(self) -> Path:
        """获取盐值文件路径."""
        return self.key_path.parent / self.SALT_FILE

    def initialize(self, password: Optional[str] = None) -> Path:
        """初始化加密系统，生成密钥.

        Args:
            password: 可选的密码，如果不提供则生成随机密钥

        Returns:
            密钥文件路径
        """
        self.key_path.parent.mkdir(parents=True, exist_ok=True)

        if password:
            if not self.salt_path.exists():
                salt = os.urandom(16)
                with open(self.salt_path, "wb") as f:
                    f.write(salt)
            else:
                with open(self.salt_path, "rb") as f:
                    salt = f.read()

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        else:
            key = Fernet.generate_key()

        with open(self.key_path, "wb") as f:
            f.write(key)

        self._key = key
        self._fernet = Fernet(key)

        return self.key_path

    def load_key(self) -> bytes:
        """加载密钥.

        Returns:
            密钥

        Raises:
            FileNotFoundError: 密钥文件不存在
        """
        if self._key is None:
            if not self.key_path.exists():
                raise FileNotFoundError(f"密钥文件不存在: {self.key_path}")

            with open(self.key_path, "rb") as f:
                self._key = f.read()

            self._fernet = Fernet(self._key)

        return self._key

    def encrypt(self, value: str) -> str:
        """加密字符串值.

        Args:
            value: 要加密的值

        Returns:
            加密后的字符串（带前缀）
        """
        self.load_key()
        encrypted = self._fernet.encrypt(value.encode())
        return f"{self.ENCRYPTED_PREFIX}{encrypted.decode()}"

    def decrypt(self, value: str) -> str:
        """解密字符串值.

        Args:
            value: 要解密的值（带前缀）

        Returns:
            解密后的字符串

        Raises:
            ValueError: 值不是加密格式
        """
        if not value.startswith(self.ENCRYPTED_PREFIX):
            return value

        self.load_key()
        encrypted = value[len(self.ENCRYPTED_PREFIX):].encode()
        decrypted = self._fernet.decrypt(encrypted)
        return decrypted.decode()

    def is_encrypted(self, value: str) -> bool:
        """检查值是否已加密.

        Args:
            value: 要检查的值

        Returns:
            是否已加密
        """
        return isinstance(value, str) and value.startswith(self.ENCRYPTED_PREFIX)

    def encrypt_config(
        self,
        data: Dict[str, Any],
        fields: List[str],
        inplace: bool = False,
    ) -> Dict[str, Any]:
        """加密配置中的指定字段.

        Args:
            data: 配置数据
            fields: 要加密的字段路径列表（支持点号分隔的嵌套路径）
            inplace: 是否原地修改

        Returns:
            加密后的配置数据
        """
        if not inplace:
            import copy
            data = copy.deepcopy(data)

        for field_path in fields:
            self._encrypt_field(data, field_path)

        return data

    def decrypt_config(
        self,
        data: Dict[str, Any],
        inplace: bool = False,
    ) -> Dict[str, Any]:
        """解密配置中的所有加密字段.

        Args:
            data: 配置数据
            inplace: 是否原地修改

        Returns:
            解密后的配置数据
        """
        if not inplace:
            import copy
            data = copy.deepcopy(data)

        self._decrypt_recursive(data)
        return data

    def _encrypt_field(self, data: Dict[str, Any], field_path: str) -> None:
        """加密指定路径的字段.

        Args:
            data: 数据字典
            field_path: 字段路径（如 "database.password"）
        """
        keys = field_path.split(".")
        current = data

        for key in keys[:-1]:
            if key in current and isinstance(current[key], dict):
                current = current[key]
            else:
                return

        last_key = keys[-1]
        if last_key in current and not self.is_encrypted(str(current[last_key])):
            current[last_key] = self.encrypt(str(current[last_key]))

    def _decrypt_recursive(self, data: Any) -> Any:
        """递归解密数据中的所有加密值.

        Args:
            data: 任意数据类型

        Returns:
            解密后的数据
        """
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and self.is_encrypted(value):
                    data[key] = self.decrypt(value)
                elif isinstance(value, (dict, list)):
                    self._decrypt_recursive(value)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, str) and self.is_encrypted(item):
                    data[i] = self.decrypt(item)
                elif isinstance(item, (dict, list)):
                    self._decrypt_recursive(item)

        return data

    def process_config_file(
        self,
        config_file: ConfigFile,
        encrypt: bool = True,
    ) -> None:
        """处理配置文件（加密或解密）.

        Args:
            config_file: 配置文件对象
            encrypt: 是否加密（False 则解密）
        """
        if not config_file.encrypted_fields:
            return

        data = ConfigManager.load_config_file(config_file.path, config_file.format)

        if encrypt:
            data = self.encrypt_config(data, config_file.encrypted_fields)
        else:
            data = self.decrypt_config(data)

        ConfigManager.save_config_file(config_file.path, config_file.format, data)

    def rotate_key(
        self,
        new_password: Optional[str] = None,
    ) -> Path:
        """轮换加密密钥.

        Args:
            new_password: 新密码

        Returns:
            新密钥文件路径
        """
        old_key = self.load_key()
        old_fernet = Fernet(old_key)

        config_files = self.config_manager.config.config_files

        encrypted_values: Dict[Path, Dict[str, Any]] = {}

        for cf in config_files:
            if cf.encrypted_fields:
                data = ConfigManager.load_config_file(cf.path, cf.format)
                encrypted_values[cf.path] = self.decrypt_config(data)

        new_key_path = self.initialize(new_password)

        for path, data in encrypted_values.items():
            cf = next((f for f in config_files if f.path == path), None)
            if cf:
                encrypted_data = self.encrypt_config(data, cf.encrypted_fields)
                ConfigManager.save_config_file(path, cf.format, encrypted_data)

        return new_key_path

    def hash_value(self, value: str, algorithm: str = "sha256") -> str:
        """计算值的哈希.

        Args:
            value: 要哈希的值
            algorithm: 哈希算法

        Returns:
            哈希值
        """
        hasher = hashlib.new(algorithm)
        hasher.update(value.encode())
        return hasher.hexdigest()

    def mask_value(self, value: str, visible_chars: int = 4) -> str:
        """遮罩敏感值.

        Args:
            value: 要遮罩的值
            visible_chars: 显示的字符数

        Returns:
            遮罩后的值
        """
        if len(value) <= visible_chars:
            return "*" * len(value)
        return value[:visible_chars] + "*" * (len(value) - visible_chars)
