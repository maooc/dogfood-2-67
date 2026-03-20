"""Sensitive field encryption module."""

import base64
import fnmatch
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


ENCRYPTION_PREFIX = "ENCRYPTED:"


class CryptoManager:
    """Manage encryption and decryption of sensitive fields."""
    
    def __init__(self, key: Optional[bytes] = None, password: Optional[str] = None):
        self._key: Optional[bytes] = key
        self._password = password
        self._fernet: Optional[Fernet] = None
    
    @property
    def fernet(self) -> Fernet:
        """Get Fernet instance for encryption/decryption."""
        if self._fernet is None:
            self._fernet = Fernet(self._get_or_create_key())
        return self._fernet
    
    def _get_or_create_key(self) -> bytes:
        """Get existing key or create new one."""
        if self._key:
            return self._key
        
        if self._password:
            return self._derive_key_from_password(self._password)
        
        return Fernet.generate_key()
    
    def _derive_key_from_password(
        self,
        password: str,
        salt: Optional[bytes] = None
    ) -> bytes:
        """Derive encryption key from password."""
        if salt is None:
            salt = b"envsync_salt_v1"
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def generate_key(self) -> bytes:
        """Generate a new encryption key."""
        return Fernet.generate_key()
    
    def set_key(self, key: bytes) -> None:
        """Set encryption key."""
        self._key = key
        self._fernet = None
    
    def set_password(self, password: str, salt: Optional[bytes] = None) -> None:
        """Set encryption password."""
        self._password = password
        self._key = self._derive_key_from_password(password, salt)
        self._fernet = None
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string value."""
        encrypted = self.fernet.encrypt(plaintext.encode())
        return f"{ENCRYPTION_PREFIX}{encrypted.decode()}"
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string value."""
        if not ciphertext.startswith(ENCRYPTION_PREFIX):
            return ciphertext
        
        encrypted = ciphertext[len(ENCRYPTION_PREFIX):]
        decrypted = self.fernet.decrypt(encrypted.encode())
        return decrypted.decode()
    
    def is_encrypted(self, value: str) -> bool:
        """Check if a value is encrypted."""
        return isinstance(value, str) and value.startswith(ENCRYPTION_PREFIX)


class KeyStorage:
    """Secure storage for encryption keys."""
    
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path.home() / ".envsync" / "keys"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_key(self, project_name: str, key: bytes) -> Path:
        """Save encryption key for a project."""
        key_file = self.storage_dir / f"{project_name}.key"
        key_file.write_bytes(key)
        key_file.chmod(0o600)
        return key_file
    
    def load_key(self, project_name: str) -> Optional[bytes]:
        """Load encryption key for a project."""
        key_file = self.storage_dir / f"{project_name}.key"
        if key_file.exists():
            return key_file.read_bytes()
        return None
    
    def delete_key(self, project_name: str) -> bool:
        """Delete encryption key for a project."""
        key_file = self.storage_dir / f"{project_name}.key"
        if key_file.exists():
            key_file.unlink()
            return True
        return False
    
    def key_exists(self, project_name: str) -> bool:
        """Check if key exists for a project."""
        return (self.storage_dir / f"{project_name}.key").exists()


class SensitiveFieldManager:
    """Manage sensitive field detection and encryption."""
    
    DEFAULT_SENSITIVE_PATTERNS = [
        "*password*",
        "*secret*",
        "*token*",
        "*api_key*",
        "*apikey*",
        "*private_key*",
        "*privatekey*",
        "*credential*",
        "*auth*",
        "*access_key*",
        "*secret_key*",
        "*private*",
    ]
    
    def __init__(
        self,
        crypto_manager: CryptoManager,
        patterns: Optional[List[str]] = None
    ):
        self.crypto = crypto_manager
        self.patterns = patterns or self.DEFAULT_SENSITIVE_PATTERNS.copy()
    
    def add_pattern(self, pattern: str) -> None:
        """Add a sensitive field pattern."""
        if pattern not in self.patterns:
            self.patterns.append(pattern)
    
    def remove_pattern(self, pattern: str) -> None:
        """Remove a sensitive field pattern."""
        if pattern in self.patterns:
            self.patterns.remove(pattern)
    
    def is_sensitive(self, field_name: str) -> bool:
        """Check if a field name matches sensitive patterns."""
        field_lower = field_name.lower()
        for pattern in self.patterns:
            if fnmatch.fnmatch(field_lower, pattern.lower()):
                return True
        return False
    
    def find_sensitive_fields(
        self,
        data: Dict[str, Any],
        prefix: str = ""
    ) -> List[str]:
        """Find all sensitive field paths in a configuration."""
        sensitive_fields = []
        
        for key, value in data.items():
            current_path = f"{prefix}.{key}" if prefix else key
            
            if self.is_sensitive(key):
                sensitive_fields.append(current_path)
            
            if isinstance(value, dict):
                sensitive_fields.extend(
                    self.find_sensitive_fields(value, current_path)
                )
        
        return sensitive_fields
    
    def encrypt_field(self, value: Any) -> str:
        """Encrypt a field value."""
        if isinstance(value, str):
            if self.crypto.is_encrypted(value):
                return value
            return self.crypto.encrypt(value)
        return self.crypto.encrypt(json.dumps(value))
    
    def decrypt_field(self, value: str) -> str:
        """Decrypt a field value."""
        return self.crypto.decrypt(value)
    
    def encrypt_config(
        self,
        data: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Encrypt sensitive fields in configuration."""
        result = data.copy()
        encrypted_fields = []
        
        if fields is None:
            fields = self.find_sensitive_fields(data)
        
        for field_path in fields:
            value = self._get_nested_value(result, field_path)
            if value is not None:
                encrypted = self.encrypt_field(value)
                self._set_nested_value(result, field_path, encrypted)
                encrypted_fields.append(field_path)
        
        return result, encrypted_fields
    
    def decrypt_config(
        self,
        data: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Decrypt sensitive fields in configuration."""
        result = data.copy()
        
        if fields is None:
            fields = self.find_sensitive_fields(data)
        
        for field_path in fields:
            value = self._get_nested_value(result, field_path)
            if value is not None and isinstance(value, str):
                if self.crypto.is_encrypted(value):
                    decrypted = self.decrypt_field(value)
                    self._set_nested_value(result, field_path, decrypted)
        
        return result
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get a nested value by dot-separated path."""
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def _set_nested_value(
        self,
        data: Dict[str, Any],
        path: str,
        value: Any
    ) -> None:
        """Set a nested value by dot-separated path."""
        keys = path.split(".")
        current = data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value


class EncryptionService:
    """High-level encryption service for configuration files."""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.config_dir = self.project_root / ".envsync"
        self.key_storage = KeyStorage(self.config_dir / "keys")
        self._crypto: Optional[CryptoManager] = None
        self._sensitive_manager: Optional[SensitiveFieldManager] = None
    
    def initialize(self, project_name: str, password: Optional[str] = None) -> bytes:
        """Initialize encryption for a project."""
        if password:
            self._crypto = CryptoManager(password=password)
            key = self._crypto._get_or_create_key()
        else:
            key = Fernet.generate_key()
            self._crypto = CryptoManager(key=key)
        
        self.key_storage.save_key(project_name, key)
        return key
    
    def load_encryption(self, project_name: str) -> CryptoManager:
        """Load encryption for a project."""
        key = self.key_storage.load_key(project_name)
        if key is None:
            raise ValueError(f"No encryption key found for project: {project_name}")
        
        self._crypto = CryptoManager(key=key)
        return self._crypto
    
    @property
    def crypto(self) -> CryptoManager:
        """Get crypto manager instance."""
        if self._crypto is None:
            raise ValueError("Encryption not initialized. Call initialize() first.")
        return self._crypto
    
    @property
    def sensitive_manager(self) -> SensitiveFieldManager:
        """Get sensitive field manager instance."""
        if self._sensitive_manager is None:
            self._sensitive_manager = SensitiveFieldManager(self.crypto)
        return self._sensitive_manager
    
    def encrypt_environment(
        self,
        config_data: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Encrypt sensitive fields in environment configuration."""
        return self.sensitive_manager.encrypt_config(config_data, fields)
    
    def decrypt_environment(
        self,
        config_data: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Decrypt sensitive fields in environment configuration."""
        return self.sensitive_manager.decrypt_config(config_data, fields)
    
    def rotate_key(self, project_name: str) -> bytes:
        """Rotate encryption key for a project."""
        from .config import ConfigManager
        
        config_manager = ConfigManager(self.project_root)
        project_config = config_manager.load_project_config()
        
        old_crypto = self.crypto
        
        new_key = Fernet.generate_key()
        new_crypto = CryptoManager(key=new_key)
        
        for env_name in project_config.environments:
            env_data = config_manager.load_environment(env_name)
            
            decrypted_data = self.decrypt_environment(env_data)
            
            self._crypto = new_crypto
            encrypted_data, _ = self.encrypt_environment(decrypted_data)
            
            config_manager.save_environment(env_name, encrypted_data)
        
        self.key_storage.save_key(project_name, new_key)
        self._crypto = new_crypto
        
        return new_key
