"""Encryption utilities for envsync."""

import os
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64


class EncryptionManager:
    """Manages encryption and decryption of sensitive configuration values."""

    def __init__(
        self,
        key_path: Optional[Path] = None,
        password: Optional[str] = None,
        salt: Optional[bytes] = None,
    ):
        """Initialize the encryption manager.

        Args:
            key_path: Path to the encryption key file. If None, uses default location.
            password: Optional password for key derivation. If None, uses random key.
            salt: Optional salt for key derivation. If None, generates random salt.
        """
        if key_path is None:
            self.key_path = Path.home() / ".config" / "envsync" / "encryption_key"
        else:
            self.key_path = Path(key_path)

        self._fernet: Optional[Fernet] = None
        self._password = password
        self._salt = salt

        # Ensure the key exists
        self._get_or_create_key()

    def _get_or_create_key(self) -> bytes:
        """Get an existing key or create a new one."""
        if self.key_path.exists():
            with open(self.key_path, "rb") as f:
                return f.read()
        else:
            # Create new key
            if self._password:
                # Derive key from password
                salt = self._salt or os.urandom(16)
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                    backend=default_backend(),
                )
                key = base64.urlsafe_b64encode(kdf.derive(self._password.encode()))
            else:
                # Generate random key
                key = Fernet.generate_key()

            # Ensure directory exists
            self.key_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.key_path, "wb") as f:
                f.write(key)

            # Secure the key file permissions
            os.chmod(self.key_path, 0o600)

            return key

    @property
    def fernet(self) -> Fernet:
        """Get the Fernet instance, initializing if necessary."""
        if self._fernet is None:
            key = self._get_or_create_key()
            self._fernet = Fernet(key)
        return self._fernet

    def encrypt(self, value: str) -> str:
        """Encrypt a string value."""
        if not value:
            return value
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        """Decrypt an encrypted string value."""
        if not value:
            return value
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except:
            # If decryption fails, return the original value
            # (might not be encrypted)
            return value

    def is_encrypted(self, value: str) -> bool:
        """Check if a value appears to be encrypted."""
        if not value:
            return False
        try:
            # Try to decrypt - if successful, it's encrypted
            self.fernet.decrypt(value.encode())
            return True
        except:
            return False

    def rotate_key(self, new_password: Optional[str] = None) -> None:
        """Rotate the encryption key.

        Note: This will require re-encrypting all existing values.
        """
        # Store the old fernet
        old_fernet = self.fernet

        # Generate new key
        self._fernet = None
        if new_password:
            self._password = new_password
        self._salt = os.urandom(16)

        # Remove old key file to force generation of new one
        if self.key_path.exists():
            self.key_path.unlink()

        # Force generation of new key
        _ = self.fernet


class DummyEncryptionManager(EncryptionManager):
    """A dummy encryption manager that doesn't actually encrypt.

    Useful for testing or environments where encryption isn't needed.
    """

    def encrypt(self, value: str) -> str:
        """Return the value unchanged (no encryption)."""
        return value

    def decrypt(self, value: str) -> str:
        """Return the value unchanged (no decryption)."""
        return value

    def is_encrypted(self, value: str) -> bool:
        """Always return False."""
        return False
